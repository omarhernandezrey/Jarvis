"""Tests de contexto de memorias - Fase 6"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unittest.mock import MagicMock

from jarvis_local.memory_context.session import MAX_ACTIVE, MAX_COMBINED_CHARS, SessionMemoryContext


def test_activate():
    ctx = SessionMemoryContext()
    ok, msg = ctx.activate({"id": "1", "text": "nombre: Omar"})
    assert ok
    assert len(ctx.list_active()) == 1


def test_max_5():
    ctx = SessionMemoryContext()
    for i in range(7):
        ctx.activate({"id": str(i), "text": f"m{i}"})
    assert len(ctx.list_active()) == MAX_ACTIVE


def test_max_chars():
    ctx = SessionMemoryContext()
    big = "x" * (MAX_COMBINED_CHARS + 10)
    ok, msg = ctx.activate({"id": "1", "text": big})
    assert not ok


def test_no_duplicate():
    ctx = SessionMemoryContext()
    ctx.activate({"id": "1", "text": "test"})
    ok, _ = ctx.activate({"id": "1", "text": "test"})
    assert not ok


def test_deactivate():
    ctx = SessionMemoryContext()
    ctx.activate({"id": "1", "text": "test"})
    assert ctx.deactivate("1")
    assert len(ctx.list_active()) == 0


def test_deactivate_nonexistent():
    ctx = SessionMemoryContext()
    assert not ctx.deactivate("fake")


def test_clear():
    ctx = SessionMemoryContext()
    ctx.activate({"id": "1", "text": "a"})
    ctx.activate({"id": "2", "text": "b"})
    ctx.clear()
    assert len(ctx.list_active()) == 0


def test_build_context():
    ctx = SessionMemoryContext()
    ctx.activate({"id": "1", "text": "nombre: Omar"})
    context = ctx.build_context()
    assert "MEMORIAS EXPLICITAS" in context
    assert "nombre: Omar" in context
    assert "FIN MEMORIAS" in context


def test_empty_context():
    ctx = SessionMemoryContext()
    assert ctx.build_context() == ""


def test_reject_secrets():
    ctx = SessionMemoryContext()
    ok, msg = ctx.activate({"id": "1", "text": "mi token es sk-abc123def456ghijklmn"})
    assert not ok
    assert "sensible" in msg.lower()


def test_new_instance_no_memories():
    ctx = SessionMemoryContext()
    assert ctx.list_active() == []


def test_context_not_in_chat_for_tools():
    """El contexto solo debe aparecer en chat, no en tool_read/tool_plan."""
    from unittest.mock import patch

    from jarvis_local.jarvis import Jarvis, _mc_test, _parse_and_execute
    j, mc = _mc_test()
    j.history.clear()
    j.memory_context.activate({"id": "1", "text": "usuario se llama Omar"})

    # Para "abre Chrome" (tool_execute), el contexto NO debe usarse
    # _parse_and_execute ejecuta la herramienta y no pasa por Ollama
    r = _parse_and_execute("abre Chrome", j)
    assert r is not None
    assert "abierto" in r.lower() or "chrome" in r.lower()
    # Verificar que Ollama NO fue llamado (contexto irrelevante para tools)
    assert mc.chat.call_count == 0

    # Para chat normal, Ollama SI se llama con contexto
    mc.chat.reset_mock()
    mc.chat.return_value = iter(["Hola Omar"])
    r2 = j.chat("como me llamo?")
    assert mc.chat.call_count == 1
    # El system prompt debe contener el contexto
    call_args = mc.chat.call_args[0][0]
    system_content = call_args[0]["content"]
    assert "MEMORIAS EXPLICITAS" in system_content
    assert "usuario se llama Omar" in system_content

    # El historial persistido NO debe contener el bloque de contexto
    history_msgs = j.store.load()
    for msg in history_msgs:
        assert "MEMORIAS EXPLICITAS" not in msg.get("content", "")


if __name__ == "__main__":
    test_activate(); test_max_5(); test_max_chars(); test_no_duplicate()
    test_deactivate(); test_deactivate_nonexistent(); test_clear()
    test_build_context(); test_empty_context(); test_reject_secrets()
    test_new_instance_no_memories()
    test_context_not_in_chat_for_tools()
    print("OK: Todos los tests de contexto de memoria pasaron.")
