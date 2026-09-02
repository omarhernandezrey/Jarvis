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

_A3 = pytest.mark.xfail(strict=True, reason="TAREA A3 — clima en lenguaje natural")
_A4 = pytest.mark.xfail(strict=True, reason="TAREA A4 — 'crea/nueva nota' → take_note")
_A6 = pytest.mark.xfail(strict=True, reason="TAREA A6 — 'lanza <app>' se va a run_command")
_A7 = pytest.mark.xfail(strict=True, reason="TAREA A7 — estado del sistema coloquial")
_B2 = pytest.mark.xfail(strict=True, reason="TAREA B2 — calculadora lenguaje natural")
_B3 = pytest.mark.xfail(strict=True, reason="TAREA B3 — ecuaciones lineales")


# ── (frase, esperado, marks) ────────────────────────────────────────────────
CASES = [
    # ---- apps y ventanas ----
    ("abre whatsapp", "open_app"),
    ("abre el chrome", "open_app"),
    pytest.param("lanza android studio", "open_app", marks=_A6),
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
    pytest.param("que tiempo hace en Medellin", "weather", marks=_A3),
    pytest.param("va a llover en Cartagena", "weather", marks=_A3),
    pytest.param("como estara el tiempo manana en Pasto", "weather", marks=_A3),

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

    # ---- info ----
    ("quien es Gabriel Garcia Marquez", "wiki"),
    ("cuentame sobre la revolucion francesa", "wiki"),
    ("noticias de hoy", "news_headlines"),
    ("dame los titulares", "news_headlines"),
    ("cual es mi ip", "get_ip"),
    ("estado del sistema", "system_status"),
    pytest.param("como anda la maquina", "system_status", marks=_A7),
    ("cuentame un chiste", "tell_joke"),
    ("dame el resumen del dia", "daily_briefing"),
    ("pregunta a wolfram la derivada de x^2", "wolfram"),
    ("donde queda la Torre Eiffel", "locate"),

    # ---- calculadora ----
    ("calcula 15 * 3 + 2", "calculate"),
    ("cuanto es 300 dividido 7", "calculate"),
    ("cuanto es 20% de 350", "calculate"),
    pytest.param("raiz cuadrada de 144", "calculate", marks=_B2),
    pytest.param("el factorial de 5", "calculate", marks=_B2),
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
    pytest.param("crea una nota comprar pan", "take_note", marks=_A4),
    pytest.param("nueva nota llamar al banco", "take_note", marks=_A4),
    pytest.param("guardame una nota con la clave del wifi", "take_note", marks=_A4),

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
