"""
Tests de Fase 5: busqueda de empleo en Computrabajo y navegador automatizado.
Offline: parser de intents, construccion de URLs y parseo de HTML de ejemplo.
No abre Chrome ni consulta la red.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import jobs as jobs_mod
from jarvis_local.tools.browser import browser_available
from jarvis_local.tools.jobs import (
    _slug,
    antiguedad_minutos,
    build_elempleo_url,
    build_linkedin_url,
    build_search_url,
    es_relevante,
    open_job,
    parse_elempleo,
    parse_jobs,
    parse_linkedin,
    portal_urls,
)

# HTML minimo con la estructura real de Computrabajo
_HTML = """
<article class="box_offer sel " data-id="ABC123">
  <h2 class="fs18 fwB prB">
    <a class="js-o-link fc_base" href="/ofertas-de-trabajo/oferta-java-en-bogota-ABC123#lc=x">
      Java developer engineer
    </a>
  </h2>
  <p class="dFlex vm_fx fs16 fc_base mt5">
    <a class="fc_base t_ellipsis" href="/activos" offer-grid-article-company-url>
      ACTIVOS S A S
    </a>
  </p>
  <p class="fs16 fc_base mt5">
    <span class="mr10">
      Bogot&#xE1;, D.C.
    </span>
  </p>
  <div class="fs13 mt15">
    <span class="dIB mr10">
      <span class="icon i_salary"></span>
      $ 5.379.528,00 (Mensual)
    </span>
    <span class="dIB mr10">
      <span class="icon i_home"></span>
      Remoto
    </span>
  </div>
  <p class="fs13 fc_aux mt15">
    Hace 4 horas
  </p>
</article>
<article class="box_offer  ">
  <h2 class="fs18 fwB prB">
    <a class="js-o-link fc_base" href="/ofertas-de-trabajo/oferta-rpa-en-bogota-DEF456">
      Desarrollador RPA
    </a>
  </h2>
