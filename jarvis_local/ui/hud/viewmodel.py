"""ViewModel — único punto de contacto entre el núcleo (Python) y la vista (QML).

Contrato (brief, §1): el núcleo no cambia; la vista nunca lo llama en directo ni
bloquea su hilo. Todo pasa por este objeto, que expone **cinco canales y nada
más**:

    state   → propiedad `state` (+ señal `stateChanged`)      máquina de estados
    token   → señal `token(str)`                              token del stream LLM
    audio   → propiedad `audio` (+ señal `audioChanged`)      nivel + espectro (FFT)
    metrics → propiedad `metrics` (+ señal `metricsChanged`)  CPU/RAM/latencia/...
    error   → señal `error(str)`                              evento de fallo

Los `push_*` son *slots*: los llaman hilos productores (muestreo de sistema,
captura de micrófono, cliente Ollama) vía `QMetaObject.invokeMethod` con
`Qt.QueuedConnection`, de modo que la mutación de estado y la emisión de señales
ocurren siempre en el hilo de la GUI.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

STATES = ("idle", "listening", "thinking", "speaking", "alert", "offline")


class ViewModel(QObject):
    # ── los cinco canales ────────────────────────────────────────────────────
    stateChanged = Signal(str)
    token = Signal(str)
    audioChanged = Signal()
    metricsChanged = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._audio = {"level": 0.0, "spectrum": []}   # spectrum vacío = sin fuente
        self._metrics: dict = {}

    # ── state ───────────────────────────────────────────────────────────────
    def _get_state(self) -> str:
        return self._state

    state = Property(str, _get_state, notify=stateChanged)

    @Slot(str)
    def set_state(self, value: str) -> None:
        value = (value or "").lower()
        if value not in STATES or value == self._state:
            return
        self._state = value
        self.stateChanged.emit(value)

    # ── audio (nivel + espectro para el anillo de datos) ────────────────────
    def _get_audio(self) -> dict:
        return self._audio

    audio = Property("QVariantMap", _get_audio, notify=audioChanged)

    @Slot(float, list)
    def push_audio(self, level: float, spectrum: list | None = None) -> None:
        lvl = 0.0 if level != level else float(level)          # descarta NaN
        self._audio = {
            "level": max(0.0, min(1.0, lvl)),
            "spectrum": [max(0.0, min(1.0, float(x))) for x in spectrum] if spectrum else [],
        }
        self.audioChanged.emit()

    @Slot()
    def clear_audio(self) -> None:
        """Sin fuente de audio: nivel a 0 y espectro vacío (el anillo cae a su
        valor base, nunca a ruido simulado)."""
        if self._audio["level"] or self._audio["spectrum"]:
            self._audio = {"level": 0.0, "spectrum": []}
            self.audioChanged.emit()

    # ── metrics (HUD, Fase 3) ──────────────────────────────────────────────
    def _get_metrics(self) -> dict:
        return self._metrics

    metrics = Property("QVariantMap", _get_metrics, notify=metricsChanged)

    @Slot(dict)
    def push_metrics(self, data: dict) -> None:
        self._metrics = dict(data)
        self.metricsChanged.emit()

    # ── token / error ──────────────────────────────────────────────────────
    @Slot(str)
    def push_token(self, text: str) -> None:
        if text:
            self.token.emit(text)

    @Slot(str)
    def push_error(self, message: str) -> None:
        self.error.emit(message or "Fallo desconocido")
