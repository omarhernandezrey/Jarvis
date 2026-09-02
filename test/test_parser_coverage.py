"""Batería de cobertura del parser determinista (PLAN_MAESTRO · TAREA A1).

Frases reales en español coloquial → intención esperada. Es la red que evita
que un cambio en `parser.py` haga que una frase ya "conocida" se escape al
agente lento (o al chat).

Convención:
  - Caso que HOY funciona  → aserción normal (debe seguir pasando).
  - Caso roto conocido     → `pytest.param(..., marks=pytest.mark.xfail(...))`.
    La tarea que lo arregle QUITA su marca xfail.
  - Conversación pura      → se espera `kind == "chat"`.

`expect` es:
  - un str  → se compara con `IntentResult.tool`
  - `"chat"`/`"ambiguous"` → se compara con `IntentResult.kind`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from jarvis_local.intent.parser import (
    dividir_acciones,
    es_multi_accion,
    parse_intent,
)

_B3 = pytest.mark.xfail(strict=True, reason="TAREA B3 — ecuaciones lineales")


# ── (frase, esperado, marks) ────────────────────────────────────────────────
CASES = [
    # ---- apps y ventanas ----
    ("abre whatsapp", "open_app"),
    ("abre el chrome", "open_app"),
    ("lanza android studio", "open_app"),          # A6
    ("lanza notion", "open_app"),                  # A6
    ("inicia docker", "open_app"),                 # A6
    ("abre algo", "ambiguous"),                    # A6: objeto vago -> aclarar
    ("lanza ls -la", "run_command"),               # A6: pinta de shell -> comando
    ("abre la calculadora", "open_app"),
    ("cierra spotify", "close_app"),
    ("cierra todo", "close_all_apps"),
    ("bloquea el equipo", "lock_pc"),
    ("toma una captura de pantalla", "screenshot"),
    ("hazme un screenshot", "screenshot"),

    # ---- volumen y multimedia ----
    ("sube el volumen", "volume_up"),
    ("baja el volumen", "volume_down"),
    ("sube el volumen al 30", "volume_set"),
    ("silencia", "volume_mute"),
    ("pausa la musica", "media_play_pause"),
    ("siguiente cancion", "media_next"),
    ("cancion anterior", "media_previous"),

    # ---- energia ----
    ("apaga el equipo", "shutdown_pc"),
    ("reinicia el pc", "restart_pc"),
    ("cancela el apagado", "cancel_shutdown"),

    # ---- clima ----
    ("clima en Bogota", "weather"),
    ("como esta el clima en Cali", "weather"),
    ("temperatura en Lima", "weather"),
    ("el clima de hoy en Quito", "weather"),
    ("que tiempo hace en Medellin", "weather"),              # A3
    ("va a llover en Cartagena", "weather"),                 # A3
    ("como estara el tiempo manana en Pasto", "weather"),    # A3
    ("pronostico para Cucuta", "weather"),                   # A3
    ("que tiempo hara el sabado en Cali", "weather"),        # A3
    ("cuanto tiempo falta para navidad", "chat"),            # A3 negativo
    ("hace tiempo que no te veo", "chat"),                   # A3 negativo

    # ---- Spotify / musica ----
    ("reproduce a Bad Bunny", "spotify_play"),
    ("pon musica de los Beatles", "spotify_play"),
    ("pon musica", "play_music"),
    ("pon bohemian rhapsody", "spotify_play"),          # A2
    ("pon algo de Shakira", "spotify_play"),            # A2
    ("pon la de Queen", "spotify_play"),                # A2
    ("ponme reggaeton", "spotify_play"),               # A2
    ("pon la cancion despacito", "spotify_play"),       # A2
    ("pon una de Soda Stereo", "spotify_play"),         # A2

    # ---- web ----
    ("busca en google gatos", "google_search"),
    ("abre https://example.com", "open_website"),
    ("reproduce lofi en youtube", "youtube_play"),
    ("abre youtube", "open_website"),          # A5
    ("abre el youtube", "open_website"),       # A5
    ("abre gmail", "open_website"),            # A5
    ("abre netflix", "open_website"),          # A5
    ("abre spotify", "open_app"),              # A5: sitio conocido NO roba app instalada

    # ---- info ----
    ("quien es Gabriel Garcia Marquez", "wiki"),
    ("cuentame sobre la revolucion francesa", "wiki"),
    ("noticias de hoy", "news_headlines"),
    ("dame los titulares", "news_headlines"),
    ("cual es mi ip", "get_ip"),
    ("estado del sistema", "system_status"),
    ("como anda la maquina", "system_status"),     # A7
    ("que tal el equipo", "system_status"),        # A7
    ("como van los recursos", "system_status"),    # A7
    ("esta pesado el pc", "system_status"),        # A7
    ("como va todo", "chat"),                      # A7 negativo (conversacion)
    ("como anda el proyecto", "chat"),             # A7 negativo
    ("cuentame un chiste", "tell_joke"),
    ("dame el resumen del dia", "daily_briefing"),
    ("pregunta a wolfram la derivada de x^2", "wolfram"),
    ("donde queda la Torre Eiffel", "locate"),

    # ---- calculadora ----
    ("calcula 15 * 3 + 2", "calculate"),
    ("cuanto es 300 dividido 7", "calculate"),
    ("cuanto es 20% de 350", "calculate"),
    ("raiz cuadrada de 144", "calculate"),        # B2
    ("el factorial de 5", "calculate"),            # B2
    ("20% de 350", "calculate"),                   # B2
    ("5 al cubo", "calculate"),                    # B2
    pytest.param("resuelve x + 135 - 234 = 345", "calculate", marks=_B3),
    pytest.param("despeja x en 2x + 4 = 10", "calculate", marks=_B3),

    # ---- recordatorios ----
    ("recuerdame llamar a mama en 10 minutos", "set_reminder"),
    ("recuerdame la reunion manana a las 3", "set_reminder"),
    ("lista mis recordatorios", "list_reminders"),
    ("cancela todos los recordatorios", "cancel_reminder"),

    # ---- notas ----
    ("toma nota comprar pan", "take_note"),
    ("apunta que debo renovar el pasaporte", "take_note"),
    ("crea una nota comprar pan", "take_note"),                    # A4
    ("nueva nota llamar al banco", "take_note"),                   # A4
    ("guardame una nota con la clave del wifi", "take_note"),      # A4
    ("apuntame que debo pagar la luz", "take_note"),               # A4
    ("hazme una nota sobre el proyecto", "take_note"),             # A4
    ("crea un recordatorio para manana a las 3", "set_reminder"),  # A4: no colisiona
    ("crea un archivo notas.txt en Documentos", "create_file"),    # A4: no colisiona

    # ---- archivos ----
    ("lista los archivos de Descargas", "list_files"),
    ("busca el archivo informe.pdf en Documentos", "search_files"),

    # ---- correo y calendario ----
    ("envia un correo a yo asunto Hola mensaje Prueba", "send_email"),
    ("mis proximos eventos", "calendar_events"),

    # ---- empleo ----
    ("busca trabajo de desarrollador en Bogota", "search_jobs"),
    ("muestrame las ofertas", "show_jobs"),

    # ---- conversacion pura (NO debe capturar herramienta) ----
    ("de que color es el cielo", "chat"),
    ("hola como estas", "chat"),
    ("que opinas de la inteligencia artificial", "chat"),
    ("gracias por tu ayuda", "chat"),
    ("cuentame como fue tu dia", "chat"),
]


@pytest.mark.parametrize("frase,expect", CASES)
def test_parser_intent(frase, expect):
    r = parse_intent(frase)
    if expect in ("chat", "ambiguous", "unsupported"):
        assert r.kind == expect, f"{frase!r}: kind={r.kind} tool={r.tool} (esperaba {expect})"
    else:
        assert r.tool == expect, f"{frase!r}: kind={r.kind} tool={r.tool} (esperaba tool={expect})"


# ── multi-accion: se resuelve en dividir_acciones(), no en parse_intent() ────
MULTI = [
    ("abre chrome y sube el volumen", ["abre chrome", "sube el volumen"]),
    ("abre youtube y pon lofi", ["abre youtube", "pon lofi"]),
    ("pon musica y baja el brillo", ["pon musica", "baja el brillo"]),
    ("sube el volumen y toma una captura", ["sube el volumen", "toma una captura"]),
    ("busca trabajo y abre la primera oferta", ["busca trabajo", "abre la primera oferta"]),
]


@pytest.mark.parametrize("frase,partes", MULTI, ids=[m[0][:45] for m in MULTI])
def test_multi_accion(frase, partes):
    assert es_multi_accion(frase) is True
    assert dividir_acciones(frase) == partes


def test_no_multi_accion_en_frase_simple():
    assert es_multi_accion("abre whatsapp") is False
    assert es_multi_accion("clima en Bogota y alrededores") is False


# ── A3: la ciudad se extrae limpia (sin adverbios temporales) ────────────────
@pytest.mark.parametrize("frase,ciudad", [
    ("clima en Bogota", "bogota"),
    ("que tiempo hace en Medellin", "medellin"),
    ("el clima de hoy en Quito", "quito"),
    ("como estara el tiempo manana en Pasto", "pasto"),
    ("va a llover en Cartagena", "cartagena"),
    ("que tiempo hara el sabado en Cali", "cali"),
])
def test_weather_city_limpia(frase, ciudad):
    r = parse_intent(frase)
    assert r.tool == "weather"
    assert r.arguments.get("city") == ciudad
