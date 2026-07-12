"""Tests de respuestas exactas - jarvis.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.jarvis import _exact_response, Jarvis
from unittest.mock import MagicMock, patch


def _mc(jarvis_obj):
    mc = MagicMock()
    mc.is_running = MagicMock(return_value=True)
    mc.model_exists = MagicMock(return_value=True)
    mc.chat = MagicMock(return_value=iter([]))
    jarvis_obj.client = mc
    return mc


def _make_jarvis():
    with patch.object(Jarvis, '_ensure_model', return_value=None):
        return Jarvis()


def test_responde_solamente():
    r = _exact_response("responde solamente voz funcionando correctamente")
    assert r == "voz funcionando correctamente"

def test_responde_solo():
    r = _exact_response("responde solo hola mundo")
    assert r == "hola mundo"

def test_di_solamente():
    r = _exact_response("di solamente prueba de texto")
    assert r == "prueba de texto"

def test_di_solo():
    r = _exact_response("di solo ok")
    assert r == "ok"

def test_dime_solamente():
    r = _exact_response("dime solamente hola")
    assert r == "hola"

def test_dime_solo():
    r = _exact_response("dime solo adios")
    assert r == "adios"

def test_contesta_solamente():
    r = _exact_response("contesta solamente si")
    assert r == "si"

def test_contesta_solo():
    r = _exact_response("contesta solo no")
    assert r == "no"

def test_case_insensitive():
    r = _exact_response("RESPONDE SOLAMENTE MAYUSCULAS")
    assert r == "MAYUSCULAS"

def test_with_greeting():
    r = _exact_response("Hola Jarvis, responde solamente voz funcionando correctamente")
    assert r == "voz funcionando correctamente"

def test_with_greeting_and_di():
    r = _exact_response("Jarvis, di solo prueba")
    assert r == "prueba"

def test_remove_double_quotes():
    r = _exact_response('di solo "Prueba 1, 2 y 3"')
    assert r == "Prueba 1, 2 y 3"

def test_remove_single_quotes():
    r = _exact_response("responde solo 'texto entre comillas'")
    assert r == "texto entre comillas"

def test_remove_curly_quotes():
    r = _exact_response("di solo \u201ctexto\u201d")
    assert r == "texto"

def test_remove_trailing_dot():
    r = _exact_response("responde solamente hola.")
    assert r == "hola"

def test_remove_trailing_exclamation():
    r = _exact_response("di solamente hola!")
    assert r == "hola"

def test_preserve_internal_punctuation():
    r = _exact_response("responde solo Prueba 1, 2 y 3.")
    assert r == "Prueba 1, 2 y 3"

def test_inverted_exclamation():
    r = _exact_response("dime solamente \u00a1Hola, Omar!")
    assert r == "\u00a1Hola, Omar"

def test_empty_content_returns_none():
    r = _exact_response("responde solamente")
    assert r is None

def test_empty_content_with_punctuation_returns_none():
    r = _exact_response("responde solamente.")
    assert r is None

def test_non_matching_returns_none():
    r = _exact_response("Hola Jarvis, como estas?")
    assert r is None

def test_normal_message_not_matched():
    r = _exact_response("que hora es")
    assert r is None

def test_partial_match_no_content():
    r = _exact_response("responde solament")
    assert r is None

def test_preserve_article_el():
    r = _exact_response("Jarvis, responde solamente el sistema de voz listo.")
    assert r == "el sistema de voz listo"

def test_preserve_article_la():
    r = _exact_response("responde solamente la prueba final.")
    assert r == "la prueba final"

def test_preserve_article_un():
    r = _exact_response("di solo un mensaje.")
    assert r == "un mensaje"

def test_preserve_inverted_exclamation_and_comma():
    r = _exact_response("dime solamente \u00a1Hola, Omar!")
    assert r == "\u00a1Hola, Omar"

def test_preserve_internal_commas():
    r = _exact_response("responde solo uno, dos y tres.")
    assert r == "uno, dos y tres"

# --- Tests de integracion con Jarvis.chat() ---

def test_chat_uses_exact_response():
    j = _make_jarvis()
    mc = _mc(j)
    r = j.chat("di solo ok")
    assert r == "ok"
    assert mc.chat.call_count == 0

def test_chat_saves_exact_to_history():
    j = _make_jarvis()
    _mc(j)
    j.history.clear()
    j.chat("responde solamente exacto")
    msgs = j.history.get_messages()
    assert msgs[0]["role"] == "user"
    assert "responde solamente exacto" in msgs[0]["content"]
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "exacto"

def test_chat_normal_uses_ollama():
    # Usar un mensaje que no sea interceptado por fast_respond ni intent parser
    j = _make_jarvis()
    mc = _mc(j)
    mc.chat.return_value = iter(["Respuesta del modelo"])
    r = j.chat("explica el algoritmo de quicksort en detalle")
    assert r == "Respuesta del modelo"
    assert mc.chat.call_count == 1

def test_chat_intercept_no_comma():
    j = _make_jarvis()
    mc = _mc(j)
    r = j.chat("Jarvis responde solamente el sistema de voz listo.")
    assert r == "el sistema de voz listo"
    assert mc.chat.call_count == 0

def test_chat_intercept_hola_jarvis():
    j = _make_jarvis()
    mc = _mc(j)
    r = j.chat("Hola Jarvis, responde solamente el sistema de voz listo.")
    assert r == "el sistema de voz listo"
    assert mc.chat.call_count == 0

def test_chat_intercept_lowercase_greeting():
    j = _make_jarvis()
    mc = _mc(j)
    r = j.chat("hola, jarvis responde solo el sistema de voz listo")
    assert r == "el sistema de voz listo"
    assert mc.chat.call_count == 0

def test_chat_intercept_multiple_spaces():
    j = _make_jarvis()
    mc = _mc(j)
    r = j.chat("  Jarvis,    responde   solamente   el sistema de voz listo.  ")
    assert r == "el sistema de voz listo"
    assert mc.chat.call_count == 0

def test_chat_not_matched_uses_ollama():
    j = _make_jarvis()
    mc = _mc(j)
    mc.chat.return_value = iter(["Si"])
    r = j.chat("llueve hoy?")
    assert r == "Si"
    assert mc.chat.call_count == 1


if __name__ == "__main__":
    test_responde_solamente(); test_responde_solo(); test_di_solamente(); test_di_solo()
    test_dime_solamente(); test_dime_solo(); test_contesta_solamente(); test_contesta_solo()
    test_case_insensitive(); test_with_greeting(); test_with_greeting_and_di()
    test_remove_double_quotes(); test_remove_single_quotes(); test_remove_curly_quotes()
    test_remove_trailing_dot(); test_remove_trailing_exclamation()
    test_preserve_internal_punctuation(); test_inverted_exclamation()
    test_empty_content_returns_none(); test_empty_content_with_punctuation_returns_none()
    test_non_matching_returns_none(); test_normal_message_not_matched()
    test_partial_match_no_content()
    test_preserve_article_el(); test_preserve_article_la(); test_preserve_article_un()
    test_preserve_inverted_exclamation_and_comma(); test_preserve_internal_commas()
    test_chat_uses_exact_response(); test_chat_saves_exact_to_history()
    test_chat_normal_uses_ollama()
    test_chat_intercept_no_comma(); test_chat_intercept_hola_jarvis()
    test_chat_intercept_lowercase_greeting(); test_chat_intercept_multiple_spaces()
    test_chat_not_matched_uses_ollama()
    print("OK: Todos los tests de jarvis pasaron.")
