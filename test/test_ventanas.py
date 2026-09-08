"""PLAN_EJECUCION FASE F · F4.2 — ventanas en Wayland.

La capa D-Bus (`gdbus` -> extensión `ventanas-jarvis@local`) se simula. Se
comprueban: detección en runtime, lectura, enfocar con VERIFY real, cerrar
con confirmación + guardia de intocables (E1) por wm_class y por pid, varias
coincidencias -> se pregunta, VERIFY de cierre con sus tres desenlaces, y el
interruptor de integración.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import ventanas as V

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or|cerrada", re.I)


class FakeShell:
    """Estado de ventanas + implementación de List/Activate/Close."""

    def __init__(self, wins):
        self.wins = wins  # lista de dicts

    def call(self, metodo, *cargs):
        if metodo == "List":
            return True, repr((json.dumps(self.wins),)), ""
        wid = int(cargs[0])
        w = next((x for x in self.wins if x["id"] == wid), None)
        if w is None:
            return False, "", f"GDBus.Error:…: ventana {wid} no encontrada"
        if metodo == "Activate":
            for x in self.wins:
                x["has_focus"] = (x["id"] == wid)
            return True, "()", ""
        if metodo == "Close":
            self.wins = [x for x in self.wins if x["id"] != wid]
            return True, "()", ""
        return False, "", "método desconocido"


def _win(id, title, wm_class, pid, focus=False, wtype=0):
    return {"id": id, "title": title, "wm_class": wm_class,
            "wm_class_instance": wm_class.lower(), "pid": pid,
            "window_type": wtype, "frame_type": 0, "has_focus": focus,
            "on_current_workspace": True}


@pytest.fixture
def shell(monkeypatch, tmp_path):
    fk = FakeShell([
        _win(101, "Calculadora", "org.gnome.Calculator", 5000, focus=True),
        _win(102, "Documento nuevo - gedit", "org.gnome.gedit", 5001),
    ])
    monkeypatch.setattr(V, "_hay_gdbus", lambda: True)
    monkeypatch.setattr(V, "_extension_responde", lambda: True)
    monkeypatch.setattr(V, "_call", fk.call)
    monkeypatch.setattr(V, "_SWITCH", tmp_path / "ventanas_integracion.json")
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)
    monkeypatch.setattr(V, "own_pids", lambda: {os.getpid()})
    return fk


# --- detección en runtime -------------------------------------------

def test_sin_gdbus_error_claro(monkeypatch):
    monkeypatch.setattr(V, "_hay_gdbus", lambda: False)
    plan = V.list_windows()
    assert plan.status == ActionStatus.ERROR
    assert "gdbus" in plan.result and "libglib2.0-bin" in plan.result


def test_extension_no_responde_dice_como_instalar(monkeypatch, tmp_path):
    monkeypatch.setattr(V, "_hay_gdbus", lambda: True)
    monkeypatch.setattr(V, "_SWITCH", tmp_path / "s.json")
    monkeypatch.setattr(V, "_extension_responde", lambda: False)
    plan = V.list_windows()
    assert plan.status == ActionStatus.ERROR
    assert "gnome-extensions enable ventanas-jarvis@local" in plan.result


# --- listar --------------------------------------------------------

def test_listar_formatea_y_marca_la_enfocada(shell):
    plan = V.list_windows()
    assert plan.status == ActionStatus.EXECUTED
    assert "Calculadora" in plan.result and "org.gnome.gedit" in plan.result
    assert "id 101" in plan.result


# --- enfocar (VERIFY) -------------------------------------------

def test_enfocar_mueve_el_foco_de_verdad(shell):
    plan = V.focus_window("gedit")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert next(w for w in shell.wins if w["id"] == 102)["has_focus"] is True


def test_enfocar_sin_coincidencia_lo_dice(shell):
    plan = V.focus_window("inkscape")
    assert "No encuentro" in plan.result


def test_enfocar_varias_coincidencias_pregunta(shell):
    shell.wins.append(_win(103, "Calculadora científica", "org.gnome.Calculator", 5002))
    plan = V.focus_window("calc")
    assert plan.status == ActionStatus.BLOCKED
    assert "id exacto" in plan.result and "101" in plan.result and "103" in plan.result


def test_enfocar_activate_falla_es_error_no_finge(shell, monkeypatch):
    monkeypatch.setattr(V, "_call",
                        lambda m, *a: (False, "", "boom") if m == "Activate" else shell.call(m, *a))
    plan = V.focus_window("gedit")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert not _EXITO.search(plan.result)


# --- cerrar: confirmación + intocables + VERIFY ----------------

def test_cerrar_pide_confirmacion_con_titulo_y_app(shell):
    plan = V.plan_close_window("gedit")
    assert plan.status == ActionStatus.PLANNED
    assert "gedit" in plan.simulation_result
    assert "org.gnome.gedit" in plan.simulation_result
    assert "5001" in plan.simulation_result
    assert "/confirmar" in plan.simulation_result


def test_cerrar_ventana_intocable_por_wm_class_se_bloquea(shell):
    shell.wins.append(_win(200, "", "gnome-shell", 9999))
    plan = V.plan_close_window("gnome-shell")
    assert plan.status == ActionStatus.BLOCKED
    assert not _EXITO.search(plan.result)


def test_cerrar_ventana_del_propio_jarvis_se_bloquea_por_pid(shell):
    shell.wins.append(_win(201, "JARVIS", "python3", os.getpid()))
    plan = V.plan_close_window("JARVIS")
    assert plan.status == ActionStatus.BLOCKED
    assert "propio JARVIS" in plan.result


def test_cerrar_varias_coincidencias_pregunta(shell):
    shell.wins.append(_win(103, "Calculadora 2", "org.gnome.Calculator", 5002))
    plan = V.plan_close_window("calculadora")
    assert plan.status == ActionStatus.BLOCKED
    assert "id exacto" in plan.result


def test_execute_cerrar_verifica_que_desaparece(shell):
    plan = V.execute_close_window(102)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert all(w["id"] != 102 for w in shell.wins)


def test_execute_cerrar_que_sigue_abierta_es_salvedad_no_error(shell, monkeypatch):
    # Close "funciona" (rc 0) pero la ventana no se va: diálogo de guardado.
    monkeypatch.setattr(V, "_call",
                        lambda m, *a: (True, "()", "") if m == "Close" else shell.call(m, *a))
    plan = V.execute_close_window(102)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "guardar" in plan.result.lower()
    assert not _EXITO.search(plan.result)


def test_execute_cerrar_reguarda_intocables(shell):
    shell.wins.append(_win(202, "x", "systemd", 1))
    plan = V.execute_close_window(202)
    assert plan.status == ActionStatus.BLOCKED


# --- interruptor de integración ------------------------------

def test_interruptor_desactiva_y_bloquea(shell):
    off = V.set_integracion(False)
    assert off.status == ActionStatus.EXECUTED and "DESACTIVADA" in off.result
    for plan in (V.list_windows(), V.focus_window("gedit"), V.plan_close_window("gedit")):
        assert plan.status == ActionStatus.BLOCKED
        assert "DESACTIVADA" in plan.result
    V.set_integracion(True)
    assert V.list_windows().status == ActionStatus.EXECUTED


# --- parser --------------------------------------------------

def test_parser_enruta_ventanas():
    assert parse_intent("qué ventanas tengo abiertas").tool == "win_list"
    r = parse_intent("cierra la ventana de firefox")
    assert r.tool == "win_close" and r.arguments["objetivo"] == "firefox"
    assert parse_intent("enfoca la ventana de gedit").tool == "win_focus"
    assert parse_intent("desactiva la integración de ventanas").tool == "win_integ_off"
    # "cierra firefox" NO es cerrar_ventana (es close_app)
    assert parse_intent("cierra firefox").tool == "close_app"


if __name__ == "__main__":
    print("usa pytest")
