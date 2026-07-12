"""
JARVIS Local - Ocultar/mostrar archivos (Fase 4)
Oculta todos los archivos de una carpeta permitida o los hace visibles.
Accion de escritura: requiere plan + /confirmar.
"""
import os
import subprocess
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus, policy
from jarvis_local.safety.permissions import is_within_allowed


def plan_hide(path: str, hide: bool = True) -> ActionPlan:
    """Crea el plan (pendiente de confirmacion) para ocultar/mostrar archivos."""
    action = "ocultar_archivos" if hide else "mostrar_archivos"
    verbo = "Ocultar" if hide else "Hacer visibles"
    norm = os.path.normpath(os.path.expandvars(path))
    allowed, _ = is_within_allowed(norm)
    if not allowed:
        return policy.block(f"La ruta '{norm}' no esta en las carpetas permitidas.")
    if not os.path.isdir(norm):
        return policy.block(f"La carpeta '{norm}' no existe.")
    plan = ActionPlan(
        action=action,
        params={"path": norm, "hide": hide},
        paths_affected=[norm],
        risk=RiskLevel.EXECUTE,
        reason=f"{verbo} todos los archivos de {norm}",
        simulation_result=(f"[Plan pendiente] {verbo} todos los archivos de {norm}. "
                           "Escribe /confirmar para ejecutar o /cancelar."),
    )
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_hide(path: str, hide: bool = True) -> ActionPlan:
    """Ejecuta el ocultar/mostrar CONFIRMADO usando attrib."""
    action = "ocultar_archivos" if hide else "mostrar_archivos"
    norm = os.path.normpath(os.path.expandvars(path))
    plan = ActionPlan(action=action, params={"path": norm, "hide": hide},
                      paths_affected=[norm], risk=RiskLevel.EXECUTE,
                      status=ActionStatus.CONFIRMED)
    allowed, _ = is_within_allowed(norm)
    if not allowed or not os.path.isdir(norm):
        plan.status = ActionStatus.ERROR
        plan.result = f"Ruta invalida o no permitida: {norm}"
        return plan
    try:
        flag = "+h" if hide else "-h"
        subprocess.run(["attrib", flag, os.path.join(norm, "*")],
                       capture_output=True, text=True, timeout=60, shell=False)
        n = len([f for f in os.listdir(norm)
                 if os.path.isfile(os.path.join(norm, f))])
        estado = "ocultos" if hide else "visibles"
        plan.result = f"Listo, senor. Los archivos de {norm} ahora estan {estado} ({n} elementos)."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar los atributos: {e}"
    return plan
