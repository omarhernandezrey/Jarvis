"""Tests de JARVIS_HUD_PAINT_STATS (hud_pro/paint_stats.py) — el contador
de QEvent.Paint por widget usado para la tarea A de CPU."""

from __future__ import annotations

import io

import pytest

from hud_pro.app import create_app
from hud_pro.paint_stats import PaintStatsFilter, install_paint_stats
from hud_pro.qt_compat import QtWidgets


@pytest.fixture
def stats(qapp):
    """Filtro instalado a mano en la QApplication de tests (sin timer:
    volcado manual), retirado al terminar para no contar paints ajenos."""
    filtro = PaintStatsFilter(qapp, interval_s=0, out=io.StringIO())
    qapp.installEventFilter(filtro)
    yield filtro
    qapp.removeEventFilter(filtro)
    filtro.deleteLater()


def _pump(qapp, n: int = 5) -> None:
    for _ in range(n):
        qapp.processEvents()


def test_paint_filter_counts_paint_events_per_widget(qapp, stats):
    w = QtWidgets.QWidget()
    w.setObjectName("WidgetDePrueba")
    w.resize(60, 40)
    w.show()
    _pump(qapp)
    stats.reset()

    for _ in range(4):
        w.update()
    _pump(qapp)

    rates = stats.rates()
    assert any("WidgetDePrueba" in label for label in rates), f"no contó nada: {rates}"
    w.close()
    w.deleteLater()


def test_paint_filter_labels_include_objectname_and_label_text(qapp, stats):
    lbl = QtWidgets.QLabel("CPU 12%", None)
    lbl.setObjectName("Metric")
    lbl.show()
    _pump(qapp)
    lbl.update()
    _pump(qapp)

    label = next(k for k in stats.rates() if "Metric" in k)
    assert "QLabel#Metric" in label
    assert "CPU 12%" in label  # sin el texto, «QLabel#Metric» no dice cuál es
    lbl.close()
    lbl.deleteLater()


def test_paint_filter_top_respects_min_rate(qapp, stats):
    w = QtWidgets.QWidget()
    w.show()
    _pump(qapp)
    stats.reset()
    for _ in range(3):
        w.update()
    _pump(qapp)

    rates = stats.rates()
    assert rates  # algo se contó
    # determinista (offscreen bombea en <1ms y el rate real depende del
    # clamp de dt): un umbral por ENCIMA del máximo observado → vacío;
    # umbral 0 → todo lo contado entra.
    assert stats.top(min_rate=max(rates.values()) + 1.0) == {}
    assert stats.top(min_rate=0.0) == rates
    w.close()
    w.deleteLater()


def test_paint_filter_dump_prints_and_resets(qapp, stats):
    out = io.StringIO()
    stats._out = out
    w = QtWidgets.QWidget()
    w.setObjectName("Vacio")
    w.show()
    _pump(qapp)
    stats.reset()
    stats.dump()
    text = out.getvalue()
    assert "[paint-stats]" in text
    assert stats.rates() == {}  # el dump empieza una ventana nueva
    w.close()
    w.deleteLater()


def test_create_app_installs_filter_only_with_env_flag(qapp, monkeypatch):
    monkeypatch.delenv("JARVIS_HUD_PAINT_STATS", raising=False)
    create_app([])
    assert not hasattr(qapp, "_paint_stats")

    monkeypatch.setenv("JARVIS_HUD_PAINT_STATS", "1")
    monkeypatch.setenv("JARVIS_HUD_PAINT_STATS_INTERVAL", "0")
    create_app([])
    filtro = getattr(qapp, "_paint_stats", None)
    assert filtro is not None, "con el flag a 1 debe instalarse el contador"
    qapp.removeEventFilter(filtro)
    filtro.deleteLater()
    del qapp._paint_stats
