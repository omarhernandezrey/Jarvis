"""
Tests de herramientas de apps - Fase 2
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.apps import (
    _OPENED,
    ALLOWED_APP_NAMES,
    _register_opened,
    close_all_apps,
    close_app,
    list_apps,
    open_app,
)


def test_list_apps():
    plan = list_apps()
    assert plan.action == "listar_apps"
    assert plan.status == ActionStatus.EXECUTED
    assert "chrome" in plan.result.lower() or "Chrome" in plan.result


def test_open_allowed_app_simulated():
    for app in ALLOWED_APP_NAMES:
        plan = open_app(app)
        if plan.status == ActionStatus.BLOCKED:
            assert "no esta instalada" in plan.result.lower() or \
                   "no se encontro" in plan.result.lower() or \
                   "no permitida" in plan.reason.lower()
        else:
            assert plan.status in (ActionStatus.EXECUTED, ActionStatus.ERROR)
            assert plan.action == "abrir_app"


def test_open_blocked_app():
    # Nombre que no existe ni en whitelist ni en apps instaladas
    plan = open_app("zzz_app_inexistente_9x")
    assert plan.status == ActionStatus.BLOCKED


def test_close_app_not_running():
    plan = close_app("zzz_app_inexistente_9x")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params.get("closed_count", 0) == 0
    assert "no parece estar abierto" in plan.result.lower()


def test_close_app_explorador_bloqueado():
    plan = close_app("explorador")
    assert plan.status == ActionStatus.BLOCKED
    assert "explorador" in plan.result.lower()


def test_close_app_sin_nombre():
    plan = close_app("")
    assert plan.status == ActionStatus.BLOCKED


def test_close_all_apps_sin_nada_abierto():
    guardado = dict(_OPENED)
    _OPENED.clear()
    try:
        plan = close_all_apps()
        assert plan.status == ActionStatus.EXECUTED
        assert "no he abierto" in plan.result.lower()
    finally:
        _OPENED.update(guardado)


def test_close_all_apps_con_registro():
    guardado = dict(_OPENED)
    _OPENED.clear()
    try:
        # app registrada pero cuyo proceso no existe: debe reportarla como
        # ya cerrada, sin tocar ningun proceso real
        _register_opened("zzz_fantasma_9x", "Zzz Fantasma")
        plan = close_all_apps()
        assert plan.status == ActionStatus.EXECUTED
        assert "zzz fantasma" in plan.result.lower()
        assert not _OPENED  # el registro queda limpio
    finally:
        _OPENED.clear()
        _OPENED.update(guardado)


def test_registro_de_aperturas():
    guardado = dict(_OPENED)
    _OPENED.clear()
    try:
        _register_opened("word", "Word", pid=99999, procnames=["WINWORD.EXE"])
        _register_opened("word", "Word", pid=99998)
        entry = _OPENED["word"]
        assert entry["pids"] == {99999, 99998}
        assert entry["procnames"] == ["WINWORD.EXE"]
    finally:
        _OPENED.clear()
        _OPENED.update(guardado)


if __name__ == "__main__":
    test_list_apps()
    test_open_allowed_app_simulated()
    test_open_blocked_app()
    test_close_app_not_running()
    test_close_app_explorador_bloqueado()
    test_close_app_sin_nombre()
    test_close_all_apps_sin_nada_abierto()
    test_close_all_apps_con_registro()
    test_registro_de_aperturas()
    print("OK: Todos los tests de apps pasaron.")


# ── H2: no abrir un duplicado si la app ya está corriendo ─────────────────────
def test_h2_no_duplica_app_de_whitelist_ya_abierta():
    from unittest.mock import MagicMock, patch

    from jarvis_local.tools import apps as A

    with patch.object(A, "_running_procnames", return_value={"google-chrome", "chrome"}), \
         patch.object(A, "get_app_path", return_value="/usr/bin/google-chrome"), \
         patch.object(A, "_try_focus", return_value=False), \
         patch("subprocess.Popen") as popen:
        plan = A.open_app("chrome")

    assert plan.status == ActionStatus.EXECUTED
    assert "ya esta abierta" in plan.result.lower() or "al frente" in plan.result.lower()
    popen.assert_not_called()


def test_h2_no_duplica_app_instalada_ya_abierta():
    from unittest.mock import patch

    from jarvis_local.tools import apps as A

    match = {"name": "Visual Studio Code", "appid": "code.desktop", "norm": "visual studio code"}
    with patch.object(A, "_running_procnames", return_value={"code"}), \
         patch.object(A, "_try_focus", return_value=False), \
         patch("jarvis_local.tools.app_index.find_app", return_value=[match]), \
         patch("jarvis_local.tools.app_index.launch_app") as launch:
        plan = A.open_app("vscode")

    assert plan.status == ActionStatus.EXECUTED
    assert "ya esta abierta" in plan.result.lower() or "al frente" in plan.result.lower()
    launch.assert_not_called()


def test_h2_si_no_corre_nada_si_lanza():
    from unittest.mock import MagicMock, patch

    from jarvis_local.tools import apps as A

    with patch.object(A, "_running_procnames", return_value=set()), \
         patch.object(A, "get_app_path", return_value="/usr/bin/xterm"), \
         patch("subprocess.Popen", return_value=MagicMock(pid=99)) as popen:
        plan = A.open_app("terminal")

    assert plan.status == ActionStatus.EXECUTED
    assert "abierto correctamente" in plan.result.lower()
    popen.assert_called_once()
