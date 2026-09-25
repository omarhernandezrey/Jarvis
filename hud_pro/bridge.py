"""Puente thread-safe entre el backend de JARVIS (hilos de STT/LLM/TTS) y el HUD.

Los métodos de ``HudBridge`` pueden llamarse desde CUALQUIER hilo: emiten señales Qt que,
al cruzar hilos, se entregan encoladas en el hilo de la GUI (sin locks ni race conditions).

Ejemplo::

    bridge = HudBridge(window)                 # crear en el hilo de la GUI
    bridge.user_message.connect(backend.ask)   # texto escrito en la consola
    # ...desde un hilo worker:
    bridge.set_state("escuchando")
    bridge.set_level(rms)                      # 0..1, puede llamarse a 50-100 Hz
    bridge.set_transcript(parcial)
    bridge.set_state("procesando")
    for token in llm.stream(prompt):
        bridge.stream(token)
    bridge.end_stream()
    bridge.set_state("listo")
"""

from __future__ import annotations

import math
import threading
import time
from typing import Optional

from .qt_compat import QtCore, QtWidgets, Signal
from .state import StateLike, parse_state
from .window import HudWindow


class HudBridge(QtCore.QObject):
    # señales internas (siempre se conectan a slots del hilo GUI)
    _sig_state = Signal(str, str)
    _sig_level = Signal(float)
    _sig_transcript = Signal(str)
    _sig_message = Signal(str, str)
    _sig_chunk = Signal(str)
    _sig_done = Signal()
    _sig_model = Signal(str)
    _sig_clear = Signal()
    _sig_spectrum = Signal(list)
    _sig_metrics = Signal(dict)
    _sig_service = Signal(str, bool)
    _sig_toast = Signal(str, str)
    _sig_tool_start = Signal(str)
    _sig_tool_end = Signal(str, float, bool)

    # señales públicas hacia el backend
    user_message = Signal(str)
    mic_toggled = Signal(bool)
    closing = Signal()

    LEVEL_MIN_INTERVAL = 1 / 90  # s; limita inundación de eventos desde el hilo de audio

    def __init__(self, window: HudWindow) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None or QtCore.QThread.currentThread() is not app.thread():
            raise RuntimeError("HudBridge debe crearse en el hilo de la GUI (después de QApplication).")
        super().__init__(window)
        self._window = window
        self._level_lock = threading.Lock()
        self._last_level_ts = 0.0

        self._sig_state.connect(self._apply_state)
        self._sig_level.connect(window.set_audio_level)
        self._sig_transcript.connect(window.set_transcript)
        self._sig_message.connect(self._apply_message)
        self._sig_chunk.connect(window.stream_assistant)
        self._sig_done.connect(window.end_assistant_stream)
        self._sig_model.connect(window.set_model_name)
        self._sig_clear.connect(window.clear_chat)
        self._sig_spectrum.connect(window.set_spectrum)
        self._sig_metrics.connect(window.update_metrics)
        self._sig_service.connect(window.set_service_active)
        self._sig_toast.connect(window.show_toast)
        self._sig_tool_start.connect(window.tool_start)
        self._sig_tool_end.connect(window.tool_end)

        window.message_submitted.connect(self.user_message.emit)
        window.mic_toggled.connect(self.mic_toggled.emit)
        window.closing.connect(self.closing.emit)
        # clic en el orbe = clic en el botón de micrófono (mismo handler,
        # mismo estado visual — el botón sigue siendo la fuente de verdad).
        window.orb.clicked.connect(window.chat.input.mic.click)

    # ── API thread-safe ───────────────────────────────────────────────────
    def set_state(self, state: StateLike, detail: str = "") -> None:
        st = parse_state(state)  # valida en el hilo que llama → error inmediato y claro
        self._sig_state.emit(st.value, detail or "")

    def set_level(self, level: float) -> None:
        try:
            value = float(level)
        except (TypeError, ValueError):
            return
        if math.isnan(value) or math.isinf(value):
            return
        now = time.monotonic()
        with self._level_lock:
            if now - self._last_level_ts < self.LEVEL_MIN_INTERVAL:
                return
            self._last_level_ts = now
        self._sig_level.emit(max(0.0, min(1.0, value)))

    def set_transcript(self, text: str) -> None:
        self._sig_transcript.emit(str(text or ""))

    def add_message(self, role: str, text: str) -> None:
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Rol inválido: {role!r}")
        self._sig_message.emit(role, str(text or ""))

    def stream(self, chunk: str) -> None:
        if chunk:
            self._sig_chunk.emit(str(chunk))

    def end_stream(self) -> None:
        self._sig_done.emit()

    def set_model(self, name: str) -> None:
        self._sig_model.emit(str(name or ""))

    def clear_chat(self) -> None:
        self._sig_clear.emit()

    def set_spectrum(self, bands: Optional[list]) -> None:
        """Espectro real 0..1 (FFT del micrófono o del TTS) para el anillo
        del orbe. `None`/lista vacía lo apaga — nunca se inventa una forma."""
        self._sig_spectrum.emit(list(bands) if bands else [])

    def set_metrics(self, data: dict) -> None:
        """Métricas reales para la barra superior (modelo, Ollama, CPU/RAM/
        VRAM, tokens/s, tiempo al primer token…). Fusiona claves — cada
        productor es dueño de las suyas, igual que `ViewModel.push_metrics`
        del HUD legado; una clave ausente no se muestra, nunca se inventa."""
        self._sig_metrics.emit(dict(data or {}))

    def set_service_active(self, name: str, active: bool) -> None:
        """Chip de servicio (mic/wake/tts/memory): punto que late mientras
        `active` — el servicio está trabajando de verdad, no decorativo."""
        self._sig_service.emit(str(name), bool(active))

    def toast(self, message: str, kind: str = "info") -> None:
        """Aviso no intrusivo (error/recordatorio/info), se apaga solo."""
        if message:
            self._sig_toast.emit(str(message), str(kind or "info"))

    def tool_start(self, name: str) -> None:
        """Tarjeta viva de herramienta: arranca con spinner, sin duración
        todavía (se completa en `tool_end`)."""
        self._sig_tool_start.emit(str(name or ""))

    def tool_end(self, name: str, ms: float, ok: bool) -> None:
        """Cierra la tarjeta de herramienta con la duración real y el
        resultado (ok/error)."""
        try:
            ms_f = float(ms)
        except (TypeError, ValueError):
            ms_f = 0.0
        self._sig_tool_end.emit(str(name or ""), ms_f, bool(ok))

    # ── Slots (hilo GUI) ──────────────────────────────────────────────────
    def _apply_state(self, state: str, detail: str) -> None:
        self._window.set_state(state, detail or None)

    def _apply_message(self, role: str, text: str) -> None:
        self._window.chat.add_message(role, text)

    @property
    def window(self) -> Optional[HudWindow]:
        return self._window
