"""Tests de escucha continua - Fase 8 (maquina de estados real)"""
import os
import sys
import threading
import time
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.voice.continuous import (
    ContinuousVoiceController,
    VoiceState,
    _merge_fragments,
    _normalize,
    extract_command_after_wake_word,
    find_wake_word,
)

# ============= Wake Word Detection Tests =============

def test_01_jarvis_responde():
    d, c = find_wake_word("Jarvis responde solamente prueba")
    assert d and c == "responde solamente prueba"

def test_02_y_arbis_responde():
    d, c = find_wake_word("y arbis responde solamente prueba")
    assert d and c == "responde solamente prueba"

def test_03_garbis_responde():
    d, c = find_wake_word("Garbis responde solamente prueba")
    assert d and c == "responde solamente prueba"

def test_04_extract_command():
    r = extract_command_after_wake_word("Jarvis abre Chrome")
    assert r == "abre Chrome"

def test_05_wake_word_no_command():
    d, c = find_wake_word("Jarvis")
    assert d and c == ""

def test_06_gerbis_only():
    d, c = find_wake_word("Gerbis")
    assert d and c == ""

def test_07_no_wake_word():
    d, c = find_wake_word("Buenos dias")
    assert not d

def test_08_case_insensitive():
    d, c = find_wake_word("JARVIS ABRE CHROME")
    assert d and c.lower() == "abre chrome"

def test_09_normalize_accents():
    n = _normalize("J\u00e1rvis resp\u00f3nde")
    assert n == "jarvis responde"

def test_10_inside_phrase_ignored():
    d, c = find_wake_word("quiero abrir jarvis en el navegador")
    assert not d

def test_11_mi_nombre_garbis_ignored():
    d, c = find_wake_word("mi nombre es garbis")
    assert not d

def test_12_extract_legacy_none():
    r = extract_command_after_wake_word("Buenos dias")
    assert r is None


# ============= Nuevas variantes STT (jarbees, etc.) =============

def test_12a_jarbees_only_with_dot():
    d, c = find_wake_word("Jarbees.")
    assert d and c == ""

def test_12b_jarbees_comma_command():
    d, c = find_wake_word("Jarbees, responde solamente prueba")
    assert d and c == "responde solamente prueba"

def test_12c_hola_jarbees_command():
    d, c = find_wake_word("hola Jarbees responde solamente prueba")
    assert d and c == "responde solamente prueba"

def test_12d_ey_comma_jarbees():
    d, c = find_wake_word("ey, Jarbees")
    assert d and c == ""

def test_12e_y_arbis_comma_responde():
    d, c = find_wake_word("y arbis, responde")
    assert d and c == "responde"

def test_12f_jarvis_responde():
    d, c = find_wake_word("Jarvis responde")
    assert d and c == "responde"

def test_12g_jarvisiano_false_positive():
    d, c = find_wake_word("jarvisiano responde")
    assert not d

def test_12h_garbison_false_positive():
    d, c = find_wake_word("garbison responde")
    assert not d

def test_12i_rejarvis_false_positive():
    d, c = find_wake_word("rejarvis responde")
    assert not d

def test_12j_miJarbeesX_false_positive():
    d, c = find_wake_word("miJarbeesX responde")
    assert not d

def test_12k_nombre_es_garbis_false_positive():
    d, c = find_wake_word("mi nombre es garbis")
    assert not d

def test_12l_charvis_detection():
    d, c = find_wake_word("charvis abre chrome")
    assert d and c == "abre chrome"

def test_12m_charbis_detection():
    d, c = find_wake_word("charbis abre chrome")
    assert d and c == "abre chrome"

def test_12n_jarbez_detection():
    d, c = find_wake_word("jarbez, hola")
    assert d and c == "hola"

def test_12o_jervis_detection():
    d, c = find_wake_word("jervis responde solo test")
    assert d and c == "responde solo test"


# ============= Fragment Merging Tests =============

def test_13_merge_no_overlap():
    result = _merge_fragments(["responde", "solamente modo"])
    assert result == "responde solamente modo"

def test_14_merge_with_overlap():
    result = _merge_fragments(["responde solamente", "modo continuo"])
    assert result == "responde solamente modo continuo"

