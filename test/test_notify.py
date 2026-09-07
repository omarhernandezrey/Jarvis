"""PLAN_EJECUCION FASE E · E5 — notificaciones (notify-send)."""
import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.notify import send_notification


def _cp(rc=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout="", stderr=stderr)


def test_sin_notify_send_lo_dice_no_falla_en_silencio():
    with patch("shutil.which", return_value=None):
        plan = send_notification("hola")
    assert plan.status == ActionStatus.ERROR
    assert "notify-send" in plan.result and "libnotify-bin" in plan.result


def test_ok_pero_verify_none_con_salvedad():
    with patch("shutil.which", return_value="/usr/bin/notify-send"), \
         patch("subprocess.run", return_value=_cp(0)) as run:
        plan = send_notification("la compilación terminó", titulo="Build",
                                 urgencia="alta")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "no puedo confirmar" in plan.result.lower()
    # urgencia mapeada a critical
    assert "critical" in run.call_args.args[0]


def test_notify_send_rc_no_cero_es_error():
    with patch("shutil.which", return_value="/usr/bin/notify-send"), \
         patch("subprocess.run", return_value=_cp(1, "cannot connect to bus")):
        plan = send_notification("x")
    assert plan.status == ActionStatus.ERROR
    assert "bus" in plan.result


def test_mensaje_vacio_pide_aclaracion():
    plan = send_notification("   ")
    assert plan.status == ActionStatus.ERROR
    assert "qué" in plan.result.lower() or "que" in plan.result.lower()


def test_parser_enruta_la_notificacion():
    r = parse_intent("mándame una notificación que diga la reunión es a las 3")
    assert r.kind == "tool_execute" and r.tool == "notify"
    assert "reunión es a las 3" in r.arguments["mensaje"] or "reunion es a las 3" in r.arguments["mensaje"]

    r2 = parse_intent("notifícame que el backup terminó")
    assert r2.tool == "notify"

    r3 = parse_intent("mándame una notificación")
    assert r3.kind == "ambiguous"


if __name__ == "__main__":
    print("usa pytest")