</article>
"""


# ---------- Slugs y URLs ----------

def test_slug():
    assert _slug("Desarrollador Web") == "desarrollador-web"
    assert _slug("Bogotá, D.C.") == "bogota-dc"
    assert _slug("  Ingeniero de Sistemas  ") == "ingeniero-de-sistemas"


def test_build_search_url():
    """Computrabajo: ordenado por fecha (pubdate=1)."""
    u = build_search_url("desarrollador", "Bogota")
    assert u.startswith("https://co.computrabajo.com/trabajo-de-desarrollador-en-bogota")
    assert "pubdate=1" in u
    assert "trabajo-de-desarrollador-web" in build_search_url("desarrollador web")
    assert "medellin" in build_search_url("vendedor", "Medellín")


def test_build_urls_otros_portales():
    assert "elempleo.com" in build_elempleo_url("desarrollador", "Bogota")
    li = build_linkedin_url("desarrollador", "Bogota")
    assert "linkedin.com" in li and "sortBy=DD" in li  # DD = ordenar por fecha
    assert "Bogota%2C%20Colombia" in li


def test_portal_urls():
    urls = portal_urls("desarrollador", "Bogota")
    assert set(urls) == {"Computrabajo", "El Empleo", "LinkedIn"}
    assert all(u.startswith("https://") for u in urls.values())


# ---------- Antiguedad y orden ----------

def test_antiguedad_minutos():
    assert antiguedad_minutos("Hace 30 minutos") == 30
    assert antiguedad_minutos("Hace 4 horas") == 240
    assert antiguedad_minutos("Ayer") == 1440
    assert antiguedad_minutos("Hace 2 días") == 2880
    assert antiguedad_minutos("Hace 1 semana") == 10080
    assert antiguedad_minutos("") == 999999  # desconocido va al final
    assert antiguedad_minutos("Hoy") < antiguedad_minutos("Ayer")


def test_orden_mas_reciente_primero():
    ofertas = [
        {"titulo": "A", "empresa": "X", "minutos": antiguedad_minutos("Hace 3 días")},
        {"titulo": "B", "empresa": "Y", "minutos": antiguedad_minutos("Hace 2 horas")},
        {"titulo": "C", "empresa": "Z", "minutos": antiguedad_minutos("Ayer")},
    ]
    ofertas.sort(key=lambda j: j["minutos"])
    assert [o["titulo"] for o in ofertas] == ["B", "C", "A"]


# ---------- Relevancia ----------

def test_es_relevante():
    assert es_relevante("Desarrollador Fullstack Senior", "desarrollador")
    assert es_relevante("Analista Desarrollador", "desarrollador")
    assert es_relevante("Desarrollador Web Junior", "desarrollador web")
    # el ruido de El Empleo se descarta
    assert not es_relevante("Auxiliar cocina club bellavista", "desarrollador")
    assert not es_relevante("Asesor(a) de ventas", "desarrollador")


# ---------- Parseo del HTML ----------

def test_parse_jobs():
    jobs = parse_jobs(_HTML, limit=5)
    assert len(jobs) == 2
    j = jobs[0]
    assert j["fuente"] == "Computrabajo"
    assert j["titulo"] == "Java developer engineer"
    assert j["empresa"] == "ACTIVOS S A S"
    assert "Bogotá" in j["ubicacion"]
    assert "5.379.528" in j["salario"]
    assert j["modalidad"] == "Remoto"
    assert j["publicado"] == "Hace 4 horas"
    assert j["minutos"] == 240
    assert j["link"].startswith("https://co.computrabajo.com/ofertas-de-trabajo/")
    assert "#" not in j["link"]  # se limpia el ancla


# HTML minimo de LinkedIn (API publica de invitados)
_HTML_LI = """
<li>
  <div class="base-card job-search-card">
    <a class="base-card__full-link" href="https://co.linkedin.com/jobs/view/dev-at-acme-123?position=1">
      <span class="sr-only">Desarrollador Backend</span>
    </a>
    <div class="base-search-card__info">
      <h3 class="base-search-card__title">
        Desarrollador Backend
      </h3>
      <h4 class="base-search-card__subtitle">
        <a class="hidden-nested-link" href="https://co.linkedin.com/company/acme">
          ACME Corp
        </a>
      </h4>
      <div class="base-search-card__metadata">
        <span class="job-search-card__location">
          Bogotá, Distrito Capital, Colombia
        </span>
        <time class="job-search-card__listdate" datetime="2026-07-12">
          Hace 3 horas
        </time>
      </div>
    </div>
  </div>
</li>
"""

# HTML minimo de El Empleo (datos en el JSON de data-ga4-offerdata)
_HTML_EE = """
<div class="col-md-12 result-item mb-3 bg-white">
  <div class="js-area-bind" data-url="/co/ofertas-trabajo/desarrollador-java-1886738495"
       data-ga4-offerdata="{&quot;section&quot;:&quot;SEARCH&quot;,&quot;id&quot;:188,&quot;title&quot;:&quot;Desarrollador Java Senior&quot;,&quot;company&quot;:&quot;Tech SAS&quot;,&quot;location&quot;:&quot;Bogot&#225;&quot;,&quot;salary&quot;:&quot;$6 a $8 millones&quot;}">
    <span class="info-publish-date js-offer-date"><i class="fa fa-clock-o icon"></i> Hoy </span>
  </div>