def test_15_merge_duplicate_last_first():
    result = _merge_fragments(["responde", "responde solamente"])
    assert result == "responde solamente"

def test_16_merge_empty_parts():
    result = _merge_fragments(["", "  ", "responde"])
    assert result == "responde"

def test_17_merge_single():
    result = _merge_fragments(["responde solamente modo continuo"])
    assert result == "responde solamente modo continuo"

def test_18_merge_three_fragments():
    # Simula: Fragmento 1: "responde", Fragmento 2: "solamente modo", Fragmento 3: "continuo funcionando"
    result = _merge_fragments(["responde", "solamente modo", "continuo funcionando"])
    assert result == "responde solamente modo continuo funcionando"


# ============= State Machine Tests =============

def test_19_controller_start_stop():
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
    )
    assert not ctrl.is_running()
    assert ctrl.state == VoiceState.STOPPED
    ctrl.start()
    time.sleep(0.1)
    assert ctrl.is_running()
    assert ctrl.state != VoiceState.STOPPED
    ctrl.stop()
    time.sleep(0.1)
    assert not ctrl.is_running()
    assert ctrl.state == VoiceState.STOPPED


def test_20_thread_daemon():
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
    )
    ctrl.start()
    time.sleep(0.1)
    assert ctrl._thread.daemon
    ctrl.stop()


def test_21_no_duplicate_thread():
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
    )
    ctrl.start()
    time.sleep(0.05)
    first_thread = ctrl._thread
    ctrl.start()  # No debe crear segundo hilo
    assert ctrl._thread is first_thread
    ctrl.stop()


def test_22_chat_called_exactly_once():
    chat_fn = MagicMock(return_value="respuesta de prueba")
    tts_fn = MagicMock()
    call_count = [0]

    def smart_stt(d, show_stats=True):
        call_count[0] += 1
        if call_count[0] == 1:
            return "jarvis responde solamente modo continuo"
        return None  # Silencio para los demas

    ctrl = ContinuousVoiceController(
        stt_fn=smart_stt,
        chat_fn=chat_fn,
        tts_speak_fn=tts_fn,
    )
    ctrl._fragment_duration = 0.01  # acelerar para el test
    ctrl._command_timeout_s = 0.1
    ctrl._silence_to_end = 2
    ctrl.start()
    time.sleep(1.0)
    ctrl.stop()
    assert chat_fn.call_count == 1, f"chat llamado {chat_fn.call_count} veces, esperado 1"
    assert "responde solamente modo continuo" in str(chat_fn.call_args)


def test_23_no_chat_before_command_complete():
    chat_fn = MagicMock(return_value="respuesta")
    fragments_sent = [0]

    def multi_fragment_stt(d, show_stats=True):
        fragments_sent[0] += 1
        if fragments_sent[0] == 1:
            return "y arbis responde"
        elif fragments_sent[0] == 2:
            return "solamente modo"
        elif fragments_sent[0] == 3:
            return "continuo funcionando"
        else:
            return None

    ctrl = ContinuousVoiceController(
        stt_fn=multi_fragment_stt,
        chat_fn=chat_fn,
    )
    ctrl._fragment_duration = 0.01
    ctrl._command_timeout_s = 0.3
    ctrl._silence_to_end = 2
    ctrl.start()
    time.sleep(1.5)
    ctrl.stop()
    assert chat_fn.call_count == 1
    called_text = chat_fn.call_args[0][0].lower()
    assert "responde" in called_text
    assert "solamente" in called_text
    assert "modo" in called_text
    assert "continuo" in called_text


def test_24_stop_during_listening():
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
    )
    ctrl.start()
    time.sleep(0.3)
    ctrl.stop()
    time.sleep(0.1)
    assert not ctrl.is_running()
    assert ctrl.state == VoiceState.STOPPED


def test_25_stop_during_collecting():
    chat_fn = MagicMock(return_value="respuesta")

    def delayed_stt(d, show_stats=True):
        time.sleep(0.2)
        return None

    ctrl = ContinuousVoiceController(
        stt_fn=delayed_stt,
        chat_fn=chat_fn,
    )
    ctrl.start()
    # Simular que esta en COLLECTING
    ctrl._command_buffer = ["responde"]
    ctrl._command_start_time = time.time()
    ctrl._set_state(VoiceState.COLLECTING_COMMAND)
    time.sleep(0.1)
    ctrl.stop()
    time.sleep(0.1)
    assert not ctrl.is_running()


