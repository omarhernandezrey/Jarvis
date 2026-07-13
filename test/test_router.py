"""
Tests del ROUTER DE INTENCION — el contrato de razonamiento de JARVIS.

Si estos fallan, el asistente esta interpretando mal al usuario, aunque todas
las herramientas funcionen. Cubren las causas raiz que se encontraron midiendo
la bateria de jarvis_local/eval/:

  1. Falsos positivos del parser (regex laxas que secuestraban frases).
  2. El porton lexico que dejaba al LLM sin ver la frase.
  3. Negacion, ambiguedad, multi-accion y fuera de alcance.

Los que necesitan el LLM o los embeddings se saltan solos si Ollama no esta.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.agent import retriever
from jarvis_local.agent.loop import _clean_text, _limpiar_args, _validar, run_agent
from jarvis_local.eval.cases import es_correcto
from jarvis_local.fast_response import fast_respond
from jarvis_local.intent.parser import es_multi_accion, parse_intent
from jarvis_local.storage.semantic import embeddings_available

sin_embeddings = not embeddings_available()
skip_sin_ollama = pytest.mark.skipif(sin_embeddings,
                                     reason="embeddings no disponibles")


# ---------------------------------------------------------------------------
# 1. El parser NO debe secuestrar frases que no le corresponden
# ---------------------------------------------------------------------------

def test_parser_no_confunde_llover_con_listar():
    """Regresion: 'ver?' sin \\b matcheaba la silaba de 'llo-VER-' y
    'va a llover en Medellin' se enrutaba a listar_archivos(path='Medellin')."""
    r = parse_intent("va a llover en Medellin?")
    assert r.tool != "list_files", "el parser sigue capturando 'llover' como 'ver'"


def test_parser_no_captura_busquedas_no_de_archivos():
    """Regresion: el sustantivo era opcional, asi que 'busca' a secas y
    'busca pega de disenador' caian en buscar_archivo."""
    for frase in ("busca", "estoy buscando pega de disenador",
                  "busca chamba de contador"):
        r = parse_intent(frase)
        assert r.tool != "search_files", f"'{frase}' no es una busqueda de archivos"


def test_parser_si_reconoce_busquedas_de_archivos_reales():
    """Endurecer la regex no debe romper los casos legitimos."""
    assert parse_intent("busca el archivo notas.txt en Documentos").tool == "search_files"
    assert parse_intent(r"busca tarea.pdf en C:\Users\herna\Documents").tool == "search_files"
    assert parse_intent("lista los archivos de Documentos").tool == "list_files"


def test_multi_accion_va_al_agente():
    """El parser resuelve UNA intencion: ante dos, ejecutaba la primera y
    descartaba la segunda en silencio. Ahora cede al agente, que encadena."""
    assert es_multi_accion("dime el clima de Cali y despues abre Chrome")
    assert es_multi_accion("busca trabajo de python y abre la primera oferta")
    assert not es_multi_accion("abre chrome")
    assert not es_multi_accion("busca trabajo de python en Bogota")

    r = parse_intent("dime el clima de Cali y despues abre Chrome")
    assert r.kind == "chat", "una peticion de dos acciones no debe resolverla el parser"


# ---------------------------------------------------------------------------
# 2. La cortesia no debe tragarse una peticion (regresion ya corregida)
# ---------------------------------------------------------------------------

def test_saludo_dentro_de_peticion_no_es_saludo():
    for frase in ("que tal anda mi maquina de recursos",
                  "buenas, abre chrome",
                  "gracias, ahora busca trabajo de disenador"):
        assert fast_respond(frase) is None, f"'{frase}' se respondio como saludo"


# ---------------------------------------------------------------------------
# 3. El retriever semantico debe ofrecerle SIEMPRE la herramienta correcta al LLM
# ---------------------------------------------------------------------------

@skip_sin_ollama
def test_retriever_entiende_lenguaje_coloquial():
    """La causa raiz #1: con palabras clave, estas frases devolvian CERO
    herramientas y el agente ni se invocaba."""
    casos = {
        "estoy buscando chamba de contador": "buscar_empleo",
        "estoy buscando pega de disenador": "buscar_empleo",
        "como anda la maquina?": "estado_del_sistema",
        "quien diablos fue Simon Bolivar": "wikipedia",
        "se me antoja escuchar algo de musica": "reproducir_musica_local",
        "apuntame que tengo que llamar al banco": "tomar_nota",
    }
    for frase, esperada in casos.items():
        ofrecidas = retriever.selected_names(frase)
        assert ofrecidas, f"'{frase}': no se le ofrecio NINGUNA herramienta al LLM"
        assert esperada in ofrecidas, (
            f"'{frase}': se esperaba {esperada} entre las ofrecidas, "
            f"llegaron {ofrecidas}")


@skip_sin_ollama
def test_retriever_descarta_la_charla():
    """Conversacion pura no debe gastar una llamada al LLM con herramientas."""
    for frase in ("de que color es el cielo", "gracias por todo"):
        assert retriever.selected_names(frase) == [], f"'{frase}' no es una peticion"


# ---------------------------------------------------------------------------
# 4. Validacion de la salida del modelo (sin Ollama: cliente simulado)
# ---------------------------------------------------------------------------

def test_validacion_rechaza_herramienta_inexistente():
    ok, correccion = _validar("herramienta_alucinada", {})
    assert not ok
    assert "no existe" in correccion.lower()
    assert "clima" in correccion  # le dice cuales SI existen


def test_validacion_rechaza_argumentos_faltantes():
    ok, correccion = _validar("wikipedia", {})  # topic es obligatorio
    assert not ok
    assert "topic" in correccion


def test_validacion_acepta_llamada_correcta():
    ok, _ = _validar("clima", {"city": "Cali"})
    assert ok


def test_argumentos_inventados_se_descartan():
    """El modelo a veces alucina parametros: no deben llegar a la herramienta."""
    limpios = _limpiar_args("clima", {"city": "Cali", "parametro_falso": 1})
    assert limpios == {"city": "Cali"}


def test_json_filtrado_no_llega_al_usuario():
    assert _clean_text('{"name": "clima", "arguments": {"city": "Cali"}}') == ""
    assert _clean_text("Como guste, senor.") == "Como guste, senor."


def _cliente(*respuestas):
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=list(respuestas))
    return c


def _llamada(nombre, args):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": nombre, "arguments": args}}]}


@skip_sin_ollama
def test_reintento_ante_herramienta_inventada():
    """No debe fallar en silencio: se le corrige al modelo y reintenta."""
    client = _cliente(
        _llamada("herramienta_que_no_existe", {}),
        _llamada("contar_chiste", {}),
    )
    r = run_agent(client, "cuentame un chiste")
    assert r.tools_used == ["contar_chiste"]
    assert client.chat_with_tools.call_count == 2  # corrigio y reintento


@skip_sin_ollama
def test_peticion_simple_usa_una_sola_llamada_al_llm():
    """Cada llamada extra al modelo cuesta ~15 s en CPU. Una peticion de una
    sola accion no debe pagar una segunda pasada solo para 'redactar'."""
    client = _cliente(_llamada("contar_chiste", {}))
    r = run_agent(client, "cuentame un chiste")
    assert r.tools_used == ["contar_chiste"]
    assert client.chat_with_tools.call_count == 1


@skip_sin_ollama
def test_reintento_ante_argumentos_faltantes():
    client = _cliente(
        _llamada("clima", {}),                    # sin city... pero city es opcional
        _llamada("wikipedia", {}),                # topic SI es obligatorio
        {"role": "assistant", "content": "Sobre quien, senor?"},
    )
    r = run_agent(client, "quien fue Simon Bolivar")
    assert r.text  # respondio algo, no exploto


@skip_sin_ollama
def test_orden_vaga_pide_aclaracion_no_adivina():
    """Regresion: 'hazlo' daba confianza baja, no se ofrecian herramientas y la
    frase caia en conversacion, donde JARVIS se quedaba mudo o divagaba.
    Una orden incompleta NO es charla: hay que preguntar."""
    for frase in ("hazlo", "abre eso", "necesito ayuda con algo"):
        r = run_agent(MagicMock(), frase)
        assert r.tools_used == [], f"'{frase}': adivino una accion"
        assert r.needs_clarification is True, f"'{frase}': no pidio aclaracion"
        assert r.text, f"'{frase}': se quedo mudo"


@skip_sin_ollama
def test_charla_no_se_confunde_con_orden_vaga():
    """La contraparte: conversacion real NO debe pedir aclaracion."""
    r = run_agent(MagicMock(), "de que color es el cielo")
    assert r.needs_clarification is False
    assert r.tools_used == []


@skip_sin_ollama
def test_accion_de_riesgo_no_se_ejecuta_sola():
    """El modelo NUNCA envia un correo por su cuenta: deja un plan pendiente."""
    client = _cliente(_llamada("enviar_correo",
                               {"to": "x@y.com", "subject": "A", "body": "B"}))
    r = run_agent(client, "manda un correo a x@y.com asunto A mensaje B")
    assert r.pending_confirmation is True
    assert "confirmar" in r.text.lower()


# ---------------------------------------------------------------------------
# 5. Comparador de la bateria
# ---------------------------------------------------------------------------

def test_comparador_de_casos():
    assert es_correcto("clima", ["clima"])
    assert not es_correcto("clima", ["listar_archivos"])
    assert es_correcto(None, [])                      # fuera de alcance: no actua
    assert not es_correcto(None, ["abrir_aplicacion"])  # alucino una accion
    assert es_correcto("CLARIFY", [], pidio_aclaracion=True)
    assert not es_correcto("CLARIFY", ["buscar_archivo"], pidio_aclaracion=False)
    assert es_correcto("a|b", ["b"])
    assert es_correcto("clima+abrir_aplicacion", ["clima", "abrir_aplicacion"])
    assert not es_correcto("clima+abrir_aplicacion", ["clima"])  # se quedo a medias


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
