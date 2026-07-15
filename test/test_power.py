"""Tests de energia del equipo (bloquear/apagar/reiniciar/suspender)"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import jarvis_local.tools.power as power
from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus


def _con_shutdown_falso(fn):
    """Captura las llamadas a shutdown.exe sin ejecutarlas."""
    original = power._run_shutdown
    llamadas = []

    def fake(args):
        llamadas.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    power._run_shutdown = fake
    try:
        fn(llamadas)
    finally:
        power._run_shutdown = original


# --- Enrutamiento del parser ---


def test_intent_apagar():
    for frase in ("apaga el computador", "apaga el pc", "apagame el equipo"):
        r = parse_intent(frase)
        assert r.tool == "shutdown_pc", frase


def test_intent_reiniciar():
    r = parse_intent("reinicia el computador")
    assert r.tool == "restart_pc"


def test_intent_bloquear():
    for frase in ("bloquea el pc", "bloquea la pantalla", "bloquea la sesion"):
        r = parse_intent(frase)
        assert r.tool == "lock_pc", frase


def test_intent_suspender():
    r = parse_intent("suspende el equipo")
    assert r.tool == "suspend_pc"


def test_intent_cancelar_apagado():
    for frase in ("cancela el apagado", "no apagues el pc"):
        r = parse_intent(frase)
        assert r.tool == "cancel_shutdown", frase


def test_intent_apaga_sonido_es_volumen():
    # "apaga el sonido" es silenciar, NO apagar el computador
    r = parse_intent("apaga el sonido")
    assert r.tool == "volume_mute"


def test_intent_apaga_jarvis_no_es_apagado():
    # "apaga jarvis" cierra JARVIS (lo maneja voz.py), no el PC
    r = parse_intent("apaga jarvis")
    assert r.tool not in ("shutdown_pc", "restart_pc")


# --- Herramientas (con shutdown.exe capturado) ---


def test_apagar_programa_con_60s():
    def caso(llamadas):
        plan = power.shutdown_pc()
        assert plan.status == ActionStatus.EXECUTED
        assert llamadas == [["/s", "/t", "60"]]
        assert "cancela el apagado" in plan.result.lower()
    _con_shutdown_falso(caso)


def test_reiniciar_programa_con_60s():
    def caso(llamadas):
        plan = power.restart_pc()
        assert plan.status == ActionStatus.EXECUTED
        assert llamadas == [["/r", "/t", "60"]]
    _con_shutdown_falso(caso)


def test_apagar_nunca_menos_de_10s():
    def caso(llamadas):
        power.shutdown_pc(seconds=0)
        assert llamadas == [["/s", "/t", "10"]]
    _con_shutdown_falso(caso)


def test_cancelar_sin_apagado_pendiente():
    def caso(llamadas):
        def fake_1116(args):
            llamadas.append(args)
            return subprocess.CompletedProcess(args, 1116, stdout="", stderr="")
        power._run_shutdown = fake_1116
        plan = power.cancel_shutdown()
        assert plan.status == ActionStatus.EXECUTED
        assert "no hay ningun apagado" in plan.result.lower()
    _con_shutdown_falso(caso)


def test_bloquear_con_mock():
    original = power._lock_workstation
    power._lock_workstation = lambda: True
    try:
        plan = power.lock_pc()
        assert plan.status == ActionStatus.EXECUTED
        assert "bloqueada" in plan.result.lower()
    finally:
        power._lock_workstation = original


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de power pasaron.")
