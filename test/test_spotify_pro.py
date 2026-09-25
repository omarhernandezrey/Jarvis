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


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """Sin las esperas de la verificación de arranque (y de la apertura de la
    app): los tests siguen corriendo en milisegundos."""
    monkeypatch.setattr(S.time, "sleep", lambda *_a, **_kw: None)


_PC = {"id": "esta_pc", "name": "este PC", "type": "Computer", "is_active": True}
_CELULAR = {"id": "telefono", "name": "celular", "type": "Smartphone", "is_active": True}


def _cliente(dispositivos=None, sonando="esta_pc"):
    """Cliente falso con `devices()` y `current_playback()` REALISTAS.

    Desde que los comandos eligen dispositivo explícitamente y se comprueba
    que la música arrancó de verdad, un `MagicMock()` pelado (que devuelve
    objetos mágicos sin sentido para todo) ya no sirve de doble: hay que
    decirle qué dispositivos hay y cuál está sonando.
    """
    sp = MagicMock()
    sp.devices.return_value = {"devices": [_PC] if dispositivos is None else dispositivos}
    sp.current_playback.return_value = (
        {"is_playing": True, "device": {"id": sonando}} if sonando else None)
    return sp


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
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.pause_playback()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.pause_playback.assert_called_once_with(device_id="esta_pc")


def test_pause_playback_nada_sonando_403():
    mock_sp = _cliente()
    mock_sp.pause_playback.side_effect = _spotify_exception(403, "no active device")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.pause_playback()
        assert plan.status == ActionStatus.ERROR
        assert "pausar" in plan.result.lower()


def test_resume_playback_success():
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_playback()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with(device_id="esta_pc")


def test_resume_playback_nada_que_reanudar_403():
    mock_sp = _cliente()
    mock_sp.start_playback.side_effect = _spotify_exception(403, "no context")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_playback()
        assert plan.status == ActionStatus.ERROR
        assert "reanudar" in plan.result.lower()


def test_next_track_success():
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.next_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.next_track.assert_called_once_with(device_id="esta_pc")


def test_previous_track_success():
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.previous_track()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.previous_track.assert_called_once_with(device_id="esta_pc")


def test_set_volume_success():
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_volume(45)
        assert plan.status == ActionStatus.EXECUTED
        assert "45" in plan.result
        mock_sp.volume.assert_called_once_with(45, device_id="esta_pc")


@pytest.mark.parametrize("entrada,esperado", [(-10, 0), (500, 100), (50, 50)])
def test_set_volume_clampa_0_100(entrada, esperado):
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        S.set_volume(entrada)
        mock_sp.volume.assert_called_once_with(esperado, device_id="esta_pc")


def test_set_shuffle_activa():
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_shuffle(True)
        assert plan.status == ActionStatus.EXECUTED
        assert "activado" in plan.result.lower()
        mock_sp.shuffle.assert_called_once_with(True, device_id="esta_pc")


def test_set_shuffle_desactiva():
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_shuffle(False)
        assert plan.status == ActionStatus.EXECUTED
        assert "desactivado" in plan.result.lower()
        mock_sp.shuffle.assert_called_once_with(False, device_id="esta_pc")


@pytest.mark.parametrize("modo,valor_api", [("cancion", "track"), ("lista", "context"), ("no", "off")])
def test_set_repeat_modos_validos(modo, valor_api):
    mock_sp = _cliente()
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.set_repeat(modo)
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.repeat.assert_called_once_with(valor_api, device_id="esta_pc")


