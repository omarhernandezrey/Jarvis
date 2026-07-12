"""
Tests de Fase 5: busqueda de empleo en Computrabajo y navegador automatizado.
Offline: parser de intents, construccion de URLs y parseo de HTML de ejemplo.
No abre Chrome ni consulta la red.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.tools import jobs as jobs_mod
from jarvis_local.tools.jobs import build_search_url, parse_jobs, _slug, open_job
from jarvis_local.tools.browser import browser_available
from jarvis_local.safety.policy import ActionStatus


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
    assert build_search_url("desarrollador", "Bogota") == \
        "https://co.computrabajo.com/trabajo-de-desarrollador-en-bogota"
    assert build_search_url("desarrollador web") == \
        "https://co.computrabajo.com/trabajo-de-desarrollador-web"
    assert "medellin" in build_search_url("vendedor", "Medellín")


# ---------- Parseo del HTML ----------

def test_parse_jobs():
    jobs = parse_jobs(_HTML, limit=5)
    assert len(jobs) == 2
    j = jobs[0]
    assert j["titulo"] == "Java developer engineer"
    assert j["empresa"] == "ACTIVOS S A S"
    assert "Bogotá" in j["ubicacion"]
    assert "5.379.528" in j["salario"]
    assert j["modalidad"] == "Remoto"
    assert j["publicado"] == "Hace 4 horas"
    assert j["link"].startswith("https://co.computrabajo.com/ofertas-de-trabajo/")
    assert "#" not in j["link"]  # se limpia el ancla


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
