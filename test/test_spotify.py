"""
Tests para la herramienta de Spotify.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import spotify as S
from jarvis_local.tools.spotify import has_credentials, play_song


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """La verificación de arranque sondea el estado con `time.sleep`: se
    quitan las esperas para que los tests sigan corriendo en milisegundos."""
    monkeypatch.setattr(S.time, "sleep", lambda *_a, **_kw: None)


def test_has_credentials_no_config():
    with patch("jarvis_local.tools.spotify.get_secrets", return_value={}):
        assert has_credentials() is False


def test_has_credentials_with_placeholder():
    cfg = {"spotify": {"client_id": "TU-CLIENT-ID", "client_secret": "TU-CLIENT-SECRET"}}
    with patch("jarvis_local.tools.spotify.get_secrets", return_value=cfg):
        assert has_credentials() is False


def test_has_credentials_valid():
    cfg = {"spotify": {"client_id": "abc", "client_secret": "def"}}
    with patch("jarvis_local.tools.spotify.get_secrets", return_value=cfg):
        assert has_credentials() is True


def test_play_song_empty_query():
    plan = play_song("")
    assert plan.status == ActionStatus.ERROR
    assert "cancion" in plan.result.lower()


def test_play_song_no_credentials():
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=False):
        plan = play_song("bohemian rhapsody")
        assert plan.status == ActionStatus.ERROR
        assert "no esta configurado" in plan.result.lower()


def test_play_song_missing_spotipy():
    import sys
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=None), \
         patch.dict(sys.modules, {"spotipy": None}):
        plan = play_song("bohemian rhapsody")
        assert plan.status == ActionStatus.ERROR
        assert "spotipy" in plan.result.lower()


def test_play_song_sin_token_pide_reautorizar():
    """_client() devuelve None si no hay token cacheado valido (para no
    bloquear en input() con el flujo OAuth). play_song da el comando de reauth."""
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=None):
        plan = play_song("bohemian rhapsody")
        assert plan.status == ActionStatus.ERROR
        assert "--reauth-spotify" in plan.result


def test_play_song_not_found():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": []}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("una cancion que no existe")
        assert plan.status == ActionStatus.ERROR
        assert "no encontre" in plan.result.lower()


def test_play_song_no_active_device():
    """Sin ningun dispositivo y sin poder abrir Spotify (no instalado):
    debe fallar con un mensaje claro, sin intentar abrir nada de verdad."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Bohemian Rhapsody", "uri": "spotify:track:1",
         "artists": [{"name": "Queen"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp), \
         patch("jarvis_local.tools.spotify.shutil.which", return_value=None):
        plan = play_song("bohemian rhapsody")
        assert plan.status == ActionStatus.ERROR
        assert "spotify" in plan.result.lower()


def test_play_song_opens_spotify_when_not_running():
    """Si la app no esta abierta, JARVIS la abre y espera a que aparezca
    como dispositivo Connect, sin lanzar un proceso real en el test."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "esta_pc"}}
    sin_pc = {"devices": [{"id": "telefono", "is_active": True, "type": "Smartphone"}]}
    con_pc = {"devices": [{"id": "esta_pc", "is_active": False, "type": "Computer"}]}
    mock_sp.devices.side_effect = [sin_pc, sin_pc, con_pc]
    mock_popen = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp), \
         patch("jarvis_local.tools.spotify.shutil.which", return_value="/snap/bin/spotify"), \
         patch("jarvis_local.tools.spotify.subprocess.Popen", mock_popen), \
         patch("jarvis_local.tools.spotify.time.sleep"):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.EXECUTED
        mock_popen.assert_called_once()
        mock_sp.start_playback.assert_called_once_with(
            device_id="esta_pc", uris=["spotify:track:1"])


def test_play_song_gives_up_after_timeout_opening_spotify():
    """Si la app no llega a registrarse a tiempo, cae al dispositivo activo
    en vez de fallar del todo."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    sin_pc = {"devices": [{"id": "telefono", "is_active": True, "type": "Smartphone"}]}
    mock_sp.devices.return_value = sin_pc
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "telefono"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp), \
         patch("jarvis_local.tools.spotify.shutil.which", return_value="/snap/bin/spotify"), \
         patch("jarvis_local.tools.spotify.subprocess.Popen"), \
         patch("jarvis_local.tools.spotify.time.sleep"):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with(
            device_id="telefono", uris=["spotify:track:1"])