def test_set_repeat_modo_invalido_no_llama_a_la_api():
    mock_sp = _cliente()
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
    mock_sp = _cliente()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.add_to_queue("song")
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.add_to_queue.assert_called_once_with("spotify:track:1", device_id="esta_pc")


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
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
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
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
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
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
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
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
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
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "dev1"}}
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
    mock_sp = _cliente()
    mock_sp.current_playback.return_value = {"item": {"name": "Song"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_last_played()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with(device_id="esta_pc")
        mock_sp.current_user_recently_played.assert_not_called()


def test_resume_last_played_sin_contexto_cae_a_recientes():
    # sin contexto activo (None) cae al historial; despues de mandar reproducir
    # SI suena (lo que comprueba la verificacion de arranque).
    mock_sp = _cliente()
    mock_sp.current_playback.side_effect = [
        None, {"is_playing": True, "device": {"id": "esta_pc"}}]
    mock_sp.current_user_recently_played.return_value = {"items": [
        {"track": {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]}},
    ]}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_last_played()
        assert plan.status == ActionStatus.EXECUTED
        mock_sp.start_playback.assert_called_once_with(
            device_id="esta_pc", uris=["spotify:track:1"])


def test_resume_last_played_sin_nada():
    mock_sp = MagicMock()
    mock_sp.current_playback.return_value = None
    mock_sp.current_user_recently_played.return_value = {"items": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.resume_last_played()
        assert plan.status == ActionStatus.ERROR


# ---------------------------------------------------------------------
# Regresiones: elegir dispositivo y comprobar que SUENA de verdad
# ---------------------------------------------------------------------

def test_el_control_va_al_dispositivo_que_esta_sonando():
    """Regresión: pausa/siguiente/volumen se mandaban SIN `device_id`, así que
    Spotify los aplicaba a "lo que esté activo" -- con la app cerrada
    fallaban con 404 y el usuario no oía nada ni en pausa ni en siguiente.

    Si la música está en el celular, "pausa" tiene que pausar el CELULAR, no
    abrir esta máquina: por eso aquí manda el dispositivo activo, no el PC.
    """
    mock_sp = _cliente(dispositivos=[dict(_PC, is_active=False), _CELULAR])
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp), \
         patch("jarvis_local.tools.spotify.shutil.which", return_value=None):
        assert S.pause_playback().status == ActionStatus.EXECUTED
        mock_sp.pause_playback.assert_called_once_with(device_id="telefono")


def test_sin_nada_activo_el_control_cae_a_este_pc():
    """Ningún dispositivo activo -> el control va a este PC (sin abrir la app:
    ya está registrado, sólo está inactivo)."""
    pc_inactivo = dict(_PC, is_active=False)
    mock_sp = _cliente(dispositivos=[pc_inactivo])
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        assert S.next_track().status == ActionStatus.EXECUTED
        mock_sp.next_track.assert_called_once_with(device_id="esta_pc")


def test_control_sin_dispositivo_ni_app_da_mensaje_accionable():
    """Sin app instalada ni dispositivos: mensaje claro, sin procesos raros."""
    mock_sp = MagicMock()
    mock_sp.devices.return_value = {"devices": []}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp), \
         patch("jarvis_local.tools.spotify.shutil.which", return_value=None):
        plan = S.pause_playback()
        assert plan.status == ActionStatus.ERROR
        assert "spotify" in plan.result.lower()


def test_si_no_arranca_se_dice_y_no_se_finge_exito():
    """Regresión: la Web API contesta 204 aunque luego no suene nada. Si tras
    mandar reproducir el dispositivo sigue parado, JARVIS lo dice en vez de
    asegurar que está sonando."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    mock_sp.devices.return_value = {"devices": [dict(_PC)]}
    mock_sp.current_playback.return_value = {"is_playing": False, "device": {"id": "esta_pc"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_song("song")
        assert plan.status == ActionStatus.ERROR
        assert "no empezo a sonar" in plan.result.lower()
        mock_sp.start_playback.assert_called_once_with(
            device_id="esta_pc", uris=["spotify:track:1"])


def test_reintenta_si_el_dispositivo_cambia_al_arrancar():
    """La app tarda en registrarse: si el dispositivo al que se mandó la orden
    no suena pero acaba de aparecer otro, se reintenta en el nuevo."""
    mock_sp = MagicMock()
    mock_sp.search.return_value = {"tracks": {"items": [
        {"name": "Song", "uri": "spotify:track:1", "artists": [{"name": "Artist"}]},
    ]}}
    pc_apagado = dict(_PC, is_active=False)
    # 1º intento: suena en la PC vieja -> no; aparece el PC recién abierto
    mock_sp.devices.side_effect = [
        {"devices": [dict(pc_apagado, id="pc_vieja")]},
        {"devices": [dict(pc_apagado, id="pc_vieja")]},
        {"devices": [dict(_PC, id="pc_nueva")]},
    ]
    mock_sp.current_playback.return_value = {"is_playing": True, "device": {"id": "pc_nueva"}}
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.play_song("song")
        assert plan.status == ActionStatus.EXECUTED
        assert mock_sp.start_playback.call_args_list[-1].kwargs["device_id"] == "pc_nueva"


def test_espera_de_apertura_cubre_el_arranque_en_frio_medido():
    """MEDIDO: la app tardó 14,8 s en registrarse en este equipo. Con la espera
    anterior (15 s) la primera petición del día quedaba al filo y fallaba por
    carrera con el arranque de la app."""
    assert S.ESPERA_APERTURA_SEGUNDOS >= 25


def test_anterior_403_explica_que_es_por_tiempo_no_por_premium():
    """Regresión: `previous` devolvía un 403 y JARVIS culpaba a la cuenta
    Premium. Con cuenta Premium de verdad (se puede reproducir), Spotify
    responde 403 Restriction violated al retroceder en los primeros segundos
    de la canción: el mensaje tiene que decir eso, no mentir sobre Premium."""
    mock_sp = _cliente()
    mock_sp.previous_track.side_effect = _spotify_exception(403, "Restriction violated")
    with patch("jarvis_local.tools.spotify.has_credentials", return_value=True), \
         patch("jarvis_local.tools.spotify._client", return_value=mock_sp):
        plan = S.previous_track()
        assert plan.status == ActionStatus.ERROR
        assert "premium" not in plan.result.lower()
        assert "segundos" in plan.result.lower()
