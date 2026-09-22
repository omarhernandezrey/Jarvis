"""Cobertura del parser para Spotify Pro: playlist/album/radio (dentro de
_parse_fase4) y control via Web API (_parse_spotify_control), mas los casos
negativos que confirman que no colisiona con lo ya existente (volumen del
sistema, pausa/siguiente/anterior genericos via MPRIS, reproducir una
cancion suelta).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from jarvis_local.intent.parser import parse_intent

CASES = [
    # ---- playlist / album / radio (_parse_fase4, antes del catch-all) ----
    ("pon mi playlist de running", "spotify_playlist"),
    ("reproduce la lista de reproduccion favoritos", "spotify_playlist"),
    ("pon el album de dark side of the moon", "spotify_album"),
    ("toca el disco abbey road", "spotify_album"),
    ("pon radio de bad bunny", "spotify_radio"),
    ("quiero una radio basada en esta cancion", "spotify_radio"),

    # ---- control via Web API (_parse_spotify_control) ----
    ("que suena", "spotify_now_playing"),
    ("que esta sonando en spotify", "spotify_now_playing"),
    ("que dispositivos de spotify hay", "spotify_devices"),
    ("cambia la musica al celular", "spotify_device_set"),
    ("pasa spotify al parlante de la sala", "spotify_device_set"),
    ("activa el aleatorio", "spotify_shuffle"),
    ("pon shuffle", "spotify_shuffle"),
    ("quita el aleatorio", "spotify_shuffle"),
    ("repite esta cancion", "spotify_repeat"),
    ("repite toda la lista", "spotify_repeat"),
    ("desactiva la repeticion", "spotify_repeat"),
    ("agrega esta cancion a la cola", "spotify_queue"),
    ("guardame esta cancion", "spotify_like"),
    ("agregala a mis me gusta", "spotify_like"),
    ("que escuche recientemente", "spotify_recent"),
    ("historial de spotify", "spotify_recent"),
    ("retoma lo ultimo que sonaba", "spotify_resume_last"),
    ("pausa spotify", "spotify_pause"),
    ("spotify pausa", "spotify_pause"),
    ("pausa en el celular", "spotify_pause"),
    ("reanuda spotify", "spotify_resume"),
    ("reanuda en el parlante", "spotify_resume"),
    ("salta la cancion en el parlante", "spotify_next"),
    ("retrocede la cancion en el celular", "spotify_previous"),

    # ---- negativos: no deben colisionar con lo generico existente ----
    ("sube el volumen a 40", "volume_set"),
    ("pausa", "media_play_pause"),
    ("pausa la musica", "media_play_pause"),
    ("siguiente cancion", "media_next"),
    ("siguiente cancion en spotify", "media_next"),
    ("cancion anterior", "media_previous"),
    ("cancion anterior en spotify", "media_previous"),
    ("pon bohemian rhapsody", "spotify_play"),
    ("pon algo de rock", "spotify_play"),
]


@pytest.mark.parametrize("frase,expect", CASES)
def test_parser_spotify(frase, expect):
    r = parse_intent(frase)
    assert r.tool == expect, f"{frase!r}: kind={r.kind} tool={r.tool} (esperaba tool={expect})"


def test_volumen_de_spotify_no_choca_con_volumen_del_sistema():
    r = parse_intent("sube el volumen de spotify a 40")
    assert r.tool == "spotify_volume"
    assert r.arguments["nivel"] == 40

    r2 = parse_intent("sube el volumen a 40")
    assert r2.tool == "volume_set"
    assert r2.arguments["level"] == 40


def test_playlist_extrae_el_nombre():
    r = parse_intent("pon mi playlist de running")
    assert r.tool == "spotify_playlist"
    assert r.arguments["name"] == "running"


def test_album_extrae_la_consulta():
    r = parse_intent("pon el album de dark side of the moon")
    assert r.tool == "spotify_album"
    assert r.arguments["query"] == "dark side of the moon"


def test_cola_extrae_la_cancion():
    r = parse_intent("agrega bohemian rhapsody a la cola")
    assert r.tool == "spotify_queue"
    assert r.arguments["song"] == "bohemian rhapsody"


def test_shuffle_activar_y_desactivar():
    r_on = parse_intent("activa el aleatorio")
    assert r_on.tool == "spotify_shuffle"
    assert r_on.arguments["activar"] is True

    r_off = parse_intent("quita el aleatorio")
    assert r_off.tool == "spotify_shuffle"
    assert r_off.arguments["activar"] is False


def test_repeat_modos():
    assert parse_intent("repite esta cancion").arguments["modo"] == "cancion"
    assert parse_intent("repite toda la lista").arguments["modo"] == "lista"
    assert parse_intent("desactiva la repeticion").arguments["modo"] == "no"


def test_cambiar_dispositivo_extrae_el_nombre():
    r = parse_intent("cambia la musica al celular")
    assert r.tool == "spotify_device_set"
    assert r.arguments["device"] == "celular"
