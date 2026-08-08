"""
Tests de carga para storage.
Verifican rendimiento con muchos datos.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.storage.history import HistoryStore
from jarvis_local.storage.memory import MemoryStore


def test_history_performance():
    """Verifica que el historial maneja 1000 mensajes rápidamente."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = HistoryStore(Path(tmp_dir))
        start = time.time()
        for i in range(1000):
            store.append("user", f"Mensaje de prueba {i}")
        elapsed = time.time() - start
        assert elapsed < 5.0  # Debe completar en menos de 5 segundos
        assert len(store.load()) <= 50  # MAX_MESSAGES


def test_memory_performance():
    """Verifica que la memoria maneja 100 memorias rápidamente."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = MemoryStore(Path(tmp_dir))
        start = time.time()
        for i in range(100):
            store.add(f"Memoria de prueba {i}")
        elapsed = time.time() - start
        assert elapsed < 2.0  # Debe completar en menos de 2 segundos
        assert len(store.list()) == 100


if __name__ == "__main__":
    test_history_performance()
    test_memory_performance()
    print("OK: Todos los tests de carga pasaron.")
