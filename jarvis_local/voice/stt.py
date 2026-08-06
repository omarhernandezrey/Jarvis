"""
JARVIS Local - Speech-to-Text con faster-whisper (Fase 3)
Graba del microfono, transcribe offline en espanol.
Con calibracion de ruido y diagnostico.
"""
import threading
import time

import yaml

from jarvis_local.config import CONFIG_FILE
from jarvis_local.safety.logger import logger


def load_voice_config() -> dict:
    """Lee config.yaml desde disco CADA VEZ. Sin cache."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return data.get("voice", {})


try:
    import numpy as _np
    import sounddevice as _sd
    _AUDIO_OK = True
except ImportError:
    _AUDIO_OK = False
    _sd = None
    _np = None

_whisper_model = None
_whisper_lock = threading.Lock()
_whisper_model_key = None


def _get_whisper_model(model_name: str, compute_type: str):
    """Singleton compartido de WhisperModel. Reutiliza entre fragmentos."""
    global _whisper_model, _whisper_model_key
    key = (model_name, compute_type)
    with _whisper_lock:
        if _whisper_model is None or _whisper_model_key != key:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                model_name, device="cpu", compute_type=compute_type,
            )
            _whisper_model_key = key
        return _whisper_model


def _get_threshold() -> float:
    cfg = load_voice_config()
    noise_floor = cfg.get("stt_noise_floor")
    min_threshold = cfg.get("stt_min_threshold", 0.00005)
    if noise_floor is not None and isinstance(noise_floor, (int, float)):
        return max(float(noise_floor) * 2.0, min_threshold)
    return min_threshold


def _get_vad_threshold() -> float:
    """Umbral para detectar VOZ activa (mas exigente que el de 'hubo audio').
    Con calibracion usa ruido_base * 2.5; sin calibrar, un piso conservador
    que casi cualquier voz supera pero el silencio absoluto no."""
    cfg = load_voice_config()
    noise_floor = cfg.get("stt_noise_floor")
    floor = cfg.get("stt_vad_min_threshold", 0.0008)
    if noise_floor is not None and isinstance(noise_floor, (int, float)):
        return max(float(noise_floor) * 2.5, floor)
    return floor


def _get_beam_size(default: int = 5) -> int:
    cfg = load_voice_config()
    try:
        return int(cfg.get("stt_beam_size", default))
    except (TypeError, ValueError):
        return default


def record_until_silence(
    max_seconds: float,
    sample_rate: int = 16000,
    silence_ms: int = 1200,
    start_timeout_s: float = 6.0,
    show_stats: bool = False,
):
    """Graba del microfono y CORTA SOLO cuando el usuario deja de hablar.

    En vez de grabar una duracion fija (y obligar a esperar en silencio o
    cortar frases largas), escucha por bloques de 100 ms:
      - si no arranca voz en start_timeout_s, devuelve lo grabado (poco);
      - cuando arranca voz, termina tras silence_ms de silencio sostenido
        o al llegar a max_seconds.

    Returns:
        (audio_float32, rms_total, hubo_voz) o (None, 0.0, False) si fallo.
    """
    if not _AUDIO_OK:
        return None, 0.0, False

    vad_threshold = _get_vad_threshold()
    block = int(sample_rate * 0.1)  # 100 ms
    blocks: list = []
    rms_history: list = []
    speech_started = False
    silent_ms = 0
    voiced_blocks = 0

    try:
        total_blocks = int(max_seconds * 10)
        for i in range(total_blocks):
            data = _sd.rec(block, samplerate=sample_rate, channels=1, dtype="int16")
            _sd.wait()
            blocks.append(data.copy())
            rms = float(_np.sqrt(_np.mean(
                (data.astype("float32") / 32768.0) ** 2)))
            rms_history.append(rms)

            # Umbral adaptativo: la calibracion guardada envejece (otro
            # microfono, ventilador encendido, ruido electrico). El piso
            # real ES el bloque mas silencioso reciente: hablar es subir
            # bastante por encima de ese piso.
            noise_floor_live = min(rms_history[-30:])
            effective = max(vad_threshold, noise_floor_live * 2.0)

            if rms > effective:
                voiced_blocks += 1
                silent_ms = 0
                # 2 bloques con voz seguidos = empezo a hablar de verdad
                if not speech_started and voiced_blocks >= 2:
                    speech_started = True
                    if show_stats:
                        print("[Voz] Grabando... (para de hablar para enviar)")
            else:
                voiced_blocks = 0
                silent_ms += 100

            if speech_started and silent_ms >= silence_ms:
                break
            if not speech_started and (i + 1) * 0.1 >= start_timeout_s:
                break
    except Exception as e:
        if show_stats:
            print(f"[Voz] ERROR captura: {e}")
        return None, 0.0, False

    if not blocks:
        return None, 0.0, False
    recording = _np.concatenate(blocks, axis=0)
    audio = recording.flatten().astype("float32") / 32768.0
    rms_total = float(_np.sqrt(_np.mean(audio ** 2)))
    return audio, rms_total, speech_started


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
        print("  Solucion: pip install sounddevice numpy")
        print("  En Linux tambien: sudo apt install libportaudio2")
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
        with open(cfg_path, encoding="utf-8") as f:
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
        "stt_model": cfg.get("stt_model", "small"),
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
        WhisperModel("small", device="cpu", compute_type="int8",
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


def listen() -> str | None:
    """
    Captura audio del microfono y transcribe con faster-whisper.

    La captura es dinamica: arranca cuando detecta voz y corta sola cuando
    el usuario deja de hablar (o al llegar al maximo). Ya no hay que esperar
    en silencio a que termine una grabacion de duracion fija.

    Returns:
        Texto transcrito en espanol, o None si fallo.
    """
    cfg = load_voice_config()
    duration = cfg.get("stt_duration", 8)
    max_duration = cfg.get("stt_max_duration", max(float(duration), 20.0))
    silence_ms = cfg.get("stt_silence_ms", 1200)
    start_timeout = cfg.get("stt_start_timeout_s", 6.0)
    sample_rate = cfg.get("stt_sample_rate", 16000)
    model_name = cfg.get("stt_model", "small")
    compute_type = cfg.get("stt_compute_type", "int8")
    language = cfg.get("stt_language", "es")
    threshold = _get_threshold()

    start_time = time.time()

    if not _AUDIO_OK:
        print("[ERROR Voz] sounddevice/numpy no estan disponibles.")
        print("  Solucion: pip install sounddevice numpy")
        print("  En Linux tambien: sudo apt install libportaudio2")
        print("  JARVIS funcionara en modo texto sin voz.")
        logger.log_error("stt", "sounddevice/numpy no instalados")
        return None

    mic_name = "desconocido"
    try:
        default = _sd.query_devices(kind="input")
        mic_name = default.get("name", "desconocido")[:40]
    except Exception:
        pass

    print(f"[Escuchando...] Habla ahora; corto solo cuando calles. "
          f"Max {max_duration:.0f}s | Mic: {mic_name}")
    audio_float, rms, had_voice = record_until_silence(
        max_seconds=float(max_duration), sample_rate=sample_rate,
        silence_ms=int(silence_ms), start_timeout_s=float(start_timeout),
        show_stats=True,
    )
    elapsed = time.time() - start_time
    if audio_float is None:
        msg = "Error al grabar audio"
        print(f"[ERROR Voz] {msg}")
        logger.log_error("stt", msg)
        return None

    print(f"  RMS: {rms:.6f} | Duracion: {elapsed:.1f}s")

    logger.log_action(
        instruction="/voz",
        result=f"voice_captured duration_ms={int(elapsed*1000)} rms={rms:.6f} threshold={threshold:.6f}",
    )

    # No cortamos aqui aunque el VAD no haya marcado voz: intentamos
    # transcribir SIEMPRE que haya audio capturado. El VAD decide cuando
    # CORTAR la grabacion, no si vale la pena mandarla a Whisper -- una voz
    # baja/susurrada puede no cruzar el umbral y aun asi ser transcribible.
    print("[Procesando...]")

    try:
        model = _get_whisper_model(model_name, compute_type)
    except Exception as e:
        msg = f"No se pudo cargar faster-whisper: {e}"
        print(f"[ERROR Voz] {msg}")
        print("  Si el modelo no esta descargado, ejecuta:")
        print(f"  python -c \"from faster_whisper import WhisperModel; WhisperModel('{model_name}', device='cpu', compute_type='{compute_type}')\"")
        logger.log_error("stt", msg)
        return None

    try:
        segments, info = model.transcribe(
            audio_float,
            language=language,
            beam_size=_get_beam_size(5),
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()

        if text:
            print(f"[Reconocido]: {text}")
            return text

        print("[Voz] No se detecto habla en el audio.")
        logger.log_action(instruction="/voz", result="no_speech_detected")
        return None

    except Exception as e:
        msg = f"Error en la transcripcion: {e}"
        print(f"[ERROR Voz] {msg}")
        logger.log_error("stt", msg)
        return None

def capture_and_transcribe(
    duration_seconds: float,
    show_stats: bool = True,
    return_extra: bool = False,
    dynamic: bool = False,
    beam_size: int | None = None,
    skip_silent: bool = False,
) -> str | dict | None:
    """Captura audio y transcribe. Reutilizada por /voz y modo continuo.

    Args:
        duration_seconds: Duracion de la captura (maximo, si dynamic=True).
        show_stats: Mostrar estadisticas en consola.
        return_extra: Si True, retorna dict con claves:
            text (str|None), rms (float), has_voice (bool).
        dynamic: Si True, la grabacion corta sola al detectar silencio
            sostenido en vez de durar exactamente duration_seconds.
        beam_size: beam de Whisper (1 = rapido, 5 = preciso). None usa config.
        skip_silent: Si True y el fragmento no supera el umbral de voz,
            NO invoca Whisper (ahorra CPU en la escucha continua: en una
            habitacion en silencio no se transcribe nada).

    Returns:
        str|None si return_extra=False.
        dict si return_extra=True.
    """
    cfg = load_voice_config()
    sample_rate = cfg.get("stt_sample_rate", 16000)
    model_name = cfg.get("stt_model", "small")
    compute_type = cfg.get("stt_compute_type", "int8")
    language = cfg.get("stt_language", "es")
    threshold = _get_threshold()
    vad_threshold = _get_vad_threshold()

    if not _AUDIO_OK:
        if show_stats:
            print("[Voz] sounddevice/numpy no disponibles.")
            print("  Solucion: pip install sounddevice numpy")
            print("  En Linux tambien: sudo apt install libportaudio2")
        if return_extra:
            return {"text": None, "rms": 0.0, "has_voice": False}
        return None

    try:
        if dynamic:
            silence_ms = int(cfg.get("stt_silence_ms", 1200))
            start_timeout = float(cfg.get("stt_start_timeout_s", 6.0))
            if show_stats:
                print(f"[Voz] Te escucho (corto solo cuando calles, "
                      f"max {duration_seconds:.0f}s)...")
            audio, rms, had_voice = record_until_silence(
                max_seconds=float(duration_seconds), sample_rate=sample_rate,
                silence_ms=silence_ms, start_timeout_s=start_timeout,
                show_stats=show_stats,
            )
            if audio is None:
                if return_extra:
                    return {"text": None, "rms": 0.0, "has_voice": False}
                return None
        else:
            if show_stats:
                print(f"[Voz] Escuchando {duration_seconds:.0f}s...")
            recording = _sd.rec(
                int(duration_seconds * sample_rate),
                samplerate=sample_rate, channels=1, dtype="int16",
            )
            _sd.wait()
            audio = recording.flatten().astype("float32") / 32768.0
            rms = float(_np.sqrt(_np.mean(audio ** 2)))
            had_voice = rms > vad_threshold

        if show_stats:
            print(f"[Voz] RMS: {rms:.6f}")

    except Exception as e:
        if show_stats:
            print(f"[Voz] ERROR captura: {e}")
        if return_extra:
            return {"text": None, "rms": 0.0, "has_voice": False}
        return None

    if skip_silent and not had_voice:
        # Sin energia de voz en el fragmento: no gastar CPU en Whisper.
        if return_extra:
            return {"text": None, "rms": rms, "has_voice": False}
        return None

    try:
        model = _get_whisper_model(model_name, compute_type)
        segments, _ = model.transcribe(
            audio, language=language,
            beam_size=beam_size if beam_size else _get_beam_size(5),
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        if show_stats:
            print(f"[Voz] Transcripcion: \"{text}\"" if text else "[Voz] Sin texto reconocido.")

        if return_extra:
            return {
                "text": text if text else None,
                "rms": rms,
                "has_voice": rms > threshold,
            }
        return text if text else None
    except Exception as e:
        if show_stats:
            print(f"[Voz] ERROR transcripcion: {type(e).__name__}: {e}")
        if return_extra:
            return {"text": None, "rms": rms, "has_voice": True}
        return None
