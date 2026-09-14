"""JARVIS Local - Consulta de la traza de peticiones (PLAN_EJECUCION FASE J · J3).

"qué pasó con mi última petición" / "traza de la última petición" -> resumen
legible de qué capa de la cascada la resolvió, cuánto tardó cada capa
atravesada, qué hizo el agente (si intervino) y qué dijo VERIFY (si tocó
alguna herramienta auditada). Solo lectura, por la ruta del parser: no debe
costar una llamada al LLM.
"""
from jarvis_local import observability
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


def query_trace(n: int = 1) -> ActionPlan:
    plan = ActionPlan(action="consultar_traza", params={"n": n},
                      risk=RiskLevel.READ, reason="Operación de solo lectura")
    n = max(1, min(int(n), 20))
    trazas = observability.traza(n)
    if not trazas:
        plan.result = "No tengo ninguna traza registrada todavía, senor."
        plan.status = ActionStatus.EXECUTED
        return plan

    partes = [observability.formatear(t) for t in reversed(trazas)]
    etiqueta = "última petición" if n == 1 else f"últimas {len(trazas)} peticiones"
    plan.result = f"Traza de la {etiqueta}, senor:\n\n" + "\n\n".join(partes)
    plan.status = ActionStatus.EXECUTED
    return plan
