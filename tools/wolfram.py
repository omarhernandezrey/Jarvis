"""
JARVIS Local - WolframAlpha (Fase 4)
Responde preguntas de datos/calculo via WolframAlpha si hay App ID en
secrets.yaml; si no, JARVIS respondera con el modelo local (Ollama).
"""
import requests
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus
from jarvis_local.config import get_secrets

API_URL = "https://api.wolframalpha.com/v1/result"


def has_app_id() -> bool:
    app_id = (get_secrets().get("wolframalpha", {}) or {}).get("app_id", "")
    return bool(app_id) and app_id != "TU-APPID"


def ask_wolfram(question: str) -> ActionPlan:
    plan = ActionPlan(action="wolframalpha", params={"pregunta": question},
                      risk=RiskLevel.READ, reason="Consultar WolframAlpha")
    if not has_app_id():
        plan.status = ActionStatus.ERROR
        plan.result = ("WolframAlpha no esta configurado, senor. Registre un App ID "
                       "gratis en developer.wolframalpha.com y agreguelo a "
                       "secrets.yaml. Mientras tanto puedo responder con mi "
                       "modelo local: solo hagame la pregunta directamente.")
        return plan
    app_id = get_secrets()["wolframalpha"]["app_id"]
    try:
        r = requests.get(API_URL, params={
            "appid": app_id, "i": question, "units": "metric"}, timeout=20)
        if r.status_code == 501:
            plan.status = ActionStatus.ERROR
            plan.result = ("WolframAlpha no entendio la pregunta, senor. "
                           "Intente reformularla (funciona mejor en ingles).")
            return plan
        r.raise_for_status()
        plan.result = f"Segun WolframAlpha: {r.text}"
        plan.status = ActionStatus.EXECUTED
    except requests.RequestException as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar WolframAlpha. Verifique su conexion."
    return plan
