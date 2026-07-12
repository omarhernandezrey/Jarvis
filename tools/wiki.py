"""
JARVIS Local - Wikipedia (Fase 4)
Habla de cualquier persona o tema via la API REST de Wikipedia en espanol.
"""
from urllib.parse import quote

import requests

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

SUMMARY_URL = "https://es.wikipedia.org/api/rest_v1/page/summary/{}"
SEARCH_URL = "https://es.wikipedia.org/w/api.php"
# Wikipedia exige un User-Agent identificable
_HEADERS = {"User-Agent": "JARVIS-Local/1.0 (asistente personal offline)"}


def _search_title(query: str) -> str | None:
    """Busca el titulo mas cercano en Wikipedia."""
    r = requests.get(SEARCH_URL, params={
        "action": "opensearch", "search": query, "limit": 1, "format": "json"},
        timeout=15, headers=_HEADERS)
    r.raise_for_status()
    data = r.json()
    titles = data[1] if len(data) > 1 else []
    return titles[0] if titles else None


def wiki_summary(topic: str) -> ActionPlan:
    plan = ActionPlan(action="wikipedia", params={"tema": topic},
                      risk=RiskLevel.READ, reason=f"Consultar Wikipedia: {topic}")
    try:
        title = _search_title(topic) or topic
        r = requests.get(SUMMARY_URL.format(quote(title, safe="")), timeout=15,
                         headers={**_HEADERS, "accept": "application/json"})
        if r.status_code == 404:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre informacion sobre '{topic}' en Wikipedia, senor."
            return plan
        r.raise_for_status()
        data = r.json()
        extract = data.get("extract", "").strip()
        if not extract:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre informacion sobre '{topic}' en Wikipedia, senor."
            return plan
        # Limitar a ~3 oraciones para respuesta hablada
        sentences = extract.split(". ")
        resumen = ". ".join(sentences[:3])
        if not resumen.endswith("."):
            resumen += "."
        plan.result = f"Segun Wikipedia: {resumen}"
        plan.status = ActionStatus.EXECUTED
    except requests.RequestException as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar Wikipedia. Verifique su conexion a internet."
    return plan