def test_26_state_transitions():
    chat_fn = MagicMock(return_value="OK")
    tts_fn = MagicMock()

    call_count = [0]

    def sequenced_stt(d, show_stats=True):
        call_count[0] += 1
        if call_count[0] == 1:
            return "jarvis modo continuo"
        return None

    ctrl = ContinuousVoiceController(
        stt_fn=sequenced_stt,
        chat_fn=chat_fn,
        tts_speak_fn=tts_fn,
    )
    ctrl._fragment_duration = 0.01
    ctrl._command_timeout_s = 0.3
    ctrl._silence_to_end = 2

    assert ctrl.state == VoiceState.STOPPED
    ctrl.start()
    time.sleep(0.05)
    assert ctrl.state == VoiceState.LISTENING_WAKE_WORD

    time.sleep(1.0)
    assert ctrl.state == VoiceState.LISTENING_WAKE_WORD
    assert chat_fn.call_count == 1
    ctrl.stop()


def test_27_buffer_cleared_after_processing():
    chat_fn = MagicMock(return_value="OK")
    call_n = [0]

    def two_rounds_stt(d, show_stats=True):
        call_n[0] += 1
        if call_n[0] == 1:
            return "jarvis comando uno"
        elif call_n[0] == 2 or call_n[0] == 3:
            return None
        elif call_n[0] == 4:
            return "jarvis comando dos"
        else:
            return None

    ctrl = ContinuousVoiceController(
        stt_fn=two_rounds_stt,
        chat_fn=chat_fn,
    )
    ctrl._fragment_duration = 0.01
    ctrl._command_timeout_s = 0.2
    ctrl._silence_to_end = 2
    ctrl.start()
    time.sleep(2.0)
    ctrl.stop()
    assert chat_fn.call_count >= 2
    assert len(ctrl._command_buffer) == 0


def test_28_tts_blocks_capture():
    # Simula TTS hablando: verifica que _pause_for_tts espera
    tts_speaking = MagicMock(return_value=True)
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
        tts_speaking_fn=tts_speaking,
    )
    t0 = time.time()
    ctrl._pause_for_tts()
    t1 = time.time()
    assert t1 - t0 >= 0.4

    # TTS no hablando: no espera
    tts_speaking.return_value = False
    t2 = time.time()
    ctrl._pause_for_tts()
    t3 = time.time()
    assert t3 - t2 < 0.3


def test_29_stt_error_does_not_kill_thread():
    def error_stt(d, show_stats=True):
        raise RuntimeError("STT simulado error")

    ctrl = ContinuousVoiceController(
        stt_fn=error_stt,
        chat_fn=lambda x: "",
    )
    ctrl._fragment_duration = 0.01
    # Patch _capture_fragment to handle errors gracefully en el loop
    ctrl.start()
    time.sleep(0.2)
    assert ctrl.is_running()
    ctrl.stop()


def test_30_process_transcription_single_shot():
    chat_fn = MagicMock(return_value="[Plan pendiente]")
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=chat_fn,
    )
    result = ctrl.process_transcription("Garbis abre Chrome")
    assert chat_fn.call_count == 1
    assert chat_fn.call_args[0][0].lower() == "abre chrome"


def test_31_process_transcription_wake_only():
    chat_fn = MagicMock()
    tts_fn = MagicMock()
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=chat_fn,
        tts_speak_fn=tts_fn,
    )
    result = ctrl.process_transcription("Jarvis")
    assert tts_fn.call_count == 1
    assert chat_fn.call_count == 0


def test_32_process_transcription_no_wake():
    chat_fn = MagicMock()
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=chat_fn,
    )
    result = ctrl.process_transcription("Buenos dias")
    assert result is None
    assert chat_fn.call_count == 0


def test_33_tts_pause_flag():
    tts_speaking = MagicMock(return_value=True)
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
        tts_speaking_fn=tts_speaking,
    )
    t0 = time.time()
    ctrl._pause_for_tts()
    t1 = time.time()
    assert t1 - t0 >= 0.4