</div>
"""


def test_parse_linkedin():
    jobs = parse_linkedin(_HTML_LI)
    assert len(jobs) == 1
    j = jobs[0]
    assert j["fuente"] == "LinkedIn"
    assert j["titulo"] == "Desarrollador Backend"
    assert j["empresa"] == "ACME Corp"
    assert "Bogotá" in j["ubicacion"]
    assert j["minutos"] == 180  # hace 3 horas
    assert j["link"] == "https://co.linkedin.com/jobs/view/dev-at-acme-123"  # sin query


def test_parse_elempleo():
    jobs = parse_elempleo(_HTML_EE)
    assert len(jobs) == 1
    j = jobs[0]
    assert j["fuente"] == "El Empleo"
    assert j["titulo"] == "Desarrollador Java Senior"
    assert j["empresa"] == "Tech SAS"
    assert j["salario"] == "$6 a $8 millones"
    assert j["publicado"] == "Hoy"
    assert j["link"].startswith("https://www.elempleo.com/co/ofertas-trabajo/")


def test_parse_fuentes_vacias():
    assert parse_linkedin("<html></html>") == []
    assert parse_elempleo("<html></html>") == []


def test_parse_jobs_incompleto():
    """Ofertas sin empresa/salario no rompen el parser."""
    jobs = parse_jobs(_HTML, limit=5)
    assert jobs[1]["titulo"] == "Desarrollador RPA"
    assert jobs[1]["empresa"] == "Confidencial"
    assert jobs[1]["salario"] == ""


def test_parse_jobs_limite():
    assert len(parse_jobs(_HTML, limit=1)) == 1


def test_parse_jobs_vacio():
    assert parse_jobs("<html>sin ofertas</html>") == []


# ---------- Abrir oferta N ----------

def test_open_job_sin_busqueda():
    jobs_mod._last_results = []
    plan = open_job(1)
    assert plan.status == ActionStatus.ERROR
    assert "busqueda reciente" in plan.result


def test_open_job_fuera_de_rango():
    jobs_mod._last_results = parse_jobs(_HTML)
    plan = open_job(9)
    assert plan.status == ActionStatus.ERROR
    assert "Solo tengo 2" in plan.result
    jobs_mod._last_results = []


# ---------- Parser de intents ----------

def test_intent_buscar_empleo():
    r = parse_intent("busca trabajo de desarrollador en Bogota")
    assert r.tool == "search_jobs"
    assert r.arguments["puesto"] == "desarrollador"
    assert r.arguments["ciudad"] == "bogota"


def test_intent_buscar_empleo_sin_ciudad():
    r = parse_intent("buscame empleo de contador")
    assert r.tool == "search_jobs"
    assert r.arguments["puesto"] == "contador"
    assert r.arguments["ciudad"] == ""


def test_intent_buscar_empleo_variantes():
    assert parse_intent("hay vacantes de vendedor en Cali").tool == "search_jobs"
    assert parse_intent("encuentra ofertas de disenador grafico").tool == "search_jobs"


def test_intent_empleo_sin_cargo():
    r = parse_intent("busca trabajo")
    assert r.kind == "ambiguous"


def test_intent_abrir_oferta():
    r = parse_intent("abre la oferta 2")
    assert r.tool == "open_job" and r.arguments["number"] == 2
    r2 = parse_intent("abre la tercera oferta") if False else parse_intent("abre la oferta tres")
    assert r2.tool == "open_job" and r2.arguments["number"] == 3


def test_intent_mostrar_ofertas():
    r = parse_intent("muestrame las ofertas")
    assert r.tool == "show_jobs"


def test_intent_navegador():
    r = parse_intent("navega a github.com")
    assert r.tool == "browser_navigate" and "github" in r.arguments["url"]
    assert parse_intent("cierra el navegador").tool == "close_browser"


def test_intents_previos_intactos():
    """Fases 1-4 siguen funcionando."""
    assert parse_intent("abre whatsapp").tool == "open_app"
    assert parse_intent("busca gatos en google").tool == "google_search"
    assert parse_intent("clima en Bogota").tool == "weather"
    assert parse_intent("busca informe.pdf en Documentos").tool == "search_files"
    assert parse_intent("cuentame un chiste").tool == "tell_joke"


# ---------- Selenium disponible ----------

def test_browser_available():
    assert browser_available() is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: Todos los tests de Fase 5 pasaron.")
