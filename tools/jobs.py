"""
JARVIS Local - Busqueda de empleo (Fase 5)
Busca ofertas en Computrabajo, El Empleo y LinkedIn, las combina y las
ordena de la MAS RECIENTE a la mas antigua. Sin API keys.
"""
import concurrent.futures
import html
import json
import re
import unicodedata
import webbrowser
import requests
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus

CT_BASE = "https://co.computrabajo.com"
EE_BASE = "https://www.elempleo.com"
LI_URL = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
          "?keywords={q}&location={loc}&sortBy=DD&start=0")

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept-Language": "es-CO,es;q=0.9",
}
TIMEOUT = 25

# Ultimos resultados, para "abre la oferta N" y "muestrame las ofertas"
_last_results: list[dict] = []
_last_url: str = ""
_last_query: tuple[str, str] = ("", "")


# ---------- utilidades ----------

def _slug(text: str) -> str:
    """'Desarrollador Web' -> 'desarrollador-web' (sin acentos)."""
    t = unicodedata.normalize("NFD", text.lower().strip())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s-]", "", t)
    return re.sub(r"[\s-]+", "-", t).strip("-")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def antiguedad_minutos(texto: str) -> int:
    """'Hace 4 horas' -> 240. Sirve para ordenar por mas reciente.
    Lo desconocido va al final (valor alto)."""
    t = _clean(texto).lower()
    if not t:
        return 999999
    if "minuto" in t or "ahora" in t or "reciente" in t:
        m = re.search(r"(\d+)", t)
        return int(m.group(1)) if m else 1
    if "hoy" in t:
        return 12 * 60
    if "ayer" in t:
        return 24 * 60
    m = re.search(r"(\d+)\s*(hora|dia|día|semana|mes)", t)
    if m:
        n = int(m.group(1))
        unidad = m.group(2)
        factor = {"hora": 60, "dia": 1440, "día": 1440,
                  "semana": 10080, "mes": 43200}[unidad]
        return n * factor
    return 999999


def _fmt_antiguedad(minutos: int) -> str:
    if minutos >= 999999:
        return ""
    if minutos < 60:
        return f"hace {minutos} min"
    if minutos < 1440:
        return f"hace {minutos // 60} h"
    dias = minutos // 1440
    return "ayer" if dias == 1 else f"hace {dias} dias"


def _job(fuente, titulo, link, empresa="Confidencial", ubicacion="",
         salario="", modalidad="", publicado="") -> dict:
    return {
        "fuente": fuente,
        "titulo": _clean(titulo),
        "link": link,
        "empresa": _clean(empresa) or "Confidencial",
        "ubicacion": _clean(ubicacion),
        "salario": _clean(salario),
        "modalidad": _clean(modalidad),
        "publicado": _clean(publicado),
        "minutos": antiguedad_minutos(publicado),
    }


# ---------- URLs de busqueda ----------

def build_search_url(puesto: str, ciudad: str = "") -> str:
    """URL de Computrabajo ordenada por fecha de publicacion."""
    url = f"{CT_BASE}/trabajo-de-{_slug(puesto)}"
    if ciudad:
        url += f"-en-{_slug(ciudad)}"
    return url + "?pubdate=1"


def build_elempleo_url(puesto: str, ciudad: str = "") -> str:
    q = requests.utils.quote(puesto)
    url = f"{EE_BASE}/co/ofertas-empleo/?Search={q}"
    if ciudad:
        url += f"&Cities={requests.utils.quote(ciudad)}"
    return url


def build_linkedin_url(puesto: str, ciudad: str = "") -> str:
    loc = ciudad or "Colombia"
    if ciudad and "colombia" not in ciudad.lower():
        loc = f"{ciudad}, Colombia"
    return LI_URL.format(q=requests.utils.quote(puesto),
                         loc=requests.utils.quote(loc))


# ---------- Parsers por fuente ----------

def parse_jobs(html_text: str, limit: int = 10) -> list[dict]:
    """Computrabajo."""
    jobs = []
    for block in re.split(r'<article class="box_offer', html_text)[1:]:
        m_title = re.search(
            r'<a class="js-o-link[^"]*"\s+href="([^"]+)"[^>]*>\s*(.+?)\s*</a>',
            block, re.S)
        if not m_title:
            continue
        link = m_title.group(1).split("#")[0]
        m_comp = re.search(r'offer-grid-article-company-url>\s*([^<]+?)\s*<', block)
        m_loc = re.search(
            r'<p class="fs16 fc_base mt5">\s*<span class="mr10">\s*([^<]+?)\s*</span>',
            block)
        m_sal = re.search(r'i_salary"></span>\s*([^<]+?)\s*</span>', block)
        m_mod = re.search(r'i_home"></span>\s*([^<]+?)\s*</span>', block)
        m_pub = re.search(r'<p class="fs13 fc_aux mt15">\s*(.+?)\s*</p>', block, re.S)
        jobs.append(_job(
            "Computrabajo", m_title.group(2),
            CT_BASE + link if link.startswith("/") else link,
            m_comp.group(1) if m_comp else "",
            m_loc.group(1) if m_loc else "",
            m_sal.group(1) if m_sal else "",
            m_mod.group(1) if m_mod else "",
            m_pub.group(1) if m_pub else "",
        ))
        if len(jobs) >= limit:
            break
    return jobs