def test_play_song_success():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Bohemian Rhapsody", "uri": "spotify:track:1",
         "artists": [{"name": "Queen"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("bohemian rhapsody")
        assert plan.status == ActionStatus.EXECUTED
        assert "Bohemian Rhapsody" in plan.result
        assert "Queen" in plan.result
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", uris=["spotify:track:1"])


def test_play_song_prefiere_coincidencia_exacta_de_nombre():
    """Caso real reportado: 'reproduce I Wanna Be Yours' devolvia 'I WANNA
    BE YOUR SLAVE' de Maneskin (primer resultado de relevancia de Spotify)
    en vez de la cancion exacta pedida. Sin campo de popularidad disponible
    (restriccion de la API para apps nuevas), la coincidencia EXACTA de
    nombre es la señal que queda para desempatar a favor de lo pedido."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "I WANNA BE YOUR SLAVE", "uri": "spotify:track:otra",
         "artists": [{"name": "Maneskin"}]},
        {"name": "I Wanna Be Yours", "uri": "spotify:track:pedida",
         "artists": [{"name": "Arctic Monkeys"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("I Wanna Be Yours")
        assert plan.status == ActionStatus.EXECUTED
        assert "Arctic Monkeys" in plan.result
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", uris=["spotify:track:pedida"])


def test_play_song_de_artista_resuelve_artista_y_compara_por_palabras():
    """Caso real reportado: 'reproduce yo soy el rey de vicente fernandez'
    devolvia 'La Morocha' de Luck Ra, sin ninguna relacion -- porque el
    titulo real es solo 'El Rey' (la gente parafrasea, no cita el titulo
    exacto) y ademas "artist-top-tracks" esta bloqueado para apps nuevas
    (403). Se resuelve el artista primero (tolera "vicente fernandez" sin
    tilde) y se prueban palabras del titulo combinadas con el filtro exacto
    de artista, comparando por proporcion de palabras en vez de texto
    exacto.

    Ambas palabras probadas ("soy" y "rey") devuelven una cancion real del
    artista para forzar el caso de desempate que fallaba: contar palabras a
    secas empataba 'El Rey' (comparte "rey") con 'Soy Mexico' (comparte
    "soy") en 1 cada una, y el orden de un set en Python no es
    determinista entre ejecuciones. Por proporcion, 'El Rey' debe ganar
    siempre: comparte una porcion mayor de "yo soy el rey".
    """
    mock_sp = MagicMock()

    def fake_search(q, type, limit=10):  # noqa: A002 - nombre del parametro real de spotipy
        if type == "artist":
            return {"artists": {"items": [{"id": "artist123", "name": "Vicente Fernández"}]}}
        if "rey" in q.lower():
            return {"tracks": {"items": [
                {"name": "El Rey", "uri": "spotify:track:correcta",
                 "artists": [{"name": "Vicente Fernández"}]},
            ]}}
        if "soy" in q.lower():
            return {"tracks": {"items": [
                {"name": "Soy México", "uri": "spotify:track:falso_positivo",
                 "artists": [{"name": "Vicente Fernández"}]},
            ]}}
        return {"tracks": {"items": []}}

    mock_sp.search.side_effect = fake_search
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("yo soy el rey de vicente fernandez")
        assert plan.status == ActionStatus.EXECUTED
        assert "El Rey" in plan.result
        mock_sp.artist_top_tracks.assert_not_called()
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", uris=["spotify:track:correcta"])


def test_play_song_de_artista_sin_coincidencia_cae_a_texto_libre():
    """Si ninguna palabra del titulo, combinada con el filtro de artista,
    encuentra algo que comparta palabras con lo pedido, no se inventa una
    coincidencia: se cae a la busqueda de texto libre de Spotify."""
    mock_sp = MagicMock()

    def fake_search(q, type, limit=10):  # noqa: A002
        if type == "artist":
            return {"artists": {"items": [{"id": "artist123", "name": "Un Artista"}]}}
        if 'artist:"Un Artista"' in q:
            return {"tracks": {"items": [
                {"name": "Totalmente Distinto", "uri": "spotify:track:otra",
                 "artists": [{"name": "Un Artista"}]},
            ]}}
        return {"tracks": {"items": [
            {"name": "Cancion Encontrada Por Texto Libre", "uri": "spotify:track:1",
             "artists": [{"name": "Un Artista"}]},
        ]}}

    mock_sp.search.side_effect = fake_search
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("algo muy especifico de un artista")
        assert plan.status == ActionStatus.EXECUTED
        assert "Cancion Encontrada Por Texto Libre" in plan.result


def test_play_song_artista_no_resuelve_cae_a_texto_libre():
    """Si el nombre despues de 'de' no es un artista real de Spotify
    (o el patron 'X de Y' aplica por casualidad a otra cosa), se cae a la
    busqueda de texto libre en vez de fallar."""
    mock_sp = MagicMock()
    mock_sp.search.side_effect = [
        {"artists": {"items": []}},
        {"tracks": {"items": [
            {"name": "Resultado De Texto Libre", "uri": "spotify:track:1",
             "artists": [{"name": "Alguien"}]},
        ]}},
    ]
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("cancion rara de algo que no es un artista")
        assert plan.status == ActionStatus.EXECUTED
        assert "Resultado De Texto Libre" in plan.result
        mock_sp.artist_top_tracks.assert_not_called()


def test_play_song_prefers_active_device():
    """Sin ningun dispositivo tipo Computer y sin poder abrir Spotify: cae
    al dispositivo activo entre los que ya hay."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "inactive", "is_active": False, "type": "Speaker"},
        {"id": "active", "is_active": True, "type": "Speaker"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "active"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp), \
         patch("jarvis_local.tools.spotify.shutil.which", return_value=None):
        play_song("cualquier cosa")
        mock_sp.start_playback.assert_called_once_with(
            device_id="active", uris=["spotify:track:1"])


def test_play_song_prefers_this_pc_over_active_phone():
    """El celular puede quedar marcado is_active por Spotify, pero JARVIS
    corre en este PC: la cancion debe sonar aqui, no en el celular."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "telefono", "is_active": True, "type": "Smartphone"},
        {"id": "esta_pc", "is_active": False, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "esta_pc"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        play_song("cualquier cosa")
        mock_sp.start_playback.assert_called_once_with(
            device_id="esta_pc", uris=["spotify:track:1"])


def test_play_song_requires_premium():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    mock_sp.start_playback.side_effect = Exception("Premium required (403)")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.ERROR
        assert "premium" in plan.result.lower()


def test_play_song_without_artists_reads_naturally():
    """Un track sin artistas (raro, pero spotipy no lo garantiza) no debe
    dejar un 'de' colgado en la respuesta."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Track Sin Artista", "uri": "spotify:track:1", "artists": []},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("track sin artista")
        assert plan.status == ActionStatus.EXECUTED
        assert plan.result == "Reproduciendo 'Track Sin Artista' en Spotify, senor."
        assert " de " not in plan.result


def _spotify_exception(http_status, msg="error"):
    from spotipy.exceptions import SpotifyException
    return SpotifyException(http_status, -1, msg)


def test_play_song_device_disappeared_404():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    mock_sp.start_playback.side_effect = _spotify_exception(404, "Device not found")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.ERROR
        assert "dispositivo" in plan.result.lower()


def test_play_song_expired_token_401():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    mock_sp.start_playback.side_effect = _spotify_exception(401, "The access token expired")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.ERROR
        # B6: un 401 ahora da el comando de re-autorizacion, no un texto vago
        assert "--reauth-spotify" in plan.result


def test_play_song_rate_limited_429():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [
        {"id": "dev1", "is_active": True, "type": "Computer"},
    ]}
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    mock_sp.start_playback.side_effect = _spotify_exception(429, "Rate limited")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.ERROR
        assert "limitando" in plan.result.lower()


