"""
Conftest para tests de JARVIS.
Configura el path una sola vez para todos los tests.
"""
import os
import sys

# Añadir el directorio raíz al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def _limpiar_cache_decisiones():
    """La cache de decisiones del agente (C6) es estado global de modulo: se
    vacia antes y despues de CADA test para que uno no herede la decision de
    otro (romperia asserts de call_count del cliente mock)."""
    try:
        from jarvis_local.agent import decision_cache
        decision_cache.clear()
        yield
        decision_cache.clear()
    except Exception:
        yield


@pytest.fixture
def jarvis_mock():
    """Fixture que proporciona Jarvis con cliente mockeado."""
    from unittest.mock import MagicMock

    from jarvis_local.jarvis import Jarvis
    j = Jarvis()
    mc = MagicMock()
    mc.is_running = MagicMock(return_value=True)
    mc.model_exists = MagicMock(return_value=True)
    mc.chat = MagicMock(return_value=iter([]))
    j.client = mc
    return j, mc
