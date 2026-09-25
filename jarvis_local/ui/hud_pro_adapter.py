"""Adaptador entre el pipeline actual de JARVIS y el HUD pro.

No modifica la lógica existente: solo traduce los eventos que YA produce el backend
(wake word, audio, STT, tokens del LLM, TTS, errores) a llamadas del ``HudBridge``.
Todos los métodos son seguros desde cualquier hilo.

Uso típico en el arranque::

    from hud_pro import create_app, HudWindow, HudBridge
    from jarvis_local.ui.hud_pro_adapter import JarvisHudAdapter

    app = create_app()
    window = HudWindow()
    bridge = HudBridge(window)
    hud = JarvisHudAdapter(bridge, on_user_text=assistant.handle_text)
    # engancha hud.on_* en los callbacks/eventos que ya emite tu pipeline
    window.show()
    app.exec()
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from hud_pro import HudBridge
from hud_pro.audio import level_from_float, level_from_pcm16

log = logging.getLogger("jarvis.hud")


class JarvisHudAdapter:
    def __init__(
        self,
        bridge: HudBridge,
        on_user_text: Callable[[str], Any] | None = None,
        on_mic_toggle: Callable[[bool], Any] | None = None,
        model_name: str = "",
    ) -> None:
        self._bridge = bridge
        if on_user_text is not None:
            bridge.user_message.connect(on_user_text)  # texto escrito en la consola (ya saneado)
        if on_mic_toggle is not None:
            bridge.mic_toggled.connect(on_mic_toggle)
        if model_name:
            bridge.set_model(model_name)

    # ── Entrada de voz ────────────────────────────────────────────────────
    def on_wake_word(self) -> None:
        self._bridge.set_state("escuchando")

    def on_mic_pcm16(self, chunk: bytes) -> None:
        self._bridge.set_level(level_from_pcm16(chunk))

    def on_mic_float(self, samples: Any) -> None:
        self._bridge.set_level(level_from_float(samples))

    def on_partial_transcript(self, text: str) -> None:
        self._bridge.set_transcript(text)

    def on_final_transcript(self, text: str) -> None:
        self._bridge.set_transcript(text)
        self._bridge.add_message("user", text)
        self._bridge.set_state("procesando")

    # ── LLM ───────────────────────────────────────────────────────────────
    def on_llm_start(self) -> None:
        self._bridge.set_state("procesando")

    def on_llm_token(self, token: str) -> None:
        self._bridge.stream(token)

    def on_llm_done(self) -> None:
        self._bridge.end_stream()

    # ── Salida de voz ─────────────────────────────────────────────────────
    def on_tts_start(self) -> None:
        self._bridge.set_state("hablando")

    def on_tts_pcm16(self, chunk: bytes) -> None:
        """Opcional: sin esto el orbe usa un nivel sintético mientras habla."""
        self._bridge.set_level(level_from_pcm16(chunk))

    def on_tts_end(self) -> None:
        self._bridge.set_state("listo")

    # ── Errores ───────────────────────────────────────────────────────────
    def on_error(self, exc: BaseException) -> None:
        log.exception("Error en el pipeline de JARVIS", exc_info=exc)
        self._bridge.end_stream()
        # no exponer trazas en la UI: solo un mensaje corto
        self._bridge.set_state("error", f"{type(exc).__name__}: {str(exc)[:120]}")
