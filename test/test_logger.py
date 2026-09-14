"""PLAN_EJECUCION FASE J · J4 — techo de memoria en actions.log/errors.log.

Se escriben en CADA `chat()`; sin rotacion crecen sin limite en una sesion
larga. `ActionLogger._rotar()` replica el mismo patron ya usado en
decisions.jsonl (agent/decision_log.py) y trace.jsonl (observability.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety import logger as logger_mod
from jarvis_local.safety.logger import ActionLogger


def _logger_en(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_mod, "get_config", lambda: {
        "logging": {"dir": ".", "actions_log": "actions.log",
                    "errors_log": "errors.log"}})
    monkeypatch.setattr(logger_mod, "BASE_DIR", tmp_path)
    return ActionLogger()


def test_actions_log_rota_al_superar_el_limite(tmp_path, monkeypatch):
    lg = _logger_en(tmp_path, monkeypatch)
    monkeypatch.setattr(logger_mod, "_MAX_LINEAS", 10)
    for i in range(25):
        lg.log_action(instruction=f"entrada {i}", result="ok")
    lineas = lg.actions_path.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 10
    assert '"entrada 24"' in lineas[-1]


def test_errors_log_rota_al_superar_el_limite(tmp_path, monkeypatch):
    lg = _logger_en(tmp_path, monkeypatch)
    monkeypatch.setattr(logger_mod, "_MAX_LINEAS", 5)
    for i in range(12):
        lg.log_error("fuente", f"error {i}")
    lineas = lg.errors_path.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 5
    assert '"error 11"' in lineas[-1]


def test_log_action_no_rota_por_debajo_del_limite(tmp_path, monkeypatch):
    lg = _logger_en(tmp_path, monkeypatch)
    monkeypatch.setattr(logger_mod, "_MAX_LINEAS", 100)
    for i in range(5):
        lg.log_action(instruction=f"entrada {i}", result="ok")
    lineas = lg.actions_path.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 5


if __name__ == "__main__":
    print("usa pytest (estas pruebas usan fixtures)")