def test_34_state_dict():
    ctrl = ContinuousVoiceController(
        stt_fn=lambda d, show_stats=True: None,
        chat_fn=lambda x: "",
    )
    st = ctrl.get_state()
    assert not st["active"]
    assert "state" in st
    assert "buffer" in st
    assert "last_command" in st


def test_35_wake_word_only_triggers_te_escucho():
    chat_fn = MagicMock()
    tts_fn = MagicMock()
    call_n = [0]

    def wake_only_stt(d, show_stats=True):
        call_n[0] += 1
        if call_n[0] == 1:
            return "jarvis"
        return None

    ctrl = ContinuousVoiceController(
        stt_fn=wake_only_stt,
        chat_fn=chat_fn,
        tts_speak_fn=tts_fn,
    )
    ctrl._fragment_duration = 0.01
    ctrl._command_timeout_s = 0.3
    ctrl._silence_to_end = 2
    ctrl.start()
    time.sleep(1.5)
    ctrl.stop()
    assert tts_fn.call_count >= 1
    calls_text = [c[0][0] for c in tts_fn.call_args_list]
    assert any("Te escucho" in t for t in calls_text)


def test_36_return_extra():
    """Verifica que capture_and_transcribe acepta return_extra."""
    from jarvis_local.voice.stt import capture_and_transcribe

    def fake_rec(d, samplerate, channels, dtype):
        import numpy as np
        return np.zeros((d,), dtype=dtype)

    def fake_wait():
        pass

    with patch("jarvis_local.voice.stt._sd", create=True) as mock_sd:
        mock_sd.rec = fake_rec
        mock_sd.wait = fake_wait
        mock_sd.query_devices = MagicMock(return_value={"name": "test"})
        mock_model = MagicMock()
        mock_model.transcribe = MagicMock(return_value=([], None))
        with patch("jarvis_local.voice.stt._get_whisper_model", return_value=mock_model):
            result = capture_and_transcribe(1, show_stats=False, return_extra=True)
            assert isinstance(result, dict)
            assert "text" in result
            assert "rms" in result
            assert "has_voice" in result


if __name__ == "__main__":
    test_01_jarvis_responde()
    test_02_y_arbis_responde()
    test_03_garbis_responde()
    test_04_extract_command()
    test_05_wake_word_no_command()
    test_06_gerbis_only()
    test_07_no_wake_word()
    test_08_case_insensitive()
    test_09_normalize_accents()
    test_10_inside_phrase_ignored()
    test_11_mi_nombre_garbis_ignored()
    test_12_extract_legacy_none()
    test_12a_jarbees_only_with_dot()
    test_12b_jarbees_comma_command()
    test_12c_hola_jarbees_command()
    test_12d_ey_comma_jarbees()
    test_12e_y_arbis_comma_responde()
    test_12f_jarvis_responde()
    test_12g_jarvisiano_false_positive()
    test_12h_garbison_false_positive()
    test_12i_rejarvis_false_positive()
    test_12j_miJarbeesX_false_positive()
    test_12k_nombre_es_garbis_false_positive()
    test_12l_charvis_detection()
    test_12m_charbis_detection()
    test_12n_jarbez_detection()
    test_12o_jervis_detection()
    test_13_merge_no_overlap()
    test_14_merge_with_overlap()
    test_15_merge_duplicate_last_first()
    test_16_merge_empty_parts()
    test_17_merge_single()
    test_18_merge_three_fragments()
    test_19_controller_start_stop()
    test_20_thread_daemon()
    test_21_no_duplicate_thread()
    test_22_chat_called_exactly_once()
    test_23_no_chat_before_command_complete()
    test_24_stop_during_listening()
    test_25_stop_during_collecting()
    test_26_state_transitions()
    test_27_buffer_cleared_after_processing()
    test_28_tts_blocks_capture()
    test_29_stt_error_does_not_kill_thread()
    test_30_process_transcription_single_shot()
    test_31_process_transcription_wake_only()
    test_32_process_transcription_no_wake()
    test_33_tts_pause_flag()
    test_34_state_dict()
    test_35_wake_word_only_triggers_te_escucho()
    test_36_return_extra()
    print("OK: Todos los tests de voz continua pasaron (51 pruebas).")
