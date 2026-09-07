"""PLAN_EJECUCION FASE D · D3 — salida estructurada (JSON Schema de Ollama).

Contrato del camino estructurado, sin Ollama: `_decidir_estructurado` traduce
el JSON del modelo al MISMO shape que `chat_with_tools` para que el resto del
bucle no cambie, y el rescate de tool-calls-como-texto deja de hacer falta.
"""
import json
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.agent import loop as agent_loop
from jarvis_local.agent.loop import _decidir_estructurado, _schema_decision, run_agent

_TOOLS = [
    {"function": {"name": "clima", "description": "d", "parameters": {}}},
    {"function": {"name": "contar_chiste", "description": "d", "parameters": {}}},
]


def _client(content: str):
    c = MagicMock()
    c.chat_structured = MagicMock(return_value={"role": "assistant", "content": content})
    return c


def test_schema_lista_las_herramientas_acotadas():
    s = _schema_decision(_TOOLS)
    assert s["properties"]["herramienta"]["enum"] == ["clima", "contar_chiste"]
    assert s["properties"]["accion"]["enum"] == ["usar_herramienta", "responder"]
    assert s["required"] == ["accion"]


def test_json_de_herramienta_se_vuelve_tool_call():
    c = _client(json.dumps({"accion": "usar_herramienta", "herramienta": "clima",
                            "argumentos": {"city": "Cali"}}))
    msg = _decidir_estructurado(c, [], _TOOLS)
    assert msg["tool_calls"] == [{"function": {"name": "clima",
                                               "arguments": {"city": "Cali"}}}]
    assert msg["content"] == ""


def test_json_de_respuesta_se_vuelve_texto():
    c = _client(json.dumps({"accion": "responder",
                            "respuesta": "No puedo hacer eso, senor."}))
    msg = _decidir_estructurado(c, [], _TOOLS)
    assert msg["tool_calls"] == []
    assert msg["content"] == "No puedo hacer eso, senor."


def test_contenido_no_json_se_trata_como_texto():
    c = _client("lo siento, no entiendo")
    msg = _decidir_estructurado(c, [], _TOOLS)
    assert msg["tool_calls"] == []
    assert msg["content"] == "lo siento, no entiendo"


def test_herramienta_fuera_de_la_lista_cae_a_texto():
    c = _client(json.dumps({"accion": "usar_herramienta",
                            "herramienta": "herramienta_inventada",
                            "argumentos": {}, "respuesta": "no tengo eso"}))
    msg = _decidir_estructurado(c, [], _TOOLS)
    assert msg["tool_calls"] == []
    assert msg["content"] == "no tengo eso"


def test_run_agent_estructurado_enruta_igual_que_tool_calling(monkeypatch):
    """De punta a punta con `structured=True`: el JSON del modelo llega a
    ejecutarse por el mismo camino, sin rescate."""
    ejecutadas = []
    monkeypatch.setattr(agent_loop, "execute",
                        lambda n, a: (ejecutadas.append((n, a)) or ("[ok]", False)))
    # el rescate NO debe usarse en modo estructurado
    monkeypatch.setattr(agent_loop, "_salvage_tool_calls",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("_salvage_tool_calls no debería llamarse")))

    c = MagicMock()
    c.chat_structured = MagicMock(return_value={
        "content": json.dumps({"accion": "usar_herramienta", "herramienta": "clima",
                               "argumentos": {"city": "Cali"}})})
    r = run_agent(c, "que clima hace en Cali", structured=True)
    assert ejecutadas and ejecutadas[0][0] == "clima"
    assert r.tools_used == ["clima"]
    c.chat_structured.assert_called_once()


def test_config_apagada_por_defecto():
    from jarvis_local.agent.loop import _salida_estructurada_activa
    assert _salida_estructurada_activa() is False


if __name__ == "__main__":
    print("usa pytest")
