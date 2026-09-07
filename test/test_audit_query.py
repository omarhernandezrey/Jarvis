"""PLAN_EJECUCION FASE D · D2.3 — "qué hiciste hoy" / "qué cambiaste ayer".

La consulta de la auditoría va por la ruta del PARSER (sin agente): es
frecuente y no debe costar una llamada al LLM.
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety.audit import AuditLog
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


def _log(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl")


def _seed(a):
    v = ActionPlan(action="fijar_volumen", params={"nivel": 30}, risk=RiskLevel.EXECUTE)
    v.status = ActionStatus.EXECUTED
    v.result = "Volumen al 30 por ciento, senor."
    v.params["verify"] = {"ok": True, "method": "get_volume", "detail": "volumen=30%"}
    a.record_plan(v, source="parser")
    d = ActionPlan(action="borrar_archivo", params={"path": "/x/viejo.txt"},
                   risk=RiskLevel.DELETE)
    d.status = ActionStatus.EXECUTED
    a.record_plan(d, source="confirmacion", confirmed=True)


def test_query_audit_resume_lo_de_hoy(tmp_path, monkeypatch):
    from jarvis_local.tools import audit_query

    a = _log(tmp_path)
    _seed(a)
    monkeypatch.setattr(audit_query, "audit", a)

    plan = audit_query.query_audit("hoy")
    assert plan.status == ActionStatus.EXECUTED
    txt = plan.result
    assert "registré 2 acciones" in txt
    assert "fijar_volumen (nivel=30)" in txt and "hecho y verificado" in txt
    assert "borrar_archivo" in txt and "[confirmado por usted]" in txt


def test_query_audit_sin_nada(tmp_path, monkeypatch):
    from jarvis_local.tools import audit_query

    a = _log(tmp_path)
    monkeypatch.setattr(audit_query, "audit", a)
    plan = audit_query.query_audit("hoy")
    assert plan.result == "No registré ninguna acción hoy, senor."


def test_query_audit_ayer_no_mezcla_con_hoy(tmp_path, monkeypatch):
    from jarvis_local.tools import audit_query

    a = _log(tmp_path)
    _seed(a)  # hoy
    ayer = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    with open(a.path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ayer, "tool": "crear_carpeta", "risk": "CREATE",
                            "params": {"path": "/x/nueva"}, "verify": None,
                            "confirmed": None, "status": "executed",
                            "outcome": "", "source": "parser"}) + "\n")
    monkeypatch.setattr(audit_query, "audit", a)

    hoy = audit_query.query_audit("hoy").result
    assert "crear_carpeta" not in hoy
    ayer_txt = audit_query.query_audit("ayer").result
    assert "crear_carpeta" in ayer_txt and "fijar_volumen" not in ayer_txt


def test_parser_enruta_la_consulta_de_auditoria():
    from jarvis_local.intent.parser import parse_intent

    for frase in ("qué hiciste hoy", "que has hecho hoy",
                  "muéstrame la auditoría", "qué acciones ejecutaste"):
        r = parse_intent(frase)
        assert r.kind == "tool_read" and r.tool == "audit_query", frase
        assert r.arguments["dia"] == "hoy", frase

    r = parse_intent("qué cambiaste ayer")
    assert r.tool == "audit_query" and r.arguments["dia"] == "ayer"


def test_audit_query_no_lo_ve_el_agente():
    """D2: la consulta es de la ruta rápida; el LLM no la ofrece."""
    from jarvis_local.tools import catalog

    assert "consultar_auditoria" not in [c.name for c in catalog.agent_contracts()]
    assert "audit_query" in catalog.read_tools()


if __name__ == "__main__":
    print("usa pytest (estas pruebas usan fixtures)")
