"""
Tests para herramienta de navegador automatizado.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.browser import BrowserManager, browser_available, close_browser, navigate


def test_browser_available():
    """Verifica que browser_available funciona."""
    result = browser_available()
    assert isinstance(result, bool)


def test_navigate_without_selenium():
    """Verifica que navigate devuelve error si Selenium no está instalado."""
    with patch("jarvis_local.tools.browser.browser_available", return_value=False):
        plan = navigate("https://example.com")
        assert plan.status == ActionStatus.ERROR
        assert "Selenium" in plan.result


def test_navigate_with_mock():
    """Verifica que navigate funciona con driver mockeado."""
    mock_driver = MagicMock()
    with patch("jarvis_local.tools.browser.browser_available", return_value=True), \
         patch.object(BrowserManager, 'get_driver', return_value=mock_driver):
        plan = navigate("https://example.com")
        assert plan.status == ActionStatus.EXECUTED
        mock_driver.get.assert_called_once_with("https://example.com")


def test_navigate_adds_https():
    """Verifica que navigate añade https:// si no tiene esquema."""
    mock_driver = MagicMock()
    with patch("jarvis_local.tools.browser.browser_available", return_value=True), \
         patch.object(BrowserManager, 'get_driver', return_value=mock_driver):
        plan = navigate("example.com")
        assert plan.status == ActionStatus.EXECUTED
        mock_driver.get.assert_called_once_with("https://example.com")


def test_close_browser():
    """Verifica que close_browser funciona."""
    mock_driver = MagicMock()
    with patch.object(BrowserManager, '_driver', mock_driver), \
         patch.object(BrowserManager, 'close'):
        plan = close_browser()
        assert plan.status == ActionStatus.EXECUTED


if __name__ == "__main__":
    test_browser_available()
    test_navigate_without_selenium()
    test_navigate_with_mock()
    test_navigate_adds_https()
    test_close_browser()
    print("OK: Todos los tests de browser pasaron.")