def parse_elempleo(html_text: str, limit: int = 10) -> list[dict]:
    """El Empleo: los datos vienen en el JSON de data-ga4-offerdata.

    OJO: el buscador de El Empleo solo filtra desde su propio JavaScript; el
    HTML servido trae siempre un listado generico. Por eso las ofertas que
    salen de aqui se filtran despues por relevancia (ver es_relevante) y la
    busqueda real de El Empleo se abre en el navegador (show_jobs_in_browser).
    """
    jobs = []
    blocks = re.split(r'class="col-md-12 result-item', html_text)[1:]
    for block in blocks:
        m_data = re.search(r'data-ga4-offerdata="([^"]+)"', block)
        m_url = re.search(r'data-url="([^"]+)"', block)
        if not m_data or not m_url:
            continue
        try:
            data = json.loads(html.unescape(m_data.group(1)))
        except json.JSONDecodeError:
            continue
        m_pub = re.search(r'js-offer-date[^>]*>.*?</i>\s*(.*?)\s*</span>',
                          block, re.S)
        link = m_url.group(1)
        jobs.append(_job(
            "El Empleo", data.get("title", ""),
            EE_BASE + link if link.startswith("/") else link,
            data.get("company", ""), data.get("location", ""),
            data.get("salary", ""), "",
            m_pub.group(1) if m_pub else "",
        ))
        if len(jobs) >= limit:
            break
    return jobs


def parse_linkedin(html_text: str, limit: int = 10) -> list[dict]:
    """LinkedIn (API publica de invitados)."""
    jobs = []
    for block in re.split(r'<li>', html_text)[1:]:
        m_title = re.search(r'base-search-card__title">\s*(.+?)\s*</h3>', block, re.S)
        m_link = re.search(r'base-card__full-link[^"]*"\s+href="([^"?]+)', block)
        if not m_title or not m_link:
            continue
        m_comp = re.search(r'hidden-nested-link"[^>]*>\s*(.+?)\s*</a>', block, re.S)
        m_loc = re.search(r'job-search-card__location">\s*(.+?)\s*</span>', block, re.S)
        m_pub = re.search(r'<time[^>]*>\s*(.+?)\s*</time>', block, re.S)
        jobs.append(_job(
            "LinkedIn", m_title.group(1), html.unescape(m_link.group(1)),
            m_comp.group(1) if m_comp else "",
            m_loc.group(1) if m_loc else "",
            "", "",
            m_pub.group(1) if m_pub else "",
        ))
        if len(jobs) >= limit:
            break
    return jobs


# ---------- Relevancia ----------

_STOPWORDS = {"de", "en", "para", "con", "el", "la", "un", "una", "y", "o"}


def es_relevante(titulo: str, puesto: str) -> bool:
    """La oferta habla del cargo buscado? Evita que 'desarrollador' traiga
    'auxiliar de cocina'. Basta con que coincida una palabra significativa."""
    t = _slug(titulo).replace("-", " ")
    palabras = [w for w in _slug(puesto).replace("-", " ").split()
                if w not in _STOPWORDS and len(w) > 2]
    if not palabras:
        return True
    return any(w in t for w in palabras)


# ---------- Descarga en paralelo ----------

def _fetch(url: str) -> str:
    r = requests.get(url, timeout=TIMEOUT, headers=_HEADERS)
    r.raise_for_status()
    return r.text


def fetch_all(puesto: str, ciudad: str = "", per_source: int = 15) -> list[dict]:
    """Consulta las fuentes en paralelo. Una fuente caida no rompe el resto.
    Solo devuelve ofertas relevantes al cargo buscado."""
    tareas = [
        (build_search_url(puesto, ciudad), parse_jobs),
        (build_linkedin_url(puesto, ciudad), parse_linkedin),
        (build_elempleo_url(puesto, ciudad), parse_elempleo),
    ]
    resultados: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futuros = {pool.submit(_fetch, url): parser for url, parser in tareas}
        try:
            for fut in concurrent.futures.as_completed(futuros, timeout=TIMEOUT + 10):
                parser = futuros[fut]
                try:
                    resultados.extend(parser(fut.result(), per_source))
                except Exception:
                    continue  # fuente caida: seguimos con las demas
        except concurrent.futures.TimeoutError:
            pass  # nos quedamos con lo que alcanzo a llegar

    # Filtrar ruido y duplicados (misma oferta en dos portales)
    vistos = set()
    limpios = []
    for j in resultados:
        if not es_relevante(j["titulo"], puesto):
            continue
        clave = (_slug(j["titulo"]), _slug(j["empresa"]))
        if clave in vistos:
            continue
        vistos.add(clave)
        limpios.append(j)
    return limpios


