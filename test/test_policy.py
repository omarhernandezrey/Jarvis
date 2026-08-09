"""
Tests de politicas de seguridad - Fase 2
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety.permissions import is_within_allowed
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, SafetyPolicy


def test_simulation_mode_default():
    sp = SafetyPolicy()
    assert sp.is_simulation_mode() is False


def test_set_simulation_mode():
    sp = SafetyPolicy()
    sp.set_simulation_mode(False)
    assert sp.is_simulation_mode() is False
    sp.set_simulation_mode(True)
    assert sp.is_simulation_mode() is True


def test_action_plan_creation():
    plan = ActionPlan(
        action="listar_archivos",
        params={"path": "C:\\Test"},
        risk=RiskLevel.READ,
    )
    assert plan.action == "listar_archivos"
    assert plan.risk == RiskLevel.READ
    assert plan.status == ActionStatus.PLANNED
    d = plan.to_dict()
    assert d["action"] == "listar_archivos"


def test_simulate_plan():
    sp = SafetyPolicy()
    plan = ActionPlan(
        action="crear_archivo",
        params={"path": "test.txt"},
        risk=RiskLevel.CREATE,
    )
    result = sp.simulate(plan)
    assert result.status == ActionStatus.PLANNED
    assert "SIMULACION" in result.simulation_result


def test_block_plan():
    sp = SafetyPolicy()
    plan = sp.block("Ruta no permitida")
    assert plan.status == ActionStatus.BLOCKED
    assert plan.risk == RiskLevel.CRITICAL


def test_confirm_without_pending():
    sp = SafetyPolicy()
    plan = sp.confirm()
    assert plan is None


def test_confirm_reject_cycle():
    sp = SafetyPolicy()
    plan = ActionPlan(
        action="abrir_app",
        params={"app": "chrome"},
        risk=RiskLevel.EXECUTE,
    )
    sp.simulate(plan)
    sp.pending_plan = plan
    sp.confirm()
    assert plan.status == ActionStatus.CONFIRMED


def test_reject_plan():
    sp = SafetyPolicy()
    plan = ActionPlan(action="test", risk=RiskLevel.CREATE)
    sp.simulate(plan)
    sp.pending_plan = plan
    sp.reject()
    assert plan.status == ActionStatus.REJECTED


def test_delete_blocked_by_double_confirm():
    sp = SafetyPolicy()
    plan = ActionPlan(
        action="borrar",
        risk=RiskLevel.DELETE,
    )
    sp.simulate(plan)
    sp.pending_plan = plan
    result = sp.confirm()
    assert result.status == ActionStatus.BLOCKED


def test_to_dict_and_str():
    plan = ActionPlan(
        action="test",
        params={"x": 1},
        paths_affected=["a.txt"],
        risk=RiskLevel.CREATE,
        reason="prueba",
        simulation_result="sim",
    )
    d = plan.to_dict()
    s = str(plan)
    assert d["action"] == "test"
    assert "test" in s


def test_concurrent_confirm():
    """Verifica que confirm() es thread-safe."""
    import threading

    sp = SafetyPolicy()
    results = []
    errors = []

    # Crear un plan compartido
    shared_plan = ActionPlan(action="test", risk=RiskLevel.EXECUTE)
    sp.pending_plan = shared_plan

    def try_confirm():
        try:
            result = sp.confirm()
            if result:
                results.append(result.status)
        except Exception as e:
            errors.append(e)

    # Lanzar múltiples hilos intentando confirmar simultáneamente
    threads = [threading.Thread(target=try_confirm) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No debe haber errores de concurrencia
    assert len(errors) == 0, f"Errores de concurrencia: {errors}"
    # Solo un hilo debe haber confirmado exitosamente (el plan se consume)
    assert len(results) == 1, f"Expected 1 confirm, got {len(results)}"


if __name__ == "__main__":
    test_simulation_mode_default()
    test_set_simulation_mode()
    test_action_plan_creation()
    test_simulate_plan()
    test_block_plan()
    test_confirm_without_pending()
    test_confirm_reject_cycle()
    test_reject_plan()
    test_delete_blocked_by_double_confirm()
    test_to_dict_and_str()
    test_concurrent_confirm()
    print("OK: Todos los tests de politicas pasaron.")
