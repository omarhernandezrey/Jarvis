"""PLAN_EJECUCION FASE J · J3 — observabilidad: una traza por petición.

Blinda que `record()`/`traza()`/`formatear()` unen de verdad lo que
`jarvis.py` ya sabe (capas, tiempos, capa que resolvió) con lo que
`decisions.jsonl` (agente) y `audit.jsonl` (D2, VERIFY) ya registraban, por
ventana de tiempo — sin id de petición compartido explícito.
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local import observability as obs


def test_record_escribe_una_linea_jsonl(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "TRACE_PATH", tmp_path / "trace.jsonl")
    ini = datetime.now()
    fin = ini + timedelta(milliseconds=15)
    obs.record(request_id="abc123", entrada="que hora es",
              capas=[{"capa": "parser", "ms": 4.0, "coincidio": True}],
              capa_resuelta="parser", resultado="Son las 10:00, senor.",
              elapsed_ms=15.0, ts_inicio=ini, ts_fin=fin)
    lineas = obs.TRACE_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1
    entry = json.loads(lineas[0])
    assert entry["request_id"] == "abc123"
    assert entry["capa_resuelta"] == "parser"
    assert entry["capas"][0]["capa"] == "parser"


def test_record_nunca_lanza_si_algo_falla(tmp_path, monkeypatch):
    # TRACE_PATH apunta a un directorio inexistente sin permiso de crearlo:
    # simulamos el fallo con una ruta que no se puede crear (archivo como padre).
    bloqueado = tmp_path / "no_es_directorio"
    bloqueado.write_text("x")
    monkeypatch.setattr(obs, "TRACE_PATH", bloqueado / "trace.jsonl")
    ini = datetime.now()
    obs.record(request_id="x", entrada="e", capas=[], capa_resuelta="parser",
              resultado="r", elapsed_ms=1.0, ts_inicio=ini, ts_fin=ini)
    # no lanzó -- eso es lo que se comprueba (llegar aquí sin excepción)


def test_traza_vacia_sin_fichero(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "TRACE_PATH", tmp_path / "no_existe.jsonl")
    assert obs.traza() == []


def test_traza_se_enriquece_con_decisiones_del_agente_en_su_ventana(tmp_path, monkeypatch):
    from jarvis_local.safety.audit import audit as audit_singleton

    trace_path = tmp_path / "trace.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(obs, "TRACE_PATH", trace_path)
    monkeypatch.setattr(obs, "_DECISIONS_PATH", decisions_path)
    # aísla también la auditoría D2: si no, `traza()` leería el audit.jsonl
    # real del proyecto y el resultado dependería de lo que hubiera en él.
    monkeypatch.setattr(audit_singleton, "path", tmp_path / "audit.jsonl")

    ini = datetime(2026, 1, 1, 12, 0, 0)
    fin = ini + timedelta(seconds=3)
    obs.record(request_id="r1", entrada="abre chrome y busca vuelos",
              capas=[{"capa": "parser", "ms": 5.0, "coincidio": False},
                     {"capa": "agente", "ms": 2900.0, "coincidio": True}],
              capa_resuelta="agente", resultado="Listo, senor.",
              elapsed_ms=2905.0, ts_inicio=ini, ts_fin=fin)

    # una decisión DENTRO de la ventana del turno
    dentro = {"ts": (ini + timedelta(seconds=1)).isoformat(),
              "entrada": "abre chrome y busca vuelos", "confianza": 0.7,
              "herramientas": ["abrir_aplicacion"], "resultado": "ok",
              "llm_calls": 1, "llm_secs": 1.2}
    # una decisión de OTRO turno, muy anterior -- no debe colarse
    fuera = {"ts": (ini - timedelta(hours=1)).isoformat(),
             "entrada": "otra cosa de antes", "confianza": 0.9,
             "herramientas": [], "resultado": "ok", "llm_calls": 1, "llm_secs": 0.5}
    decisions_path.write_text(
        json.dumps(fuera) + "\n" + json.dumps(dentro) + "\n", encoding="utf-8")

    trazas = obs.traza(1)
    assert len(trazas) == 1
    t = trazas[0]
    assert len(t["decisiones_agente"]) == 1
    assert t["decisiones_agente"][0]["herramientas"] == ["abrir_aplicacion"]
    assert t["auditoria_d2"] == []


def test_formatear_incluye_capas_y_resultado():
    req = {
        "request_id": "abc", "entrada": "que hora es", "capa_resuelta": "parser",
        "elapsed_ms": 5.2, "resultado": "Son las 10:00, senor.",
        "capas": [{"capa": "parser", "ms": 5.0, "coincidio": True}],
        "decisiones_agente": [], "auditoria_d2": [],
    }
    texto = obs.formatear(req)
    assert "parser" in texto
    assert "Son las 10:00, senor." in texto
    assert "5.2" in texto or "5.0" in texto


if __name__ == "__main__":
    print("usa pytest")
