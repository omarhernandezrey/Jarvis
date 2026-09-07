"""JARVIS Local - Notificaciones de escritorio (PLAN_EJECUCION FASE E · E5).

`notify-send` (libnotify). Detección de disponibilidad en tiempo de ejecución:
si no está, se dice claramente (paquete `libnotify-bin`); nunca se falla en
silencio (D0).
"""
from __future__ import annotations

import shutil
import subprocess

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

_URGENCIAS = {"baja": "low", "low": "low", "normal": "normal",
              "alta": "critical", "critical": "critical", "urgente": "critical"}


def send_notification(mensaje: str, titulo: str = "JARVIS",
                      urgencia: str = "normal") -> ActionPlan:
    plan = ActionPlan(action="enviar_notificacion",
                      params={"titulo": titulo, "mensaje": mensaje[:200]},
                      risk=RiskLevel.EXECUTE, reason="Mostrar una notificación de escritorio")
    msg = (mensaje or "").strip()
    if not msg:
        plan.status = ActionStatus.ERROR
        plan.error = "sin mensaje"
        plan.result = "¿Qué quieres que diga la notificación, senor?"
        return plan

    binario = shutil.which("notify-send")
    if not binario:
        plan.status = ActionStatus.ERROR
        plan.error = "notify-send no instalado"
        plan.result = ("No puedo mostrar notificaciones: falta `notify-send`, "
                       "senor. Instálalo con `sudo apt install libnotify-bin`.")
        return plan

    u = _URGENCIAS.get((urgencia or "normal").strip().lower(), "normal")
    try:
        out = subprocess.run(
            [binario, "-a", "JARVIS", "-u", u, titulo or "JARVIS", msg],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude lanzar notify-send, senor: {e}"
        return plan

    if out.returncode != 0:
        err = (out.stderr or "").strip() or f"código {out.returncode}"
        plan.status = ActionStatus.ERROR
        plan.error = err
        plan.result = f"notify-send falló, senor: {err}"
        return plan

    # notify-send aceptó el mensaje (rc 0). Que la notificación se HAYA
    # mostrado en pantalla no es comprobable -> verify None con salvedad (D1).
    plan.params["verify"] = {
        "ok": None, "method": "notify-send rc",
        "detail": "notify-send la aceptó; no puedo confirmar que apareciera en pantalla"}
    plan.status = ActionStatus.EXECUTED
    plan.result = (f"Notificación enviada, senor: «{titulo}: {msg[:80]}». "
                   "(No puedo confirmar que se mostrara en pantalla.)")
    return plan
