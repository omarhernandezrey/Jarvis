"""
JARVIS Local - Direccion IP (Fase 4)
IP local (offline) y publica (api.ipify.org).
"""
import socket
import requests
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus


def local_ip() -> str:
    """IP local del equipo (no requiere internet)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no envia datos, solo resuelve la ruta
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def get_ip() -> ActionPlan:
    plan = ActionPlan(action="direccion_ip", risk=RiskLevel.READ,
                      reason="Consultar direccion IP")
    lines = [f"IP local: {local_ip()}"]
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=10)
        r.raise_for_status()
        lines.append(f"IP publica: {r.json()['ip']}")
    except requests.RequestException:
        lines.append("IP publica: no disponible (sin internet)")
    plan.result = "Su direccion IP, senor:\n  " + "\n  ".join(lines)
    plan.status = ActionStatus.EXECUTED
    return plan
