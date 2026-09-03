"""Modelo del agente / chat configurable y verificable.

`llama3.2:3b` es el modelo único por defecto (routing + chat). El modelo se
puede cambiar sin editar `config.yaml` con `JARVIS_AGENT_MODEL` /
`JARVIS_CHAT_MODEL`, y `jarvis doctor` avisa si el modelo de routing no
soporta tool calling nativo.

Contexto histórico: `qwen2.5:3b` y `hermes3:3b` se evaluaron como router;
`hermes3:3b` quedó descartado (1/12 en la batería). Ver
`docs/AUDITORIA_2026-09.md` §7.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import jarvis_local.config as cfg_module
from jarvis_local import doctor


# ── Override por variable de entorno ──────────────────────────────────────
def test_env_override_agent_model(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_MODEL", "qwen2.5:3b")
    cfg = cfg_module.reload_config()
    assert cfg["ollama"]["agent_model"] == "qwen2.5:3b"
    # el modelo de chat no se toca
    assert cfg["ollama"]["model"] == "llama3.2:3b"


def test_env_override_chat_model(monkeypatch):
    monkeypatch.setenv("JARVIS_CHAT_MODEL", "qwen2.5:3b")
    cfg = cfg_module.reload_config()
    assert cfg["ollama"]["model"] == "qwen2.5:3b"


def test_env_override_ambos(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_MODEL", "modelo-a")
    monkeypatch.setenv("JARVIS_CHAT_MODEL", "modelo-b")
    cfg = cfg_module.reload_config()
    assert cfg["ollama"]["agent_model"] == "modelo-a"
    assert cfg["ollama"]["model"] == "modelo-b"


def test_sin_env_usa_config_yaml(monkeypatch):
    monkeypatch.delenv("JARVIS_AGENT_MODEL", raising=False)
    monkeypatch.delenv("JARVIS_CHAT_MODEL", raising=False)
    cfg = cfg_module.reload_config()
    # el modelo único por defecto: llama3.2:3b en routing y en chat
    assert cfg["ollama"]["agent_model"] == "llama3.2:3b"
    assert cfg["ollama"]["model"] == "llama3.2:3b"


def test_env_vacia_se_ignora(monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_MODEL", "   ")
    cfg = cfg_module.reload_config()
    assert cfg["ollama"]["agent_model"] == "llama3.2:3b"


def teardown_function(_):
    # que el cache no se lleve un override entre tests
    cfg_module.reload_config()


# ── doctor comprueba capacidad de tool calling ────────────────────────────
def _client_mock(models, caps):
    c = MagicMock()
    c.is_running.return_value = True
    c.list_models.return_value = [{"name": n} for n in models]
    c.get_model_info.return_value = {"capabilities": caps}
    return c


def test_doctor_router_sin_tools_es_falta():
    with patch("jarvis_local.ollama_client.client.OllamaClient") as C, \
         patch("jarvis_local.config.get_config",
               return_value={"ollama": {"host": "h", "model": "llama3.2:3b",
                                        "agent_model": "modelo-raro"}}):
        C.return_value = _client_mock(
            ["llama3.2:3b", "modelo-raro", "bge-m3"], ["completion"])
        lineas = doctor._check_ollama()
    faltas = [t for ok, t in lineas if not ok]
    assert any("Tool calling" in t and "modelo-raro" in t for t in faltas)


def test_doctor_router_con_tools_ok():
    with patch("jarvis_local.ollama_client.client.OllamaClient") as C, \
         patch("jarvis_local.config.get_config",
               return_value={"ollama": {"host": "h", "model": "llama3.2:3b",
                                        "agent_model": "llama3.2:3b"}}):
        C.return_value = _client_mock(
            ["llama3.2:3b", "bge-m3"], ["completion", "tools"])
        lineas = doctor._check_ollama()
    assert all(ok for ok, _ in lineas)
    assert not any("Tool calling" in t for _, t in lineas)


def test_doctor_capacidad_desconocida_no_rompe():
    """Si /api/show no devuelve `capabilities` como lista, no se inventa nada."""
    with patch("jarvis_local.ollama_client.client.OllamaClient") as C, \
         patch("jarvis_local.config.get_config",
               return_value={"ollama": {"host": "h", "model": "llama3.2:3b",
                                        "agent_model": "llama3.2:3b"}}):
        c = _client_mock(["llama3.2:3b", "bge-m3"], None)
        c.get_model_info.side_effect = RuntimeError("api vieja")
        C.return_value = c
        lineas = doctor._check_ollama()
    assert all(ok for ok, _ in lineas)