def test_play_song_search_raises_generic_error():
    """Si search() explota (red caida, etc.), debe dar un error legible en
    vez de propagar la excepcion."""
    mock_sp = MagicMock()
    mock_sp.search.side_effect = ConnectionError("no network")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = play_song("cualquier cosa")
        assert plan.status == ActionStatus.ERROR
        assert "no pude reproducir" in plan.result.lower()


# ==========================================================================
# Verificación real (bug encontrado en revisión): pausa/reanudar/siguiente/
# anterior/volumen/aleatorio/repetir/transferir/me-gusta aceptaban el 204 de
# la Web API como éxito sin comprobar que el dispositivo remoto de verdad
# reaccionó -- inconsistente con play_song (_arranco_de_verdad) en el mismo
# archivo, y en contra de lo que catalog.py ya declaraba en su propio
# `verify=`. Cada par aquí prueba: (a) éxito real se reporta EXECUTED, (b)
# la API "acepta" la orden pero el estado releído no cambia -> ERROR, no un
# "listo, senor" falso.
# ==========================================================================
from jarvis_local.tools.spotify import (  # noqa: E402
    like_current_track,
    next_track,
    pause_playback,
    previous_track,
    resume_playback,
    set_repeat,
    set_shuffle,
    set_volume,
    transfer_playback,
)


