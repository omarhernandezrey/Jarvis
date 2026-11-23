"""TAREA D1 — `jarvis doctor`: diagnóstico del entorno."""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from jarvis_local import doctor


def test_ollama_caido_es_falta():
    with patch("jarvis_local.ollama_client.client.OllamaClient") as C:
        C.return_value.is_running.return_value = False
        lineas = doctor._check_ollama()
    assert len(lineas) == 1
    ok, texto = lineas[0]
    assert not ok
    assert texto.startswith(doctor.NO)
    assert "ollama serve" in texto


def test_ollama_ok_con_modelos_presentes():
    with patch("jarvis_local.ollama_client.client.OllamaClient") as C:
        C.return_value.is_running.return_value = True
        C.return_value.list_models.return_value = [
            {"name": "qwen2.5:3b"}, {"name": "llama3.2:3b"}, {"name": "bge-m3:latest"},
        ]
        lineas = doctor._check_ollama()
    assert all(ok for ok, _ in lineas)
    assert any("Modelo memoria semántica" in t for _, t in lineas)


def test_ollama_modelo_faltante_se_reporta_con_comando():
    with patch("jarvis_local.ollama_client.client.OllamaClient") as C:
        C.return_value.is_running.return_value = True
        C.return_value.list_models.return_value = [{"name": "qwen2.5:3b"}]  # falta bge-m3
        lineas = doctor._check_ollama()
    faltas = [t for ok, t in lineas if not ok]
    assert any("bge-m3" in t and "ollama pull" in t for t in faltas)


def test_secrets_ausente_es_warn_no_falta(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "_check_secrets",
                        doctor._check_secrets)  # sin cambios; solo forzamos path
    with patch("jarvis_local.config.BASE_DIR", tmp_path):
        lineas = doctor._check_secrets()
    ok, texto = lineas[0]
    assert texto.startswith(doctor.WARN)      # opcional, no crítico


def test_diagnosticar_devuelve_informe_y_no_lanza():
    # Todo mockeado a "presente" -> criticos_ok True
    with patch.object(doctor, "_check_red", return_value=doctor._linea(doctor.OK, "Internet")), \
         patch.object(doctor, "_check_ollama",
                      return_value=[doctor._linea(doctor.OK, "Ollama")]), \
         patch.object(doctor, "_check_secrets",
                      return_value=[doctor._linea(doctor.OK, "secrets.yaml")]), \
         patch.object(doctor, "_check_google_calendar",
                      return_value=doctor._linea(doctor.WARN, "Google Calendar")), \
         patch.object(doctor, "_check_spotify",
                      return_value=doctor._linea(doctor.WARN, "Spotify")), \
         patch.object(doctor, "_check_microfono",
                      return_value=doctor._linea(doctor.OK, "Micrófono")), \
         patch.object(doctor, "_check_navegador",
                      return_value=doctor._linea(doctor.OK, "Navegador")):
        ok, informe = doctor.diagnosticar()
    assert ok is True
    assert "diagnóstico del entorno" in informe
    assert "Todo lo esencial está listo." in informe


def test_diagnosticar_marca_no_ok_si_algo_falta():
    with patch.object(doctor, "_check_red", return_value=doctor._linea(doctor.OK, "Internet")), \
         patch.object(doctor, "_check_ollama",
                      return_value=[doctor._linea(doctor.NO, "Ollama", "no responde")]), \
         patch.object(doctor, "_check_secrets", return_value=[]), \
         patch.object(doctor, "_check_google_calendar",
                      return_value=doctor._linea(doctor.WARN, "GCal")), \
         patch.object(doctor, "_check_spotify", return_value=doctor._linea(doctor.WARN, "Sp")), \
         patch.object(doctor, "_check_microfono", return_value=doctor._linea(doctor.OK, "Mic")), \
         patch.object(doctor, "_check_navegador", return_value=doctor._linea(doctor.OK, "Nav")):
        ok, _ = doctor.diagnosticar()
    assert ok is False


def test_cli_doctor_no_arranca_jarvis(monkeypatch):
    """`python -m jarvis_local.cli doctor` no debe iniciar el asistente."""
    from jarvis_local import cli

    monkeypatch.setattr(sys, "argv", ["cli", "doctor"])
    called = {"init": False}
    monkeypatch.setattr(cli, "init_jarvis",
                        lambda *a, **k: called.__setitem__("init", True))
    with patch.object(doctor, "diagnosticar", return_value=(True, "ok")):
        try:
            cli.main()
        except SystemExit as e:
            assert e.code == 0
    assert called["init"] is False


