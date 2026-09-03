"""
JARVIS Local - Herramientas de Terminal (Fase 2)
Preparacion y ejecucion de comandos PowerShell/CMD.
"""
import subprocess

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.permissions import validate_shell_command
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy


def _shell_argv(command: str) -> list[str]:
    """Construye el argv para ejecutar el comando en el shell apropiado."""
    if IS_WINDOWS:
        return ["powershell", "-NoProfile", "-Command", command]
    # En Linux, usar bash -c pero con el comando sanitizado
    return ["bash", "-c", command]


def plan_command(command: str) -> ActionPlan:
    permitido, motivo, clean_command = validate_shell_command(command)
    if not permitido:
        return policy.block(motivo)

    plan = ActionPlan(
        action="ejecutar_comando",
        params={"command": clean_command},
        risk=RiskLevel.EXECUTE,
        reason="Ejecutar comando",
    )
    shell_name = "PowerShell" if IS_WINDOWS else "bash"
    plan.simulation_result = (
        f"[SIMULACION] Se ejecutaria en {shell_name}:\n"
        f"  > {clean_command}\n"
        f"Estado: PENDIENTE DE CONFIRMACION"
    )
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_command(command: str) -> ActionPlan:
    # GUARDIA UNICO: unico punto que llega a subprocess con un shell.
    permitido, motivo, clean_command = validate_shell_command(command)
    if not permitido:
        return policy.block(motivo)

    plan = ActionPlan(
        action="ejecutar_comando",
        params={"command": clean_command},
        risk=RiskLevel.EXECUTE,
        reason="Ejecutar comando",
    )
    try:
        # Defensa en profundidad: aunque el llamante haya validado, se
        # revalida justo antes de subprocess. Nada llega aqui sin pasar.
        _ok, _motivo, clean_command = validate_shell_command(clean_command)
        if not _ok:
            return policy.block(_motivo)
        result = subprocess.run(
            _shell_argv(clean_command),
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
    except OSError as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error de sistema al ejecutar comando: {e}"
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error inesperado al ejecutar comando: {e}"
    return plan
