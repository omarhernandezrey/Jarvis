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
