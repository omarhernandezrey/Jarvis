"""
JARVIS Local - Estado del sistema (Fase 4)
Uso de CPU, RAM, disco y estado de la bateria (psutil).
"""
import psutil

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


def system_status() -> ActionPlan:
    plan = ActionPlan(action="estado_sistema", risk=RiskLevel.READ,
                      reason="Consultar estado del sistema (solo lectura)")
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        lines = [
            f"CPU: {cpu:.0f} por ciento en uso",
            f"RAM: {ram.percent:.0f} por ciento en uso "
            f"({ram.used / 1024**3:.1f} de {ram.total / 1024**3:.1f} GB)",
            f"Disco C: {disk.percent:.0f} por ciento usado "
            f"({disk.free / 1024**3:.0f} GB libres)",
        ]
        bat = psutil.sensors_battery()
        if bat is not None:
            estado = "cargando" if bat.power_plugged else "descargando"
            lines.append(f"Bateria: {bat.percent:.0f} por ciento ({estado})")
        else:
            lines.append("Bateria: no detectada (equipo de escritorio)")
        plan.result = "Estado del sistema, senor:\n  " + "\n  ".join(lines)
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude leer el estado del sistema: {e}"
    return plan
