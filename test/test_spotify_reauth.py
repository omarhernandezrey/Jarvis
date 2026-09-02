"""TAREA B6 — Spotify: re-autorización accionable cuando el token está muerto."""
import os
import sys
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
