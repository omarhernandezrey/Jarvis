"""PLAN_EJECUCION FASE G — escritura del portapapeles.

El backend (`wl-copy`/`xclip`) se simula con un dict en memoria. Se comprueban:
detección en runtime, VERIFY releyendo, confirmación condicional (comando/URL/
credencial/largo), guardar+restaurar el contenido previo, el interruptor, y
que el plan auditado NO lleva el texto entero (solo un preview).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import clipboard as C

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or|listo,?\s*se[nñ]or", re.I)


@pytest.fixture
def clip(monkeypatch, tmp_path):
    estado = {"texto": "lo que habia antes", "falla_lectura": False, "escribe": True}

    def _leer():
        return None if estado["falla_lectura"] else estado["texto"]

    def _escribir(t):
        if estado["escribe"]:
            estado["texto"] = t
        return estado["escribe"]

    monkeypatch.setattr(C, "_backend", lambda: ("wl-clipboard", ["wl-copy"], ["wl-paste"]))
    monkeypatch.setattr(C, "_leer", _leer)
    monkeypatch.setattr(C, "_escribir", _escribir)
    monkeypatch.setattr(C, "_SWITCH", tmp_path / "clip.json")
    monkeypatch.setattr(C, "_PENDIENTE", {})
    monkeypatch.setattr(C, "_PREVIO", {"texto": None, "hubo": False})
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)
    monkeypatch.setattr("jarvis_local.tools.verify.wait_until",
                        lambda pred, **k: bool(pred()))
    return estado


# --- detección en runtime -----------------------------------------

def test_sin_backend_error_claro(monkeypatch):
    monkeypatch.setattr(C, "_backend", lambda: None)
    plan = C.plan_write_clipboard("hola")
    assert plan.status == ActionStatus.ERROR
    assert "wl-clipboard" in plan.result


# --- escribir simple: directo + VERIFY ---------------------------

def test_escribir_texto_simple_va_directo_y_verifica(clip):
    plan = C.plan_write_clipboard("hola mundo")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert clip["texto"] == "hola mundo"


def test_verify_falso_si_el_portapapeles_no_queda_con_el_texto(clip):
    clip["escribe"] = False                       # _escribir devuelve False
    plan = C.plan_write_clipboard("hola")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert not _EXITO.search(plan.result)


def test_verify_none_si_no_se_puede_releer(clip):
    clip["falla_lectura"] = True
    plan = C.plan_write_clipboard("hola")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "no he podido confirmar" in plan.result.lower()


# --- confirmación condicional -----------------------------------

@pytest.mark.parametrize("texto,pista", [
    ("sudo apt update", "comando"),
    ("mira esto http://ejemplo.com", "URL"),
    ("token=abc123def456", "credencial"),
    ("x" * 400, "largo"),
])
def test_confirmacion_cuando_parece_peligroso(clip, texto, pista):
    plan = C.plan_write_clipboard(texto)
    assert plan.status == ActionStatus.PLANNED
    assert pista in plan.simulation_result
    assert "/confirmar" in plan.simulation_result
    assert clip["texto"] == "lo que habia antes"      # aún NO se ha copiado


def test_confirmar_ejecuta_y_verifica(clip):
    plan = C.plan_write_clipboard("sudo reboot")
    tok = plan.params["token"]
    hecho = C.execute_write_clipboard(C._PENDIENTE.pop(tok))
    assert hecho.status == ActionStatus.EXECUTED
    assert hecho.params["verify"]["ok"] is True
    assert clip["texto"] == "sudo reboot"


# --- auditoría: sin el texto entero ---------------------------

def test_el_plan_no_lleva_el_texto_entero(clip):
    secreto = "SECRETO-" + "z" * 500
    plan = C.plan_write_clipboard(secreto)          # largo -> PLANNED
    blob = repr(plan.params) + (plan.simulation_result or "")
    assert secreto not in blob
    assert plan.params["n"] == len(secreto)         # sí registra la longitud
    assert "…" in plan.params["preview"]


# --- guardar y restaurar el previo --------------------------

def test_restaurar_devuelve_el_contenido_anterior(clip):
    C.plan_write_clipboard("texto nuevo")
    assert clip["texto"] == "texto nuevo"
    r = C.restore_clipboard()
    assert r.status == ActionStatus.EXECUTED
    assert r.params["verify"]["ok"] is True
    assert clip["texto"] == "lo que habia antes"


def test_restaurar_sin_haber_escrito_lo_dice(clip):
    r = C.restore_clipboard()
    assert r.status == ActionStatus.EXECUTED
    assert "no he tocado" in r.result.lower()


# --- interruptor -------------------------------------------

def test_interruptor_off_bloquea_y_on_reactiva(clip):
    off = C.set_escritura(False)
    assert off.status == ActionStatus.EXECUTED
    b = C.plan_write_clipboard("hola")
    assert b.status == ActionStatus.BLOCKED and "desactivada" in b.result
    assert clip["texto"] == "lo que habia antes"
    C.set_escritura(True)
    assert C.plan_write_clipboard("hola").status == ActionStatus.EXECUTED


# --- parser ---------------------------------------------

def test_parser_enruta_portapapeles():
    r = parse_intent("copia esto: git status")
    assert r.tool == "clip_write" and r.arguments["texto"] == "git status"
    assert parse_intent("deshaz el portapapeles").tool == "clip_restore"
    assert parse_intent("desactiva la escritura del portapapeles").tool == "clip_off"
    # copiar un archivo NO es esto
    assert parse_intent("copia el archivo notas.txt a backup").tool == "copy_file"
    # leer sigue siendo leer
    assert parse_intent("lee el portapapeles").tool == "read_clipboard"


if __name__ == "__main__":
    print("usa pytest")
