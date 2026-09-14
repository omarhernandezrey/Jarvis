"""PLAN_EJECUCION FASE J · J3 — "traza de la última petición".

La consulta va por la ruta del PARSER (sin agente), igual que la auditoría
D2: es una vista de observabilidad, no debe costar una llamada al LLM.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local import observability
from jarvis_local.safety.policy import ActionStatus


def _seed(monkeypatch, tmp_path):
    monkeypatch.setattr(observability, "TRACE_PATH", tmp_path / "trace.jsonl")
    monkeypatch.setattr(observability, "_DECISIONS_PATH", tmp_path / "decisions.jsonl")
    from jarvis_local.safety.audit import audit as audit_singleton
    monkeypatch.setattr(audit_singleton, "path", tmp_path / "audit.jsonl")

    ini = datetime.now()
    observability.record(
        request_id="r1", entrada="que hora es",
        capas=[], capa_resuelta="rapida", resultado="Son las 10:00, senor.",
        elapsed_ms=8.0, ts_inicio=ini, ts_fin=ini + timedelta(milliseconds=8))


def test_query_trace_resume_la_ultima_peticion(tmp_path, monkeypatch):
    from jarvis_local.tools import trace_query

    _seed(monkeypatch, tmp_path)
    plan = trace_query.query_trace(1)
    assert plan.status == ActionStatus.EXECUTED
    assert "que hora es" in plan.result
    assert "rapida" in plan.result


def test_query_trace_sin_nada(tmp_path, monkeypatch):
    from jarvis_local.tools import trace_query

    monkeypatch.setattr(observability, "TRACE_PATH", tmp_path / "no_existe.jsonl")
    plan = trace_query.query_trace(1)
    assert plan.result == "No tengo ninguna traza registrada todavía, senor."


def test_parser_enruta_la_consulta_de_traza():
    from jarvis_local.intent.parser import parse_intent

    for frase in ("traza de la última petición", "que paso con mi ultima peticion",
                  "que capas atravesaste"):
        r = parse_intent(frase)
        assert r.kind == "tool_read" and r.tool == "trace_query", frase


def test_traza_no_se_confunde_con_referencia_anaforica_generica():
    """La palabra 'ultima' por sí sola sigue disparando `es_anaforica` para
    frases que SÍ dependen del turno anterior -- solo se adelanta el chequeo
    de traza para su propio patrón (que nombra 'peticion' explícitamente)."""
    from jarvis_local.intent.parser import parse_intent

    r = parse_intent("abreme la ultima")
    assert r.kind == "chat"  # sigue yendo al agente, como antes


def test_trace_query_no_lo_ve_el_agente():
    """La consulta es de la ruta rápida; el LLM no la ofrece."""
    from jarvis_local.tools import catalog

    assert "consultar_traza" not in [c.name for c in catalog.agent_contracts()]
    assert "trace_query" in catalog.read_tools()


if __name__ == "__main__":
    print("usa pytest (estas pruebas usan fixtures)")
