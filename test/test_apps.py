"""
Tests de herramientas de apps - Fase 2
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.tools.apps import open_app, list_apps, ALLOWED_APP_NAMES
from jarvis_local.safety.policy import ActionStatus


def test_list_apps():
    plan = list_apps()
    assert plan.action == "listar_apps"
    assert plan.status == ActionStatus.EXECUTED
    assert "chrome" in plan.result.lower() or "Chrome" in plan.result


def test_open_allowed_app_simulated():
    for app in ALLOWED_APP_NAMES:
        plan = open_app(app)
        if plan.status == ActionStatus.BLOCKED:
            assert "no esta instalada" in plan.simulation_result.lower() or \
                   "no se encontro" in plan.simulation_result.lower() or \
                   "no permitida" in plan.reason.lower()
        else:
            assert plan.status == ActionStatus.PLANNED
            assert plan.action == "abrir_app"


def test_open_blocked_app():
    plan = open_app("calc")
    assert plan.status == ActionStatus.BLOCKED


if __name__ == "__main__":
    test_list_apps()
    test_open_allowed_app_simulated()
    test_open_blocked_app()
    print("OK: Todos los tests de apps pasaron.")
