"""PLAN_EJECUCION FASE F · F1 — brillo (brightnessctl).

brightnessctl se simula. Se comprueban: detección en runtime, el límite
inferior duro (nunca a oscuras sin poder corregir), y el VERIFY con sus tres
desenlaces.
"""
import os
import re
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import brightness as B

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or", re.I)


def _bctl_fake(estado):
    """Devuelve un _bctl simulado: `estado['pct']` es el brillo actual (0-100),
    max=100. `set N%` lo mueve (salvo estado['muta']=False)."""
    def _bctl(*args):
        if args[:2] == ("-m", "get"):
            return subprocess.CompletedProcess(args, 0, str(estado["pct"]), "")
        if args[:2] == ("-m", "max"):
            return subprocess.CompletedProcess(args, 0, "100", "")
        if args and args[0] == "set":
            if estado.get("rc", 0) != 0:
                return subprocess.CompletedProcess(args, estado["rc"], "", "sin permiso")
            if estado.get("muta", True):
                estado["pct"] = int(args[1].rstrip("%"))
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")
    return _bctl


def _patch(monkeypatch, estado, hay=True):
    monkeypatch.setattr(B, "_hay_brightnessctl", lambda: hay)
    monkeypatch.setattr(B, "_bctl", _bctl_fake(estado))
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)


def test_sin_brightnessctl_lo_dice(monkeypatch):
    _patch(monkeypatch, {"pct": 50}, hay=False)
    plan = B.set_brightness(60)
    assert plan.status == ActionStatus.ERROR
    assert "brightnessctl" in plan.result and "apt install" in plan.result


def test_fijar_y_verificar(monkeypatch):
    est = {"pct": 20}
    _patch(monkeypatch, est)
    plan = B.set_brightness(60)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "60 por ciento" in plan.result
    assert est["pct"] == 60


def test_limite_inferior_nunca_a_oscuras(monkeypatch):
    est = {"pct": 80}
    _patch(monkeypatch, est)
    plan = B.set_brightness(0)
    assert plan.status == ActionStatus.EXECUTED
    assert est["pct"] == B.MIN_BRILLO_PCT          # no bajó a 0
    assert f"no bajo del {B.MIN_BRILLO_PCT}%" in plan.result


def test_rc0_pero_no_se_movio_es_error(monkeypatch):
    _patch(monkeypatch, {"pct": 30, "muta": False})   # 'set' devuelve 0 pero no cambia
    plan = B.set_brightness(70)
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert "no se quedó ahí" in plan.result
    assert not _EXITO.search(plan.result)


def test_sin_lectura_de_vuelta_salvedad(monkeypatch):
    est = {"pct": 40}
    _patch(monkeypatch, est)
    with patch.object(B, "get_brightness", return_value=None):
        plan = B.set_brightness(55)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "no pude" in plan.result.lower() or "no pude confirmar" in plan.result.lower()


def test_subir_parte_del_valor_actual(monkeypatch):
    est = {"pct": 45}
    _patch(monkeypatch, est)
    B.brightness_up()
    assert est["pct"] == 55


def test_parser_enruta_brillo():
    assert parse_intent("sube el brillo").tool == "brightness_up"
    assert parse_intent("pantalla más oscura").tool == "brightness_down"
    r = parse_intent("pon el brillo al 35")
    assert r.tool == "brightness_set" and r.arguments["level"] == 35
    # el volumen no se ve afectado
    assert parse_intent("sube el volumen").tool == "volume_up"


if __name__ == "__main__":
    print("usa pytest")
