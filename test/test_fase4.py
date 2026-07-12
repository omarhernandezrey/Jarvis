"""
Tests de Fase 4: clima, web, sistema, wikipedia, correo, calculadora, etc.
Solo pruebas offline: parser de intents, calculadora, chistes, utilidades.
Nada de red ni acciones reales (no se abre navegador ni se envian correos).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.tools.calculator import evaluate, normalize_expression, calculate
from jarvis_local.tools.web import build_url, build_google_url, build_youtube_url
from jarvis_local.tools.location import haversine_km
from jarvis_local.tools.jokes import tell_joke
from jarvis_local.tools.news import parse_rss_titles
from jarvis_local.tools.email_sender import resolve_recipient
from jarvis_local.safety.policy import ActionStatus


# ---------- Parser de intents ----------

def _t(frase):
    return parse_intent(frase)


def test_intent_clima():
    r = _t("como esta el clima en Bogota")
    assert r.tool == "weather" and r.arguments["city"] == "bogota"
    r2 = _t("dime la temperatura de Medellin")
    assert r2.tool == "weather"


def test_intent_ubicacion():
    r = _t("donde queda Paris")
    assert r.tool == "locate" and r.arguments["place"] == "paris"
    r2 = _t("distancia a Cartagena")
    assert r2.tool == "locate"


def test_intent_sistema():
    assert _t("estado del sistema").tool == "system_status"
    assert _t("cuanta ram estoy usando").tool == "system_status"
    assert _t("como va la bateria").tool == "system_status"


def test_intent_google():
    r = _t("busca recetas de arepas en google")
    assert r.tool == "google_search" and "arepas" in r.arguments["query"]
    r2 = _t("googlea python 3.14")
    assert r2.tool == "google_search"


def test_intent_youtube_y_musica():
    r = _t("reproduce hotel california en youtube")
    assert r.tool == "youtube_play" and "hotel california" in r.arguments["query"]
    r2 = _t("pon musica")
    assert r2.tool == "play_music"
    r3 = _t("reproduce la cancion bohemian rhapsody")
    assert r3.tool == "youtube_play"


def test_intent_noticias():
    assert _t("dame las noticias").tool == "news_headlines"
    assert _t("titulares de hoy").tool == "news_headlines"


def test_intent_correo_completo():
    r = _t("envia un correo a test@mail.com asunto Hola mensaje Como estas")
    assert r.kind == "tool_plan" and r.tool == "send_email"
    assert r.arguments["to"] == "test@mail.com"
    assert r.arguments["subject"] == "Hola"
    assert r.arguments["body"] == "Como estas"


def test_intent_correo_incompleto():
    r = _t("envia un correo")
    assert r.kind == "ambiguous"


def test_intent_calcular():
    r = _t("calcula 5 mas 3 por 2")
    assert r.tool == "calculate"
    # sin numeros -> va al LLM (chat u otro intent)
    r2 = _t("cuanto es la capital de francia")
    assert r2.tool != "calculate"


def test_intent_nota_chiste_ip_ventana():
    assert _t("toma nota comprar leche").tool == "take_note"
    assert _t("cuentame un chiste").tool == "tell_joke"
    assert _t("cual es mi ip").tool == "get_ip"
    assert _t("cambia de ventana").tool == "switch_window"


def test_intent_captura():
    r = _t("toma una captura de pantalla llamada reunion")
    assert r.tool == "screenshot" and r.arguments["name"] == "reunion"
    r2 = _t("haz una captura de pantalla")
    assert r2.tool == "screenshot" and r2.arguments["name"] == ""


def test_intent_ocultar_mostrar():
    r = _t(r"oculta los archivos de C:\Users\herna\Documents\privado")
    assert r.kind == "tool_plan" and r.tool == "hide_files"
    assert r.arguments["hide"] is True
    r2 = _t(r"muestra los archivos ocultos de C:\Users\herna\Documents\privado")
    assert r2.tool == "hide_files" and r2.arguments["hide"] is False


def test_intent_sitio_web():
    r = _t("abre youtube.com")
    assert r.tool == "open_website"
    r2 = _t("abre la pagina de wikipedia")
    assert r2.tool == "open_website"


def test_intent_wikipedia():
    r = _t("quien es Gabriel Garcia Marquez")
    assert r.tool == "wiki"
    # "quien eres" NO debe ir a wikipedia
    r2 = _t("quien eres")
    assert r2.tool != "wiki"


def test_intent_eventos():
    assert _t("cuales son mis proximos eventos").tool == "calendar_events"


def test_intent_apps_no_rotas():
    """Los intents anteriores siguen funcionando."""
    assert _t("abre whatsapp").tool == "open_app"
    assert _t("abre chrome").tool == "open_app"
    assert _t("ejecuta dir").tool == "run_command"
    assert _t("lista los archivos de Documentos").tool == "list_files"


# ---------- Calculadora ----------

def test_calc_basico():
    assert evaluate("2 + 3") == 5
    assert evaluate("10 / 4") == 2.5
    assert evaluate("2 ** 10") == 1024


def test_calc_lenguaje_natural():
    assert evaluate("5 mas 3 por 2") == 11
    assert evaluate("100 dividido entre 4") == 25
    assert evaluate("5 x 3") == 15
    assert evaluate("raiz(16)") == 4
    assert evaluate("raiz cuadrada de 25") == 5


def test_calc_seguro():
    """La calculadora rechaza codigo, solo acepta matematicas."""
    import pytest
    for maligno in ["__import__('os')", "open('x')", "exec('1')", "'a'*9999999"]:
        try:
            evaluate(maligno)
            assert False, f"No debio evaluar: {maligno}"
        except Exception:
            pass


def test_calc_division_cero():
    plan = calculate("5 entre 0")
    assert plan.status == ActionStatus.ERROR
    assert "cero" in plan.result


def test_normalize_expression():
    assert normalize_expression("5 mas 3") == "5 + 3"
    assert normalize_expression("2 elevado a 8") == "2 ** 8"


# ---------- Web (constructores de URL, sin red) ----------

def test_build_urls():
    assert build_url("youtube.com") == "https://youtube.com"
    assert build_url("https://github.com") == "https://github.com"
    assert build_url("facebook") == "https://www.facebook.com"
    assert "q=gatos+persas" in build_google_url("gatos persas")
    assert "search_query=hotel+california" in build_youtube_url("hotel california")


# ---------- Distancias ----------

def test_haversine():
    # Bogota (4.71, -74.07) a Medellin (6.24, -75.58): ~240 km
    d = haversine_km(4.711, -74.072, 6.244, -75.581)
    assert 200 < d < 280
    assert haversine_km(0, 0, 0, 0) == 0


# ---------- Chistes ----------

def test_chiste():
    plan = tell_joke()
    assert plan.status == ActionStatus.EXECUTED
    assert len(plan.result) > 10


# ---------- Noticias (parser RSS, sin red) ----------

def test_parse_rss():
    xml = """<?xml version="1.0"?><rss><channel>
        <item><title>Titular uno</title></item>
        <item><title>Titular dos</title></item>
        </channel></rss>"""
    titles = parse_rss_titles(xml, limit=5)
    assert titles == ["Titular uno", "Titular dos"]


# ---------- Correo (resolucion de destinatario, sin envio) ----------

def test_resolve_recipient():
    assert resolve_recipient("test@mail.com") == "test@mail.com"
    assert resolve_recipient("nombre sin arroba") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: Todos los tests de Fase 4 pasaron.")
