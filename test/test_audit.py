"""PLAN_EJECUCION FASE D · D2 — auditoría append-only.

Blinda: que TODA acción de escritura/destructiva/sistema quede registrada con
sus parámetros, el VerifyOutcome de D1 y si hubo confirmación; que las
lecturas NO se auditen; que los secretos se redacten antes de tocar disco;
que el fichero sea append-only y rote por tamaño sin crecer sin límite.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta

from jarvis_local.safety.audit import AuditLog
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


def _log(tmp_path, **kw):
    return AuditLog(tmp_path / "audit.jsonl", **kw)


def _lines(path):
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_registra_accion_de_escritura_con_verify_y_confirmacion(tmp_path):
    a = _log(tmp_path)
    plan = ActionPlan(action="fijar_volumen", params={"nivel": 50}, risk=RiskLevel.EXECUTE)
    plan.status = ActionStatus.EXECUTED
    plan.result = "Volumen al 50 por ciento, senor."
    plan.params["verify"] = {"ok": True, "method": "get_volume", "detail": "volumen=50%"}

    assert a.record_plan(plan, source="parser") is True
    e = _lines(a.path)[0]
    assert e["tool"] == "fijar_volumen"
    assert e["risk"] == "EXECUTE"
    assert e["params"] == {"nivel": 50}          # sin la clave 'verify' dentro
    assert e["verify"] == {"ok": True, "method": "get_volume", "detail": "volumen=50%"}
    assert e["confirmed"] is None
    assert e["status"] == "executed"
    assert e["source"] == "parser"
    assert "ts" in e


def test_lecturas_no_se_auditan(tmp_path):
    a = _log(tmp_path)
    plan = ActionPlan(action="listar_archivos", risk=RiskLevel.READ)
    plan.status = ActionStatus.EXECUTED
    assert a.record_plan(plan, source="parser") is False
    assert not a.path.exists() or _lines(a.path) == []


def test_confirmacion_explicita_queda_registrada(tmp_path):
    a = _log(tmp_path)
    plan = ActionPlan(action="borrar_archivo", params={"path": "/x/y.txt"},
                      risk=RiskLevel.DELETE)
    plan.status = ActionStatus.EXECUTED
    a.record_plan(plan, source="confirmacion", confirmed=True)
    e = _lines(a.path)[0]
    assert e["confirmed"] is True
    assert e["risk"] == "DELETE"


def test_redacta_secretos_antes_de_escribir(tmp_path):
    a = _log(tmp_path)
    plan = ActionPlan(action="ejecutar_comando",
                      params={"command": "curl -H 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345'"},
                      risk=RiskLevel.CRITICAL)
    plan.status = ActionStatus.EXECUTED
    plan.result = "token=supersecreto12345 aplicado"
    a.record_plan(plan, source="agente")
    raw = a.path.read_text(encoding="utf-8")
    assert "abcdefghijklmnopqrstuvwxyz012345" not in raw
    assert "supersecreto12345" not in raw
    assert "[AUTH_HEADER]" in raw or "[REDACTED]" in raw


def test_es_append_only(tmp_path):
    a = _log(tmp_path)
    for i in range(3):
        p = ActionPlan(action=f"t{i}", params={"i": i}, risk=RiskLevel.CREATE)
        p.status = ActionStatus.EXECUTED
        a.record_plan(p, source="parser")
    ls = _lines(a.path)
    assert [e["tool"] for e in ls] == ["t0", "t1", "t2"]   # en orden, nada sobrescrito
    # no hay API de borrado/actualización
    assert not hasattr(a, "update") and not hasattr(a, "delete")


def test_rotacion_por_tamano_conserva_los_ultimos(tmp_path):
    a = _log(tmp_path, max_bytes=400, keep=2)
    for i in range(60):
        p = ActionPlan(action=f"accion_numero_{i:03d}", params={"relleno": "x" * 20},
                       risk=RiskLevel.EXECUTE)
        p.status = ActionStatus.EXECUTED
        a.record_plan(p, source="parser")
    rotados = sorted(tmp_path.glob("audit-*.jsonl"))
    assert len(rotados) == 2                    # keep=2, los más viejos borrados
    assert a.path.exists()
    # el registro completo (rotados + activo) sigue siendo leíble y ordenado
    todo = a.read(limit=10_000)
    nums = [int(e["tool"].split("_")[-1]) for e in todo]
    assert nums == sorted(nums)
    assert nums[-1] == 59                       # la última acción está


def test_read_filtra_por_fecha(tmp_path):
    a = _log(tmp_path)
    hoy = ActionPlan(action="hoy", risk=RiskLevel.EXECUTE)
    hoy.status = ActionStatus.EXECUTED
    a.record_plan(hoy, source="parser")
    # inyecta una entrada "de ayer" a mano (append-only, misma vía de lectura)
    ayer = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    with open(a.path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ayer, "tool": "ayer", "risk": "EXECUTE",
                            "params": {}, "verify": None, "confirmed": None,
                            "status": "executed", "outcome": "", "source": "parser"}) + "\n")

    de_hoy = [e["tool"] for e in a.for_day(date.today())]
    assert "hoy" in de_hoy and "ayer" not in de_hoy
    de_ayer = [e["tool"] for e in a.for_day(date.today() - timedelta(days=1))]
    assert "ayer" in de_ayer and "hoy" not in de_ayer


def test_last_entry_vacio_devuelve_none(tmp_path):
    a = _log(tmp_path)
    assert a.last_entry() is None


def test_last_entry_devuelve_la_mas_reciente(tmp_path):
    a = _log(tmp_path)
    for i in range(5):
        p = ActionPlan(action=f"accion_{i}", risk=RiskLevel.EXECUTE)
        p.status = ActionStatus.EXECUTED
        a.record_plan(p, source="parser")
    e = a.last_entry()
    assert e is not None
    assert e["tool"] == "accion_4"


def test_last_entry_tras_rotacion_lee_el_fichero_activo(tmp_path):
    a = _log(tmp_path, max_bytes=400, keep=2)
    for i in range(60):
        p = ActionPlan(action=f"accion_numero_{i:03d}", params={"relleno": "x" * 20},
                       risk=RiskLevel.EXECUTE)
        p.status = ActionStatus.EXECUTED
        a.record_plan(p, source="parser")
    e = a.last_entry()
    assert e is not None
    assert e["tool"] == "accion_numero_059"


if __name__ == "__main__":
    import inspect
    import tempfile
    from pathlib import Path
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and list(inspect.signature(fn).parameters) == ["tmp_path"]:
            fn(Path(tempfile.mkdtemp()))
    print("OK: tests de auditoría (D2) sin fixtures pasaron (usa pytest para todos).")
