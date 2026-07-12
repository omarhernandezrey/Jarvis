"""
JARVIS Local - Busqueda de empleo en Computrabajo (Fase 5)
Busca ofertas por puesto y ciudad, las lee en voz alta y puede abrirlas.
Scraping ligero con requests (sin API key). Colombia: co.computrabajo.com
"""
import html
import re
import unicodedata
import webbrowser
import requests
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus

BASE = "https://co.computrabajo.com"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept-Language": "es-CO,es;q=0.9",
}

# Ultimos resultados para "abre la oferta N" y "muestrame las ofertas"
_last_results: list[dict] = []
_last_url: str = ""


def _slug(text: str) -> str:
    """'Desarrollador Web' -> 'desarrollador-web' (sin acentos)."""
    t = unicodedata.normalize("NFD", text.lower().strip())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s-]", "", t)
    return re.sub(r"[\s-]+", "-", t).strip("-")


def build_search_url(puesto: str, ciudad: str = "") -> str:
    url = f"{BASE}/trabajo-de-{_slug(puesto)}"
    if ciudad:
        url += f"-en-{_slug(ciudad)}"
    return url


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_jobs(html_text: str, limit: int = 5) -> list[dict]:
    """Extrae ofertas del HTML de resultados de Computrabajo."""
    jobs = []
    blocks = re.split(r'<article class="box_offer', html_text)[1:]
    for block in blocks:
        m_title = re.search(
            r'<a class="js-o-link[^"]*"\s+href="([^"]+)"[^>]*>\s*(.+?)\s*</a>',
            block, re.S)
        if not m_title:
            continue
        link = m_title.group(1).split("#")[0]
        job = {
            "titulo": _clean(m_title.group(2)),
            "link": BASE + link if link.startswith("/") else link,
            "empresa": "Confidencial",
            "ubicacion": "",
            "salario": "",
            "modalidad": "",
            "publicado": "",
        }
        m_comp = re.search(r'offer-grid-article-company-url>\s*([^<]+?)\s*<', block)
        if m_comp:
            job["empresa"] = _clean(m_comp.group(1))
        m_loc = re.search(
            r'<p class="fs16 fc_base mt5">\s*<span class="mr10">\s*([^<]+?)\s*</span>',
            block)
        if m_loc:
            job["ubicacion"] = _clean(m_loc.group(1))
        m_sal = re.search(r'i_salary"></span>\s*([^<]+?)\s*</span>', block)
        if m_sal:
            job["salario"] = _clean(m_sal.group(1))
        m_mod = re.search(r'i_home"></span>\s*([^<]+?)\s*</span>', block)
        if m_mod:
            job["modalidad"] = _clean(m_mod.group(1))
        m_pub = re.search(r'<p class="fs13 fc_aux mt15">\s*(.+?)\s*</p>', block, re.S)
        if m_pub:
            job["publicado"] = _clean(m_pub.group(1))
        jobs.append(job)
        if len(jobs) >= limit:
            break
    return jobs


def search_jobs(puesto: str, ciudad: str = "", limit: int = 5) -> ActionPlan:
    """Busca ofertas de empleo en Computrabajo."""
    global _last_results, _last_url
    donde = f" en {ciudad}" if ciudad else " en Colombia"
    plan = ActionPlan(action="buscar_empleo",
                      params={"puesto": puesto, "ciudad": ciudad},
                      risk=RiskLevel.READ,
                      reason=f"Buscar empleo de {puesto}{donde}")
    try:
        url = build_search_url(puesto, ciudad)
        _last_url = url
        r = requests.get(url, timeout=25, headers=_HEADERS)
        r.raise_for_status()
        jobs = parse_jobs(r.text, limit)
        if not jobs:
            plan.result = (f"No encontre ofertas de '{puesto}'{donde}, senor. "
                           "Intente con otro cargo o ciudad.")
            plan.status = ActionStatus.EXECUTED
            _last_results = []
            return plan
        _last_results = jobs
        lines = []
        for i, j in enumerate(jobs, 1):
            extra = " | ".join(x for x in (j["salario"], j["modalidad"], j["publicado"]) if x)
            lines.append(f"  {i}. {j['titulo']} — {j['empresa']}"
                         + (f" ({j['ubicacion']})" if j["ubicacion"] else "")
                         + (f"\n     {extra}" if extra else ""))
        plan.result = (f"Encontre estas ofertas de {puesto}{donde}, senor:\n"
                       + "\n".join(lines)
                       + "\n\nDiga 'abre la oferta N' para ver una en el navegador, "
                         "o 'muestrame las ofertas' para abrir la busqueda completa.")
        plan.status = ActionStatus.EXECUTED
        plan.params["url"] = url
    except requests.RequestException as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = "No pude consultar Computrabajo. Verifique su conexion a internet."
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
        plan.result = f"Solo tengo {len(_last_results)} ofertas, senor. Elija entre 1 y {len(_last_results)}."
        return plan
    job = _last_results[number - 1]
    try:
        webbrowser.open(job["link"])
        plan.result = f"Abriendo la oferta {number}: {job['titulo']} en {job['empresa']}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude abrir la oferta: {e}"
    return plan


def last_search_url() -> str:
    """URL de la ultima busqueda (para abrirla en el navegador automatizado)."""
    return _last_url
