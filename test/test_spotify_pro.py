"""Tests para las funciones "Pro" de Spotify (control avanzado, playlists y
descubrimiento, multi-dispositivo, biblioteca personal). Mismo patron de
mocks que test_spotify.py/test_spotify_reauth.py: nunca se toca la API real,
se parchea jarvis_local.tools.spotify._client para devolver un MagicMock.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import spotify as S


def _spotify_exception(http_status, msg="error"):
    from spotipy.exceptions import SpotifyException
    return SpotifyException(http_status, -1, msg)


def _err(name, msg, http=None):
    e = type(name, (Exception,), {})(msg)
    if http is not None:
        e.http_status = http
    return e


class _ClienteQueExplota:
    """Cualquier metodo que se le llame lanza `err` -- sirve para probar de
    forma uniforme el manejo de errores compartido (_manejar_error_spotify)
    en todas las funciones nuevas sin tener que mockear cada metodo spotipy
    distinto que usa cada una."""

    def __init__(self, err):
        self._err = err

    def __getattr__(self, name):
        def _raise(*a, **kw):
            raise self._err
        return _raise


# Tabla de todas las funciones "Pro" con argumentos validos (pasan la
# validacion local, para llegar siempre hasta _cliente_o_error/la API).
_FUNCIONES = [
    ("pause_playback", lambda: S.pause_playback()),
    ("resume_playback", lambda: S.resume_playback()),
    ("next_track", lambda: S.next_track()),
    ("previous_track", lambda: S.previous_track()),
    ("set_volume", lambda: S.set_volume(50)),
    ("set_shuffle", lambda: S.set_shuffle(True)),
    ("set_repeat", lambda: S.set_repeat("cancion")),
    ("now_playing", lambda: S.now_playing()),
    ("add_to_queue", lambda: S.add_to_queue("alguna cancion")),
    ("play_playlist", lambda: S.play_playlist("running")),
    ("play_album", lambda: S.play_album("algun album")),
    ("play_radio", lambda: S.play_radio("algun artista")),
    ("list_devices", lambda: S.list_devices()),
    ("transfer_playback", lambda: S.transfer_playback("celular")),
    ("like_current_track", lambda: S.like_current_track()),
    ("recently_played", lambda: S.recently_played()),
    ("resume_last_played", lambda: S.resume_last_played()),
]


@pytest.mark.parametrize("nombre,llamar", _FUNCIONES, ids=[n for n, _ in _FUNCIONES])
def test_sin_credenciales(nombre, llamar):
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=False):
        plan = llamar()
        assert plan.status == ActionStatus.ERROR
        assert "no esta configurado" in plan.result.lower()


@pytest.mark.parametrize("nombre,llamar", _FUNCIONES, ids=[n for n, _ in _FUNCIONES])
def test_sin_token_pide_reautorizar(nombre, llamar):
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=None):
        plan = llamar()
        assert plan.status == ActionStatus.ERROR
        assert "--reauth-spotify" in plan.result


@pytest.mark.parametrize("nombre,llamar", _FUNCIONES, ids=[n for n, _ in _FUNCIONES])
def test_error_de_auth_da_mensaje_accionable(monkeypatch, tmp_path, nombre, llamar):
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr(S, "_CACHE_PATH", tmp_path / ".spotify_cache")
    (tmp_path / ".spotify_cache").write_text("{}")
    err = _err("SpotifyException", "The access token expired", http=401)
    monkeypatch.setattr(S, "_client", lambda: _ClienteQueExplota(err))
    plan = llamar()
    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" in plan.result
    assert not (tmp_path / ".spotify_cache").exists()


@pytest.mark.parametrize("nombre,llamar", _FUNCIONES, ids=[n for n, _ in _FUNCIONES])
def test_rate_limited_429(monkeypatch, nombre, llamar):
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    err = _spotify_exception(429, "Rate limited")
    monkeypatch.setattr(S, "_client", lambda: _ClienteQueExplota(err))
    plan = llamar()
    assert plan.status == ActionStatus.ERROR
    assert "limitando" in plan.result.lower()


# ---------------------------------------------------------------------
# Paquete 1 -- Control avanzado
# ---------------------------------------------------------------------

def test_pause_playback_success():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.pause_playback()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.pause_playback.assert_called_once()


def test_pause_playback_nada_sonando_403():
    mock_sp = MagicMock()
    mock_sp.pause_playback.side_effect = _spotify_exception(403, "no active device")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.pause_playback()
        assert plan.status == ActionStatus.ERROR
        assert "pausar" in plan.result.lower()


def test_resume_playback_success():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_playback()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with()


def test_resume_playback_nada_que_reanudar_403():
    mock_sp = MagicMock()
    mock_sp.start_playback.side_effect = _spotify_exception(403, "no context")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_playback()
        assert plan.status == ActionStatus.ERROR
        assert "reanudar" in plan.result.lower()


def test_next_track_success():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.next_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.next_track.assert_called_once()


def test_previous_track_success():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.previous_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.previous_track.assert_called_once()


def test_set_volume_success():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_volume(45)
        assert plan.status == ActionStatus.EXECUTED
        assert "45" in plan.result
        mock_sp.volume.assert_called_once_with(45)


@pytest.mark.parametrize("entrada,esperado", [(-10, 0), (500, 100), (50, 50)])
def test_set_volume_clampa_0_100(entrada, esperado):
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        S.set_volume(entrada)
        mock_sp.volume.assert_called_once_with(esperado)


def test_set_shuffle_activa():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_shuffle(True)
        assert plan.status == ActionStatus.EXECUTED
        assert "activado" in plan.result.lower()
        mock_sp.shuffle.assert_called_once_with(True)


def test_set_shuffle_desactiva():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_shuffle(False)
        assert plan.status == ActionStatus.EXECUTED
        assert "desactivado" in plan.result.lower()
        mock_sp.shuffle.assert_called_once_with(False)


@pytest.mark.parametrize("modo,valor_api", [("cancion", "track"), ("lista", "context"), ("no", "off")])
def test_set_repeat_modos_validos(modo, valor_api):
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_repeat(modo)
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.repeat.assert_called_once_with(valor_api)


def test_set_repeat_modo_invalido_no_llama_a_la_api():
    mock_sp = MagicMock()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_repeat("cualquier_cosa")
        assert plan.status == ActionStatus.ERROR
        mock_sp.repeat.assert_not_called()


def test_now_playing_nada_sonando():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.now_playing()
        assert plan.status == ActionStatus.EXECUTED
        assert "no hay nada sonando" in plan.result.lower()


def test_now_playing_item_none():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {"item": None}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.now_playing()
        assert plan.status == ActionStatus.EXECUTED
        assert "no hay nada sonando" in plan.result.lower()


def test_now_playing_con_cancion():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "item": {"name": "Bohemian Rhapsody", "artists": [{"name": "Queen"}]},
        "device": {"name": "Mi Celular"},
        "is_playing": True,
    }
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.now_playing()
        assert plan.status == ActionStatus.EXECUTED
        assert "Bohemian Rhapsody" in plan.result
        assert "Queen" in plan.result
        assert "Mi Celular" in plan.result
        assert "sonando" in plan.result.lower()


def test_add_to_queue_success():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.add_to_queue("song")
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.add_to_queue.assert_called_once_with("spotify:track:1")


def test_add_to_queue_no_encontrada():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": []}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.add_to_queue("cancion inexistente")
        assert plan.status == ActionStatus.ERROR
        assert "no encontre" in plan.result.lower()
        mock_sp.add_to_queue.assert_not_called()


def test_add_to_queue_query_vacio():
    plan = S.add_to_queue("")
    assert plan.status == ActionStatus.ERROR


# ---------------------------------------------------------------------
# Paquete 2 -- Playlists y descubrimiento
# ---------------------------------------------------------------------

def test_play_playlist_success():
    mock_sp = MagicMock()
    mock_sp.current_user_playlists.return_value = {"items": [
        {"name": "Running Mix", "uri": "spotify:playlist:1"},
        {"name": "Chill", "uri": "spotify:playlist:2"},
    ]}
    mock_sp.devices.return_value = {"devices": [{"id": "dev1", "is_active": True, "type": "Computer"}]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_playlist("running")
        assert plan.status == ActionStatus.EXECUTED
        assert "Running Mix" in plan.result
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", context_uri="spotify:playlist:1")


def test_play_playlist_sin_candidatos_blocked():
    mock_sp = MagicMock()
    mock_sp.current_user_playlists.return_value = {"items": [
        {"name": "Chill", "uri": "spotify:playlist:2"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_playlist("running")
        assert plan.status == ActionStatus.BLOCKED
        mock_sp.start_playback.assert_not_called()


def test_play_playlist_ambigua_blocked():
    mock_sp = MagicMock()
    mock_sp.current_user_playlists.return_value = {"items": [
        {"name": "Rock clasico", "uri": "spotify:playlist:1"},
        {"name": "Rock moderno", "uri": "spotify:playlist:2"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_playlist("rock")
        assert plan.status == ActionStatus.BLOCKED
        assert "Rock clasico" in plan.result
        assert "Rock moderno" in plan.result
        mock_sp.start_playback.assert_not_called()


def test_play_playlist_nombre_vacio():
    plan = S.play_playlist("")
    assert plan.status == ActionStatus.ERROR


def test_play_album_success():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"albums": {"items": [
        {"name": "Dark Side of the Moon", "uri": "spotify:album:1",
         "artists": [{"name": "Pink Floyd"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [{"id": "dev1", "is_active": True, "type": "Computer"}]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_album("dark side of the moon")
        assert plan.status == ActionStatus.EXECUTED
        assert "Pink Floyd" in plan.result
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", context_uri="spotify:album:1")


def test_play_album_no_encontrado():
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"albums": {"items": []}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_album("album que no existe")
        assert plan.status == ActionStatus.ERROR


def test_play_radio_con_recomendaciones():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [{"id": "dev1", "is_active": True, "type": "Computer"}]}
    mock_sp.search.return_value = {"artists": {"items": [{"id": "art1", "name": "Bad Bunny",
                                                           "uri": "spotify:artist:art1"}]}}
    mock_sp.recommendations.return_value = {"tracks": [
        {"uri": "spotify:track:r1"}, {"uri": "spotify:track:r2"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_radio("bad bunny")
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", uris=["spotify:track:r1", "spotify:track:r2"])


def test_play_radio_recomendaciones_fallan_cae_a_catalogo_artista():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [{"id": "dev1", "is_active": True, "type": "Computer"}]}
    mock_sp.search.return_value = {"artists": {"items": [{"id": "art1", "name": "Bad Bunny",
                                                           "uri": "spotify:artist:art1"}]}}
    mock_sp.recommendations.side_effect = _spotify_exception(404, "not available")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_radio("bad bunny")
        assert plan.status == ActionStatus.EXECUTED
        assert "Bad Bunny" in plan.result
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", context_uri="spotify:artist:art1")


def test_play_radio_sin_resolver_nada():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [{"id": "dev1", "is_active": True, "type": "Computer"}]}
    mock_sp.search.return_value = {"artists": {"items": []}, "tracks": {"items": []}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_radio("algo que no existe en absoluto")
        assert plan.status == ActionStatus.ERROR
        mock_sp.start_playback.assert_not_called()


def test_play_radio_query_vacio():
    plan = S.play_radio("")
    assert plan.status == ActionStatus.ERROR


# ---------------------------------------------------------------------
# Paquete 3 -- Multi-dispositivo
# ---------------------------------------------------------------------

def test_list_devices_con_dispositivos():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": "d1", "name": "Este PC", "is_active": True, "type": "Computer"},
        {"id": "d2", "name": "Mi Celular", "is_active": False, "type": "Smartphone"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.list_devices()
        assert plan.status == ActionStatus.EXECUTED
        assert "Este PC" in plan.result
        assert "Mi Celular" in plan.result


def test_list_devices_vacio():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.list_devices()
        assert plan.status == ActionStatus.EXECUTED
        assert "no veo ningun dispositivo" in plan.result.lower()


def test_transfer_playback_success():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": "d1", "name": "Este PC", "is_active": True, "type": "Computer"},
        {"id": "d2", "name": "Mi Celular", "is_active": False, "type": "Smartphone"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.transfer_playback("celular")
        assert plan.status == ActionStatus.EXECUTED
        assert "Mi Celular" in plan.result
        mock_sp.transfer_playback.assert_called_once_with(device_id="d2", force_play=True)


def test_transfer_playback_no_encontrado_blocked():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": "d1", "name": "Este PC", "is_active": True, "type": "Computer"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.transfer_playback("parlante inexistente")
        assert plan.status == ActionStatus.BLOCKED
        mock_sp.transfer_playback.assert_not_called()


def test_transfer_playback_ambiguo_blocked():
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": [
        {"id": "d1", "name": "Celular de Omar", "is_active": False, "type": "Smartphone"},
        {"id": "d2", "name": "Otro Celular", "is_active": False, "type": "Smartphone"},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.transfer_playback("celular")
        assert plan.status == ActionStatus.BLOCKED
        mock_sp.transfer_playback.assert_not_called()


def test_transfer_playback_device_vacio():
    plan = S.transfer_playback("")
    assert plan.status == ActionStatus.ERROR


# ---------------------------------------------------------------------
# Paquete 4 -- Biblioteca personal
# ---------------------------------------------------------------------

def test_like_current_track_success():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {
        "item": {"id": "t1", "name": "Song", "artists": [{"name": "Artist"}]},
    }
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.like_current_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.current_user_saved_tracks_add.assert_called_once_with(["t1"])


def test_like_current_track_nada_sonando():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.like_current_track()
        assert plan.status == ActionStatus.ERROR
        mock_sp.current_user_saved_tracks_add.assert_not_called()


def test_recently_played_con_historial():
    mock_sp = MagicMock()
    mock_sp.current_user_recently_played.return_value = {"items": [
        {"track": {"name": "Song A", "artists": [{"name": "Artist A"}]}},
        {"track": {"name": "Song B", "artists": [{"name": "Artist B"}]}},
        {"track": {"name": "Song A", "artists": [{"name": "Artist A"}]}},  # duplicado
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.recently_played()
        assert plan.status == ActionStatus.EXECUTED
        assert "Song A" in plan.result
        assert "Song B" in plan.result
        assert plan.result.count("Song A") == 1  # deduplicado


def test_recently_played_vacio():
    mock_sp = MagicMock()
    mock_sp.current_user_recently_played.return_value = {"items": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.recently_played()
        assert plan.status == ActionStatus.EXECUTED
        assert "no hay historial" in plan.result.lower()


@pytest.mark.parametrize("entrada,esperado", [(0, 1), (500, 50), (20, 20)])
def test_recently_played_clampa_limite(entrada, esperado):
    mock_sp = MagicMock()
    mock_sp.current_user_recently_played.return_value = {"items": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        S.recently_played(entrada)
        mock_sp.current_user_recently_played.assert_called_once_with(limit=esperado)


def test_resume_last_played_con_contexto_activo():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = {"item": {"name": "Song"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_last_played()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with()
        mock_sp.current_user_recently_played.assert_not_called()


def test_resume_last_played_sin_contexto_cae_a_recientes():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None
    mock_sp.current_user_recently_played.return_value = {"items": [
        {"track": {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]}},
    ]}
    mock_sp.devices.return_value = {"devices": [{"id": "dev1", "is_active": True, "type": "Computer"}]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_last_played()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with(
            device_id="dev1", uris=["spotify:track:1"])


def test_resume_last_played_sin_nada():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None
    mock_sp.current_user_recently_played.return_value = {"items": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_last_played()
        assert plan.status == ActionStatus.ERROR
