"""
Tests de voz - Fase 3 (solo mocks, sin hardware real)
"""
import sys
import os
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_list_microphones_no_crash():
    from jarvis_local.voice.audio_devices import list_microphones
    result = list_microphones()
    assert isinstance(result, list)


def test_get_default_mic_returns_none_or_dict():
    from jarvis_local.voice.audio_devices import get_default_microphone
    result = get_default_microphone()
    assert result is None or isinstance(result, dict)


def test_listen_no_microphone():
    import sys
    import jarvis_local.voice.stt as stt_mod
    mock_sd = MagicMock()
    mock_sd.query_devices.side_effect = Exception("no mic")
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True
    with patch("builtins.print"), patch.object(stt_mod, "logger"):
        result = stt_mod.listen()
        assert result is None


def test_listen_model_not_downloaded():
    import sys
    import jarvis_local.voice.stt as stt_mod
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
    fake_rec = np.zeros(16000 * 2, dtype="int16")
    mock_sd.rec.return_value = fake_rec.reshape(-1, 1)
    mock_sd.wait = MagicMock()
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True

    mock_fw = MagicMock()
    mock_fw.WhisperModel = MagicMock(side_effect=FileNotFoundError("no model"))
    sys.modules["faster_whisper"] = mock_fw

    with patch("builtins.print"), patch.object(stt_mod, "logger"):
        result = stt_mod.listen()
        assert result is None

    del sys.modules["faster_whisper"]


def test_tts_voice_not_downloaded():
    import jarvis_local.voice.tts as tts_mod
    with patch("builtins.print"), patch.object(tts_mod, "_get_voice_path", return_value=None):
        tts_mod.piper_tts = MagicMock()
        result = tts_mod.speak("hola")
        assert result is False


def test_is_piper_available_no_model():
    with patch("jarvis_local.voice.tts._get_voice_path", return_value=None):
        from jarvis_local.voice.tts import is_piper_available
        assert is_piper_available() is False


def test_config_has_voice_section():
    from jarvis_local.config import reload_config
    cfg = reload_config()
    voice = cfg.get("voice", {})
    assert "stt_model" in voice
    assert voice["stt_model"] == "base"
    assert "tts_voice" in voice
    assert "tts_enabled" in voice
    assert voice["tts_enabled"] is False
    assert "stt_noise_floor" in voice
    assert "stt_min_threshold" in voice


def test_voz_does_not_import_tools():
    import jarvis_local.voice.stt as stt_mod
    source = open(stt_mod.__file__, encoding="utf-8").read()
    assert "tools.files" not in source
    assert "tools.apps" not in source
    assert "tools.terminal" not in source
    assert "safety.policy" not in source


def test_logs_dont_contain_transcription():
    import sys
    import jarvis_local.voice.stt as stt_mod
    mock_logger = MagicMock()
    stt_mod.logger = mock_logger
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
    fake_rec = (np.random.randn(16000 * 2) * 100).astype("int16")
    mock_sd.rec.return_value = fake_rec.reshape(-1, 1)
    mock_sd.wait = MagicMock()
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True

    mock_model = MagicMock()
    mock_seg = MagicMock()
    mock_seg.text = "texto de prueba confidencial"
    mock_model.transcribe.return_value = ([mock_seg], MagicMock())
    mock_fw = MagicMock()
    mock_fw.WhisperModel = MagicMock(return_value=mock_model)
    sys.modules["faster_whisper"] = mock_fw

    with patch("builtins.print"):
        result = stt_mod.listen()

    del sys.modules["faster_whisper"]

    if result:
        calls = [str(c) for c in mock_logger.log_action.call_args_list]
        for call_str in calls:
            assert "prueba confidencial" not in call_str, \
                f"Transcripcion en log: {call_str}"


# --- NUEVOS TESTS FASE 3 (correccion RMS) ---

def test_threshold_without_calibration():
    from jarvis_local.voice.stt import _get_threshold
    from jarvis_local.config import get_config
    cfg = get_config()
    cfg["voice"]["stt_noise_floor"] = None
    t = _get_threshold()
    assert t == 0.00005, f"Sin calibracion debe ser 0.00005, fue {t}"


def test_threshold_with_calibration():
    from jarvis_local.voice.stt import _get_threshold
    from jarvis_local.config import get_config
    cfg = get_config()
    cfg["voice"]["stt_noise_floor"] = 0.0003
    t = _get_threshold()
    expected = max(0.0003 * 2.0, 0.00005)
    assert t == expected, f"Esperado {expected}, fue {t}"


def test_threshold_respects_min():
    from jarvis_local.voice.stt import _get_threshold
    from jarvis_local.config import get_config
    cfg = get_config()
    cfg["voice"]["stt_noise_floor"] = 0.000001
    t = _get_threshold()
    assert t == 0.00005, f"El min debe ser 0.00005, fue {t}"


