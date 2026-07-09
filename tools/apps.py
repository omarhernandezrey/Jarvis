"""
JARVIS Local - Herramientas de Aplicaciones (Fase 2)
Abrir aplicaciones de la whitelist con subprocess controlado.
"""
import subprocess
import os
from jarvis_local.safety.permissions import get_app_path, list_allowed_apps
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus, policy


ALLOWED_APP_NAMES = ["chrome", "vscode", "explorador", "powershell", "terminal"]


def open_app(name: str) -> ActionPlan:
    name_lower = name.lower()
    if name_lower not in ALLOWED_APP_NAMES:
        return policy.block(f"App no permitida: '{name}'. Apps permitidas: {', '.join(ALLOWED_APP_NAMES)}")

    path = get_app_path(name_lower)
    if not path:
        all_apps = list_allowed_apps()
        info = all_apps.get(name_lower, {})
        installed = info.get("installed", False)
        if installed:
            return policy.block(f"No se encontro el ejecutable de {name} aunque parece instalada")
        else:
            return policy.block(f"{name} no esta instalada en este sistema")

    plan = ActionPlan(
        action="abrir_app",
        params={"app": name_lower, "path": path},
        paths_affected=[path],
        risk=RiskLevel.EXECUTE,
        reason=f"Abrir {name} requiere confirmacion explicita",
    )
    plan = policy.simulate(plan)
    policy.pending_plan = plan
    return plan


def list_apps() -> ActionPlan:
    apps = list_allowed_apps()
    lines = []
    for name, info in apps.items():
        status = "INSTALADA" if info["installed"] else "NO INSTALADA"
        lines.append(f"  {name}: {info['description']} [{status}]")
    plan = ActionPlan(
        action="listar_apps",
        risk=RiskLevel.READ,
        reason="Operacion de solo lectura",
    )
    plan.result = "\n".join(lines)
    plan.status = ActionStatus.EXECUTED
    return plan


def execute_open_app(name: str) -> ActionPlan:
    """Ejecuta la apertura de una app CONFIRMADA."""
    name_lower = name.lower()
    path = get_app_path(name_lower)
    if not path:
        return policy.block(f"No se pudo abrir {name}: ejecutable no encontrado")
    plan = ActionPlan(
        action="abrir_app_ejecutando",
        params={"app": name_lower, "path": path},
        paths_affected=[path],
        risk=RiskLevel.EXECUTE,
        status=ActionStatus.CONFIRMED,
    )
    try:
        subprocess.Popen([path], shell=False)
        plan.result = f"{name} abierto correctamente"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
    return plan
