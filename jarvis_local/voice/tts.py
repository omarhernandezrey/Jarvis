"""
JARVIS Local - Text-to-Speech (Fase 3C)

Jarvis NUNCA se queda mudo. Hay dos capas de voz, las dos neurales:

Capa 1    : edge-tts + PyAV + sounddevice (es-MX-JorgeNeural, la voz
            "oficial" de Jarvis). Sin API key, pero depende de un endpoint
            no documentado de Microsoft que REQUIERE internet y que, cada
            cierto tiempo, empieza a responder 403 a la version instalada
            de edge-tts hasta que se actualiza el paquete.
Capa 2    : Piper, TTS neural que corre 100% en esta maquina (es_MX-ald,
            masculina mexicana). Sin internet y sin servicios de terceros.
            Entra en accion SOLO si la capa 1 falla.

Por que existe la capa 2: el diseno anterior era "voz neural de Microsoft
o silencio". El 2026-11-23 Microsoft empezo a devolver 403 a edge-tts
7.2.8 y Jarvis se quedo completamente mudo -- y no era la primera vez. Un
Jarvis que no responde es un Jarvis roto, asi que ahora un 403 degrada la
voz (suena Piper, con acento mexicano parecido) en vez de apagarla. Ver
`_piper_speak`.

Cache     : las frases generadas se guardan en data/tts_cache, asi que las
            respuestas repetidas ("Te escucho.", saludos) suenan al instante
            y siguen sonando con la voz de la capa 1 aunque no haya internet.
"""
import asyncio
import contextlib
import hashlib
import io

import numpy as np
import sounddevice as sd

from jarvis_local.config import BASE_DIR, get_config

# Voz principal y UNICA: hombre mexicano (la mas usada en proyectos JARVIS
# en espanol). Configurable en config.yaml -> voice.tts_voice, pero si ese
# valor no tiene forma de voz de Edge TTS valida (ej. quedo en "auto", vacio,
# o alguien lo borro/corrompio por error) se ignora y se usa este default en
# vez de dejar a Jarvis sin voz configurada. Asi la voz elegida nunca se
# "pierde" por un config.yaml invalido.
# Otras opciones validas: es-AR-TomasNeural, es-CO-GonzaloNeural,
# es-US-AlonsoNeural
_DEFAULT_EDGE_VOICE = "es-MX-JorgeNeural"


def _is_valid_edge_voice(name: str) -> bool:
    """Forma esperada de un nombre de voz de Edge TTS: 'xx-YY-NombreNeural'."""
    return bool(name) and name.count("-") >= 2 and name.endswith("Neural")


_configured_voice = str(
    (get_config().get("voice") or {}).get("tts_voice", _DEFAULT_EDGE_VOICE)
)
_EDGE_VOICE = (
    _configured_voice if _is_valid_edge_voice(_configured_voice) else _DEFAULT_EDGE_VOICE
)
def _pct_rate(wpm: int) -> str:
    """Velocidad en palabras/minuto -> porcentaje que espera edge-tts."""
    pct = int((wpm - 175) / 175 * 100)
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


def _pct_volumen(vol: float) -> str:
    """Volumen 0-1 -> porcentaje que espera edge-tts."""
    pct = int((vol - 1.0) * 100)
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


# `voice.tts_rate` / `voice.tts_volume` de config.yaml SÍ se aplican (antes eran
# dos constantes "+0%" y la configuración era decorativa: daba igual poner
# tts_rate: 120, JARVIS seguía hablando a la velocidad por defecto).
_cfg_voice = get_config().get("voice") or {}
_EDGE_RATE = _pct_rate(int(_cfg_voice.get("tts_rate", 175)))
_EDGE_VOLUME = _pct_volumen(float(_cfg_voice.get("tts_volume", 1.0)))

# Cache de audio generado (para modo offline y latencia cero en repetidas)
_CACHE_DIR = BASE_DIR / "data" / "tts_cache"
_CACHE_MAX_FILES = 300

# Estado numerico (para get_voice_state compatible con CLI)
_rate_wpm = 175
_volume_float = 1.0
_voice_index_pyttsx3 = None

_is_speaking = False
_engine_pyttsx3 = None


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
        # con timeout fallamos rapido y speak() se queda en silencio en vez
        # de esperar indefinidamente.
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
# Capa 2: Piper -- voz neural LOCAL de respaldo (sin internet, sin terceros)
# ---------------------------------------------------------------------------

# Voz masculina mexicana, la mas parecida a es-MX-JorgeNeural dentro del
# catalogo de Piper. Configurable en config.yaml -> voice.tts_fallback_voice.
_DEFAULT_PIPER_VOICE = "es_MX-ald-medium"
_PIPER_DIR = BASE_DIR / "data" / "piper_voices"

_configured_piper = str(_cfg_voice.get("tts_fallback_voice", _DEFAULT_PIPER_VOICE))
_PIPER_VOICE = _configured_piper or _DEFAULT_PIPER_VOICE