# ---------------------------------------------------------------------
# _check_spotify: validacion real del token (no solo "el archivo existe").
# ---------------------------------------------------------------------

def test_doctor_spotify_sin_cache_ni_respaldo_pide_reauth(tmp_path, monkeypatch):
    from jarvis_local.tools import spotify as S
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr("jarvis_local.config.BASE_DIR", tmp_path)
    ok, texto = doctor._check_spotify()
    assert texto.startswith(doctor.WARN)
    assert "--reauth-spotify" in texto


def test_doctor_spotify_token_valido(tmp_path, monkeypatch):
    from jarvis_local.tools import spotify as S
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr("jarvis_local.config.BASE_DIR", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / ".spotify_cache").write_text("{}")
    monkeypatch.setattr(S, "_client", lambda: MagicMock())
    ok, texto = doctor._check_spotify()
    assert ok is True
    assert "válido" in texto


def test_doctor_spotify_token_caducado_es_falta(tmp_path, monkeypatch):
    from jarvis_local.tools import spotify as S
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr("jarvis_local.config.BASE_DIR", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / ".spotify_cache").write_text("{}")
    monkeypatch.setattr(S, "_client", lambda: None)
    monkeypatch.setattr(S, "_ultimo_error_token", None)
    ok, texto = doctor._check_spotify()
    assert not ok
    assert "--reauth-spotify" in texto


def test_doctor_spotify_sin_red_no_verificable(tmp_path, monkeypatch):
    """Sin internet el doctor NO afirma que el token esta muerto."""
    import requests

    from jarvis_local.tools import spotify as S
    monkeypatch.setattr(S, "has_credentials", lambda: True)
    monkeypatch.setattr("jarvis_local.config.BASE_DIR", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / ".spotify_cache").write_text("{}")
    monkeypatch.setattr(S, "_client", lambda: None)
    monkeypatch.setattr(S, "_ultimo_error_token",
                        requests.exceptions.ConnectionError("sin red"))
    ok, texto = doctor._check_spotify()
    assert texto.startswith(doctor.WARN)
    assert "no verificable" in texto


# ── Voz de salida (las dos capas) ─────────────────────────────────────────
# Antes el doctor no comprobaba la voz: la unica forma de descubrir que
# Jarvis se habia quedado mudo era hablarle y no oir nada.

def test_doctor_avisa_si_edge_tts_esta_en_version_bloqueada(monkeypatch):
    """La causa real de la mudez: edge-tts 7.2.8, que Microsoft rechaza con
    403. El doctor tiene que senalar la version, no solo que el paquete
    importe."""
    import edge_tts

    from jarvis_local import doctor

    monkeypatch.setattr(edge_tts, "__version__", "7.2.8", raising=False)
    lineas = doctor._check_voz_salida()
    principal = next(t for _, t in lineas if "Voz principal" in t)
    assert "403" in principal
    assert "pip install -U edge-tts" in principal


def test_doctor_ok_con_edge_tts_al_dia(monkeypatch):
    import edge_tts

    from jarvis_local import doctor

    monkeypatch.setattr(edge_tts, "__version__", "7.3.1", raising=False)
    lineas = doctor._check_voz_salida()
    ok, principal = next((o, t) for o, t in lineas if "Voz principal" in t)
    assert ok is True
    assert "7.3.1" in principal


def test_doctor_avisa_si_falta_la_voz_local_de_respaldo(monkeypatch):
    """Sin la capa 2, un fallo de la capa 1 vuelve a significar silencio
    total: eso es un aviso, no un detalle informativo."""
    from jarvis_local import doctor
    from jarvis_local.voice import tts

    monkeypatch.setattr(tts, "is_piper_available", lambda: False)
    lineas = doctor._check_voz_salida()
    ok, respaldo = next((o, t) for o, t in lineas if "respaldo" in t)
    assert ok is False
    assert "piper.download_voices" in respaldo


def test_doctor_incluye_la_voz_en_el_informe():
    from jarvis_local.doctor import diagnosticar

    _, informe = diagnosticar()
    assert "Voz principal" in informe
    assert "Voz de respaldo (local)" in informe
