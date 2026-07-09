"""
Tests de voz - Fase 3 (corregido: usa archivo temp para threshold)
"""
import sys, os, yaml, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import jarvis_local.voice.stt as stt_mod


def _temp_config(noise=None, min_thresh=0.00005):
    """Crea un config.yaml temporal con valores voice especificos."""
    fd, tmp_path = tempfile.mkstemp(suffix=".yaml")
    cfg = {"voice": {"stt_noise_floor": noise, "stt_min_threshold": min_thresh,
                      "stt_model": "base", "stt_language": "es",
                      "stt_compute_type": "int8", "stt_duration": 8,
                      "stt_sample_rate": 16000}}
    with os.fdopen(fd, "w") as tmp:
        yaml.safe_dump(cfg, tmp)
    return tmp_path


def test_list_microphones_no_crash():
    from jarvis_local.voice.audio_devices import list_microphones
    result = list_microphones()
    assert isinstance(result, list)


def test_get_default_mic_returns_none_or_dict():
    from jarvis_local.voice.audio_devices import get_default_microphone
    result = get_default_microphone()
    assert result is None or isinstance(result, dict)


def test_listen_no_microphone():
    mock_sd = MagicMock()
    mock_sd.query_devices.side_effect = Exception("no mic")
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True
    with patch("builtins.print"), patch.object(stt_mod, "logger"):
        result = stt_mod.listen()
        assert result is None


def test_listen_model_not_downloaded():
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




def test_tts_list_voices():
    from jarvis_local.voice.tts import list_voices
    voices = list_voices()
    assert isinstance(voices, list)
    assert len(voices) > 0


def test_tts_select_valid_voice():
    from jarvis_local.voice.tts import select_voice, list_voices
    voices = list_voices()
    if voices:
        result = select_voice(0)
        assert result is True


def test_tts_select_invalid_voice():
    from jarvis_local.voice.tts import select_voice
    result = select_voice(999)
    assert result is False


def test_tts_set_rate_valid():
    from jarvis_local.voice.tts import set_rate
    assert set_rate(175) is True


def test_tts_set_rate_invalid():
    from jarvis_local.voice.tts import set_rate
    assert set_rate(100) is False
    assert set_rate(300) is False


def test_tts_set_volume_valid():
    from jarvis_local.voice.tts import set_volume
    assert set_volume(0.5) is True
    assert set_volume(1.0) is True
    assert set_volume(0.0) is True


def test_tts_set_volume_invalid():
    from jarvis_local.voice.tts import set_volume
    assert set_volume(-0.1) is False
    assert set_volume(1.1) is False


def test_tts_is_available():
    from jarvis_local.voice.tts import is_available
    result = is_available()
    assert isinstance(result, bool)


def test_tts_speak_does_not_crash():
    from jarvis_local.voice.tts import speak
    result = speak("")
    assert result is False


def test_tts_no_piper_import():
    import jarvis_local.voice.tts as tts_mod
    source = open(tts_mod.__file__, encoding="utf-8").read()
    assert "piper" not in source
    assert "piper_tts" not in source
    assert "gTTS" not in source



def test_config_has_voice_section():
    from jarvis_local.config import reload_config
    cfg = reload_config()
    voice = cfg.get("voice", {})
    assert voice["stt_model"] == "base"
    assert voice["tts_enabled"] is False
    assert "stt_noise_floor" in voice
    assert "stt_min_threshold" in voice


def test_voz_does_not_import_tools():
    source = open(stt_mod.__file__, encoding="utf-8").read()
    assert "tools.files" not in source
    assert "tools.apps" not in source
    assert "tools.terminal" not in source
    assert "safety.policy" not in source


def test_logs_dont_contain_transcription():
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
            assert "prueba confidencial" not in call_str


def test_low_audio_with_valid_transcription():
    audio_data = (np.ones(16000 * 2, dtype="int16") * 10)
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
    assert result == "texto valido detectado"


def test_low_audio_without_transcription():
    audio_data = (np.ones(16000 * 2, dtype="int16") * 2)
    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
    mock_sd.rec.return_value = audio_data.reshape(-1, 1)
    mock_sd.wait = MagicMock()
    stt_mod._sd = mock_sd
    stt_mod._np = np
    stt_mod._AUDIO_OK = True
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MagicMock())
    mock_fw = MagicMock()
    mock_fw.WhisperModel = MagicMock(return_value=mock_model)
    sys.modules["faster_whisper"] = mock_fw
    with patch("builtins.print"), patch.object(stt_mod, "logger"):
        result = stt_mod.listen()
    del sys.modules["faster_whisper"]
    assert result is None


def test_audio_stats_output():
    rec = (np.random.randn(16000 * 1) * 500).astype("int16")
    stt_mod._np = np
    stats = stt_mod._audio_stats(rec.reshape(-1, 1))
    assert "rms" in stats
    assert "rms_min" in stats
    assert "rms_max" in stats
    assert "peak" in stats
    assert stats["duration_s"] > 0


