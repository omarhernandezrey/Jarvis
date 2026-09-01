"""Arranque de la vista Qt Quick.

`main()` crea la QGuiApplication, construye el `Runtime` (ViewModel + servicios,
único puente con el núcleo), lo expone al contexto QML, carga `qml/Main.qml` y
entra en el bucle de eventos.

`Runtime` es el **único lugar** donde se registran los recursos de larga vida
(hilos de muestreo, timers, servicios de voz/chat). `Runtime.shutdown()` los
para todos y se conecta a `app.aboutToQuit`; un test lo verifica.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

_QML_DIR = Path(__file__).parent / "qml"


def _configure_environment() -> None:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    # Transparencia REAL de la ventana (Fase 4): la superficie GL necesita un
    # canal alfa; sin esto, `color: "transparent"` en el Window pinta negro.
    try:
        from PySide6.QtGui import QSurfaceFormat
        fmt = QSurfaceFormat.defaultFormat()
        fmt.setAlphaBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
    except Exception:
        pass


class Runtime:
    """Contenedor de todo lo vivo detrás de la vista. Registra sus timers y los
    cancela en `shutdown()`."""

    def __init__(self, view_model=None) -> None:
        from jarvis_local.ui.hud.chat_service import ChatService
        from jarvis_local.ui.hud.conversation_model import ConversationModel
        from jarvis_local.ui.hud.services import MetricsService, detect_reduced_motion
        from jarvis_local.ui.hud.viewmodel import ViewModel

        self.vm = view_model or ViewModel()
        self.conversation = ConversationModel()
        self.chat = ChatService(self.vm, self.conversation)
        self.voice = self._make_voice()
        self.metrics = MetricsService(self.vm)
        self.reduced_motion = detect_reduced_motion()
        self.timers: list = []          # todos los QTimer de larga vida, aquí
        self._alive = True

        self.voice.transcribed.connect(self.chat.send)
        # fallo/aviso de voz → visible en la columna de conversación (no callar)
        self.voice.notice.connect(self.chat.errorTurn)
        self.chat.assistantEnd.connect(
            lambda text, meta, kind: _maybe_speak(self.voice, text, kind))

        self._wire_alert_autoclear()

    def _make_voice(self):
        from jarvis_local.ui.hud.voice_service import VoiceService
        return VoiceService(self.vm)

    def _wire_alert_autoclear(self) -> None:
        from PySide6.QtCore import QTimer

        timer = QTimer(self.vm)
        timer.setObjectName("alertAutoclear")
        timer.setSingleShot(True)
        timer.setInterval(2500)
        timer.timeout.connect(
            lambda: self.vm.set_state("idle") if self.vm.state == "alert" else None)
        self.vm.stateChanged.connect(
            lambda s: timer.start() if s == "alert" else timer.stop())
        self.timers.append(timer)

    def bind_context(self, engine) -> None:
        from jarvis_local.config import get_config
        hud_cfg = get_config().get("hud", {})

        ctx = engine.rootContext()
        ctx.setContextProperty("Vm", self.vm)
        # OJO: no llamarlo "Conversation" — colisiona con el tipo Conversation.qml
        # y `model: Conversation` resolvería al componente, no al modelo.
        ctx.setContextProperty("ConversationModel", self.conversation)
        ctx.setContextProperty("Chat", self.chat)
        ctx.setContextProperty("Voice", self.voice)
        ctx.setContextProperty("ReducedMotion", self.reduced_motion)
        # Ventana sin marco (addendum §8.1): en algunas sesiones Wayland/GNOME
        # deja de recibir foco de teclado. Por defecto OFF (ventana normal, que
        # funciona en todas partes). Activar con  config.yaml → hud:\n  frameless: true
        ctx.setContextProperty("Frameless", bool(hud_cfg.get("frameless", False)))

    def start(self) -> None:
        self.metrics.start()

    def shutdown(self) -> None:
        if not self._alive:
            return
        self._alive = False
        for t in self.timers:
            with contextlib.suppress(Exception):
                t.stop()
        with contextlib.suppress(Exception):
            self.chat.cancel()
        with contextlib.suppress(Exception):
            self.voice.stop_recording()
            self.voice.stop_speech()
        self.metrics.stop()


def create_engine(app, view_model=None):
    """Crea el QQmlApplicationEngine con el Runtime en contexto y Main.qml
    cargado. Separado de `main()` para instanciarlo en tests sin `app.exec()`.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    runtime = Runtime(view_model)

    engine = QQmlApplicationEngine()
    runtime.bind_context(engine)
    engine.addImportPath(str(_QML_DIR))
    engine.load(QUrl.fromLocalFile(str(_QML_DIR / "Main.qml")))

    engine._runtime = runtime  # noqa: SLF001  (que sobreviva al scope)
    # compat con tests previos
    engine._vm = runtime.vm            # noqa: SLF001
    engine._conversation = runtime.conversation  # noqa: SLF001
    engine._chat = runtime.chat        # noqa: SLF001
    engine._voice = runtime.voice      # noqa: SLF001
    engine._metrics = runtime.metrics  # noqa: SLF001

    if engine.rootObjects():
        runtime.start()
        if app is not None:
            app.aboutToQuit.connect(runtime.shutdown)
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
    engine._runtime.shutdown()  # noqa: SLF001  (idempotente)
    engine.deleteLater()
    del engine
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
