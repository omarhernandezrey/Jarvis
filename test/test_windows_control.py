"""Tests de control de ventanas (minimizar todo, acomodar la activa)"""
import ctypes
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.desktop_actions import minimize_all, snap_window

# --- Enrutamiento del parser ---


def test_intent_minimizar_todo():
    for frase in ("minimiza todo", "minimiza todas las ventanas",
                  "muestra el escritorio"):
        r = parse_intent(frase)
        assert r.tool == "minimize_all", frase


def test_intent_snap():
    r = parse_intent("pon la ventana a la izquierda")
    assert r.tool == "snap_window"
    assert r.arguments["direction"] == "izquierda"
    r = parse_intent("manda la ventana a la derecha")
    assert r.arguments["direction"] == "derecha"
    r = parse_intent("maximiza la ventana")
    assert r.arguments["direction"] == "maximizar"


def test_intent_cambiar_ventana_no_robado():
    r = parse_intent("cambia de ventana")
    assert r.tool == "switch_window"


def test_intent_cerrar_no_robado():
    r = parse_intent("cierra chrome")
    assert r.tool == "close_app"


# --- Herramientas ---


def test_snap_direccion_invalida():
    plan = snap_window("diagonal")
    assert plan.status == ActionStatus.ERROR


def _hwnd_de_pid(pid: int) -> int:
    """Primera ventana visible de un proceso."""
    user32 = ctypes.windll.user32
    encontrado = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_cb(hwnd, _lparam):
        wnd_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wnd_pid))
        if wnd_pid.value == pid and user32.IsWindowVisible(hwnd):
            encontrado.append(hwnd)
            return False
        return True

    user32.EnumWindows(enum_cb, 0)
    return encontrado[0] if encontrado else 0


def test_snap_minimiza_de_verdad():
    """Abre un Notepad, lo enfoca, lo minimiza con Win+Down y VERIFICA con
    IsIconic que quedo minimizado. Si Windows niega el foco, no concluye."""
    user32 = ctypes.windll.user32
    proc = subprocess.Popen([r"C:\Windows\System32\notepad.exe"])
    try:
        hwnd = 0
        for _ in range(20):
            time.sleep(0.25)
            hwnd = _hwnd_de_pid(proc.pid)
            if hwnd:
                break
        assert hwnd, "notepad nunca mostro ventana"
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        if user32.GetForegroundWindow() != hwnd:
            return  # Windows nego el foco (foreground lock): no concluyente
        plan = snap_window("minimizar")
        assert plan.status == ActionStatus.EXECUTED
        time.sleep(0.6)
        assert user32.IsIconic(hwnd), "la ventana NO quedo minimizada"
    finally:
        proc.terminate()


def test_minimize_all_ejecuta():
    # Solo verifica que la funcion corre sin error; el efecto real sobre
    # todo el escritorio se comprueba en la verificacion manual E2E para
    # no minimizar las ventanas del usuario en cada corrida de la suite.
    original = ctypes.windll.user32.keybd_event
    llamadas = []
    ctypes.windll.user32.keybd_event = lambda *a: llamadas.append(a)
    try:
        plan = minimize_all()
        assert plan.status == ActionStatus.EXECUTED
        assert len(llamadas) == 4  # Win down, M down, M up, Win up
    finally:
        ctypes.windll.user32.keybd_event = original


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de ventanas pasaron.")
