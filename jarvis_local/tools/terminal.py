"""
JARVIS Local - Herramientas de Terminal (Fase 2)
Preparacion y ejecucion de comandos PowerShell/CMD.
"""
import subprocess

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.permissions import is_command_blocked
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy


def _shell_argv(command: str) -> list[str]:
    if IS_WINDOWS:
        return ["powershell", "-NoProfile", "-Command", command]
    return ["bash", "-c", command]


def plan_command(command: str) -> ActionPlan:
    blocked, reason = is_command_blocked(command)
    if blocked:
        return policy.block(f"Comando bloqueado: {reason}")

    plan = ActionPlan(
        action="ejecutar_comando",
        params={"command": command},
        risk=RiskLevel.EXECUTE,
        reason="Ejecutar comando",
    )
    shell_name = "PowerShell" if IS_WINDOWS else "bash"
    plan.simulation_result = (
        f"[SIMULACION] Se ejecutaria en {shell_name}:\n"
        f"  > {command}\n"
        f"Estado: PENDIENTE DE CONFIRMACION"
    )
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_command(command: str) -> ActionPlan:
    blocked, reason = is_command_blocked(command)
    if blocked:
        return policy.block(f"Comando bloqueado: {reason}")

    plan = ActionPlan(
        action="ejecutar_comando",
        params={"command": command},
        risk=RiskLevel.EXECUTE,
        reason="Ejecutar comando",
    )
    try:
        result = subprocess.run(
            _shell_argv(command),
            capture_output=True, text=True, timeout=30, shell=False,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode == 0:
            plan.result = out or "Comando ejecutado correctamente."
            plan.status = ActionStatus.EXECUTED
        else:
            plan.result = f"Salida: {out}\nError: {err}" if out or err else f"Codigo de salida: {result.returncode}"
            plan.status = ActionStatus.ERROR
            plan.error = err or f"Codigo de salida: {result.returncode}"
    except subprocess.TimeoutExpired:
        plan.status = ActionStatus.ERROR
        plan.error = "Timeout"
        plan.result = "El comando excedio el tiempo limite de 30 segundos."
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error al ejecutar comando: {e}"
    return plan
