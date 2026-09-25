"""TAREA B6 — Spotify: re-autorización accionable cuando el token está muerto."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import spotify as S


@pytest.fixture(autouse=True)
def _con_credenciales(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "get_secrets", lambda: {"spotify": {
        "client_id": "cid", "client_secret": "csec",
        "redirect_uri": "http://127.0.0.1:8888/callback"}})
    monkeypatch.setattr(S, "_CACHE_PATH", tmp_path / ".spotify_cache")
    (tmp_path / ".spotify_cache").write_text("{}")
    yield


def test_client_no_abre_navegador_solo():
    """open_browser debe ir en False: una peticion normal nunca abre el
    navegador por su cuenta."""
    captured = {}

    class _FakeOAuth:
        def __init__(self, **kw):
            captured.update(kw)

    with patch.dict(sys.modules, {"spotipy": MagicMock(),
                                  "spotipy.oauth2": MagicMock(SpotifyOAuth=_FakeOAuth)}):
        S._client()
    assert captured.get("open_browser") is False


def _err(name, msg, http=None):
    e = type(name, (Exception,), {})(msg)
    if http is not None:
        e.http_status = http
    return e


@pytest.mark.parametrize("err", [
    _err("SpotifyOauthError", "error: invalid_grant"),
    _err("SpotifyException", "The access token expired", http=401),
    Exception("Refresh token revoked"),
])
def test_token_muerto_da_mensaje_accionable(monkeypatch, err):
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr(S, "_client", lambda: MagicMock())
    monkeypatch.setattr(S, "_buscar_track", MagicMock(side_effect=err))

    plan = S.play_song("bohemian rhapsody")

    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" in plan.result
    assert "invalid_grant" not in plan.result
    assert not S._CACHE_PATH.exists()          # token muerto borrado


def test_error_de_reproduccion_no_pide_reauth(monkeypatch):
    """Un 403 (Premium) NO debe confundirse con token muerto."""
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr(S, "_client", lambda: MagicMock())
    monkeypatch.setattr(S, "_buscar_track",
                        MagicMock(side_effect=_err("SpotifyException", "premium required", http=403)))
    plan = S.play_song("algo")
    assert "--reauth-spotify" not in plan.result
    assert "premium" in plan.result.lower()
    assert S._CACHE_PATH.exists()              # NO se borra por un error ajeno al token


# ---------------------------------------------------------------------
# Regresion del "vuelve a fallar": un bache de RED al refrescar el token
# NO debe borrarlo ni pedir reautorizacion (el token sigue siendo valido).
# ---------------------------------------------------------------------

def _spotipy_falso(oauth_cls):
    """Modulos spotipy/spotipy.oauth2 falsos con la clase OAuth dada."""
    return patch.dict(sys.modules, {
        "spotipy": MagicMock(),
        "spotipy.oauth2": MagicMock(SpotifyOAuth=oauth_cls),
    })


def test_error_de_red_conserva_token_y_no_pide_reauth():
    """get_cached_token() explota con ConnectionError (p. ej. sin internet al
    refrescar): el cache NO se borra y el mensaje pide reintentar, no reauth."""
    import requests

    class _OAuthSinRed:
        def __init__(self, **kw):
            pass

        def get_cached_token(self):
            raise requests.exceptions.ConnectionError("sin salida a internet")

    with _spotipy_falso(_OAuthSinRed):
        plan = S.play_song("back in black")

    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" not in plan.result
    assert "conexion" in plan.result.lower()
    assert S._CACHE_PATH.exists()              # el token NO se toca
    assert S._CACHE_PATH.read_text() == "{}"


def test_token_invalido_borra_cache_y_pide_reauth():
    """El refresh responde invalid_grant (token revocado de verdad): ahi SI
    se borra el cache muerto y se pide reautorizar."""
    from spotipy.exceptions import SpotifyOauthError

    class _OAuthTokenMuerto:
        def __init__(self, **kw):
            pass

        def get_cached_token(self):
            raise SpotifyOauthError("error: invalid_grant",
                                    error="invalid_grant",
                                    error_description="Refresh token revoked")

    with _spotipy_falso(_OAuthTokenMuerto):
        plan = S.play_song("back in black")

    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" in plan.result
    assert not S._CACHE_PATH.exists()          # token muerto borrado


def test_error_de_red_no_contamina_la_siguiente_llamada():
    """Tras un fallo de red, la siguiente llamada con _client mockeado a None
    debe seguir pidiendo reauth (el estado del error no se filtra)."""
    import requests

    class _OAuthSinRed:
        def __init__(self, **kw):
            pass

        def get_cached_token(self):
            raise requests.exceptions.ConnectionError("sin salida a internet")

    with _spotipy_falso(_OAuthSinRed):
        S.play_song("algo")

    with patch.object(S, "_client", return_value=None):
        plan = S.play_song("algo")
    assert "--reauth-spotify" in plan.result


# ---------------------------------------------------------------------
# reauthorize(): debe verificar que el token REALMENTE se guardo (spotipy
# traga los OSError de escritura con solo un warning en su logger).
# ---------------------------------------------------------------------

def test_reauthorize_avisa_si_no_se_guardo_el_token():
    class _OAuthQueNoEscribe:
        def __init__(self, **kw):
            pass

        def get_access_token(self, **kw):
            return "tok"

    S._CACHE_PATH.unlink(missing_ok=True)
    with _spotipy_falso(_OAuthQueNoEscribe):
        msg = S.reauthorize()
    assert "no pude guardar el token" in msg


def test_reauthorize_ok_confirma():
    class _OAuthQueEscribe:
        def __init__(self, **kw):
            pass

        def get_access_token(self, **kw):
            S._CACHE_PATH.write_text("{}")
            return "tok"

    with _spotipy_falso(_OAuthQueEscribe):
        msg = S.reauthorize()
    assert "autorizado" in msg.lower()


def test_reauthorize_puerto_ocupado_da_mensaje_claro():
    """Si el callback no puede bindear el puerto 8888 (u otro fallo del flujo
    OAuth), el usuario ve un mensaje accionable, no un traceback."""
    class _OAuthPuertoOcupado:
        def __init__(self, **kw):
            pass

        def get_access_token(self, **kw):
            raise OSError("Address already in use")

    with _spotipy_falso(_OAuthPuertoOcupado):
        msg = S.reauthorize()
    assert "No pude completar la autorizacion" in msg
    assert "8888" in msg


# ---------------------------------------------------------------------
# Copia de seguridad del token: borrado externo o corrupcion del cache se
# repara solo, sin que el usuario tenga que reautorizar.
# ---------------------------------------------------------------------

_TOKEN_VIVO = {"access_token": "tok", "refresh_token": "rt",
               "expires_at": 9_999_999_999, "scope": "todo"}


class _OAuthLeeCache:
    """OAuth falso que lee el cache del disco, como hace el real."""

    def __init__(self, cache_path=None, **kw):
        self.cache_path = cache_path

    def get_cached_token(self):
        p = Path(self.cache_path)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text()) or None
        except ValueError:
            return None


def test_respaldo_se_crea_con_token_valido():
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))
    with _spotipy_falso(_OAuthLeeCache):
        assert S._client() is not None
    assert S._backup_path().exists()
    assert json.loads(S._backup_path().read_text()) == _TOKEN_VIVO


def test_client_restaura_token_borrado_externamente():
    """git clean / limpieza de disco borro el cache: se restaura del respaldo
    y la musica sigue sin pedir reautorizar."""
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))
    S._respaldar_cache()
    S._CACHE_PATH.unlink()                              # borrado externo
    with _spotipy_falso(_OAuthLeeCache):
        assert S._client() is not None
    assert json.loads(S._CACHE_PATH.read_text()) == _TOKEN_VIVO


def test_client_restaura_cache_corrupto():
    """Corte a mitad de escritura (JSON invalido): idem."""
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))
    S._respaldar_cache()
    S._CACHE_PATH.write_text("{{{json roto")            # corrupcion
    with _spotipy_falso(_OAuthLeeCache):
        assert S._client() is not None
    assert json.loads(S._CACHE_PATH.read_text()) == _TOKEN_VIVO


def test_borrar_tokens_elimina_cache_y_respaldo():
    """Cuando el token muere de verdad, el respaldo tambien se borra: si no,
    resucitaria un token revocado en la siguiente llamada."""
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))
    S._respaldar_cache()
    S._borrar_tokens()
    assert not S._CACHE_PATH.exists()
    assert not S._backup_path().exists()


# ---------------------------------------------------------------------
# Auto-sanacion de un 401 a mitad de operacion: se intenta renovar con el
# refresh_token antes de molestar al usuario.
# ---------------------------------------------------------------------

def _oauth_con_refresh(func):
    """OAuth falso cuyo refresh_access_token delega en `func`."""
    class _OAuth:
        def __init__(self, **kw):
            pass

        def refresh_access_token(self, rt):
            return func(rt)

    return _OAuth


def test_401_con_refresco_ok_pide_reintentar_sin_reauth(monkeypatch):
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr(S, "_client", lambda: MagicMock())
    monkeypatch.setattr(S, "_buscar_track",
                        MagicMock(side_effect=_err("SpotifyException",
                                                   "The access token expired", http=401)))
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))

    def _escribe_token_fresco(rt):
        S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))

    with _spotipy_falso(_oauth_con_refresh(_escribe_token_fresco)):
        plan = S.play_song("algo")

    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" not in plan.result
    assert "renove el acceso" in plan.result
    assert S._CACHE_PATH.exists()


def test_401_con_refresco_sin_red_conserva_token(monkeypatch):
    import requests

    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr(S, "_client", lambda: MagicMock())
    monkeypatch.setattr(S, "_buscar_track",
                        MagicMock(side_effect=_err("SpotifyException",
                                                   "The access token expired", http=401)))
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))

    def _sin_red(rt):
        raise requests.exceptions.ConnectionError("sin internet")

    with _spotipy_falso(_oauth_con_refresh(_sin_red)):
        plan = S.play_song("algo")

    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" not in plan.result
    assert "conexion" in plan.result.lower()
    assert S._CACHE_PATH.exists()              # el token NO se toca


def test_401_con_refresh_rechazado_borra_cache_y_respaldo(monkeypatch):
    from spotipy.exceptions import SpotifyOauthError

    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr(S, "_client", lambda: MagicMock())
    monkeypatch.setattr(S, "_buscar_track",
                        MagicMock(side_effect=_err("SpotifyException",
                                                   "The access token expired", http=401)))
    S._CACHE_PATH.write_text(json.dumps(_TOKEN_VIVO))
    S._respaldar_cache()

    def _rechazado(rt):
        raise SpotifyOauthError("error: invalid_grant",
                                error="invalid_grant",
                                error_description="Refresh token revoked")

    with _spotipy_falso(_oauth_con_refresh(_rechazado)):
        plan = S.play_song("algo")

    assert plan.status == ActionStatus.ERROR
    assert "--reauth-spotify" in plan.result
    assert not S._CACHE_PATH.exists()
    assert not S._backup_path().exists()
