"""
JARVIS Local - Herramientas Web (Fase 4)
Abrir sitios web, buscar en Google y reproducir en YouTube.
"""
import webbrowser
from urllib.parse import quote_plus

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


def build_url(site: str) -> str:
    """Normaliza un nombre de sitio a URL completa."""
    s = site.strip().strip('"\'').rstrip('.!?').strip()
    if s.startswith(("http://", "https://")):
        return s
    if "." in s and " " not in s:
        return f"https://{s}"
    # nombre sin dominio: probar .com
    return f"https://www.{s.replace(' ', '')}.com"


def build_google_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query.strip())}"


def build_youtube_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(query.strip())}"


def _open(url: str, action: str, reason: str) -> ActionPlan:
    plan = ActionPlan(action=action, params={"url": url},
                      risk=RiskLevel.EXECUTE, reason=reason)
    try:
        webbrowser.open(url)
        plan.result = f"Abriendo {url} en su navegador."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude abrir el navegador: {e}"
    return plan


def open_website(site: str) -> ActionPlan:
    """Abre cualquier sitio web en el navegador por defecto."""
    url = build_url(site)
    return _open(url, "abrir_sitio_web", f"Abrir sitio web {url}")


def google_search(query: str) -> ActionPlan:
    """Busca cualquier cosa en Google."""
    plan = _open(build_google_url(query), "buscar_google", f"Buscar '{query}' en Google")
    if plan.status == ActionStatus.EXECUTED:
        plan.result = f"Buscando '{query}' en Google."
    return plan


def youtube_play(query: str) -> ActionPlan:
    """Busca/reproduce una cancion o video en YouTube."""
    plan = _open(build_youtube_url(query), "reproducir_youtube",
                 f"Reproducir '{query}' en YouTube")
    if plan.status == ActionStatus.EXECUTED:
        plan.result = f"Buscando '{query}' en YouTube. Seleccione el video que desee."
    return plan