def _mock_un_dispositivo(device_id="dev1"):
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": device_id, "is_active": True, "type": "Computer"},
    ]}
    return mock_sp


def test_pause_playback_confirma_pausa_real():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"is_playing": False, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = pause_playback()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.pause_playback.assert_called_once_with(device_id="dev1")


def test_pause_playback_error_si_sigue_sonando():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = pause_playback()
        assert plan.status == ActionStatus.ERROR
        assert "sigue sonando" in plan.result.lower()


def test_resume_playback_confirma_reanudacion_real():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = resume_playback()
        assert plan.status == ActionStatus.EXECUTED


def test_resume_playback_error_si_sigue_pausado():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"is_playing": False, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = resume_playback()
        assert plan.status == ActionStatus.ERROR


def test_next_track_confirma_cambio_de_pista():
    mock_sp = _mock_un_dispositivo()
    # 1ra lectura ("antes" de saltar), despues ya cambio de pista
    mock_sp.current_playback.side_effect = [
        {"item": {"id": "track_viejo"}, "device": {"id": "dev1"}},
        {"item": {"id": "track_nuevo"}, "device": {"id": "dev1"}},
    ]
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = next_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.next_track.assert_called_once_with(device_id="dev1")


def test_next_track_error_si_sigue_la_misma_pista():
    mock_sp = _mock_un_dispositivo()
    # misma pista antes y despues en TODAS las lecturas: nunca cambia
    mock_sp.current_playback.return_value = {"item": {"id": "track_igual"},
                                              "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = next_track()
        assert plan.status == ActionStatus.ERROR
        assert "misma" in plan.result.lower()


def test_previous_track_confirma_cambio_de_pista():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.side_effect = [
        {"item": {"id": "track_actual"}, "device": {"id": "dev1"}},
        {"item": {"id": "track_anterior"}, "device": {"id": "dev1"}},
    ]
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = previous_track()
        assert plan.status == ActionStatus.EXECUTED


def test_set_volume_confirma_volumen_real():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"device": {"id": "dev1", "volume_percent": 42}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = set_volume(42)
        assert plan.status == ActionStatus.EXECUTED


def test_set_volume_error_si_no_cambio():
    mock_sp = _mock_un_dispositivo()
    # se pidio 80 pero el dispositivo sigue en 20 -- fuera de la tolerancia de +/-2
    mock_sp.current_playback.return_value = {"device": {"id": "dev1", "volume_percent": 20}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = set_volume(80)
        assert plan.status == ActionStatus.ERROR
        assert "volumen no cambio" in plan.result.lower()


def test_set_shuffle_confirma_estado_real():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"shuffle_state": True, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = set_shuffle(True)
        assert plan.status == ActionStatus.EXECUTED


def test_set_shuffle_error_si_no_cambio():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"shuffle_state": False, "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = set_shuffle(True)
        assert plan.status == ActionStatus.ERROR


def test_set_repeat_confirma_estado_real():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"repeat_state": "track", "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = set_repeat("cancion")
        assert plan.status == ActionStatus.EXECUTED


def test_set_repeat_error_si_no_cambio():
    mock_sp = _mock_un_dispositivo()
    mock_sp.current_playback.return_value = {"repeat_state": "off", "device": {"id": "dev1"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = set_repeat("cancion")
        assert plan.status == ActionStatus.ERROR


def test_transfer_playback_confirma_dispositivo_real():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": "telefono", "name": "Mi telefono", "is_active": False},
    ]}
    mock_sp.current_playback.return_value = {"device": {"id": "telefono"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = transfer_playback("telefono")
        assert plan.status == ActionStatus.EXECUTED


def test_transfer_playback_error_si_no_se_movio():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": "telefono", "name": "Mi telefono", "is_active": False},
    ]}
    mock_sp.current_playback.return_value = {"device": {"id": "esta_pc"}}  # no se movio
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = transfer_playback("telefono")
        assert plan.status == ActionStatus.ERROR
        assert "no se movio" in plan.result.lower()


def test_like_current_track_confirma_que_quedo_guardada():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "item": {"id": "track1", "name": "Song", "artists": [{"name": "Artist"}]}}
    mock_sp.current_user_saved_tracks_contains.return_value = [True]
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = like_current_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.current_user_saved_tracks_add.assert_called_once_with(["track1"])


def test_like_current_track_error_si_no_quedo_guardada():
    """Bug real: `current_user_saved_tracks_add` no explota pero la pista
    nunca aparece guardada al releer -- antes JARVIS decia "Guarde..." igual."""
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "item": {"id": "track1", "name": "Song", "artists": [{"name": "Artist"}]}}
    mock_sp.current_user_saved_tracks_contains.return_value = [False]
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = like_current_track()
        assert plan.status == ActionStatus.ERROR
        assert "no quedo guardada" in plan.result.lower()


if __name__ == "__main__":
    test_has_credentials_no_config()
    test_has_credentials_with_placeholder()
    test_has_credentials_valid()
    test_play_song_empty_query()
    test_play_song_no_credentials()
    test_play_song_missing_spotipy()
    test_play_song_not_found()
    test_play_song_no_active_device()
    test_play_song_opens_spotify_when_not_running()
    test_play_song_gives_up_after_timeout_opening_spotify()
    test_play_song_success()
    test_play_song_prefiere_coincidencia_exacta_de_nombre()
    test_play_song_de_artista_resuelve_artista_y_compara_por_palabras()
    test_play_song_de_artista_sin_coincidencia_cae_a_texto_libre()
    test_play_song_artista_no_resuelve_cae_a_texto_libre()
    test_play_song_prefers_active_device()
    test_play_song_prefers_this_pc_over_active_phone()
    test_play_song_requires_premium()
    test_play_song_without_artists_reads_naturally()
    test_play_song_device_disappeared_404()
    test_play_song_expired_token_401()
    test_play_song_rate_limited_429()
    test_play_song_search_raises_generic_error()
    print("OK: Todos los tests de spotify pasaron.")
