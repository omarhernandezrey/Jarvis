"""FASE C · C3 — Puerta de herramientas.

El mecanismo de selección top-K ya existía (`agent/retriever.py`, `TOP_K = 4`,
construido antes de esta fase): cuando SÍ hacen falta herramientas, el LLM ve
las 4 más relevantes del catálogo, no las 46 — evita el prefill de ~17,6 s con
esquemas completos. C3 verifica que sigue intacto y correctamente enganchado
al catálogo único de FASE B (`tools/catalog.py`), y lo blinda contra
regresiones: que nadie vuelva a mandar el catálogo entero al LLM, y que toda
herramienta nueva del catálogo traiga sus frases de ejemplo (si no, el
embedding de esa herramienta queda pobre y el retriever la recupera peor).
"""
from unittest.mock import MagicMock

import pytest

from jarvis_local.agent import retriever
from jarvis_local.agent.loop import run_agent
from jarvis_local.tools import catalog

try:
    sin_embeddings = not retriever._construir_indice()
except Exception:
    sin_embeddings = True
skip_sin_ollama = pytest.mark.skipif(sin_embeddings, reason="Ollama/bge-m3 no disponible")


def _llamada(nombre, args):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": nombre, "arguments": args}}]}


def _cliente(*respuestas):
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=list(respuestas))
    return c


# ---------- completitud: sin Ollama, chequeo estático ----------

def test_ejemplos_cubren_todo_el_catalogo():
    """Toda herramienta que el agente ofrece al LLM tiene frases de ejemplo
    para el embedding. Si falta una, su vector queda pobre (solo nombre +
    descripción formal) y el retriever la recupera peor que a las demás."""
    nombres_catalogo = {c.name for c in catalog.agent_contracts()}
    nombres_ejemplos = set(retriever._EJEMPLOS)
    faltan = nombres_catalogo - nombres_ejemplos
    assert not faltan, f"sin ejemplos (embedding pobre): {sorted(faltan)}"


def test_ejemplos_no_tiene_huerfanos():
    """Un ejemplo cuyo nombre ya no existe en el catálogo es basura muerta
    (o, peor, un nombre mal escrito que nunca se usó)."""
    nombres_catalogo = {c.name for c in catalog.agent_contracts()}
    nombres_ejemplos = set(retriever._EJEMPLOS)
    huerfanos = nombres_ejemplos - nombres_catalogo
    assert not huerfanos, f"ejemplos de herramientas que ya no existen: {sorted(huerfanos)}"


def test_todas_las_listas_de_ejemplos_no_vacias():
    vacias = [n for n, ejemplos in retriever._EJEMPLOS.items() if not ejemplos]
    assert not vacias, f"listas de ejemplos vacías: {vacias}"


# ---------- el índice deriva del catálogo único (FASE B) ----------

@skip_sin_ollama
def test_indice_del_retriever_deriva_del_catalogo_unico():
    retriever._construir_indice()
    nombres_indice = set(retriever._nombres)
    nombres_catalogo = {c.name for c in catalog.agent_contracts()}
    assert nombres_indice == nombres_catalogo


# ---------- el tope top-K se respeta de verdad ----------

@skip_sin_ollama
@pytest.mark.parametrize("frase", [
    "necesito saber si toca llevar sombrilla para salir en cali",
    "cuánto me da el quince por ciento de una cuenta de ochenta mil pesos",
    "a ver qué vacantes hay de electricista en bucaramanga",
    "cuéntame un chiste que esté bueno",
])
def test_select_tools_nunca_supera_top_k(frase):
    ofrecidas = retriever.select_tools(frase)
    assert 0 < len(ofrecidas) <= retriever.TOP_K, (
        f"'{frase}': {len(ofrecidas)} esquemas ofrecidos, "
        f"el límite es {retriever.TOP_K}")


@skip_sin_ollama
def test_run_agent_nunca_manda_mas_de_top_k_esquemas_al_llm():
    """Integración: la llamada real a chat_with_tools recibe como máximo
    TOP_K esquemas, no los 46 del catálogo."""
    client = _cliente(_llamada("contar_chiste", {}))
    run_agent(client, "cuéntame un chiste que esté bueno")
    assert client.chat_with_tools.call_count == 1
    _messages, tools_enviadas = client.chat_with_tools.call_args[0]
    assert 0 < len(tools_enviadas) <= retriever.TOP_K
    assert len(tools_enviadas) < len(catalog.agent_contracts())


@skip_sin_ollama
def test_run_agent_ofrece_la_herramienta_correcta_entre_las_top_k():
    client = _cliente(_llamada("contar_chiste", {}))
    run_agent(client, "cuéntame un chiste que esté bueno")
    _messages, tools_enviadas = client.chat_with_tools.call_args[0]
    nombres = {t["function"]["name"] for t in tools_enviadas}
    assert "contar_chiste" in nombres
