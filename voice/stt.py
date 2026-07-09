"""
JARVIS Local - Speech-to-Text con faster-whisper (Fase 3)
Graba del microfono, transcribe offline en espanol.
Con calibracion de ruido y diagnostico.
"""
import os
import time
import yaml
from typing import Optional
from jarvis_local.config import CONFIG_FILE
from jarvis_local.safety.logger import logger


def load_voice_config() -> dict:
    """Lee config.yaml desde disco CADA VEZ. Sin cache."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return data.get("voice", {})


try:
    import sounddevice as _sd
    import numpy as _np
    _AUDIO_OK = True
except ImportError:
    _AUDIO_OK = False
    _sd = None
    _np = None


def _get_threshold() -> float:
    cfg = load_voice_config()
    noise_floor = cfg.get("stt_noise_floor")
    min_threshold = cfg.get("stt_min_threshold", 0.00005)
    if noise_floor is not None and isinstance(noise_floor, (int, float)):
        return max(float(noise_floor) * 2.0, min_threshold)
    return min_threshold


def _audio_stats(recording) -> dict:
    """Calcula estadisticas del audio capturado."""
    audio = recording.flatten().astype("float32") / 32768.0
    rms = float(_np.sqrt(_np.mean(audio ** 2)))
    return {
        "rms": rms,
        "rms_min": float(_np.min(_np.abs(audio))),
        "rms_avg": rms,
        "rms_max": float(_np.max(_np.abs(audio))),
        "peak": float(_np.max(_np.abs(audio))),
        "duration_s": len(audio) / 16000.0,
    }


def calibrate() -> dict:
    """Captura 3s de silencio y calcula el ruido base."""
    print(f"Configuracion cargada desde: {CONFIG_FILE}")
    if not _AUDIO_OK:
        print("[ERROR] sounddevice/numpy no disponibles.")
        return {"error": "audio_no_disponible"}

    try:
        default = _sd.query_devices(kind="input")
        mic_name = default.get("name", "desconocido")[:40]
    except Exception:
        mic_name = "desconocido"

    print(f"[Calibrando...] 3s de silencio | Microfono: {mic_name}")
    print("  Guarda silencio absoluto...")

    try:
        recording = _sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="int16")
        _sd.wait()
    except Exception as e:
        print(f"[ERROR] No se pudo grabar: {e}")
        return {"error": str(e)}

    audio = recording.flatten().astype("float32") / 32768.0
    rms = float(_np.sqrt(_np.mean(audio ** 2)))

    threshold = max(rms * 2.0, 0.00005)

    cfg_path = CONFIG_FILE
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg_data = yaml.safe_load(f) or {}
    else:
        cfg_data = {}
    cfg_data.setdefault("voice", {})["stt_noise_floor"] = round(rms, 8)
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg_data, f, allow_unicode=True, default_flow_style=False)

    verify_cfg = load_voice_config()
    verify_noise = verify_cfg.get("stt_noise_floor")
    verify_threshold = _get_threshold()
    print(f"  Configuracion persistida: ruido_base={verify_noise}, umbral={verify_threshold}")

    print(f"  Ruido base: {rms:.8f}")
    print(f"  Umbral de voz: {threshold:.8f} (formula: ruido_base * 2, min 0.00005)")
    print(f"  Guardado en: {cfg_path}")

    return {
        "noise_floor": round(rms, 8),
        "threshold": round(threshold, 8),
        "mic": mic_name,
    }


def diagnose() -> dict:
    """Muestra diagnostico del sistema de voz."""
    print(f"Configuracion cargada desde: {CONFIG_FILE}")
    info = {"microfonos": [], "config": {}}

    try:
        mics = _sd.query_devices()
        for i, dev in enumerate(mics):
            if dev.get("max_input_channels", 0) > 0:
                info["microfonos"].append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sr": dev.get("default_samplerate", 0),
                })
    except Exception:
        pass

    cfg = load_voice_config()
    info["config"] = {
        "stt_model": cfg.get("stt_model", "base"),
        "stt_language": cfg.get("stt_language", "es"),
        "stt_duration": cfg.get("stt_duration", 8),
        "stt_sample_rate": cfg.get("stt_sample_rate", 16000),
        "stt_compute_type": cfg.get("stt_compute_type", "int8"),
        "noise_floor": cfg.get("stt_noise_floor"),
        "threshold": _get_threshold(),
        "whisper_model_downloaded": False,
    }

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8",
                             download_root=None, local_files_only=True)
        info["config"]["whisper_model_downloaded"] = True
    except Exception:
        pass

    print("=== DIAGNOSTICO DE VOZ ===")
    print(f"Microfonos detectados: {len(info['microfonos'])}")
    for m in info["microfonos"][:5]:
        print(f"  [{m['index']}] {m['name'][:50]} (ch={m['channels']}, sr={m['sr']})")

    try:
        default = _sd.query_devices(kind="input")
        print(f"Dispositivo activo: {default['name']}")
    except Exception:
        print("Dispositivo activo: no detectado")

    cfg = info["config"]
    print(f"Modelo STT: {cfg['stt_model']} ({'descargado' if cfg['whisper_model_downloaded'] else 'pendiente'})")
    print(f"Idioma: {cfg['stt_language']}")
    print(f"Duracion captura: {cfg['stt_duration']}s")
    print(f"Sample rate: {cfg['stt_sample_rate']} Hz")
    print(f"Ruido base calibrado: {cfg['noise_floor'] or 'NO CALIBRADO'}")
    print(f"Umbral de voz: {cfg['threshold']:.6f}")
    print(f"Formula: max(ruido_base * 2, {cfg.get('stt_min_threshold', 0.00005)})")

    print("\n--- Prueba de captura corta ---")
    try:
        t0 = time.time()
        rec = _sd.rec(int(1 * 16000), samplerate=16000, channels=1, dtype="int16")
        _sd.wait()
        dur = time.time() - t0
        audio_f = rec.flatten().astype("float32") / 32768.0
        rms_test = float(_np.sqrt(_np.mean(audio_f ** 2)))
        print(f"  Duracion: {dur:.2f}s")
        print(f"  RMS: {rms_test:.8f}")
        print(f"  Por encima del umbral: {'SI' if rms_test > cfg['threshold'] else 'NO'}")
    except Exception as e:
        print(f"  Error: {e}")

    return info


def listen() -> Optional[str]:
    """
    Captura audio del microfono y transcribe con faster-whisper.

    Returns:
        Texto transcrito en espanol, o None si fallo.
    """
    cfg = load_voice_config()
    duration = cfg.get("stt_duration", 8)
    sample_rate = cfg.get("stt_sample_rate", 16000)
    model_name = cfg.get("stt_model", "base")
    compute_type = cfg.get("stt_compute_type", "int8")
    language = cfg.get("stt_language", "es")
    threshold = _get_threshold()

    start_time = time.time()

    if not _AUDIO_OK:
        print("[ERROR Voz] sounddevice/numpy no estan disponibles.")
        logger.log_error("stt", "sounddevice/numpy no instalados")
        return None

    try:
        mic_name = "desconocido"
        try:
            default = _sd.query_devices(kind="input")
            mic_name = default.get("name", "desconocido")[:40]
        except Exception:
            pass

        print(f"[Escuchando...] max {duration}s | Microfono: {mic_name}")
        print(f"  Sample rate: {sample_rate} Hz | Umbral: {threshold:.6f}")
        recording = _sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        _sd.wait()
        elapsed = time.time() - start_time

        stats = _audio_stats(recording)
        print(f"  RMS min={stats['rms_min']:.6f} avg={stats['rms_avg']:.6f} max={stats['rms_max']:.6f}")
        print(f"  Peak: {stats['peak']:.6f} | Duracion: {elapsed:.1f}s")
    except Exception as e:
        msg = f"Error al grabar audio: {e}"
        print(f"[ERROR Voz] {msg}")
        logger.log_error("stt", msg)
        return None

    logger.log_action(
        instruction="/voz",
        result=f"voice_captured duration_ms={int(elapsed*1000)} rms={stats['rms_avg']:.6f} threshold={threshold:.6f}",
    )

    # Intentar transcribir SIEMPRE que haya audio
    print("[Procesando...]")

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
    except FileNotFoundError:
        print(f"[ERROR Voz] El modelo '{model_name}' no esta descargado.")
        print(f"  Descargalo con: python -c \"from faster_whisper import WhisperModel; WhisperModel('{model_name}', device='cpu', compute_type='{compute_type}')\"")
        logger.log_error("stt", f"Modelo no descargado: {model_name}")
        return None
    except Exception as e:
        msg = f"No se pudo cargar faster-whisper: {e}"
        print(f"[ERROR Voz] {msg}")
        logger.log_error("stt", msg)
        return None

    try:
        audio_float = recording.flatten().astype("float32") / 32768.0
        segments, info = model.transcribe(
            audio_float,
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()

        if text:
            print(f"[Reconocido]: {text}")
            return text

        if stats["rms_avg"] < threshold:
            print(f"[Voz] No se detecto habla. RMS={stats['rms_avg']:.6f} < umbral={threshold:.6f}")
            print(f"  Ejecuta /voz calibrar para ajustar el umbral a tu ambiente.")
            logger.log_action(instruction="/voz", result="no_speech_detected")
            return None

        print("[Voz] No se detecto habla en el audio.")
        logger.log_action(instruction="/voz", result="no_speech_detected")
        return None

    except Exception as e:
        msg = f"Error en la transcripcion: {e}"
        print(f"[ERROR Voz] {msg}")
        logger.log_error("stt", msg)
        return None
