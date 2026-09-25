"""Arranque del HUD pro (paquete ``hud_pro`` + :mod:`jarvis_local.ui.hud_pro_adapter`).

Reutiliza el MISMO pipeline que ya usa el HUD legado — ``ChatService`` y
``VoiceService`` de ``jarvis_local.ui.hud`` — sin tocar su lógica: este
módulo es sólo el cableado entre esas señales y el ``HudBridge`` del HUD
pro, vía ``JarvisHudAdapter``. Todo el trabajo real (STT, LLM, TTS) sigue
viviendo donde ya vivía.

Desviaciones deliberadas del cableado "ideal" (documentadas, no escondidas):

- No existe un detector de wake-word en continuo en este pipeline, sólo
  micrófono push-to-talk (botón). Activar el micrófono ES el evento más
  cercano a una "wake word" que hay hoy — se usa como tal.
- ``VoiceService.audio`` ya emite un NIVEL calculado (no las muestras
  crudas), así que se pasa directo a ``bridge.set_level()`` en vez de
  fabricar una señal falsa para ``on_mic_pcm16``/``on_mic_float`` (esos dos
  métodos siguen ahí para quien SÍ tenga muestras crudas que ofrecer).

``main()`` sigue el mismo contrato que ``jarvis_local.ui.hud.app.main()``
(devuelve el código de salida) para que el lanzador elija entre ambos sin
más diferencia que la importación.
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("jarvis.hud_pro")


def _configure_environment() -> None:
    # El proyecto sólo trae PySide6 instalado; forzarlo explícito evita que
    # qt_compat pruebe PyQt6/PyQt5 primero si algún día llegan a convivir.
    os.environ.setdefault("QT_API", "pyside6")


def create_window():
    """Construye la app/ventana/cableado del HUD pro SIN mostrarla ni entrar
    al bucle de eventos. Separado de `main()` para que el lanzador (cli.py)
    pueda distinguir un fallo de arranque (import roto, HudWindow que no se
    puede crear) — ahí sí corresponde caer al HUD legado — de un fallo ya
    con la ventana en uso, donde no tiene sentido abrir otra interfaz.
    Devuelve `(app, window)`; `window.show()` + `exec_app(app)` la arrancan.
    """
    _configure_environment()

    from hud_pro import HudBridge, HudWindow, create_app
    from jarvis_local.config import get_config
    from jarvis_local.ui.hud.chat_service import ChatService
    from jarvis_local.ui.hud.conversation_model import ConversationModel
    from jarvis_local.ui.hud.viewmodel import ViewModel
    from jarvis_local.ui.hud.voice_service import VoiceService
    from jarvis_local.ui.hud_pro_adapter import JarvisHudAdapter

    app = create_app(sys.argv)
    app.setDesktopFileName("jarvis")  # agrupa con scripts/jarvis.desktop, igual que el HUD legado

    win = HudWindow()
    bridge = HudBridge(win)

    # Mismo pipeline que `Runtime` (jarvis_local/ui/hud/app.py): un
    # ViewModel "de repuesto" sin motor QML detrás — ChatService y
    # VoiceService lo necesitan para construirse, pero nada lo lee aquí; el
    # HUD pro se alimenta de las señales de chat/voice directamente.
    #
    # `parent=win` es obligatorio, no cosmético: sin un padre Qt, nada
    # mantiene vivas estas instancias una vez que `create_window()` retorna
    # (conectar una señal SUYA a un slot ajeno no evita que el recolector de
    # basura de Python se las lleve) — el pipeline se quedaría mudo con la
    # ventana todavía abierta.
    vm = ViewModel(win)
    conversation = ConversationModel(win)
    chat = ChatService(vm, conversation, parent=win)
    voice = VoiceService(vm, parent=win)

    try:
        model_name = get_config().get("ollama", {}).get("model", "")
    except Exception:
        model_name = ""

    hud = JarvisHudAdapter(
        bridge,
        on_user_text=chat.send,  # (5) consola del HUD pro -> mismo handler que el texto de hoy
        on_mic_toggle=lambda on: (voice.start_recording() if on else voice.stop_recording()),
        model_name=model_name,
    )

    # ── Entrada de voz ──────────────────────────────────────────────────
    voice.micStateChanged.connect(
        lambda s: hud.on_wake_word() if s == "listening" else None)
    voice.audio.connect(lambda level, _spectrum: bridge.set_level(level))
    voice.transcribed.connect(chat.send)                # dispara el turno real
    voice.transcribed.connect(hud.on_final_transcript)  # lo refleja en el HUD pro
    # Igual que Runtime (voice.notice -> chat.errorTurn): un aviso de voz
    # (grabación muy corta, audio no entendido, STT roto) se trata como
    # error también aquí, no se calla.
    voice.notice.connect(lambda msg: hud.on_error(RuntimeError(msg)))
    voice.speakingChanged.connect(
        lambda speaking: hud.on_tts_start() if speaking else hud.on_tts_end())

    # ── LLM ─────────────────────────────────────────────────────────────
    chat.assistantToken.connect(hud.on_llm_token)

    def _on_assistant_end(text: str, _meta: str, _kind: str) -> None:
        # El parser/las herramientas responden SIN streaming (chat_service
        # sólo envuelve stream=True): si nunca hubo tokens no hay burbuja
        # que cerrar, hay que mostrar el texto final directo.
        if win.chat.is_streaming():
            hud.on_llm_done()
        elif text:
            bridge.add_message("assistant", text)

    def _speak_reply(text: str, _meta: str, kind: str) -> None:
        # Mismo criterio que `_maybe_speak` en jarvis_local/ui/hud/app.py:
        # sólo se habla la respuesta del LLM (no la de una herramienta), y
        # sólo si la voz de salida está activada en config.yaml.
        if kind != "chat" or not text:
            return
        try:
            if get_config().get("voice", {}).get("tts_enabled", False):
                voice.speak(text)
        except Exception:
            pass

    chat.assistantEnd.connect(_on_assistant_end)
    chat.assistantEnd.connect(_speak_reply)
    chat.errorTurn.connect(lambda msg: hud.on_error(RuntimeError(msg)))

    # ── Cierre limpio ───────────────────────────────────────────────────
    bridge.closing.connect(chat.cancel)
    bridge.closing.connect(voice.stop_recording)
    bridge.closing.connect(voice.stop_speech)

    return app, win


def main() -> int:
    from hud_pro.qt_compat import exec_app

    app, win = create_window()
    win.show()
    return exec_app(app)


if __name__ == "__main__":
    raise SystemExit(main())
