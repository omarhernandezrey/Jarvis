"""Servicios de datos reales para el HUD.

`MetricsService` muestrea, **cada 2 s y en un hilo aparte** (nunca en el hilo de
la GUI: `is_running()` hace I/O de red), el estado real de los subsistemas y lo
entrega al ViewModel mediante `push_metrics` con `QueuedConnection`, de modo que
la mutación de estado y la emisión de señales ocurren en el hilo de la GUI.

Nada se inventa: si un dato no se puede leer, se envía `None` y la vista lo
pinta como ausente.
"""
from __future__ import annotations

import os
import subprocess
import threading

from PySide6.QtCore import QObject, Signal

SAMPLE_S = 2.0


def detect_reduced_motion() -> bool:
    """¿El sistema pide reducir animaciones? Orden: variable de entorno →
    GNOME (`enable-animations`). Best-effort; ante la duda, False."""
    env = os.environ.get("JARVIS_REDUCED_MOTION", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"],
            capture_output=True, text=True, timeout=1.5,
        )
        if out.returncode == 0:
            return out.stdout.strip() == "false"
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def _read_cpu_ram():
    try:
        import psutil
        return psutil.cpu_percent(interval=None), psutil.virtual_memory().percent
    except Exception:
        return None, None


_ollama_client = None


def _read_ollama():
    """(online: bool, model: str|None, ping_ms: int|None) del cliente real.
    Reutiliza un único OllamaClient (crear/cerrar uno por muestra hacía crecer
    la RSS)."""
    global _ollama_client
    try:
        import time

        from jarvis_local.config import get_config
        from jarvis_local.ollama_client.client import OllamaClient
        model = get_config().get("ollama", {}).get("model")
        if _ollama_client is None:
            _ollama_client = OllamaClient()
        t0 = time.monotonic()
        online = _ollama_client.is_running()
        ping = round((time.monotonic() - t0) * 1000) if online else None
        return online, model, ping
    except Exception:
        return False, None, None


_voice_cache: dict | None = None


def _read_voice(force: bool = False):
    """Estado de voz. `sd.query_devices` desde un hilo, cada 2 s, hacía crecer
    la RSS (PortAudio se re-inicializa): se consulta UNA vez y se cachea. La
    disponibilidad real del micrófono se reevalúa cuando el usuario intenta
    grabar (VoiceService pone `denied` si el stream falla)."""
    global _voice_cache
    if _voice_cache is not None and not force:
        return _voice_cache
    tts_ok = False
    try:
        import edge_tts  # noqa: F401
        tts_ok = True
    except Exception:
        tts_ok = False
    mic = "absent"
    try:
        import sounddevice as sd
        if sd.query_devices(kind="input") is not None:
            mic = "available"
    except Exception:
        mic = "absent"
    _voice_cache = {"tts": tts_ok, "mic": mic}
    return _voice_cache


def _read_tools():
    try:
        from jarvis_local.agent.registry import TOOLS
        from jarvis_local.config import get_config
        agent_on = bool(get_config().get("agent", {}).get("enabled", False))
        return {"count": len(TOOLS), "agent": agent_on}
    except Exception:
        return {"count": None, "agent": False}


def _read_memory():
    try:
        from jarvis_local.config import BASE_DIR, get_config
        from jarvis_local.storage.memory import MemoryStore
        auto = bool(get_config().get("memory", {}).get("auto_recall", False))
        return {"auto_recall": auto, "count": len(MemoryStore(BASE_DIR / "data").list())}
    except Exception:
        return {"auto_recall": False, "count": None}


def sample_all() -> dict:
    cpu, ram = _read_cpu_ram()
    online, model, ping = _read_ollama()
    return {
        "cpu": cpu,
        "ram": ram,
        "online": online,
        "model": model,
        "healthPingMs": ping,
        "voice": _read_voice(),
        "tools": _read_tools(),
        "memory": _read_memory(),
    }


class MetricsService(QObject):
    """Hilo de muestreo (2 s) que alimenta el ViewModel y aplica la política
    OFFLINE↔IDLE del núcleo a partir del health-check real, sin pisar los
    estados de interacción (listening/thinking/speaking)."""

    # emitidas desde el hilo de muestreo; entrega en cola al hilo de la GUI
    _sampled = Signal(dict)
    _wantState = Signal(str)

    def __init__(self, view_model: QObject, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sampled.connect(view_model.push_metrics)
        self._wantState.connect(view_model.set_state)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="metrics", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=3.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            data = sample_all()
            self._sampled.emit(data)
            online = data.get("online")
            state = self._vm.state
            if online is False and state in ("idle", "offline"):
                self._wantState.emit("offline")
            elif online and state == "offline":
                self._wantState.emit("idle")
            self._stop.wait(SAMPLE_S)
