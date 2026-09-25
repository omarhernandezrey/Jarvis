"""
Tests de conexion a Ollama - Fase 1
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from jarvis_local.ollama_client.client import OllamaClient


def test_client_creation():
    client = OllamaClient()
    assert client.host == "http://localhost:11434"
    assert client.timeout == 600


def test_client_custom_params():
    client = OllamaClient(host="http://localhost:9999", timeout=30)
    assert client.host == "http://localhost:9999"
    assert client.timeout == 30


def test_is_running_success():
    """Verifica is_running devuelve True cuando el servidor responde correctamente."""
    from unittest.mock import MagicMock, patch

    client = OllamaClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch.object(client, "_get_client", return_value=mock_session):
        assert client.is_running() is True
        mock_session.get.assert_called_once()


def test_is_running_failure():
    """Verifica is_running devuelve False cuando hay error de conexion."""
    from unittest.mock import MagicMock, patch

    client = OllamaClient()
    mock_session = MagicMock()
    mock_session.get.side_effect = ConnectionError("Connection refused")

    with patch.object(client, "_get_client", return_value=mock_session):
        assert client.is_running() is False


def test_list_models_success():
    """Verifica list_models devuelve una lista de modelos."""
    from unittest.mock import MagicMock, patch

    client = OllamaClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3:8b", "size": 4500000000},
            {"name": "qwen2.5:3b", "size": 1800000000},
        ]
    }
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch.object(client, "_get_client", return_value=mock_session):
        result = client.list_models()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "llama3:8b"


def test_list_models_failure():
    """Verifica list_models lanza excepcion cuando el servidor falla."""
    from unittest.mock import MagicMock, patch

    client = OllamaClient()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.RequestException("Server error")
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    with patch.object(client, "_get_client", return_value=mock_session):
        import pytest
        with pytest.raises(requests.RequestException):
            client.list_models()


if __name__ == "__main__":
    test_client_creation()
    test_client_custom_params()
    test_is_running_success()
    test_is_running_failure()
    test_list_models_success()
    test_list_models_failure()
    print("OK: Tests de cliente Ollama completados.")


# ── TAREA C4: keep_alive + num_predict recortado para el agente ───────────────
def test_c4_payload_del_agente_tiene_keepalive_y_num_predict_bajo():
    from unittest.mock import MagicMock, patch

    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"role": "assistant", "content": "ok"}}

    def _fake_post(url, json=None, timeout=None, **kw):
        captured["url"] = url
        captured["payload"] = json
        return _Resp()

    c = OllamaClient()
    fake_http = MagicMock()
    fake_http.post.side_effect = _fake_post
    with patch.object(c, "_get_client", return_value=fake_http):
        c.chat_with_tools([{"role": "user", "content": "hola"}], tools=[])

    pl = captured["payload"]
    assert pl.get("keep_alive")                       # el modelo se queda en RAM
    assert pl["options"]["num_predict"] <= 80         # el router elige, no redacta



# ── TAREA C5: el paso de routing usa ollama.agent_model si esta configurado ───
def test_c5_chat_with_tools_usa_agent_model(monkeypatch):
    from unittest.mock import MagicMock, patch

    import jarvis_local.ollama_client.client as C

    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"role": "assistant", "content": "ok"}}

    c = OllamaClient()   # antes de tocar get_config (el constructor lo usa)
    monkeypatch.setattr(C, "get_config", lambda: {"ollama": {
        "model": "qwen2.5:3b", "agent_model": "llama3.2:3b"}})
    fake_http = MagicMock()
    fake_http.post.side_effect = lambda url, json=None, timeout=None, **kw: (
        captured.update(payload=json) or _Resp())
    with patch.object(c, "_get_client", return_value=fake_http):
        c.chat_with_tools([{"role": "user", "content": "x"}], tools=[])

    assert captured["payload"]["model"] == "llama3.2:3b"
