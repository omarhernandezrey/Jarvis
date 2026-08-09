"""
Tests para herramienta de WolframAlpha.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.wolfram import ask_wolfram, has_app_id


def test_has_app_id_no_config():
    """Verifica que has_app_id devuelve False si no hay config."""
    with patch("jarvis_local.tools.wolfram.get_secrets", return_value={}):
        assert has_app_id() is False


def test_has_app_id_with_placeholder():
    """Verifica que has_app_id devuelve False con placeholder."""
    with patch("jarvis_local.tools.wolfram.get_secrets", return_value={"wolframalpha": {"app_id": "TU-APPID"}}):
        assert has_app_id() is False


def test_has_app_id_with_valid():
    """Verifica que has_app_id devuelve True con App ID válido."""
    with patch("jarvis_local.tools.wolfram.get_secrets", return_value={"wolframalpha": {"app_id": "XXXXXX-XXXXXXXXXX"}}):
        assert has_app_id() is True


def test_ask_wolfram_no_app_id():
    """Verifica que ask_wolfram devuelve error si no hay App ID."""
    with patch("jarvis_local.tools.wolfram.has_app_id", return_value=False):
        plan = ask_wolfram("2+2")
        assert plan.status == ActionStatus.ERROR
        assert "no esta configurado" in plan.result.lower()


def test_ask_wolfram_success():
    """Verifica que ask_wolfram funciona con respuesta exitosa."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "4"
    with patch("jarvis_local.tools.wolfram.has_app_id", return_value=True), \
         patch("jarvis_local.tools.wolfram.get_secrets", return_value={"wolframalpha": {"app_id": "TEST"}}), \
         patch("requests.get", return_value=mock_response):
        plan = ask_wolfram("2+2")
        assert plan.status == ActionStatus.EXECUTED
        assert "4" in plan.result


def test_ask_wolfram_501():
    """Verifica que ask_wolfram maneja error 501."""
    mock_response = MagicMock()
    mock_response.status_code = 501
    with patch("jarvis_local.tools.wolfram.has_app_id", return_value=True), \
         patch("jarvis_local.tools.wolfram.get_secrets", return_value={"wolframalpha": {"app_id": "TEST"}}), \
         patch("requests.get", return_value=mock_response):
        plan = ask_wolfram("pregunta rara")
        assert plan.status == ActionStatus.ERROR
        assert "no entendio" in plan.result.lower()


if __name__ == "__main__":
    test_has_app_id_no_config()
    test_has_app_id_with_placeholder()
    test_has_app_id_with_valid()
    test_ask_wolfram_no_app_id()
    test_ask_wolfram_success()
    test_ask_wolfram_501()
    print("OK: Todos los tests de wolfram pasaron.")
