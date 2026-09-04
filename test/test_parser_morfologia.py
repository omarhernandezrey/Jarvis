"""FASE C · C1 — Normalización morfológica del parser.

El parser casaba formas de superficie ("abre", "manda", "de") y fallaba con
enclíticos ("abrime", "mándale"), voseo irregular ("podés") y la contracción
"del". Se normaliza el texto UNA vez antes de aplicar los patrones, con una
lista de VERBOS (no de frases). Blinda:

  - split de enclíticos guiado por raíces de mando + infinitivos + gerundios;
  - un verbo con clítico y nada más ("hazlo", "búscalo ya") NO se parte:
    es una orden vaga y debe seguir cayendo en la aclaración del agente;
  - verbos con frase enclítica fija ("ponme al día", "recuérdame…") intactos;
  - voseo irregular → tuteo;
  - los 4 fallos del banco que ataca C1: A04, B02, E04, E05.
"""
import pytest

from jarvis_local.intent.parser import _normalizar_morfologia as N
from jarvis_local.intent.parser import parse_intent

# ---------- split de enclíticos ----------

@pytest.mark.parametrize("dado, esperado", [
    ("abrime chrome", "abre me chrome"),
    ("abreme chrome", "abre me chrome"),
    ("abrirme chrome", "abrir me chrome"),
    ("cierrame el spotify", "cierra me el spotify"),
    ("mandale un correo a ana", "manda le un correo a ana"),
    ("mandamelo a ana", "manda melo a ana"),
    ("enviaselo al jefe", "envia selo al jefe"),
    ("enviarle el archivo a ana", "enviar le el archivo a ana"),
])
def test_split_enclitico(dado, esperado):
    assert N(dado) == esperado


@pytest.mark.parametrize("frase", [
    # verbos con gate que ya absorbe el clítico -> NO se parten (sin regresión)
    "leeme el archivo notas.txt", "buscame trabajo de contador",
    "muestrame la carpeta de descargas", "cuentame un chiste bueno",
])
def test_verbos_con_gate_absorbente_no_se_parten(frase):
    assert N(frase) == frase


# ---------- orden vaga: NO se parte ----------

@pytest.mark.parametrize("frase", [
    "hazlo", "buscalo", "ponlo", "mandalo", "buscalo ya", "mandalo pues",
    "hazlo ya parce", "reproducelo", "abrelo", "borralo",
])
def test_orden_vaga_no_se_parte(frase):
    # el verbo+clítico queda tal cual (o al menos no gana un objeto falso)
    assert N(frase) == frase


# ---------- verbos con frase enclítica fija: intactos ----------

@pytest.mark.parametrize("frase", [
    "ponme al dia", "recuerdame en 10 minutos sacar la ropa",
    "cuentame un chiste", "hazme una nota que compre pan",
    "dame la hora", "dile a juan que llego tarde",
])
def test_verbos_excluidos_intactos(frase):
    assert N(frase) == frase


# ---------- voseo irregular → tuteo ----------

@pytest.mark.parametrize("dado, esperado", [
    ("vos podes con eso", "vos puedes con eso"),
    ("no sentis frio?", "no sientes frio?"),
    ("tenes razon", "tienes razon"),
    ("queres que lo haga", "quieres que lo haga"),
    ("que decis vos", "que dices vos"),
])
def test_voseo_irregular(dado, esperado):
    assert N(dado) == esperado


def test_texto_sin_morfologia_intacto():
    for s in ["pon bohemian rhapsody", "5 al cubo", "como anda la maquina",
              "que clima hace en bogota", "abre chrome"]:
        assert N(s) == s


# ---------- los 4 fallos del banco que ataca C1 ----------

def test_A04_abrime_va_al_parser():
    ir = parse_intent("abrime chrome")
    assert ir.kind == "tool_execute" and ir.tool == "open_app"
    assert ir.arguments["app"] == "chrome"


def test_B02_opinion_del_clima_no_dispara_weather():
    ir = parse_intent("que opinas del clima loco que ha hecho estos dias")
    assert ir.kind == "chat"


def test_E04_oculta_del_escritorio_es_plan():
    ir = parse_intent("oculta todos los archivos del escritorio")
    assert ir.kind == "tool_plan" and ir.tool == "hide_files"
    assert ir.arguments["path"] == "escritorio"


def test_E05_mandale_correo_diciendole_es_plan():
    ir = parse_intent("mandale un correo a juan@example.com diciendole que renuncio")
    assert ir.kind == "tool_plan" and ir.tool == "send_email"
    assert ir.arguments["to"] == "juan@example.com"
    assert "renuncio" in ir.arguments["body"].lower()


# ---------- no-regresión ----------

@pytest.mark.parametrize("frase, kind", [
    ("hazlo", "chat"),
    ("ponlo ahi", "chat"),
    ("buscalo", "chat"),
    ("abreme la segunda", "chat"),           # anafórica: sigue yendo al agente
])
def test_ordenes_vagas_siguen_en_chat(frase, kind):
    assert parse_intent(frase).kind == kind


@pytest.mark.parametrize("frase", [
    "que clima hace en bogota", "va a llover en medellin manana",
    "como esta el tiempo en cartagena", "clima en cali",
])
def test_consultas_de_clima_siguen_disparando_weather(frase):
    ir = parse_intent(frase)
    assert ir.kind == "tool_read" and ir.tool == "weather"


def test_pon_cancion_sigue_a_spotify():
    ir = parse_intent("pon bohemian rhapsody")
    assert ir.tool == "spotify_play"


def test_ponme_al_dia_sigue_a_briefing():
    assert parse_intent("ponme al dia").tool == "daily_briefing"


def test_calculo_al_cubo_intacto():
    ir = parse_intent("5 al cubo")
    assert ir.tool == "calculate"
