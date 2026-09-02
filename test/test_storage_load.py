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

# Estos son guardas contra PATOLOGÍAS (una regresión O(n²): releer y reescribir
# todo el fichero en cada append), NO micro-benchmarks. El coste normal de 1000
# appends con lock+write es < 1 s; el margen es amplio a propósito para que no
# fallen de forma intermitente cuando la máquina de CI/desarrollo está cargada
# (se vio 5,01 s bajo carga con el techo antiguo de 5,0 s). Una regresión real
# supera estos límites por un orden de magnitud.
_HIST_MAX_S = 15.0
_MEM_MAX_S = 10.0


def test_history_performance():
    """1000 mensajes al historial no deben degradarse a un coste patológico."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = HistoryStore(Path(tmp_dir))
        start = time.time()
        for i in range(1000):
            store.append("user", f"Mensaje de prueba {i}")
        elapsed = time.time() - start
        assert elapsed < _HIST_MAX_S, f"1000 appends tardaron {elapsed:.1f}s"
        assert len(store.load()) <= 50  # MAX_MESSAGES


def test_memory_performance():
    """100 memorias no deben degradarse a un coste patológico."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = MemoryStore(Path(tmp_dir))
        start = time.time()
        for i in range(100):
            store.add(f"Memoria de prueba {i}")
        elapsed = time.time() - start
        assert elapsed < _MEM_MAX_S, f"100 add tardaron {elapsed:.1f}s"
        assert len(store.list()) == 100


if __name__ == "__main__":
    test_history_performance()
    test_memory_performance()
    print("OK: Todos los tests de carga pasaron.")
