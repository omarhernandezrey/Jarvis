"""PLAN_EJECUCION FASE D · D1 — VERIFY post-acción.

El caso que estos tests blindan: una herramienta de WRITE cuyo comando de
sistema devuelve "ok" (returncode 0) pero cuyo EFECTO no ocurrió. Antes de D1,
JARVIS respondía "volumen al 50 por ciento, señor" y nadie se enteraba de que
seguía al 20. Ahora lo comprueba, reintenta por otra vía, y si sigue sin
cuadrar lo dice — nunca lo presenta como hecho.
"""
import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety.policy import ActionPlan, ActionStatus
from jarvis_local.tools import media_controls as mc
from jarvis_local.tools import verify as v


def _ok_proc(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


# --- finish(): los tres desenlaces ---------------------------------------------


def test_finish_ok_reporta_exito():
    plan = ActionPlan(action="x")
    out = v.VerifyOutcome(True, "volumen=50%", "get_volume")
    r = v.finish(plan, out, ok_msg="Listo.", fail_msg="No pude.")
    assert r.status == ActionStatus.EXECUTED
    assert r.result == "Listo."
    assert r.params["verify"]["ok"] is True


def test_finish_no_medible_reporta_con_salvedad():
    plan = ActionPlan(action="x")
    out = v.VerifyOutcome(None, "sin wpctl/WASAPI", "get_volume")
    r = v.finish(plan, out, ok_msg="Listo.", fail_msg="No pude.")
    # EXECUTED, pero JAMÁS afirma el efecto sin más: lo marca como no confirmado
    assert r.status == ActionStatus.EXECUTED
    assert "No pude confirmar" in r.result
    assert "sin wpctl/WASAPI" in r.result
    assert r.params["verify"]["ok"] is None


def test_finish_negativo_nunca_es_exito():
    plan = ActionPlan(action="x")
    out = v.VerifyOutcome(False, "volumen=20%, se pidió 50%", "get_volume")
    r = v.finish(plan, out, ok_msg="Listo.", fail_msg="No pude.",
                 tried=["wpctl -> 20%", "pactl -> 20%"])
    assert r.status == ActionStatus.ERROR
    assert "No pude." in r.result
    assert "Intenté" in r.result and "wpctl" in r.result and "pactl" in r.result
    assert r.params["verify"]["ok"] is False


# --- comprobadores -----------------------------------------------------------


def test_volume_settled_detecta_desajuste():
    with patch.object(mc, "get_volume", return_value=20):
        assert v.volume_settled(50).ok is False
    with patch.object(mc, "get_volume", return_value=51):
        assert v.volume_settled(50).ok is True          # dentro de tolerancia
    with patch.object(mc, "get_volume", return_value=None):
        assert v.volume_settled(50).ok is None          # no medible


def test_volume_changed_respeta_sentido_y_tope():
    with patch.object(mc, "get_volume", return_value=60):
        assert v.volume_changed(50, direction=1).ok is True
        assert v.volume_changed(50, direction=-1).ok is False
    with patch.object(mc, "get_volume", return_value=100):
        assert v.volume_changed(100, direction=1).ok is True   # ya en el tope


# --- set_volume: fallo silencioso detectado, reintentado y reportado ---------


def test_set_volume_fallo_silencioso_se_detecta_y_no_se_finge():
    """wpctl y pactl devuelven 0 pero el volumen no se mueve -> ERROR honesto."""
    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=_ok_proc()), \
         patch.object(mc, "_pactl", return_value=_ok_proc()), \
         patch.object(mc, "get_volume", return_value=20):
        plan = mc.set_volume(50)

    assert plan.status == ActionStatus.ERROR
    assert "50" in plan.result
    assert "Intenté" in plan.result                       # dice QUÉ intentó
    assert "pactl" in plan.result                          # incluye el reintento
    assert plan.params["verify"]["ok"] is False


def test_set_volume_reintento_por_via_alterna_funciona():
    """wpctl no mueve nada; pactl sí. Queda EXECUTED y consta el reintento."""
    estado = {"v": 20}

    def _pactl_ok(*args):
        if args and args[0] == "set-sink-volume":
            estado["v"] = 50
        return _ok_proc()

    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=_ok_proc()), \
         patch.object(mc, "_pactl", side_effect=_pactl_ok), \
         patch.object(mc, "get_volume", side_effect=lambda: estado["v"]):
        plan = mc.set_volume(50)

    assert plan.status == ActionStatus.EXECUTED
    assert "50 por ciento" in plan.result
    assert "reintento" in plan.reason
    assert plan.params["verify"]["ok"] is True


