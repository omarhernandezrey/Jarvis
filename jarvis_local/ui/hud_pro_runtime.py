"""Arranque del HUD pro (paquete ``hud_pro`` + :mod:`jarvis_local.ui.hud_pro_adapter`).

Reutiliza el MISMO pipeline que ya usa el HUD legado — ``ChatService``,
``VoiceService`` y ``MetricsService`` de ``jarvis_local.ui.hud`` — sin tocar
su lógica (salvo dos señales nuevas, puramente aditivas, en chat_service.py:
``toolUsed`` y la métrica ``ttftMs``). Este módulo es sólo el cableado entre
esas señales y el ``HudBridge`` del HUD pro, vía ``JarvisHudAdapter``. Todo
el trabajo real (STT, LLM, TTS, métricas del sistema) sigue viviendo donde
ya vivía.

Desviaciones deliberadas del cableado "ideal" (documentadas, no escondidas):

- No existe un detector de wake-word en continuo en este pipeline, sólo
  micrófono push-to-talk (botón). Activar el micrófono ES el evento más
  cercano a una "wake word" que hay hoy — el chip "WAKE" y `on_wake_word()`
  reflejan ESE mismo mecanismo, con el tooltip dejándolo explícito.
- ``VoiceService.audio`` ya emite un NIVEL calculado (no las muestras
  crudas), así que se pasa directo a ``bridge.set_level()`` en vez de
  fabricar una señal falsa para ``on_mic_pcm16``/``on_mic_float`` (esos dos
  métodos siguen ahí para quien SÍ tenga muestras crudas que ofrecer). El
  MISMO callback ya trae un espectro FFT real (64 bandas, ver
  ``voice_service.py::_cb``/``_out_cb``) — se pasa tal cual a
  ``bridge.set_spectrum()``, que remuestrea a la resolución visual del
  orbe; no hace falta reconstruir un extractor de 48 bandas aparte.
- "Cambiar modelo" NO se conecta a ninguna acción rápida: no existe un
  método en `jarvis_local.config` para persistir un modelo nuevo en
  caliente (sólo se lee de config.yaml al arrancar) — no se inventa.
- VRAM (nvidia-smi): esta máquina de desarrollo no tiene GPU NVIDIA: el
  lector nunca falla, sólo devuelve `None` (no se muestra) — se deja el
  soporte real para quien sí la tenga.
- El resultado ok/error de una herramienta sólo es fiable cuando la
  herramienta lanza una excepción real (`Jarvis.last_tool_ok`, ver
  jarvis_local/jarvis.py); un fallo "lógico" que la propia herramienta
  reporta como texto (p. ej. "no encontrado") no se distingue de un éxito
  — inferirlo del texto sería adivinar, no leer un dato real.

``main()`` sigue el mismo contrato que ``jarvis_local.ui.hud.app.main()``
(devuelve el código de salida) para que el lanzador elija entre ambos sin
más diferencia que la importación.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys

log = logging.getLogger("jarvis.hud_pro")


def _configure_environment() -> None:
    # El proyecto sólo trae PySide6 instalado; forzarlo explícito evita que
    # qt_compat pruebe PyQt6/PyQt5 primero si algún día llegan a convivir.
    os.environ.setdefault("QT_API", "pyside6")


def _read_vram() -> tuple[float | None, float | None]:
    """(usados_mb, total_mb) vía `nvidia-smi`, o (None, None) si no hay GPU
    NVIDIA o la herramienta no existe. Nunca lanza, nunca inventa un número."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1.5,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None, None
        used_s, total_s = out.stdout.strip().splitlines()[0].split(",")
        return float(used_s.strip()), float(total_s.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None


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
    from hud_pro.qt_compat import QtCore
    from jarvis_local.config import get_config
    from jarvis_local.ui.hud.chat_service import ChatService
    from jarvis_local.ui.hud.conversation_model import ConversationModel
    from jarvis_local.ui.hud.services import MetricsService
    from jarvis_local.ui.hud.viewmodel import ViewModel
    from jarvis_local.ui.hud.voice_service import VoiceService
    from jarvis_local.ui.hud_pro_adapter import JarvisHudAdapter

    app = create_app(sys.argv)
    app.setDesktopFileName("jarvis")  # agrupa con scripts/jarvis.desktop, igual que el HUD legado

    win = HudWindow()
    bridge = HudBridge(win)

    # Mismo pipeline que `Runtime` (jarvis_local/ui/hud/app.py): un
    # ViewModel "de repuesto" sin motor QML detrás — ChatService, VoiceService
    # y MetricsService lo necesitan para construirse, pero nada lo lee aquí;
    # el HUD pro se alimenta de las señales directamente.
    #
    # `parent=win` es obligatorio, no cosmético: sin un padre Qt, nada
    # mantiene vivas estas instancias una vez que `create_window()` retorna
    # — el pipeline se quedaría mudo con la ventana todavía abierta.
    vm = ViewModel(win)
    conversation = ConversationModel(win)
    chat = ChatService(vm, conversation, parent=win)
    voice = VoiceService(vm, parent=win)
    metrics_service = MetricsService(vm, parent=win)

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
    def _on_mic_state(state: str) -> None:
        listening = state == "listening"
        if listening:
            hud.on_wake_word()
        bridge.set_service_active("mic", listening)
        bridge.set_service_active("wake", listening)  # mismo mecanismo real, ver docstring

    voice.micStateChanged.connect(_on_mic_state)

    def _on_audio(level: float, spectrum: list) -> None:
        bridge.set_level(level)
        bridge.set_spectrum(spectrum)  # FFT real (mic o TTS); [] la apaga sola

    voice.audio.connect(_on_audio)
    voice.transcribed.connect(chat.send)                # dispara el turno real
    voice.transcribed.connect(hud.on_final_transcript)  # lo refleja en el HUD pro
    # Igual que Runtime (voice.notice -> chat.errorTurn): un aviso de voz
    # (grabación muy corta, audio no entendido, STT roto) se trata como
    # error también aquí, no se calla — y además se ve como toast.
    voice.notice.connect(lambda msg: hud.on_error(RuntimeError(msg)))
    voice.notice.connect(lambda msg: bridge.toast(msg, "error"))

    def _on_speaking(speaking: bool) -> None:
        bridge.set_service_active("tts", speaking)
        if speaking:
            hud.on_tts_start()
        else:
            hud.on_tts_end()

    voice.speakingChanged.connect(_on_speaking)

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

    _mute_state = {"muted": False}

    def _speak_reply(text: str, _meta: str, kind: str) -> None:
        # Mismo criterio que `_maybe_speak` en jarvis_local/ui/hud/app.py:
        # sólo se habla la respuesta del LLM (no la de una herramienta), y
        # sólo si la voz de salida está activada en config.yaml — más el
        # silencio manual de la acción rápida "Silenciar".
        if kind != "chat" or not text or _mute_state["muted"]:
            return
        try:
            if get_config().get("voice", {}).get("tts_enabled", False):
                voice.speak(text)
        except Exception:
            pass

    chat.assistantEnd.connect(_on_assistant_end)
    chat.assistantEnd.connect(_speak_reply)
    chat.errorTurn.connect(lambda msg: hud.on_error(RuntimeError(msg)))
    chat.errorTurn.connect(lambda msg: bridge.toast(msg, "error"))
    chat.metrics.connect(bridge.set_metrics)  # tokensPerSecond / ttftMs / latencyMs, tal cual

    # ── Tarjeta de actividad de herramienta ──────────────────────────────
    # `toolUsed` llega con la herramienta YA terminada (duración real
    # incluida): se muestra el spinner un instante (mismo criterio que la
    # pausa de 0.28s de "executing" en chat_service.py) y se cierra con el
    # resultado real — no es una barra de progreso inventada.
    def _on_tool_used(name: str, ms: float, ok: bool) -> None:
        bridge.tool_start(name)
        QtCore.QTimer.singleShot(280, lambda: bridge.tool_end(name, ms, ok))

    chat.toolUsed.connect(_on_tool_used)

    # ── Métricas reales (barra superior + chips) ─────────────────────────
    # Reutiliza MetricsService tal cual (mismo hilo de muestreo cada 2s,
    # mismo `sample_all()` "nada se inventa"); sólo se añade un segundo
    # destino para el mismo dato — el ViewModel de repuesto sigue
    # recibiéndolo también, aunque aquí nada lo lea.
    _last_memory = {"count": None, "auto_recall": False}

    def _on_sampled(data: dict) -> None:
        forward = {
            "online": data.get("online"),
            "pingMs": data.get("healthPingMs"),
            "voice": data.get("voice"),
            "memory": data.get("memory"),
        }
        used, total = _read_vram()
        if used is not None:
            forward["vramUsedMb"] = used
            forward["vramTotalMb"] = total
        bridge.set_metrics(forward)
        mem = data.get("memory")
        if isinstance(mem, dict):
            _last_memory.update(mem)

    metrics_service._sampled.connect(_on_sampled)  # noqa: SLF001 — misma señal real, un destino más
    metrics_service.start()

    # ── Acciones rápidas (sólo funciones que existen de verdad) ──────────
    def _on_new_conversation() -> None:
        import contextlib

        bridge.clear_chat()
        jarvis_instance = getattr(chat, "_jarvis", None)  # noqa: SLF001
        if jarvis_instance is not None:
            with contextlib.suppress(Exception):
                jarvis_instance.history.clear()

    def _on_mute(muted: bool) -> None:
        _mute_state["muted"] = muted
        if muted:
            voice.stop_speech()

    def _on_memory_requested() -> None:
        if _last_memory["count"] is None:
            bridge.toast("Memoria: sin datos todavía.", "info")
            return
        auto = "activo" if _last_memory["auto_recall"] else "apagado"
        bridge.toast(f"Memoria: {_last_memory['count']} recuerdos · auto-recall {auto}", "info")

    win.new_conversation_requested.connect(_on_new_conversation)
    win.mute_toggled.connect(_on_mute)
    win.memory_requested.connect(_on_memory_requested)

    # ── Recordatorios: mismo gancho que ya expone reminders.py (pensado
    # para esto, nunca se usaba en producción) — toast + voz real, en vez
    # del pitido/print pensado para consola. ─────────────────────────────
    def _on_reminder(message: str) -> None:
        bridge.toast(message, "reminder")
        try:
            from jarvis_local.voice.tts import speak as tts_speak
            tts_speak(message)
        except Exception:
            pass

    try:
        from jarvis_local.tools import reminders
        reminders._notify_hook = _on_reminder  # noqa: SLF001 — punto de inyección pensado para esto
    except Exception:
        pass

    # ── Cierre limpio ───────────────────────────────────────────────────
    bridge.closing.connect(chat.cancel)
    bridge.closing.connect(voice.stop_recording)
    bridge.closing.connect(voice.stop_speech)
    bridge.closing.connect(metrics_service.stop)

    return app, win


def main() -> int:
    from hud_pro.qt_compat import exec_app

    app, win = create_window()
    win.show()
    return exec_app(app)


if __name__ == "__main__":
    raise SystemExit(main())
