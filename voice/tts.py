"""
JARVIS Local - Text-to-Speech con SAPI5/pyttsx3 (Fase 3B)
Usa el motor de voz nativo de Windows. MIT. Sin modelos, sin descargas.
"""
import threading
from typing import Optional
from jarvis_local.config import get_config


_engine = None
_voice_index = None
_rate = 175
_volume = 1.0


def _get_engine():
    global _engine
    if _engine is None:
        import pyttsx3
        _engine = pyttsx3.init()
        _apply_settings()
    return _engine


def _apply_settings():
    if _engine is None:
        return
    voices = _engine.getProperty("voices")
    idx = _voice_index if _voice_index is not None else _auto_spanish_index(voices)
    if idx is not None and 0 <= idx < len(voices):
        _engine.setProperty("voice", voices[idx].id)
    _engine.setProperty("rate", _rate)
    _engine.setProperty("volume", _volume)


def _auto_spanish_index(voices) -> Optional[int]:
    for i, v in enumerate(voices):
        for lang in (v.languages or []):
            lang_l = str(lang).lower()
            if any(x in lang_l for x in ["es-co", "es-mx", "es-es", "es_", "es-",
                                          "spanish", "español", "espagnol"]):
                return i
    for i, v in enumerate(voices):
        name_l = (v.name or "").lower()
        if any(x in name_l for x in ["spanish", "español", "espanol", "espagnol"]):
            return i
    return 0 if voices else None


def list_voices() -> list[dict]:
    try:
        engine = _get_engine()
        voices = engine.getProperty("voices")
        result = []
        for i, v in enumerate(voices):
            result.append({
                "index": i,
                "name": v.name,
                "id": v.id[:80],
                "languages": [str(l) for l in (v.languages or [])],
            })
        return result
    except Exception as e:
        return [{"index": -1, "name": f"ERROR: {e}", "id": "", "languages": []}]


def select_voice(index: int) -> bool:
    global _voice_index
    try:
        engine = _get_engine()
        voices = engine.getProperty("voices")
        if 0 <= index < len(voices):
            _voice_index = index
            _apply_settings()
            return True
        return False
    except Exception:
        return False


def set_rate(wpm: int) -> bool:
    global _rate
    if 120 <= wpm <= 250:
        _rate = wpm
        if _engine is not None:
            _engine.setProperty("rate", _rate)
        return True
    return False


def set_volume(vol: float) -> bool:
    global _volume
    if 0.0 <= vol <= 1.0:
        _volume = vol
        if _engine is not None:
            _engine.setProperty("volume", _volume)
        return True
    return False


def get_voice_state() -> dict:
    return {
        "voice_index": _voice_index,
        "rate": _rate,
        "volume": _volume,
        "engine": "pyttsx3 (SAPI5)",
    }


def is_available() -> bool:
    try:
        import pyttsx3
        e = pyttsx3.init()
        return len(e.getProperty("voices")) > 0
    except Exception:
        return False


def speak(text: str) -> bool:
    if not text:
        return False
    try:
        engine = _get_engine()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[TTS Error] {e}")
        return False