def test_real_noise_floor_015259():
    """Ruido base real del Conexant: 0.00015259 -> umbral 0.00030518"""
    from jarvis_local.voice.stt import _get_threshold
    from jarvis_local.config import get_config
    cfg = get_config()
    cfg["voice"]["stt_noise_floor"] = 0.00015259
    t = _get_threshold()
    assert abs(t - 0.00030518) < 0.00000001, f"Esperado ~0.00030518, fue {t}"


def test_low_audio_with_valid_transcription():
    """Audio bajo pero Whisper si devuelve texto -> debe retornarlo."""
    import sys
    import jarvis_local.voice.stt as stt_mod

    audio_data = (np.ones(16000 * 2, dtype="int16") * 10)  # RMS muy bajo
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
    mock_sd.rec.return_value = audio_data.reshape(-1, 1)
    mock_sd.wait = MagicMock()
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True

    mock_model = MagicMock()
    mock_seg = MagicMock()
    mock_seg.text = "texto valido detectado"
    mock_model.transcribe.return_value = ([mock_seg], MagicMock())
    mock_fw = MagicMock()
    mock_fw.WhisperModel = MagicMock(return_value=mock_model)
    sys.modules["faster_whisper"] = mock_fw

    with patch("builtins.print"), patch.object(stt_mod, "logger"):
        result = stt_mod.listen()

    del sys.modules["faster_whisper"]
    assert result == "texto valido detectado", \
        f"Audio bajo con transcripcion debe retornar texto, fue: {result}"


def test_low_audio_without_transcription():
    """Audio bajo SIN transcripcion -> debe retornar None."""
    import sys
    import jarvis_local.voice.stt as stt_mod

    audio_data = (np.ones(16000 * 2, dtype="int16") * 2)  # RMS extremadamente bajo
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
    mock_sd.rec.return_value = audio_data.reshape(-1, 1)
    mock_sd.wait = MagicMock()
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())  # Sin segmentos
    mock_fw = MagicMock()
    mock_fw.WhisperModel = MagicMock(return_value=mock_model)
    sys.modules["faster_whisper"] = mock_fw

    with patch("builtins.print"), patch.object(stt_mod, "logger"):
        result = stt_mod.listen()

    del sys.modules["faster_whisper"]
    assert result is None, \
        "Audio bajo sin transcripcion debe retornar None"


def test_calibrate_saves_noise_floor():
    import jarvis_local.voice.stt as stt_mod
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
    cal_data = (np.ones(3 * 16000, dtype="int16") * 5)
    mock_sd.rec.return_value = cal_data.reshape(-1, 1)
    mock_sd.wait = MagicMock()
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True

    with patch("builtins.print"):
        result = stt_mod.calibrate()

    assert result.get("noise_floor") is not None
    assert result.get("threshold") is not None
    assert result["threshold"] >= 0.00005

    from jarvis_local.config import reload_config
    cfg = reload_config()
    assert cfg["voice"]["stt_noise_floor"] is not None


def test_calibrate_formula():
    """Verifica que threshold = max(noise * 2, min_threshold)."""
    from jarvis_local.config import get_config
    from jarvis_local.voice.stt import _get_threshold
    cfg = get_config()
    for noise, expected in [(0.001, 0.002), (0.00001, 0.00005), (0.0, 0.00005)]:
        cfg["voice"]["stt_noise_floor"] = noise
        t = _get_threshold()
        assert t == expected, f"noise={noise} -> expected={expected}, got={t}"


def test_audio_stats_output():
    import jarvis_local.voice.stt as stt_mod
    rec = (np.random.randn(16000 * 1) * 500).astype("int16")
    stt_mod._np = np
    stats = stt_mod._audio_stats(rec.reshape(-1, 1))
    assert "rms" in stats
    assert "rms_min" in stats
    assert "rms_max" in stats
    assert "peak" in stats
    assert stats["duration_s"] > 0


def test_system_prompt_obedience():
    """El system prompt debe contener la regla de obediencia estricta."""
    from jarvis_local.jarvis import SYSTEM_PROMPT
    assert "OBEDIENCIA ESTRICTA" in SYSTEM_PROMPT
    assert "responde solamente" in SYSTEM_PROMPT.lower()
    assert "DEBES responder unicamente" in SYSTEM_PROMPT


if __name__ == "__main__":
    test_list_microphones_no_crash()
    test_get_default_mic_returns_none_or_dict()
    test_listen_no_microphone()
    test_listen_model_not_downloaded()
    test_tts_voice_not_downloaded()
    test_is_piper_available_no_model()
    test_config_has_voice_section()
    test_voz_does_not_import_tools()
    test_logs_dont_contain_transcription()
    test_threshold_without_calibration()
    test_threshold_with_calibration()
    test_threshold_respects_min()
    test_real_noise_floor_015259()
    test_low_audio_with_valid_transcription()
    test_low_audio_without_transcription()
    test_calibrate_saves_noise_floor()
    test_calibrate_formula()
    test_audio_stats_output()
    test_system_prompt_obedience()
    print("OK: Todos los tests de voz pasaron.")