# ---------- API publica ----------

def search_jobs(puesto: str, ciudad: str = "", limit: int = 8) -> ActionPlan:
    """Busca en Computrabajo + El Empleo + LinkedIn, ordena por mas reciente."""
    global _last_results, _last_url, _last_query
    donde = f" en {ciudad}" if ciudad else " en Colombia"
    plan = ActionPlan(action="buscar_empleo",
                      params={"puesto": puesto, "ciudad": ciudad},
                      risk=RiskLevel.READ,
                      reason=f"Buscar empleo de {puesto}{donde}")
    try:
        jobs = fetch_all(puesto, ciudad)
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar los portales de empleo. Verifique su conexion."
        return plan

    if not jobs:
        _last_query = (puesto, ciudad)
        _last_url = build_search_url(puesto, ciudad)
        plan.result = (f"No encontre ofertas de '{puesto}'{donde}, senor. "
                       "Intente con otro cargo o ciudad, o diga 'muestrame las "
                       "ofertas' para buscar en los portales directamente.")
        plan.status = ActionStatus.EXECUTED
        _last_results = []
        return plan

    # De la mas reciente a la mas antigua
    jobs.sort(key=lambda j: j["minutos"])
    jobs = jobs[:limit]
    _last_results = jobs
    _last_url = build_search_url(puesto, ciudad)
    _last_query = (puesto, ciudad)

    lines = []
    for i, j in enumerate(jobs, 1):
        cuando = _fmt_antiguedad(j["minutos"]) or j["publicado"]
        cab = f"  {i}. [{j['fuente']}] {j['titulo']} — {j['empresa']}"
        if cuando:
            cab += f" ({cuando})"
        detalles = " | ".join(x for x in (j["ubicacion"], j["salario"], j["modalidad"]) if x)
        lines.append(cab + (f"\n     {detalles}" if detalles else ""))

    fuentes = ", ".join(sorted({j["fuente"] for j in jobs}))
    plan.result = (
        f"Ofertas mas recientes de {puesto}{donde} ({fuentes}), senor:\n"
        + "\n".join(lines)
        + "\n\nDiga 'abre la oferta N' para verla, o 'muestrame las ofertas' "
          "para abrir la busqueda en el navegador.")
    plan.status = ActionStatus.EXECUTED
    return plan


def open_job(number: int) -> ActionPlan:
    """Abre en el navegador la oferta N de la ultima busqueda."""
    plan = ActionPlan(action="abrir_oferta", params={"numero": number},
                      risk=RiskLevel.EXECUTE, reason=f"Abrir oferta {number}")
    if not _last_results:
        plan.status = ActionStatus.ERROR
        plan.result = ("No hay una busqueda reciente, senor. Primero diga "
                       "'busca trabajo de <cargo> en <ciudad>'.")
        return plan
    if not 1 <= number <= len(_last_results):
        plan.status = ActionStatus.ERROR
        plan.result = (f"Solo tengo {len(_last_results)} ofertas, senor. "
                       f"Elija entre 1 y {len(_last_results)}.")
        return plan
    job = _last_results[number - 1]
    try:
        webbrowser.open(job["link"])
        plan.result = (f"Abriendo la oferta {number} de {job['fuente']}: "
                       f"{job['titulo']} en {job['empresa']}, senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude abrir la oferta: {e}"
    return plan


def last_search_url() -> str:
    """URL de la ultima busqueda (para el navegador automatizado)."""
    return _last_url


def last_query() -> tuple[str, str]:
    """(puesto, ciudad) de la ultima busqueda."""
    return _last_query


def portal_urls(puesto: str, ciudad: str = "") -> dict[str, str]:
    """URLs de busqueda de los tres portales, para abrirlas en el navegador."""
    return {
        "Computrabajo": build_search_url(puesto, ciudad),
        "El Empleo": build_elempleo_url(puesto, ciudad),
        "LinkedIn": (f"https://www.linkedin.com/jobs/search?keywords="
                     f"{requests.utils.quote(puesto)}&location="
                     f"{requests.utils.quote(ciudad or 'Colombia')}&sortBy=DD"),
    }
