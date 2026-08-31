"""Arranque de la vista Qt Quick.

`main()` crea la QGuiApplication, instancia el ViewModel (único puente con el
núcleo), lo expone al contexto QML como `Vm`, carga `qml/Main.qml` y entra en el
bucle de eventos de Qt. Los productores de datos reales (muestreo de sistema,
salud de Ollama, micrófono, stream del LLM) se conectan en fases siguientes vía
los slots `push_*` del ViewModel.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_QML_DIR = Path(__file__).parent / "qml"


def _configure_environment() -> None:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def create_engine(app, view_model=None):
    """Crea el QQmlApplicationEngine con `Vm` en contexto y Main.qml cargado.

    Separado de `main()` para poder instanciarlo en tests sin `app.exec()`.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from jarvis_local.ui.hud.chat_service import ChatService
    from jarvis_local.ui.hud.conversation_model import ConversationModel
    from jarvis_local.ui.hud.viewmodel import ViewModel
    from jarvis_local.ui.hud.voice_service import VoiceService

    vm = view_model or ViewModel()
    conversation = ConversationModel()
    chat = ChatService(vm, conversation)
    voice = VoiceService(vm)

    # voz → chat, y respuesta hablada si config.voice.tts_enabled
    voice.transcribed.connect(chat.send)
    chat.assistantEnd.connect(lambda text, meta, kind: _maybe_speak(voice, text, kind))

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("Vm", vm)
    ctx.setContextProperty("Conversation", conversation)
    ctx.setContextProperty("Chat", chat)
    ctx.setContextProperty("Voice", voice)
    engine.addImportPath(str(_QML_DIR))
    engine.load(QUrl.fromLocalFile(str(_QML_DIR / "Main.qml")))

    # el engine no es dueño de estos objetos: que sobrevivan al scope
    engine._vm = vm            # noqa: SLF001
    engine._conversation = conversation  # noqa: SLF001
    engine._chat = chat        # noqa: SLF001
    engine._voice = voice      # noqa: SLF001

    # ALERT vuelve a IDLE tras 2.5 s si nadie cambió el estado entretanto
    _wire_alert_autoclear(vm)

    # muestreo real de sistema / Ollama / voz / memoria / tools (cada 2 s)
    from jarvis_local.ui.hud.services import MetricsService
    metrics = MetricsService(vm)
    if engine.rootObjects():
        metrics.start()
        if app is not None:
            app.aboutToQuit.connect(metrics.stop)
    engine._metrics = metrics  # noqa: SLF001
    return engine


def _maybe_speak(voice, text: str, kind: str) -> None:
    if kind != "chat" or not text:
        return
    try:
        from jarvis_local.config import get_config
        if get_config().get("voice", {}).get("tts_enabled", False):
            voice.speak(text)
    except Exception:
        pass


def _wire_alert_autoclear(vm) -> None:
    from PySide6.QtCore import QTimer

    timer = QTimer(vm)
    timer.setSingleShot(True)
    timer.setInterval(2500)
    timer.timeout.connect(lambda: vm.set_state("idle") if vm.state == "alert" else None)
    vm.stateChanged.connect(lambda s: timer.start() if s == "alert" else timer.stop())


def main() -> int:
    _configure_environment()

    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setOrganizationName("JARVIS")

    engine = create_engine(app)
    if not engine.rootObjects():
        print("[hud] No se pudo cargar la interfaz QML.", file=sys.stderr)
        return 1

    rc = app.exec()
    # teardown determinista: destruir el árbol QML mientras el ViewModel sigue
    # vivo evita 'TypeError: property of null' en los bindings finales.
    engine.deleteLater()
    del engine
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