def test_system_prompt_obedience():
    from jarvis_local.jarvis import SYSTEM_PROMPT
    assert "OBEDIENCIA ESTRICTA" in SYSTEM_PROMPT
    assert "responde solamente" in SYSTEM_PROMPT.lower()
    assert "DEBES responder unicamente" in SYSTEM_PROMPT


# --- TESTS DE UMBRAL CON ARCHIVO TEMPORAL ---

def test_threshold_no_calibration():
    path = _temp_config(noise=None)
    try:
        stt_mod.CONFIG_FILE = Path(path)
        t = stt_mod._get_threshold()
        assert t == 0.00005, f"Sin calibracion debe ser 0.00005, fue {t}"
    finally:
        os.unlink(path)


def test_threshold_with_value():
    path = _temp_config(noise=0.0003)
    try:
        stt_mod.CONFIG_FILE = Path(path)
        t = stt_mod._get_threshold()
        expected = max(0.0003 * 2.0, 0.00005)
        assert t == expected, f"Esperado {expected}, fue {t}"
    finally:
        os.unlink(path)


def test_threshold_respects_min():
    path = _temp_config(noise=0.000001)
    try:
        stt_mod.CONFIG_FILE = Path(path)
        t = stt_mod._get_threshold()
        assert t == 0.00005, f"El min debe ser 0.00005, fue {t}"
    finally:
        os.unlink(path)


def test_real_noise_floor_015259():
    path = _temp_config(noise=0.00015259)
    try:
        stt_mod.CONFIG_FILE = Path(path)
        t = stt_mod._get_threshold()
        assert abs(t - 0.00030518) < 0.00000001, f"Esperado ~0.00030518, fue {t}"
    finally:
        os.unlink(path)


def test_calibrate_formula():
    for noise, expected in [(0.001, 0.002), (0.00001, 0.00005), (0.0, 0.00005)]:
        path = _temp_config(noise=noise)
        try:
            stt_mod.CONFIG_FILE = Path(path)
            t = stt_mod._get_threshold()
            assert t == expected, f"noise={noise} -> expected={expected}, got={t}"
        finally:
            os.unlink(path)


# --- PRUEBA DE INTEGRACION: calibrar + diagnostico comparten valor ---

def test_calibrate_diagnose_integration():
    """Simula calibracion en archivo temp, luego verifica que
    diagnose y _get_threshold leen el nuevo valor desde disco."""
    path = _temp_config(noise=None)
    try:
        stt_mod.CONFIG_FILE = Path(path)

        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {"name": "TestMic", "max_input_channels": 1}
        cal_data = (np.ones(3 * 16000, dtype="int16") * 150)
        mock_sd.rec.return_value = cal_data.reshape(-1, 1)
        mock_sd.wait = MagicMock()
        stt_mod._sd = mock_sd
        stt_mod._np = np
        stt_mod._AUDIO_OK = True

        with patch("builtins.print"):
            result = stt_mod.calibrate()

        expected_noise = result["noise_floor"]
        expected_threshold = result["threshold"]

        # Leer desde disco con load_voice_config()
        cfg = stt_mod.load_voice_config()
        disk_noise = cfg.get("stt_noise_floor")
        assert disk_noise is not None, "noise_floor no se guardo en disco"
        assert abs(disk_noise - expected_noise) < 0.00000001, \
            f"Disco {disk_noise} != calibrado {expected_noise}"

        # Verificar que _get_threshold lee desde disco
        t = stt_mod._get_threshold()
        assert abs(t - expected_threshold) < 0.000001, \
            f"_get_threshold {t} != esperado {expected_threshold}"

        # Verificar que diagnose lee desde disco
        with patch("builtins.print"):
            diag = stt_mod.diagnose()

        diag_noise = diag.get("config", {}).get("noise_floor")
        diag_thresh = diag.get("config", {}).get("threshold")
        assert diag_noise is not None
        assert abs(diag_thresh - expected_threshold) < 0.000001, \
            f"diagnose threshold {diag_thresh} != {expected_threshold}"
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_list_microphones_no_crash()
    test_get_default_mic_returns_none_or_dict()
    test_listen_no_microphone()
    test_listen_model_not_downloaded()
    test_tts_list_voices()
    test_tts_select_valid_voice()
    test_tts_select_invalid_voice()
    test_tts_set_rate_valid()
    test_tts_set_rate_invalid()
    test_tts_set_volume_valid()
    test_tts_set_volume_invalid()
    test_tts_is_available()
    test_tts_speak_does_not_crash()
    test_tts_no_piper_import()
    test_config_has_voice_section()
    test_voz_does_not_import_tools()
    test_logs_dont_contain_transcription()
    test_low_audio_with_valid_transcription()
    test_low_audio_without_transcription()
    test_audio_stats_output()
    test_system_prompt_obedience()
    test_threshold_no_calibration()
    test_threshold_with_value()
    test_threshold_respects_min()
    test_real_noise_floor_015259()
    test_calibrate_formula()
    test_calibrate_diagnose_integration()
    print("OK: Todos los tests de voz pasaron.")
