"""
Tests de integración básicos para JARVIS.
Verifican flujos completos del pipeline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

from jarvis_local.fast_response import fast_respond
from jarvis_local.jarvis import Jarvis
from jarvis_local.safety.policy import ActionStatus


def test_fast_response_hora():
    """Test de integración: usuario dice 'hora' → fast_response → respuesta con hora."""
    response = fast_respond("que hora es")
    assert response is not None
    assert "las" in response.lower() or ":" in response


def test_fast_response_saludo():
    """Test de integración: usuario dice 'hola' → fast_response → saludo."""
    response = fast_respond("hola")
    assert response is not None
    assert "buenos" in response.lower() or "buenas" in response.lower()


def test_parser_abrir_app():
    """Test de integración: usuario dice 'abre calculator' → parser → open_app."""
    from jarvis_local.intent.parser import parse_intent
    intent = parse_intent("abre calculator")
    assert intent.kind == "tool_execute"
    assert intent.tool == "open_app"


def test_parser_clima():
    """Test de integración: usuario dice 'clima en Bogotá' → parser → weather."""
    from jarvis_local.intent.parser import parse_intent
    intent = parse_intent("clima en Bogota")
    assert intent.kind == "tool_read"
    assert intent.tool == "weather"


def test_memory_flow():
    """Test de integración: memoria → add → list → found."""
    import tempfile
    from pathlib import Path
    from jarvis_local.storage.memory import MemoryStore

    with tempfile.TemporaryDirectory() as tmp_dir:
        store = MemoryStore(Path(tmp_dir))
        item = store.add("Soy alérgico a los mariscos")
        assert item is not None
        items = store.list()
        assert len(items) == 1
        assert "mariscos" in items[0]["text"]


def test_history_flow():
    """Test de integración: historial → append → load → persisted."""
    import tempfile
    from pathlib import Path
    from jarvis_local.storage.history import HistoryStore

    with tempfile.TemporaryDirectory() as tmp_dir:
        store = HistoryStore(Path(tmp_dir))
        store.append("user", "Hola JARVIS")
        store.append("assistant", "Hola señor")
        messages = store.load()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"


def test_jarvis_init_mock():
    """Test de integración: Jarvis se inicializa con mock."""
    with patch.object(Jarvis, '_ensure_model', return_value=None):
        jarvis = Jarvis()
        assert jarvis is not None
        assert jarvis.client is not None


if __name__ == "__main__":
    test_fast_response_hora()
    test_fast_response_saludo()
    test_parser_abrir_app()
    test_parser_clima()
    test_memory_flow()
    test_history_flow()
    test_jarvis_init_mock()
    print("OK: Todos los tests de integración pasaron.")
