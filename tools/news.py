"""
JARVIS Local - Noticias (Fase 4)
Titulares principales via RSS de Google News (sin API key).
Fuente configurable en config.yaml (news.rss_url).
"""
import xml.etree.ElementTree as ET
import requests
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus
from jarvis_local.config import get_config

DEFAULT_RSS = "https://news.google.com/rss?hl=es-419&gl=CO&ceid=CO:es-419"


def parse_rss_titles(xml_text: str, limit: int = 5) -> list[str]:
    """Extrae titulos de un feed RSS."""
    root = ET.fromstring(xml_text)
    titles = []
    for item in root.iter("item"):
        t = item.findtext("title")
        if t:
            titles.append(t.strip())
        if len(titles) >= limit:
            break
    return titles


def headlines(limit: int = 5) -> ActionPlan:
    plan = ActionPlan(action="titulares", risk=RiskLevel.READ,
                      reason="Consultar titulares de noticias")
    try:
        cfg = get_config()
        url = cfg.get("news", {}).get("rss_url", DEFAULT_RSS)
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0 JARVIS-Local"})
        r.raise_for_status()
        titles = parse_rss_titles(r.text, limit)
        if not titles:
            plan.status = ActionStatus.ERROR
            plan.result = "No pude obtener titulares en este momento, senor."
            return plan
        listado = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(titles))
        plan.result = f"Titulares principales, senor:\n{listado}"
        plan.status = ActionStatus.EXECUTED
    except (requests.RequestException, ET.ParseError) as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar las noticias. Verifique su conexion a internet."
    return plan
