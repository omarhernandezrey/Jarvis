"""Tests de control de volumen y multimedia"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.media_controls import (
    get_volume,
    is_muted,
    media_next,
    media_play_pause,
    media_previous,
    set_volume,
    volume_down,
    volume_mute,
    volume_up,
)

# --- Enrutamiento del parser ---


def test_intent_subir_volumen():
    for frase in ("sube el volumen", "subele al volumen", "mas volumen"):
        r = parse_intent(frase)
        assert r.tool == "volume_up", frase


def test_intent_bajar_volumen():
    for frase in ("baja el volumen", "bajale al volumen", "menos volumen"):
        r = parse_intent(frase)
        assert r.tool == "volume_down", frase


def test_intent_volumen_exacto():
    r = parse_intent("pon el volumen al 50")
    assert r.tool == "volume_set"
    assert r.arguments["level"] == 50
    r = parse_intent("volumen al 80 por ciento")
    assert r.tool == "volume_set"
    assert r.arguments["level"] == 80


def test_intent_silenciar():
    for frase in ("silencia el computador", "silencio", "quita el sonido"):
        r = parse_intent(frase)
        assert r.tool == "volume_mute", frase
        assert r.arguments["mute"] is True, frase


def test_intent_activar_sonido():
    for frase in ("quita el silencio", "activa el sonido"):
        r = parse_intent(frase)
        assert r.tool == "volume_mute", frase
        assert r.arguments["mute"] is False, frase


def test_intent_pausa():
    for frase in ("pausa la musica", "pausa", "reanuda la musica"):
        r = parse_intent(frase)
        assert r.tool == "media_play_pause", frase


def test_intent_cambio_cancion():
    assert parse_intent("siguiente cancion").tool == "media_next"
    assert parse_intent("cambia de cancion").tool == "media_next"
    assert parse_intent("cancion anterior").tool == "media_previous"


def test_intent_musica_no_robada():
    # "pon musica" sigue siendo reproducir musica local, no un control
    assert parse_intent("pon musica").tool == "play_music"
    assert parse_intent("reproduce hotel california en youtube").tool == "youtube_play"


# --- Herramientas (con verificacion real si hay dispositivo de audio) ---


def test_set_volume_verificado():
    inicial = get_volume()
    if inicial is None:
        # sin dispositivo de audio (CI): la funcion debe fallar con gracia
        plan = set_volume(50)
        assert plan.status in (ActionStatus.EXECUTED, ActionStatus.ERROR)
        return
    try:
        plan = set_volume(37)
        assert plan.status == ActionStatus.EXECUTED
        assert get_volume() == 37  # verificado contra el sistema real
    finally:
        set_volume(inicial)


def test_volume_up_down_verificado():
    inicial = get_volume()
    if inicial is None:
        return
    try:
        set_volume(50)
        assert volume_up().status == ActionStatus.EXECUTED
        assert get_volume() == 60
        assert volume_down().status == ActionStatus.EXECUTED
        assert get_volume() == 50
    finally:
        set_volume(inicial)


def test_mute_verificado():
    inicial = is_muted()
    if inicial is None:
        return
    try:
        assert volume_mute(True).status == ActionStatus.EXECUTED
        assert is_muted() is True
        assert volume_mute(False).status == ActionStatus.EXECUTED
        assert is_muted() is False
    finally:
        volume_mute(inicial)


def test_media_keys_no_fallan():
    # Las teclas multimedia no tienen estado legible: verificar que no explotan
    assert media_play_pause().status == ActionStatus.EXECUTED
    assert media_play_pause().status == ActionStatus.EXECUTED  # revertir
    assert media_next().status == ActionStatus.EXECUTED
    assert media_previous().status == ActionStatus.EXECUTED  # revertir


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de media pasaron.")
