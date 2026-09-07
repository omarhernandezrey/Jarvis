"""JARVIS Local - Consulta de la auditoría (PLAN_EJECUCION FASE D · D2).

"qué hiciste hoy", "qué cambiaste ayer" -> resumen legible de las acciones de
escritura/sistema registradas en la auditoría append-only. Solo lectura, y por
la ruta del parser: no debe costar una llamada al LLM.
"""
from datetime import date, timedelta

from jarvis_local.safety.audit import audit
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


def _estado(entry: dict) -> str:
    st = entry.get("status", "")
    v = entry.get("verify")
    if st == "executed":
        if isinstance(v, dict):
            if v.get("ok") is True:
                return "hecho y verificado"
            if v.get("ok") is None:
                return "hecho (no se pudo verificar el efecto)"
            if v.get("ok") is False:
                return "dado por hecho pero la verificación FALLÓ"
        return "hecho"
    return {
        "error": "error",
        "planned": "pendiente de confirmación",
        "confirmed": "confirmado, sin ejecutar",
        "blocked": "bloqueado",
        "rejected": "cancelado",
    }.get(st, st or "?")


def _fmt_params(params: dict) -> str:
    p = ", ".join(f"{k}={v}" for k, v in (params or {}).items())
    return f" ({p})" if p else ""


def query_audit(dia: str = "hoy") -> ActionPlan:
    plan = ActionPlan(action="consultar_auditoria", params={"dia": dia},
                      risk=RiskLevel.READ, reason="Operacion de solo lectura")
    es_ayer = str(dia).strip().lower().startswith("ayer")
    d = date.today() - timedelta(days=1) if es_ayer else date.today()
    etiqueta = "ayer" if es_ayer else "hoy"

    entradas = audit.for_day(d)
    if not entradas:
        plan.result = f"No registré ninguna acción {etiqueta}, senor."
        plan.status = ActionStatus.EXECUTED
        return plan

    lineas = []
    for e in entradas:
        hhmm = (e.get("ts", "")[11:16]) or "--:--"
        marca = " [confirmado por usted]" if e.get("confirmed") is True else ""
        lineas.append(f"  {hhmm}  {e.get('tool', '?')}{_fmt_params(e.get('params', {}))}"
                      f" — {_estado(e)}{marca}")

    n = len(entradas)
    cabecera = (f"{etiqueta.capitalize()}, senor, registré "
                f"{n} {'acción' if n == 1 else 'acciones'}:")
    plan.result = cabecera + "\n" + "\n".join(lineas)
    plan.status = ActionStatus.EXECUTED
    return plan
