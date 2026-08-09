"""
JARVIS Local - Deteccion de dispositivos de audio (Fase 3)
"""


def list_microphones() -> list[dict]:
    """Lista microfonos disponibles. No crashea si no hay sounddevice."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        mics = []
        for i, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                mics.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "default_samplerate": dev.get("default_samplerate", 16000),
                })
        return mics
    except Exception:
        return []


def get_default_microphone() -> dict | None:
    """Obtiene el microfono por defecto."""
    mics = list_microphones()
    if not mics:
        return None
    try:
        import sounddevice as sd
        default = sd.query_devices(kind="input")
        for m in mics:
            if m["name"] == default["name"]:
                return m
    except Exception:
        pass
    return mics[0] if mics else None
