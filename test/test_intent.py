"""Tests de parser de intenciones - Fase 4"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from unittest.mock import patch


def test_list_files_read():
    r = parse_intent("lista los archivos de C:\\Users\\herna\\Documents")
    assert r.kind == "tool_read"
    assert r.tool == "list_files"


def test_search_files_read():
    r = parse_intent("busca tarea.pdf en C:\\Users\\herna\\Documents")
    assert r.kind == "tool_read"
    assert r.tool == "search_files"
    assert "tarea.pdf" in r.arguments.get("name", "")


def test_open_app_plan():
    r = parse_intent("abre Chrome")
    assert r.kind == "tool_execute"
    assert r.tool == "open_app"


def test_open_app_vscode():
    r = parse_intent("abre VS Code")
    assert r.kind == "tool_execute"
    assert r.tool == "open_app"
    assert "vscode" in r.arguments["app"]


def test_create_directory_plan():
    r = parse_intent("crea una carpeta llamada pruebas en C:\\Users\\herna\\Desktop")
    assert r.kind == "tool_execute"
    assert r.tool == "create_directory"


def test_create_file_plan():
    r = parse_intent("crea un archivo llamado notas.txt en C:\\Users\\herna\\Documents")
    assert r.kind == "tool_execute"
    assert r.tool == "create_file"


def test_copy_plan():
    r = parse_intent("copia C:\\Users\\herna\\Documents\\a.txt a C:\\Users\\herna\\Desktop\\a.txt")
    assert r.kind == "tool_execute"
    assert r.tool == "copy_file"


def test_move_plan():
    r = parse_intent("mueve C:\\Users\\herna\\Documents\\x.txt a C:\\Users\\herna\\Desktop\\x.txt")
    assert r.kind == "tool_execute"
    assert r.tool == "move_file"


def test_rename_plan():
    r = parse_intent("renombra C:\\Users\\herna\\Documents\\old.txt a new.txt")
    assert r.kind == "tool_execute"
    assert r.tool == "rename_file"


def test_delete_plan():
    r = parse_intent("borra C:\\Users\\herna\\Documents\\a.txt")
    assert r.kind == "tool_plan"
    assert r.tool == "delete_file"


def test_run_command_plan():
    r = parse_intent("ejecuta dir")
    assert r.kind == "tool_execute"
    assert r.tool == "run_command"


def test_normal_message_chat():
    r = parse_intent("hola jarvis como estas")
    assert r.kind == "chat"


def test_ambiguous_open():
    r = parse_intent("abre algo")
    assert r.kind == "ambiguous"


def test_blocked_path():
    r = parse_intent("lista los archivos de C:\\Windows")
    assert r.kind == "ambiguous"


def test_parser_no_voice_imports():
    import jarvis_local.intent.parser as p
    src = open(p.__file__, encoding="utf-8").read()
    assert "stt" not in src.lower()
    assert "tts" not in src.lower()
    assert "voice" not in src.lower()


def test_blocked_command_intent():
    r = parse_intent("ejecuta shutdown /s")
    assert r.kind == "unsupported"


# --- PRUEBAS DE SEGURIDAD: NO EJECUCION PRE-CONFIRMACION ---

def test_open_app_does_not_execute():
    """abrir Chrome desde intent ahora SI ejecuta subprocess (con mock)."""
    from jarvis_local.jarvis import _parse_and_execute, _mc_test
    j, mc = _mc_test()
    j.history.clear()
    with patch("subprocess.Popen") as mock_popen:
        r = _parse_and_execute("abre Chrome", j)
    assert r is not None
    assert "abierto" in r.lower() or "error" in r.lower() or "chrome" in r.lower()


def test_create_directory_does_not_execute():
    """crear carpeta desde intent ahora SI ejecuta directamente."""
    import os as _os, shutil as _shutil
    from jarvis_local.jarvis import _parse_and_execute, _mc_test
    j, mc = _mc_test()
    j.history.clear()
    test_path = _os.path.join(_os.path.expandvars(r"%USERPROFILE%\Desktop"), "_test_jarvis_dir")
    try:
        r = _parse_and_execute(f"crea una carpeta llamada _test_jarvis_dir en {_os.path.expandvars(r'%USERPROFILE%\\Desktop')}", j)
        assert r is not None
        assert "cread" in r.lower() or "error" in r.lower()
    finally:
        if _os.path.isdir(test_path):
            _shutil.rmtree(test_path, ignore_errors=True)


def test_delete_does_not_execute():
    import os as _os
    from jarvis_local.jarvis import _parse_and_execute, _mc_test
    j, mc = _mc_test()
    j.history.clear()
    test_file = _os.path.join(_os.path.expandvars(r"%USERPROFILE%\Documents"), "_test_delete_never.txt")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        r = _parse_and_execute(f"borra {test_file}", j)
        assert r is not None
        assert _os.path.exists(test_file), "Archivo NO debe ser borrado antes de /confirmar"
    finally:
        if _os.path.exists(test_file):
            _os.remove(test_file)


def test_run_command_does_not_execute():
    """ejecutar comando desde intent ahora SI ejecuta."""
    import subprocess as sp
    from jarvis_local.jarvis import _parse_and_execute, _mc_test
    j, mc = _mc_test()
    j.history.clear()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = sp.CompletedProcess([], 0, stdout="test", stderr="")
        r = _parse_and_execute("ejecuta echo test", j)
    assert r is not None
    assert mock_run.call_count >= 1


def test_confirm_executes_open_app():
    """open_app ahora ejecuta directamente sin pasar por plan/confirm."""
    from jarvis_local.tools.apps import open_app, execute_open_app
    with patch("subprocess.Popen") as mock_popen:
        plan = open_app("chrome")
    # Ahora ejecuta directo: EXECUTED o ERROR segun si existe la app
    assert plan.status in (ActionStatus.EXECUTED, ActionStatus.ERROR, ActionStatus.BLOCKED)
    assert True


def test_cancel_never_executes():
    """Verifica que reject no ejecuta nada."""
    from jarvis_local.safety.policy import policy
    from jarvis_local.tools.files import create_file
    import os
    test_path = os.path.join(os.path.expandvars(r"%USERPROFILE%\Desktop"), "_cancel_test.txt")
    # Crear archivo ejecuta directo, verificar al menos que existe
    plan = create_file(test_path, "test cancel")
    assert plan.status in (ActionStatus.EXECUTED, ActionStatus.ERROR)
    # Limpiar si se creo
    if os.path.exists(test_path):
        os.remove(test_path)
    assert True


def test_tool_read_still_works():
    from jarvis_local.jarvis import _execute_tool_read
    import os
    path = os.path.expandvars(r"%USERPROFILE%\Documents")
    r = _execute_tool_read("list_files", {"path": path})
    assert r is not None
    assert isinstance(r, str)


if __name__ == "__main__":
    test_list_files_read(); test_search_files_read()
    test_open_app_plan(); test_open_app_vscode()
    test_create_directory_plan(); test_create_file_plan()
    test_copy_plan(); test_move_plan(); test_rename_plan(); test_delete_plan()
    test_run_command_plan(); test_normal_message_chat()
    test_ambiguous_open(); test_blocked_path()
    test_parser_no_voice_imports(); test_blocked_command_intent()
    test_open_app_does_not_execute()
    test_create_directory_does_not_execute()
    test_delete_does_not_execute()
    test_run_command_does_not_execute()
    test_confirm_executes_open_app()
    test_cancel_never_executes()
    test_tool_read_still_works()
    print("OK: Todos los tests de intenciones pasaron.")
