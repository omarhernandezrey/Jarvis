"""PLAN_EJECUCION FASE D · D4 — fallback de modelo del router.

`ollama.router_fallback` estaba en config sin cablear. Si el modelo principal
del router falla TÉCNICAMENTE (no responde / no está descargado), se reintenta
la MISMA petición con el modelo de fallback. Sin Ollama: se simulan los fallos.
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.agent import loop as agent_loop
from jarvis_local.agent.loop import _llamar_modelo, run_agent

_TOOLS = [{"function": {"name": "clima", "description": "d", "parameters": {}}}]


class _NoResponde(Exception):
    """Simula timeout / conexión caída del modelo principal."""


class _NoDescargado(Exception):
    """Simula el 404 de Ollama: model '<x>' not found."""


@pytest.fixture
def _fb(monkeypatch):
    monkeypatch.setattr(agent_loop, "_router_fallback", lambda: "qwen2.5:3b")


def test_llamar_modelo_ok_no_usa_fallback():
    c = MagicMock()
    c.chat_with_tools = MagicMock(return_value={"content": "", "tool_calls": []})
    msg, uso_fb = _llamar_modelo(c, [], _TOOLS, structured=False)
    assert uso_fb is False
    c.chat_with_tools.assert_called_once()
    assert c.chat_with_tools.call_args.kwargs.get("model") is None


@pytest.mark.parametrize("exc", [_NoResponde("read timed out"),
                                 _NoDescargado("model 'llama3.2:3b' not found")])
def test_principal_falla_reintenta_con_el_fallback(_fb, exc):
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=[
        exc,  # principal (model=None)
        {"content": "", "tool_calls": [{"function": {"name": "clima", "arguments": {}}}]},
    ])
    msg, uso_fb = _llamar_modelo(c, [], _TOOLS, structured=False)
    assert uso_fb is True
    assert c.chat_with_tools.call_count == 2
    assert c.chat_with_tools.call_args_list[1].kwargs["model"] == "qwen2.5:3b"
    assert msg["tool_calls"][0]["function"]["name"] == "clima"


def test_sin_fallback_configurado_propaga_el_error(monkeypatch):
    monkeypatch.setattr(agent_loop, "_router_fallback", lambda: "")
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=_NoResponde("boom"))
    with pytest.raises(_NoResponde):
        _llamar_modelo(c, [], _TOOLS, structured=False)
    c.chat_with_tools.assert_called_once()


def test_fallback_tambien_falla_propaga_el_error_del_principal(_fb):
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=[
        _NoResponde("principal caído"),
        _NoDescargado("fallback tampoco está"),
    ])
    with pytest.raises(_NoResponde, match="principal"):
        _llamar_modelo(c, [], _TOOLS, structured=False)
    assert c.chat_with_tools.call_count == 2


def test_estructurado_tambien_cae_al_fallback(_fb):
    import json
    c = MagicMock()
    c.chat_structured = MagicMock(side_effect=[
        _NoDescargado("no está"),
        {"content": json.dumps({"accion": "usar_herramienta", "herramienta": "clima",
                                "argumentos": {}})},
    ])
    msg, uso_fb = _llamar_modelo(c, [], _TOOLS, structured=True)
    assert uso_fb is True
    assert c.chat_structured.call_args_list[1].kwargs["model"] == "qwen2.5:3b"
    assert msg["tool_calls"][0]["function"]["name"] == "clima"


def test_run_agent_sobrevive_con_fallback(_fb, monkeypatch):
    """De punta a punta: el principal no responde, el turno se resuelve por el
    fallback y la herramienta se ejecuta igual."""
    ejec = []
    monkeypatch.setattr(agent_loop, "execute",
                        lambda n, a: (ejec.append(n) or ("[ok]", False)))
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=[
        _NoResponde("read timed out"),
        {"content": "", "tool_calls": [{"function": {"name": "clima",
                                                     "arguments": {"city": "Cali"}}}]},
    ])
    r = run_agent(c, "que clima hace en Cali")
    assert ejec == ["clima"]
    assert r.tools_used == ["clima"]


def test_run_agent_sin_fallback_da_error_claro(monkeypatch):
    monkeypatch.setattr(agent_loop, "_router_fallback", lambda: "")
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=_NoResponde("boom"))
    r = run_agent(c, "que clima hace en Cali")
    assert r.tools_used == []
    assert "inconveniente" in r.text.lower() or "tardo demasiado" in r.text.lower()


if __name__ == "__main__":
    print("usa pytest")
