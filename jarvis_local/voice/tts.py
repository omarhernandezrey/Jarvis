"""
JARVIS Local - Text-to-Speech (Fase 3C)
Primario  : edge-tts + PyAV + sounddevice (voz neural masculina latina).
            Sin API key. Solo requiere internet.
Cache     : las frases generadas se guardan en data/tts_cache, asi que las
            respuestas repetidas ("Te escucho.", saludos) suenan al instante
            y siguen sonando con voz neural aunque no haya internet.
Fallback  : Linux: espeak-ng por subprocess (pyttsx3+espeak es un no-op
            silencioso en varias distros). Windows: pyttsx3/SAPI5.
"""
import asyncio
import contextlib
import hashlib
import io
import shutil as _shutil
import subprocess
import threading

import numpy as np
import sounddevice as sd

from jarvis_local.config import BASE_DIR, IS_WINDOWS, get_config

# Voz principal: hombre mexicano (la mas usada en proyectos JARVIS en espanol)
# Configurable en config.yaml -> voice.tts_voice
# Otras opciones: es-AR-TomasNeural, es-CO-GonzaloNeural, es-US-AlonsoNeural
_EDGE_VOICE = str(
    (get_config().get("voice") or {}).get("tts_voice", "es-MX-JorgeNeural")
)
_EDGE_RATE = "+0%"
_EDGE_VOLUME = "+0%"

# Cache de audio generado (para modo offline y latencia cero en repetidas)
_CACHE_DIR = BASE_DIR / "data" / "tts_cache"
_CACHE_MAX_FILES = 300

# Estado numerico (para get_voice_state compatible con CLI)
_rate_wpm = 175
_volume_float = 1.0
_voice_index_pyttsx3 = None

_is_speaking = False
_engine_pyttsx3 = None
_engine_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Asyncio helper
# ---------------------------------------------------------------------------

def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Edge-TTS: genera MP3 como bytes en memoria
# ---------------------------------------------------------------------------

async def _edge_generate_async(text: str) -> bytes:
    try:
        import edge_tts

        async def _gen() -> bytes:
            mp3 = b""
            communicate = edge_tts.Communicate(text, _EDGE_VOICE,
                                               rate=_EDGE_RATE, volume=_EDGE_VOLUME)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3 += chunk["data"]
            return mp3

        # Sin internet, el stream puede colgarse en vez de fallar rapido:
        # con timeout caemos al fallback offline en vez de dejar mudo a Jarvis.
        return await asyncio.wait_for(_gen(), timeout=15)
    except Exception:
        return b""


# ---------------------------------------------------------------------------
# Cache en disco de MP3 generados
# ---------------------------------------------------------------------------

def _cache_path(text: str):
    key = f"{_EDGE_VOICE}|{_EDGE_RATE}|{_EDGE_VOLUME}|{text}"
    return _CACHE_DIR / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".mp3")


def _cache_get(text: str) -> bytes:
    try:
        p = _cache_path(text)
        if p.exists():
            return p.read_bytes()
    except Exception:
        pass
    return b""


