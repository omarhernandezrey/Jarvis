"""Tests de la nueva capa de vista (PySide6 + Qt Quick).

Cubren el contrato del ViewModel (cinco canales, 'sin dato' se conserva como
None y nunca se inventa) y que el motor QML carga sin warnings.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import pytest

pytest.importorskip("PySide6.QtQuick")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from jarvis_local.ui.hud import services  # noqa: E402
from jarvis_local.ui.hud.viewmodel import STATES, ViewModel  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])


def test_viewmodel_state_validation():
    vm = ViewModel()
    assert vm.state == "idle"
    vm.set_state("thinking")
    assert vm.state == "thinking"
    vm.set_state("no-existe")
    assert vm.state == "thinking"  # inválido: sin cambio
    for s in STATES:
        vm.set_state(s)
        assert vm.state == s


def test_viewmodel_metrics_merge():
    vm = ViewModel()
    vm.push_metrics({"cpu": 10, "ram": 20})
    vm.push_metrics({"ram": 25, "model": "x"})
    assert vm.metrics == {"cpu": 10, "ram": 25, "model": "x"}
    # None se conserva tal cual (ausente, no rellenado)
    vm.push_metrics({"cpu": None})
    assert vm.metrics["cpu"] is None


def test_viewmodel_audio_clamp_and_clear():
    vm = ViewModel()
    vm.push_audio(5.0, [2.0, -1.0, 0.5])
    assert vm.audio["level"] == 1.0
    assert vm.audio["spectrum"] == [1.0, 0.0, 0.5]
    vm.push_audio(float("nan"))
    assert vm.audio["level"] == 0.0
    vm.push_audio(0.4, [0.1])
    vm.clear_audio()
    assert vm.audio == {"level": 0.0, "spectrum": []}


def test_sample_all_shape_no_invention():
    """sample_all() devuelve un dict con las claves esperadas; los valores son
    None o de tipo correcto -- nunca aleatorios ni de relleno."""
    data = services.sample_all()
    for key in ("cpu", "ram", "online", "model", "healthPingMs",
                "voice", "tools", "memory"):
        assert key in data
    assert data["cpu"] is None or isinstance(data["cpu"], (int, float))
    assert data["ram"] is None or isinstance(data["ram"], (int, float))
    assert isinstance(data["online"], bool)
    assert data["model"] is None or isinstance(data["model"], str)
    assert data["healthPingMs"] is None or isinstance(data["healthPingMs"], int)
    assert set(data["voice"]) == {"tts", "mic"}
    assert set(data["tools"]) == {"count", "agent"}
    assert set(data["memory"]) == {"auto_recall", "count"}


def test_qml_engine_loads_without_warnings():
    from jarvis_local.ui.hud.app import create_engine

    warns = []
    vm = ViewModel()
    engine = create_engine(_app, vm)
    engine.warnings.connect(lambda ws: warns.extend(w.toString() for w in ws))
    try:
        assert engine.rootObjects(), "Main.qml no cargó"
        assert warns == [], f"warnings QML: {warns}"
    finally:
        engine._metrics.stop()  # noqa: SLF001
        engine.deleteLater()