# El modelo pesa ~63 MB: se carga una sola vez, y solo si de verdad se
# necesita (si la capa 1 nunca falla, Piper nunca se carga en memoria).
_piper_loaded = None


def piper_model_path():
    """Ruta del .onnx de la voz local de respaldo."""
    return _PIPER_DIR / f"{_PIPER_VOICE}.onnx"


def piper_download_hint() -> str:
    """Comando exacto para instalar la voz local. Se muestra cuando falta:
    un error accionable vale mas que 'no hay voz disponible'."""
    return (
        f"python -m piper.download_voices {_PIPER_VOICE} "
        f"--download-dir {_PIPER_DIR}"
    )


def is_piper_available() -> bool:
    """La voz local de respaldo esta lista: paquete piper instalado Y
    modelo descargado en disco."""
    try:
        import piper  # noqa: F401
    except Exception:
        return False
    return piper_model_path().exists()


def _get_piper_voice():
    """Carga (una vez) el modelo local. None si no se puede."""
    global _piper_loaded
    if _piper_loaded is not None:
        return _piper_loaded
    try:
        from piper import PiperVoice
        _piper_loaded = PiperVoice.load(str(piper_model_path()))
        return _piper_loaded
    except Exception:
        return None


def _piper_synth(text: str) -> tuple:
    """Sintetiza con Piper. Retorna (array_float32, samplerate) o (None, 0).

    Respeta voice.tts_rate / voice.tts_volume igual que la capa 1:
    `length_scale` es inverso a la velocidad (mas largo = mas lento), asi
    que un tts_rate alto se traduce en length_scale bajo.
    """
    try:
        from piper.config import SynthesisConfig

        voice = _get_piper_voice()
        if voice is None:
            return None, 0

        syn = SynthesisConfig(
            length_scale=175.0 / max(_rate_wpm, 1),
            volume=max(0.0, min(_volume_float, 1.0)),
        )
        chunks = list(voice.synthesize(text, syn_config=syn))
        if not chunks:
            return None, 0
        audio = np.concatenate([c.audio_float_array for c in chunks])
        return audio.astype(np.float32), int(chunks[0].sample_rate)
    except Exception:
        return None, 0


def _piper_speak(text: str) -> bool:
    """Habla con la voz local. Es la red de seguridad: si esto tambien
    falla, Jarvis se queda mudo y lo dice con el motivo concreto."""
    if not is_piper_available():
        print(
            f"[TTS] La voz principal ({_EDGE_VOICE}) fallo y la voz local de "
            f"respaldo no esta instalada, asi que Jarvis no puede hablar.\n"
            f"      Instalala con: {piper_download_hint()}"
        )
        return False
    audio, sr = _piper_synth(text)
    if audio is None or sr <= 0:
        print(f"[TTS] La voz local ({_PIPER_VOICE}) no pudo sintetizar el texto.")
        return False
    print(
        f"[TTS] Voz principal ({_EDGE_VOICE}) no disponible -- hablando con la "
        f"voz local de respaldo ({_PIPER_VOICE})."
    )
    return _play_numpy(audio, sr)


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
        # Capa 1 caida (403 de Microsoft, sin internet, PyAV sin poder
        # decodificar...). Antes esto era silencio garantizado; ahora se
        # degrada a la voz neural local para que Jarvis siga respondiendo.
        return _piper_speak(text)
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
    """Hay alguna forma de hablar: la capa 1 (edge-tts) o la capa 2 (voz
    local Piper). No confirma que haya internet en este momento -- eso
    solo se sabe al intentar speak(); pero si la capa 2 esta lista,
    speak() funciona aunque la 1 este caida."""
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return is_piper_available()


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
        _EDGE_RATE = _pct_rate(wpm)
        _engine_pyttsx3 = None  # Forzar re-init
        return True
    return False


def set_volume(vol: float) -> bool:
    global _volume_float, _EDGE_VOLUME, _engine_pyttsx3
    if 0.0 <= vol <= 1.0:
        _volume_float = vol
        _EDGE_VOLUME = _pct_volumen(vol)
        _engine_pyttsx3 = None  # Forzar re-init
        return True
    return False


def set_edge_voice(voice_name: str) -> bool:
    """Cambia la voz neural principal (ej. es-CO-GonzaloNeural) en caliente.
    Para hacerlo permanente: config.yaml -> voice.tts_voice."""
    global _EDGE_VOICE
    if _is_valid_edge_voice(voice_name):
        _EDGE_VOICE = voice_name
        return True
    return False


def get_voice_state() -> dict:
    return {
        "voice_index": _voice_index_pyttsx3,
        "rate": _rate_wpm,
        "volume": _volume_float,
        "engine": (
            f"edge-tts ({_EDGE_VOICE}) | respaldo local: piper ({_PIPER_VOICE})"
            + ("" if is_piper_available() else " [NO INSTALADO]")
        ),
        "edge_voice": _EDGE_VOICE,
        "fallback_voice": _PIPER_VOICE,
        "fallback_ready": is_piper_available(),
        "cache_dir": str(_CACHE_DIR),
    }