def _cache_put(text: str, mp3_bytes: bytes) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(text).write_bytes(mp3_bytes)
        files = sorted(_CACHE_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
        for old in files[:-_CACHE_MAX_FILES]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Decodificacion MP3 -> numpy con PyAV + reproduccion con sounddevice
# ---------------------------------------------------------------------------

def _mp3_bytes_to_numpy(mp3_bytes: bytes) -> tuple:
    """Retorna (array_float32, samplerate) o (None, 0) si falla."""
    try:
        import av
        buf = io.BytesIO(mp3_bytes)
        container = av.open(buf, format="mp3")
        stream = container.streams.audio[0]
        samplerate = stream.rate
        frames = []
        for frame in container.decode(stream):
            frames.append(frame.to_ndarray())
        container.close()
        if not frames:
            return None, 0
        audio = np.concatenate(frames, axis=1).T.astype(np.float32)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        return audio, samplerate
    except Exception:
        return None, 0


def _play_numpy(audio: np.ndarray, samplerate: int) -> bool:
    try:
        sd.play(audio, samplerate=samplerate)
        sd.wait()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fallback: pyttsx3 SAPI5
# ---------------------------------------------------------------------------

def _get_pyttsx3_engine():
    global _engine_pyttsx3
    with _engine_lock:
        if _engine_pyttsx3 is None:
            import pyttsx3
            _engine_pyttsx3 = pyttsx3.init()
            _apply_pyttsx3_settings()
        return _engine_pyttsx3


def _apply_pyttsx3_settings():
    if _engine_pyttsx3 is None:
        return
    voices = _engine_pyttsx3.getProperty("voices")
    idx = _voice_index_pyttsx3 if _voice_index_pyttsx3 is not None else _auto_spanish_idx(voices)
    if idx is not None and 0 <= idx < len(voices):
        _engine_pyttsx3.setProperty("voice", voices[idx].id)
    _engine_pyttsx3.setProperty("rate", _rate_wpm)
    _engine_pyttsx3.setProperty("volume", _volume_float)


def _auto_spanish_idx(voices) -> int | None:
    for i, v in enumerate(voices):
        for lang in (v.languages or []):
            if any(x in str(lang).lower() for x in ["es-co", "es-mx", "es-es", "es_", "es-", "spanish"]):
                return i
    for i, v in enumerate(voices):
        if any(x in (v.name or "").lower() for x in ["spanish", "espanol", "español"]):
            return i
    return 0 if voices else None


def _pyttsx3_speak(text: str) -> bool:
    try:
        engine = _get_pyttsx3_engine()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[TTS Fallback Error] {e}")
        return False


# ---------------------------------------------------------------------------
# Fallback Linux: espeak-ng por subprocess. pyttsx3 con el driver espeak
# retorna OK sin emitir sonido en varias distros; el binario si funciona.
# ---------------------------------------------------------------------------

def _espeak_binary() -> str | None:
    return _shutil.which("espeak-ng") or _shutil.which("espeak")


def _espeak_speak(text: str) -> bool:
    binary = _espeak_binary()
    if not binary:
        return False
    try:
        amp = max(0, min(200, int(_volume_float * 200)))
        subprocess.run(
            [binary, "-v", "es-419", "-s", str(_rate_wpm), "-a", str(amp), text],
            capture_output=True, timeout=120, check=True,
        )
        return True
    except Exception as e:
        print(f"[TTS Fallback Error] espeak: {e}")
        return False


def _offline_speak(text: str) -> bool:
    if IS_WINDOWS:
        return _pyttsx3_speak(text)
    return _espeak_speak(text) or _pyttsx3_speak(text)


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def speak(text: str) -> bool:
    global _is_speaking
    if not text:
        return False
    _is_speaking = True
    try:
        mp3_bytes = _cache_get(text)
        from_cache = bool(mp3_bytes)
        if not mp3_bytes:
            # Un reintento: edge-tts falla transitoriamente (DNS, 403 de
            # Microsoft) y a la segunda suele responder.
            for _ in range(2):
                mp3_bytes = _run_async(_edge_generate_async(text))
                if mp3_bytes:
                    break
        if mp3_bytes:
            audio, sr = _mp3_bytes_to_numpy(mp3_bytes)
            if audio is not None and sr > 0:
                if not from_cache:
                    _cache_put(text, mp3_bytes)
                return _play_numpy(audio, sr)
        # Fallback offline: espeak-ng (Linux) / pyttsx3 SAPI5 (Windows)
        print("[TTS] Voz neural no disponible (sin internet?); uso la voz de respaldo.")
        return _offline_speak(text)
    except Exception as e:
        print(f"[TTS Error] {e}")
        return False
    finally:
        _is_speaking = False


def stop_speaking() -> None:
    """Interrumpe la reproduccion en curso (edge-tts/sounddevice)."""
    with contextlib.suppress(Exception):
        sd.stop()


def is_speaking() -> bool:
    return _is_speaking


def is_available() -> bool:
    """Hay ALGUNA forma de hablar: fallback offline instalado, o edge-tts
    (que solo necesita internet y sounddevice, ya presentes)."""
    if not IS_WINDOWS and _espeak_binary():
        return True
    try:
        import pyttsx3
        e = pyttsx3.init()
        if len(e.getProperty("voices")) > 0:
            return True
    except Exception:
        pass
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def list_voices() -> list[dict]:
    """Lista voces SAPI5 disponibles (fallback). La voz principal es edge-tts."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        result = [{"index": -1, "name": f"[PRINCIPAL] edge-tts: {_EDGE_VOICE}",
                   "id": "edge-tts", "languages": ["es-CO"]}]
        for i, v in enumerate(voices):
            result.append({
                "index": i,
                "name": v.name,
                "id": v.id[:80],
                "languages": [str(lang) for lang in (v.languages or [])],
            })
        return result
    except Exception as e:
        return [{"index": -1, "name": f"ERROR: {e}", "id": "", "languages": []}]


def select_voice(index: int) -> bool:
    """Selecciona voz SAPI5 fallback por indice."""
    global _voice_index_pyttsx3, _engine_pyttsx3
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if 0 <= index < len(voices):
            _voice_index_pyttsx3 = index
            _engine_pyttsx3 = None  # Forzar re-init con nueva voz
            return True
        return False
    except Exception:
        return False


def set_rate(wpm: int) -> bool:
    global _rate_wpm, _EDGE_RATE, _engine_pyttsx3
    if 120 <= wpm <= 250:
        _rate_wpm = wpm
        pct = int((wpm - 175) / 175 * 100)
        _EDGE_RATE = f"+{pct}%" if pct >= 0 else f"{pct}%"
        _engine_pyttsx3 = None  # Forzar re-init
        return True
    return False


def set_volume(vol: float) -> bool:
    global _volume_float, _EDGE_VOLUME, _engine_pyttsx3
    if 0.0 <= vol <= 1.0:
        _volume_float = vol
        pct = int((vol - 1.0) * 100)
        _EDGE_VOLUME = f"+{pct}%" if pct >= 0 else f"{pct}%"
        _engine_pyttsx3 = None  # Forzar re-init
        return True
    return False


def set_edge_voice(voice_name: str) -> bool:
    """Cambia la voz neural principal (ej. es-CO-GonzaloNeural) en caliente.
    Para hacerlo permanente: config.yaml -> voice.tts_voice."""
    global _EDGE_VOICE
    if voice_name and voice_name.count("-") >= 2:
        _EDGE_VOICE = voice_name
        return True
    return False


def get_voice_state() -> dict:
    fallback = "pyttsx3/SAPI5" if IS_WINDOWS else (
        _espeak_binary() or "sin fallback offline")
    return {
        "voice_index": _voice_index_pyttsx3,
        "rate": _rate_wpm,
        "volume": _volume_float,
        "engine": f"edge-tts ({_EDGE_VOICE}) | fallback {fallback}",
        "edge_voice": _EDGE_VOICE,
        "cache_dir": str(_CACHE_DIR),
    }
