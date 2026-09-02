"""TAREA B5 — Google Calendar: refresh de token + re-autorización accionable.

Antes: un token OAuth muerto (invalid_grant) hacía que "mis próximos eventos"
devolviera el traceback tecnico y volviera a fallar igual en cada llamada.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import gcalendar as G

pytest.importorskip("googleapiclient")
pytest.importorskip("google_auth_oauthlib")


@pytest.fixture(autouse=True)
def _fake_paths(tmp_path, monkeypatch):
    """TOKEN_FILE y CREDENTIALS_FILE apuntan a un tmp (no tocar los reales)."""
    monkeypatch.setattr(G, "TOKEN_FILE", tmp_path / "token.json")
    monkeypatch.setattr(G, "CREDENTIALS_FILE", tmp_path / "credentials.json")
    yield


def test_sin_credenciales_da_instrucciones_de_setup():
    plan = G.upcoming_events(3)
    assert plan.status == ActionStatus.ERROR
    assert "--reauth-calendar" in plan.result


def test_token_muerto_da_mensaje_accionable_sin_traceback():
    from google.auth.exceptions import RefreshError

    G.CREDENTIALS_FILE.write_text("{}")
    G.TOKEN_FILE.write_text("{}")

    fake_creds = MagicMock(valid=False, expired=True, refresh_token="x")
    fake_creds.refresh.side_effect = RefreshError("invalid_grant: Bad Request")

    with patch("google.oauth2.credentials.Credentials.from_authorized_user_file",
               return_value=fake_creds):
        plan = G.upcoming_events(3)

    assert plan.status == ActionStatus.ERROR
    assert "reauth-calendar" in plan.result
    assert "invalid_grant" not in plan.result          # sin jerga tecnica
    assert "Traceback" not in plan.result
    assert not G.TOKEN_FILE.exists()                    # el token muerto se borro


def test_token_refrescable_construye_el_servicio():
    G.CREDENTIALS_FILE.write_text("{}")
    G.TOKEN_FILE.write_text("{}")

    fake_creds = MagicMock(valid=False, expired=True, refresh_token="x")

    def _refresh(_req):
        fake_creds.valid = True

    fake_creds.refresh.side_effect = _refresh
    fake_creds.to_json.return_value = "{}"
    built = MagicMock()
    built.events().list().execute.return_value = {"items": []}

    with patch("google.oauth2.credentials.Credentials.from_authorized_user_file",
               return_value=fake_creds), \
         patch("googleapiclient.discovery.build", return_value=built):
        plan = G.upcoming_events(3)

    fake_creds.refresh.assert_called_once()
    assert plan.status == ActionStatus.EXECUTED


def test_reauthorize_sin_credenciales_devuelve_setup():
    assert "--reauth-calendar" in G.reauthorize()
