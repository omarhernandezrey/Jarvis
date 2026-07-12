"""
JARVIS Local - Herramientas de Aplicaciones (Fase 2)
Abrir aplicaciones de la whitelist con subprocess controlado.
"""
import subprocess
import os
from jarvis_local.safety.permissions import get_app_path, list_allowed_apps
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus, policy


ALLOWED_APP_NAMES = ["chrome", "vscode", "explorador", "powershell", "terminal",
                       "wsl", "notepad", "calculadora", "control", "configuracion",
                       "cmd", "taskmgr", "edge", "firefox"]

# Directorio inicial (ruta Linux) al abrir la terminal de WSL
WSL_START_DIR = "/home/omarhernandez/personalProjects"


def _launch_wsl(wsl_path: str) -> None:
    """Abre WSL en WSL_START_DIR, en Windows Terminal si esta disponible."""
    wt_path = get_app_path("terminal")
    args = [wsl_path, "--cd", WSL_START_DIR]
    if wt_path:
        subprocess.Popen([wt_path] + args, shell=False)
    else:
        subprocess.Popen(args, shell=False,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)


def open_app(name: str) -> ActionPlan:
    name_lower = name.lower()
    if name_lower not in ALLOWED_APP_NAMES:
        return _open_installed_app(name)

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
        reason=f"Abrir {name}",
    )
    try:
        if name_lower == "configuracion":
            subprocess.Popen(["start", "ms-settings:"], shell=True)
        elif name_lower == "wsl":
            _launch_wsl(path)
        else:
            subprocess.Popen([path], shell=False)
        plan.result = f"{name} abierto correctamente."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No se pudo abrir {name}: {e}"
    return plan


def _open_installed_app(name: str) -> ActionPlan:
    """Abre una app instalada (menu inicio) por nombre con busqueda difusa."""
    from jarvis_local.tools.app_index import find_app, launch_app
    try:
        matches = find_app(name)
    except Exception as e:
        return policy.block(f"No pude consultar las apps instaladas: {e}")
    if not matches:
        return policy.block(
            f"No encontre ninguna aplicacion parecida a '{name}' en este equipo. "
            f"Tambien puedo abrir: {', '.join(ALLOWED_APP_NAMES)}")

    best = matches[0]
    plan = ActionPlan(
        action="abrir_app",
        params={"app": best["name"], "appid": best["appid"]},
        paths_affected=[best["appid"]],
        risk=RiskLevel.EXECUTE,
        reason=f"Abrir {best['name']} (app instalada)",
    )
    try:
        launch_app(best["appid"])
        plan.result = f"{best['name']} abierto correctamente."
        if len(matches) > 1:
            otros = ", ".join(m["name"] for m in matches[1:4])
            plan.result += f" (Tambien encontre: {otros})"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No se pudo abrir {best['name']}: {e}"
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
        return _open_installed_app(name)
    plan = ActionPlan(
        action="abrir_app_ejecutando",
        params={"app": name_lower, "path": path},
        paths_affected=[path],
        risk=RiskLevel.EXECUTE,
        status=ActionStatus.CONFIRMED,
    )
    try:
        if name_lower == "wsl":
            _launch_wsl(path)
        else:
            subprocess.Popen([path], shell=False)
        plan.result = f"{name} abierto correctamente"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
    return plan
