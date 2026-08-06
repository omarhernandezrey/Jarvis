"""
JARVIS Local - Ocultar/mostrar archivos (Fase 4)
Oculta todos los archivos de una carpeta permitida o los hace visibles.
Accion de escritura: requiere plan + /confirmar.
"""
import os
import subprocess
from pathlib import Path

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.permissions import is_within_allowed
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy


def plan_hide(path: str, hide: bool = True) -> ActionPlan:
    """Crea el plan (pendiente de confirmacion) para ocultar/mostrar archivos."""
    action = "ocultar_archivos" if hide else "mostrar_archivos"
    verbo = "Ocultar" if hide else "Hacer visibles"
    norm = str(Path(path).expanduser().resolve())
    allowed, _ = is_within_allowed(norm)
    if not allowed:
        return policy.block(f"La ruta '{norm}' no esta en las carpetas permitidas.")
    if not Path(norm).is_dir():
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
    """Ejecuta el ocultar/mostrar CONFIRMADO."""
    action = "ocultar_archivos" if hide else "mostrar_archivos"
    norm = str(Path(path).expanduser().resolve())
    plan = ActionPlan(action=action, params={"path": norm, "hide": hide},
                      paths_affected=[norm], risk=RiskLevel.EXECUTE,
                      status=ActionStatus.CONFIRMED)
    allowed, _ = is_within_allowed(norm)
    if not allowed or not Path(norm).is_dir():
        plan.status = ActionStatus.ERROR
        plan.result = f"Ruta invalida o no permitida: {norm}"
        return plan
    try:
        if IS_WINDOWS:
            _hide_windows(norm, hide)
        else:
            _hide_linux(norm, hide)
        n = len([f for f in os.listdir(norm)
                 if os.path.isfile(str(Path(norm) / f))])
        estado = "ocultos" if hide else "visibles"
        plan.result = f"Listo, senor. Los archivos de {norm} ahora estan {estado} ({n} elementos)."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar los atributos: {e}"
    return plan


def _hide_windows(norm: str, hide: bool):
    """Oculta/muestra archivos en Windows usando attrib."""
    flag = "+h" if hide else "-h"
    subprocess.run(["attrib", flag, str(Path(norm) / "*")],
                   capture_output=True, text=True, timeout=60, shell=False)


def _hide_linux(norm: str, hide: bool):
    """
    Oculta/muestra archivos en Linux renombrando con/sin prefijo '.'.
    En Linux, los archivos ocultos empiezan con punto.
    """
    for filename in os.listdir(norm):
        filepath = str(Path(norm) / filename)
        if not Path(filepath).is_file():
            continue
        if hide and not filename.startswith('.'):
            # Ocultar: añadir prefijo punto
            os.rename(filepath, str(Path(norm) / ('.' + filename)))
        elif not hide and filename.startswith('.') and filename != '.':
            # Mostrar: quitar prefijo punto
            new_name = filename[1:]  # Quitar el punto inicial
            os.rename(filepath, os.path.join(norm, new_name))
