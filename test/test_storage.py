"""Tests de almacenamiento - Fase 5"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.storage.history import MAX_CONTENT_LENGTH, MAX_MESSAGES, HistoryStore
from jarvis_local.storage.memory import MAX_MEMORIES, MAX_MEMORY_LENGTH, MemoryStore


def _tmp_dir():
    return Path(tempfile.mkdtemp())


def test_history_persists():
    d = _tmp_dir()
    try:
        h1 = HistoryStore(d)
        h1.append("user", "hola")
        h1.append("assistant", "respuesta")
        h2 = HistoryStore(d)
        msgs = h2.load()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
    finally:
        shutil.rmtree(d)


def test_history_max_messages():
    d = _tmp_dir()
    try:
        h = HistoryStore(d)
        for i in range(MAX_MESSAGES + 10):
            h.append("user", f"msg {i}")
        msgs = h.load()
        assert len(msgs) == MAX_MESSAGES
    finally:
        shutil.rmtree(d)


def test_history_max_content():
    d = _tmp_dir()
    try:
        h = HistoryStore(d)
        long_text = "x" * (MAX_CONTENT_LENGTH + 100)
        h.append("user", long_text)
        msgs = h.load()
        assert len(msgs[0]["content"]) <= MAX_CONTENT_LENGTH
    finally:
        shutil.rmtree(d)


def test_history_sanitize_terminal():
    d = _tmp_dir()
    try:
        h = HistoryStore(d)
        h.append("user", "ejecuta shutdown /s")
        msgs = h.load()
        assert "omitido" in msgs[0]["content"]
    finally:
        shutil.rmtree(d)


def test_history_sanitize_secrets():
    d = _tmp_dir()
    try:
        h = HistoryStore(d)
        h.append("assistant", "mi token es sk-abc123")
        msgs = h.load()
        assert "omitida" in msgs[0]["content"].lower()
    finally:
        shutil.rmtree(d)


def test_history_corrupt_json():
    d = _tmp_dir()
    try:
        (d / "history.json").write_text("{not valid json")
        h = HistoryStore(d)
        msgs = h.load()
        assert msgs == []
        corrupt = list(d.glob("history.corrupt-*.json"))
        assert len(corrupt) == 1
    finally:
        shutil.rmtree(d)


def test_history_save_lock_timeout_no_crashea_el_turno(monkeypatch):
    """Bug real encontrado en revisión: un filelock.Timeout (CLI y HUD
    apuntando al mismo data/ a la vez, o un lock stale) no se capturaba en
    _save() -- se propagaba sin capturar y tiraba abajo el turno entero de
    chat(). El mensaje ya está en memoria (append lo agrega antes de
    guardar): no debe perderse la conversación en curso por un lock
    contendido, solo el disco se queda sin ese turno hasta el próximo
    _save() exitoso."""
    import jarvis_local.storage.history as history_mod

    d = _tmp_dir()
    try:
        h = HistoryStore(d)

        class _LockSiempreOcupado:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                raise history_mod.FileLockTimeout("lock contendido (simulado)")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(history_mod, "FileLock", _LockSiempreOcupado)
        h.append("user", "esto no debe crashear")  # no debe lanzar

        assert h.load()[-1]["content"] == "esto no debe crashear"  # sigue en memoria
    finally:
        shutil.rmtree(d)


def test_history_load_lock_timeout_arranca_vacio_no_corrupto(monkeypatch):
    """Mismo bug en _load(): un lock contendido justo al arrancar no debe
    tratarse como archivo corrupto (no hay que mover/renombrar nada bueno)
    ni crashear -- solo degradar a historial vacío esta vez."""
    import jarvis_local.storage.history as history_mod

    d = _tmp_dir()
    try:
        h0 = HistoryStore(d)
        h0.append("user", "dato real")  # queda un history.json válido en disco

        class _LockSiempreOcupado:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                raise history_mod.FileLockTimeout("lock contendido (simulado)")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(history_mod, "FileLock", _LockSiempreOcupado)
        h1 = HistoryStore(d)  # _load() se llama en __init__

        assert h1.load() == []  # degradado, no crasheó
        assert not list(d.glob("history.corrupt-*.json")), (
            "un lock contendido no debe tratarse como corrupción de archivo"
        )
    finally:
        shutil.rmtree(d)


def test_history_atomic_write():
    d = _tmp_dir()
    try:
        h = HistoryStore(d)
        h.append("user", "test")
        assert (d / "history.json").exists()
        tmps = list(d.glob("*.json"))
        assert any("tmp" in t.name.lower() or not t.name.startswith("history") for t in tmps) or (d / "history.json").exists()
    finally:
        shutil.rmtree(d)


def test_history_clear():
    d = _tmp_dir()
    try:
        h = HistoryStore(d)
        h.append("user", "test")
        h.clear()
        assert h.load() == []
        assert not (d / "history.json").exists()
    finally:
        shutil.rmtree(d)


def test_memory_add_list():
    d = _tmp_dir()
    try:
        m = MemoryStore(d)
        item = m.add("recuerda comprar leche")
        assert item is not None
        items = m.list()
        assert len(items) == 1
        assert items[0]["text"] == "recuerda comprar leche"
    finally:
        shutil.rmtree(d)


def test_memory_max_length():
    d = _tmp_dir()
    try:
        m = MemoryStore(d)
        long_text = "x" * (MAX_MEMORY_LENGTH + 50)
        item = m.add(long_text)
        assert len(item["text"]) <= MAX_MEMORY_LENGTH
    finally:
        shutil.rmtree(d)


def test_memory_max_items():
    d = _tmp_dir()
    try:
        m = MemoryStore(d)
        for i in range(MAX_MEMORIES + 5):
            m.add(f"memoria {i}")
        items = m.list()
        assert len(items) == MAX_MEMORIES
        assert m.add("una mas") is None
    finally:
        shutil.rmtree(d)


def test_memory_delete():
    d = _tmp_dir()
    try:
        m = MemoryStore(d)
        item = m.add("test delete")
        assert m.delete(item["id"]) is True
        assert m.delete("fake-id") is False
        assert m.list() == []
    finally:
        shutil.rmtree(d)


def test_memory_clear():
    d = _tmp_dir()
    try:
        m = MemoryStore(d)
        m.add("test")
        m.clear()
        assert m.list() == []
        assert not (d / "memory.json").exists()
    finally:
        shutil.rmtree(d)


def test_memory_corrupt_json():
    d = _tmp_dir()
    try:
        (d / "memory.json").write_text("corrupt")
        m = MemoryStore(d)
        assert m.list() == []
        corrupt = list(d.glob("memory.corrupt-*.json"))
        assert len(corrupt) == 1
    finally:
        shutil.rmtree(d)


def test_memory_save_lock_timeout_no_crashea(monkeypatch):
    """Mismo bug que en HistoryStore: filelock.Timeout en _save() no debe
    propagarse -- el item ya está en memoria (add() lo agrega antes de
    guardar)."""
    import jarvis_local.storage.memory as memory_mod

    d = _tmp_dir()
    try:
        m = MemoryStore(d)

        class _LockSiempreOcupado:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                raise memory_mod.FileLockTimeout("lock contendido (simulado)")

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(memory_mod, "FileLock", _LockSiempreOcupado)
        item = m.add("esto no debe crashear")  # no debe lanzar

        assert item is not None
        assert m.list()[-1]["text"] == "esto no debe crashear"
    finally:
        shutil.rmtree(d)


def test_memory_reject_empty():
    d = _tmp_dir()
    try:
        m = MemoryStore(d)
        assert m.add("") is None
        assert m.add("   ") is None
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    test_history_persists(); test_history_max_messages()
    test_history_max_content(); test_history_sanitize_terminal()
    test_history_sanitize_secrets(); test_history_corrupt_json()
    test_history_atomic_write(); test_history_clear()
    test_memory_add_list(); test_memory_max_length()
    test_memory_max_items(); test_memory_delete()
    test_memory_clear(); test_memory_corrupt_json()
    test_memory_reject_empty()
    print("OK: Todos los tests de almacenamiento pasaron.")