def test_set_volume_sin_lectura_no_afirma_el_efecto():
    """Sin forma de leer el volumen (CI sin audio): EXECUTED con salvedad."""
    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=_ok_proc()), \
         patch.object(mc, "get_volume", return_value=None):
        plan = mc.set_volume(50)

    assert plan.status == ActionStatus.EXECUTED
    assert "No pude confirmar" in plan.result
    assert plan.params["verify"]["ok"] is None


# --- volume_up / volume_mute: mismo contrato --------------------------------


def test_volume_up_fallo_silencioso_se_detecta():
    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=_ok_proc()), \
         patch.object(mc, "_pactl", return_value=_ok_proc()), \
         patch.object(mc, "get_volume", return_value=50):   # nunca sube
        plan = mc.volume_up()

    assert plan.status == ActionStatus.ERROR
    assert "no pude cambiar el volumen" in plan.result.lower()
    assert plan.params["verify"]["ok"] is False


def test_volume_mute_fallo_silencioso_se_detecta():
    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=_ok_proc()), \
         patch.object(mc, "_pactl", return_value=_ok_proc()), \
         patch.object(mc, "is_muted", return_value=False):   # nunca se silencia
        plan = mc.volume_mute(True)

    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert "Intenté" in plan.result


def test_volume_mute_ok_por_via_alterna():
    estado = {"muted": False}

    def _pactl_ok(*args):
        if args and args[0] == "set-sink-mute":
            estado["muted"] = args[-1] == "1"
        return _ok_proc()

    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=_ok_proc()), \
         patch.object(mc, "_pactl", side_effect=_pactl_ok), \
         patch.object(mc, "is_muted", side_effect=lambda: estado["muted"]):
        plan = mc.volume_mute(True)

    assert plan.status == ActionStatus.EXECUTED
    assert "reintento" in plan.reason


# --- archivos: existir no basta; tamaño y contenido -------------------------


def _docs_tmp(nombre: str):
    from jarvis_local.config import user_dir
    return os.path.join(user_dir("documents"), nombre)


def test_file_written_detecta_fichero_vacio():
    """Un fichero creado pero VACÍO pasa 'existe' y falla la verificación real."""
    from jarvis_local.tools import files

    ruta = _docs_tmp("_verify_d1_vacio.txt")
    try:
        # 1ª vía deja el fichero vacío; la 2ª (cruda) tampoco escribe nada
        with patch("pathlib.Path.write_text", lambda self, *a, **k: self.touch()), \
             patch("jarvis_local.tools.files.os.open", side_effect=OSError("disco lleno")):
            plan = files.create_file(ruta, "contenido que debía quedar escrito")
        assert plan.status == ActionStatus.ERROR
        assert plan.params["verify"]["ok"] is False
        assert "tamaño" in plan.result.lower() or "contenido" in plan.result.lower()
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def test_create_file_ok_verifica_contenido_y_tamano():
    from jarvis_local.tools import files

    ruta = _docs_tmp("_verify_d1_ok.txt")
    try:
        plan = files.create_file(ruta, "hola señor")
        assert plan.status == ActionStatus.EXECUTED
        assert plan.params["verify"]["ok"] is True
        assert "contenido verificado" in plan.params["verify"]["detail"]
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def test_create_file_reintento_lowlevel_cuando_pathlib_no_escribe():
    from jarvis_local.tools import files

    ruta = _docs_tmp("_verify_d1_retry.txt")
    try:
        # 1ª estrategia (write_text) no deja nada; la 2ª (os.write real) sí
        with patch("pathlib.Path.write_text", lambda self, *a, **k: None):
            plan = files.create_file(ruta, "rescatado por fsync")
        assert plan.status == ActionStatus.EXECUTED
        assert plan.params["verify"]["ok"] is True
        assert "reintento" in plan.reason
        assert open(ruta, encoding="utf-8").read() == "rescatado por fsync"
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def test_moved_verifica_que_el_origen_ya_no_esta():
    ruta_o = _docs_tmp("_verify_d1_src.txt")
    ruta_d = _docs_tmp("_verify_d1_dst.txt")
    with open(ruta_o, "w", encoding="utf-8") as f:
        f.write("x" * 20)
    try:
        # simular una "copia disfrazada de move": destino creado, origen sigue
        with open(ruta_d, "w", encoding="utf-8") as f:
            f.write("x" * 20)
        out = v.moved(ruta_o, ruta_d)
        assert out.ok is False and "sigue ahí" in out.detail
    finally:
        for r in (ruta_o, ruta_d):
            if os.path.exists(r):
                os.remove(r)


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_"):
            _fn()
    print("OK: tests de VERIFY (D1) pasaron.")
