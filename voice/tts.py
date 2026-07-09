"""
JARVIS Local - Text-to-Speech con Piper (Fase 3)
Sintetiza voz en espanol offline y reproduce.

NOTA: piper-tts en PyPI actualmente es GPL-3.0 (OHF-Voice).
El import se llama 'piper', no 'piper_tts'.
"""
import io
import os
import tempfile
import time
from typing import Optional
from jarvis_local.config import get_config
from jarvis_local.safety.logger import logger


def _get_voice_path() -> Optional[str]:
    """Busca la voz Piper instalada. None si no existe."""
    cfg = get_config().get("voice", {})
    voice_name = cfg.get("tts_voice", "es_MX-ald-x_low")

    data_dirs = [
        os.path.join(os.path.expanduser("~"), ".local", "share", "piper-tts"),
        os.path.join(os.path.expanduser("~"), ".config", "piper-tts"),
        os.path.join(os.path.expanduser("~"), "piper-voices"),
    ]

    for base in data_dirs:
        onnx_path = os.path.join(base, f"{voice_name}.onnx")
        json_path = os.path.join(base, f"{voice_name}.onnx.json")
        if os.path.exists(onnx_path) and os.path.exists(json_path):
            return voice_name

    return None


def is_piper_available() -> bool:
    """Verifica si Piper y la voz estan disponibles."""
    try:
        import piper
    except ImportError:
        return False
    return _get_voice_path() is not None


def speak(text: str) -> bool:
    """
    Sintetiza y reproduce voz en espanol con Piper.

    Returns:
        True si se reprodujo correctamente, False si fallo.
    """
    if not text:
        return False

    try:
        import piper
    except ImportError:
        print("[Voz] Piper no instalado. Respuesta solo texto.")
        return False

    voice_name = _get_voice_path()
    if not voice_name:
        cfg = get_config().get("voice", {})
        vname = cfg.get("tts_voice", "es_MX-ald-x_low")
        print("[Voz] Voz Piper no descargada. Respuesta solo texto.")
        print(f"  Descargala con: python -c \"import piper; piper.download_voice('{vname}')\"")
        return False

    print("[Reproduciendo respuesta...]")

    try:
        wav_bytes = piper.synthesize(text, voice_name)

        try:
            import sounddevice as sd
            import numpy as np
            import wave

            wav_io = io.BytesIO(wav_bytes)
            with wave.open(wav_io, "rb") as wf:
                sample_rate = wf.getframerate()
                audio_data = wf.readframes(wf.getnframes())
                audio_array = (
                    np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                )

            sd.play(audio_array, samplerate=sample_rate)
            sd.wait()

        except Exception:
            tmp_path = os.path.join(tempfile.gettempdir(), "jarvis_tts_temp.wav")
            try:
                with open(tmp_path, "wb") as f:
                    f.write(wav_bytes)
                os.startfile(tmp_path)
                time.sleep(max(1.0, len(text) * 0.06))
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        return True

    except Exception as e:
        logger.log_error("tts", str(e))
        return False
