"""
JARVIS Local - Herramientas Web (Fase 4)
Abrir sitios web, buscar en Google y reproducir en YouTube.
"""
import json
import re
import webbrowser
from urllib.parse import quote_plus, urlparse

import requests

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

_YT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept-Language": "es-CO,es;q=0.9",
}
_YT_TIMEOUT = 6.0
_YT_INITIAL_DATA_RE = re.compile(r"var ytInitialData = (\{.*?\});</script>", re.DOTALL)


def _is_safe_url(url: str) -> bool:
    """Verifica que la URL sea segura (solo http/https)."""
    parsed = urlparse(url)
    # Solo permitir http, https y URLs sin esquema (se añadirá https)
    return parsed.scheme in ("http", "https", "")


def build_url(site: str) -> str:
    """Normaliza un nombre de sitio a URL completa."""
    s = site.strip().strip('"\'').rstrip('.!?').strip()

    # Verificar si tiene un esquema (http, https, javascript, data, etc.)
    if ":" in s and not s.startswith(("http://", "https://")):
        # Tiene un esquema que no es http/https, verificar si es seguro
        if not _is_safe_url(s):
            return "https://www.google.com"  # Fallback seguro
        return s

    if s.startswith(("http://", "https://")):
        # Validar que el esquema sea seguro
        if not _is_safe_url(s):
            return "https://www.google.com"  # Fallback seguro
        return s
    if "." in s and " " not in s:
        url = f"https://{s}"
        if not _is_safe_url(url):
            return "https://www.google.com"  # Fallback seguro
        return url
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


def _fetch_youtube_search_html(query: str) -> str | None:
    """HTML publico de la pagina de resultados de YouTube, sin API key —
    mismo patron que `jobs.py::_fetch`. `None` si la red falla."""
    try:
        r = requests.get(build_youtube_url(query), headers=_YT_HEADERS, timeout=_YT_TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _find_video_renderer(node):
    """Primer `videoRenderer` real (no `reelItemRenderer`/shorts, no
    `channelRenderer`, etc.) en el arbol de `ytInitialData` — recorrido en
    el mismo orden en que aparecen en la pagina, así que es el primer
    resultado que vería una persona."""
    if isinstance(node, dict):
        if "videoRenderer" in node:
            return node["videoRenderer"]
        for value in node.values():
            found = _find_video_renderer(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_video_renderer(item)
            if found is not None:
                return found
    return None


def parse_first_youtube_video(html: str) -> tuple[str, str] | None:
    """(video_id, titulo) del primer video real de una pagina de resultados
    de YouTube ya descargada. Lee el bloque `var ytInitialData = {...};`
    que YouTube ya manda embebido en el HTML (lo necesita su propio JS para
    pintar la pagina — no hace falta ejecutar JS ni usar su API). `None` si
    YouTube cambio el formato de la pagina — el caller debe caer a abrir la
    busqueda, nunca inventar un video."""
    m = _YT_INITIAL_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    renderer = _find_video_renderer(data)
    if not renderer:
        return None
    video_id = renderer.get("videoId")
    if not video_id:
        return None
    try:
        title = renderer["title"]["runs"][0]["text"]
    except (KeyError, IndexError, TypeError):
        title = video_id
    return video_id, title


def _first_youtube_video(query: str) -> tuple[str, str] | None:
    """(video_id, titulo) del primer resultado real de buscar `query` en
    YouTube. `None` si la red falla, YouTube cambio su HTML, o no hay
    resultados — el caller debe caer a abrir la busqueda."""
    html = _fetch_youtube_search_html(query)
    if html is None:
        return None
    return parse_first_youtube_video(html)


def build_youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def youtube_play(query: str) -> ActionPlan:
    """Busca y reproduce una cancion o video en YouTube: abre directo el
    primer resultado real (la pagina /watch, que arranca sola) en vez de
    la pagina de busqueda — antes el usuario tenia que elegir el video a
    mano. Si no se puede determinar el video (red caida, YouTube cambio su
    HTML), cae a abrir la busqueda en vez de inventar un video."""
    found = _first_youtube_video(query)
    if found is not None:
        video_id, title = found
        plan = _open(build_youtube_watch_url(video_id), "reproducir_youtube",
                     f"Reproducir '{query}' en YouTube")
        if plan.status == ActionStatus.EXECUTED:
            plan.result = f"Reproduciendo '{title}' en YouTube."
        return plan

    plan = _open(build_youtube_url(query), "reproducir_youtube",
                 f"Reproducir '{query}' en YouTube")
    if plan.status == ActionStatus.EXECUTED:
        plan.result = (f"No pude identificar un video exacto de '{query}', "
                       "le abro la busqueda en YouTube. Seleccione el video que desee.")
    return plan
