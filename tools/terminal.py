"""
JARVIS Local - Herramientas de Terminal (Fase 2)
Preparacion de comandos PowerShell/CMD. NO los ejecuta en esta fase.
"""
from jarvis_local.safety.permissions import is_command_blocked
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus, policy


def plan_command(command: str) -> ActionPlan:
    blocked, reason = is_command_blocked(command)
    if blocked:
        return policy.block(f"Comando bloqueado: {reason}")

    plan = ActionPlan(
        action="ejecutar_comando",
        params={"command": command},
        risk=RiskLevel.EXECUTE,
        reason="Ejecutar comandos requiere confirmacion explicita",
    )
    plan.simulation_result = (
        f"[SIMULACION] Se ejecutaria en PowerShell:\n"
        f"  > {command}\n"
        f"Estado: PENDIENTE DE CONFIRMACION"
    )
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan
