"""Tests de los componentes de FASE D (paneles, paleta, checklist de
arranque) — offscreen, sin necesitar GPU real: son QWidget normales."""

from __future__ import annotations

import pytest

from hud_pro.command_palette import Command, CommandPalette
from hud_pro.panels import ActivityPanel, Sparkline, SystemPanel, TokenGauge
from hud_pro.qt_compat import QtCore
from hud_pro.startup_checklist import CheckItem, StartupChecklist
from hud_pro.state import OrbState
from hud_pro.window import HudWindow


@pytest.fixture
def hud_window(qapp):
    """Crea HudWindow y la CIERRA al terminar el test (mismo patrón que la
    fixture `win` de test_hud_pro.py): una ventana viva deja el orbe
    raster animando a 30fps en offscreen, y suficientes de ellas saturan
    el event loop del proceso — eso retrasaba la animación QML de
    test_ui_hud.py (560ms no terminaban en su settle de 1s) cuando corría
    la suite completa. Fallo real observado, no hipótesis."""
    created = []

    def _make(width: int = 1366, height: int = 768, show: bool = True) -> HudWindow:
        w = HudWindow()
        w.resize(width, height)
        if show:
            w.show()
        qapp.processEvents()
        created.append(w)
        return w

    yield _make
    for w in created:
        w.close()
        w.deleteLater()
    qapp.processEvents()


# ── Sparkline ────────────────────────────────────────────────────────────
def test_sparkline_push_updates_cached_pixmap(qapp):
    s = Sparkline()
    s.resize(80, 28)
    assert s._pixmap is None
    s.push(10.0)
    first = s._pixmap
    assert first is not None
    s.push(20.0)
    second = s._pixmap
    assert second is not first, "cada push() debe recalcular el cache, no reusar el pixmap viejo"


def test_sparkline_resize_without_push_does_not_crash_and_keeps_cache_fresh(qapp):
    s = Sparkline()
    s.resize(80, 28)
    s.push(5.0)
    s.resize(120, 28)  # el resize sí debe re-cachear (cambió el tamaño real)
    assert s._pixmap is not None
    assert s._pixmap.width() > 0


# ── SystemPanel: presupuesto de CPU — el timer sólo corre visible ───────
def test_system_panel_timer_only_runs_while_visible(qapp):
    panel = SystemPanel(ollama_ping_fn=lambda: None)
    assert not panel._timer.isActive()
    panel.show()
    qapp.processEvents()
    assert panel._timer.isActive(), "visible: el timer de 1Hz debe correr"
    assert panel._timer.interval() == SystemPanel.UPDATE_MS
    panel.hide()
    qapp.processEvents()
    assert not panel._timer.isActive(), "oculto: cero coste, el timer debe pararse"


def test_system_panel_sample_updates_labels_with_real_psutil_data(qapp):
    panel = SystemPanel(ollama_ping_fn=lambda: 12.5)
    panel.show()
    qapp.processEvents()
    panel._sample()
    assert panel._ping_val.text() == "12 ms"
    assert panel._uptime_label.text().startswith("uptime ")


def test_system_panel_ping_none_shows_placeholder(qapp):
    panel = SystemPanel(ollama_ping_fn=lambda: None)
    panel._sample()
    assert panel._ping_val.text() == "—"


# ── ActivityPanel ────────────────────────────────────────────────────────
def test_activity_panel_starts_with_empty_state_placeholders(qapp):
    panel = ActivityPanel()
    assert panel._tools_list.count() == 1
    assert "Sin herramientas" in panel._tools_list.item(0).text()
    assert "Sin recordatorios" in panel._reminders_list.item(0).text()
    assert panel._memory_label.text() == "Memoria: —"


def test_activity_panel_add_tool_event_replaces_placeholder(qapp):
    panel = ActivityPanel()
    panel.add_tool_event("buscar_memoria", True, 340.0)
    assert panel._tools_list.count() == 1
    text = panel._tools_list.item(0).text()
    assert "buscar_memoria" in text and "✓" in text and "340" in text


def test_activity_panel_caps_tool_history_at_max_events(qapp):
    panel = ActivityPanel()
    for i in range(panel.MAX_EVENTS + 5):
        panel.add_tool_event(f"tool_{i}", True, 1.0)
    assert panel._tools_list.count() == panel.MAX_EVENTS
    assert "tool_" in panel._tools_list.item(0).text()  # el más reciente queda arriba


def test_activity_panel_reminders_real_data_and_empty_state(qapp):
    panel = ActivityPanel()
    panel.update_reminders(["Llamar al médico a las 5pm"])
    assert panel._reminders_list.count() == 1
    assert "médico" in panel._reminders_list.item(0).text()
    panel.update_reminders([])
    assert "Sin recordatorios" in panel._reminders_list.item(0).text()


def test_activity_panel_memory_count(qapp):
    panel = ActivityPanel()
    panel.set_memory_count(42)
    assert panel._memory_label.text() == "Memoria: 42 recuerdos"
    panel.set_memory_count(None)
    assert panel._memory_label.text() == "Memoria: —"


# ── TokenGauge ───────────────────────────────────────────────────────────
def test_token_gauge_hidden_by_default_and_updates_on_real_data(qapp):
    gauge = TokenGauge()
    assert not gauge.isVisible()
    gauge.update_tokens(7.4, 610.0)
    assert "7 tok/s" in gauge._tps_label.text()
    assert "610" in gauge._ttft_label.text()


# ── CommandPalette ───────────────────────────────────────────────────────
def test_command_palette_filters_by_query(qapp):
    calls = []
    cmds = [
        Command("Nueva conversación", "borra todo", lambda: calls.append("new")),
        Command("Modo enfoque", "esconde chips", lambda: calls.append("focus")),
    ]
    palette = CommandPalette(cmds)
    assert palette._list.count() == 2
    palette._populate("enfoque")
    assert palette._list.count() == 1
    assert "Modo enfoque" in palette._list.item(0).text()


def test_command_palette_runs_selected_command_and_closes(qapp):
    calls = []
    cmds = [Command("Acción real", "hace algo de verdad", lambda: calls.append("ran"))]
    palette = CommandPalette(cmds)
    palette.open()
    assert palette.isVisible()
    palette._run_selected()
    assert calls == ["ran"], "debe llamar la acción REAL asociada al comando"
    assert not palette.isVisible()


def test_command_palette_escape_closes_without_running(qapp):
    calls = []
    cmds = [Command("Algo", "hint", lambda: calls.append("ran"))]
    palette = CommandPalette(cmds)
    palette.open()
    ev = QtCore.QEvent(QtCore.QEvent.Type.KeyPress)
    from hud_pro.qt_compat import Qt, QtGui
    key_event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    palette.keyPressEvent(key_event)
    assert calls == []
    assert not palette.isVisible()


# ── StartupChecklist ─────────────────────────────────────────────────────
def test_startup_checklist_runs_real_checks_and_closes(qapp):
    seen = []

    def check_ok():
        seen.append("ok")
        return True

    def check_fail():
        seen.append("fail")
        return False

    checklist = StartupChecklist([CheckItem("Servicio A", check_ok), CheckItem("Servicio B", check_fail)])
    finished = []
    checklist.finished.connect(lambda: finished.append(1))
    checklist.start()
    deadline = QtCore.QElapsedTimer()
    deadline.start()
    while not finished and deadline.elapsed() < 2000:
        qapp.processEvents()
    assert seen == ["ok", "fail"], "cada ítem debe correr su comprobación REAL, no un progreso fingido"
    assert "✓" in checklist._rows[0].text()
    assert "✗" in checklist._rows[1].text()
    assert finished == [1]


# ── HudWindow: integración de FASE D ─────────────────────────────────────
def test_hud_window_side_dock_respects_wide_threshold(qapp, hud_window):
    w = hud_window(HudWindow.WIDE_LAYOUT_MIN_WIDTH - 100, 900)
    assert not w._is_wide_layout()
    assert not w._side_dock.isVisible(), "angosta y cajón cerrado: paneles ocultos"

    w._toggle_side_drawer()
    qapp.processEvents()
    assert w._side_dock.isVisible(), "el botón del cajón debe poder abrirlo en modo angosto"


def test_hud_window_focus_mode_hides_chrome_and_restores(qapp, hud_window):
    w = hud_window()
    assert w.top_bar.isVisible()
    assert w._services_row_widget.isVisible()

    w._toggle_focus_mode()
    qapp.processEvents()
    assert not w.top_bar.isVisible()
    assert not w._services_row_widget.isVisible()

    w._toggle_focus_mode()
    qapp.processEvents()
    assert w.top_bar.isVisible()
    assert w._services_row_widget.isVisible()


def test_hud_window_token_gauge_visible_only_while_generating(qapp, hud_window):
    w = hud_window()
    w.set_state(OrbState.IDLE)
    assert not w.token_gauge.isVisible()
    w.set_state(OrbState.THINKING)
    assert w.token_gauge.isVisible()
    w.set_state(OrbState.SPEAKING)
    assert w.token_gauge.isVisible()
    w.set_state(OrbState.LISTENING)
    assert not w.token_gauge.isVisible()


def test_hud_window_tool_end_reaches_activity_panel(qapp, hud_window):
    w = hud_window(show=False)
    w.tool_start("buscar_memoria")
    w.tool_end("buscar_memoria", 120.0, True)
    assert w.activity_panel._tools_list.count() == 1
    assert "buscar_memoria" in w.activity_panel._tools_list.item(0).text()


def test_hud_window_update_metrics_reaches_token_gauge_and_memory(qapp, hud_window):
    w = hud_window(show=False)
    w.update_metrics({"tokensPerSecond": 12.0, "ttftMs": 300.0, "memory": {"count": 7}})
    assert "12 tok/s" in w.token_gauge._tps_label.text()
    assert w.activity_panel._memory_label.text() == "Memoria: 7 recuerdos"


def test_hud_window_command_palette_shortcut_and_real_actions(qapp, hud_window):
    w = hud_window()
    assert not w._command_palette.isVisible()
    w._command_palette.open()
    assert w._command_palette.isVisible()
    titles = [w._command_palette._list.item(i).text() for i in range(w._command_palette._list.count())]
    assert any("enfoque" in t.lower() for t in titles)


# ── Widgets HUD compactos de esquina (rediseño para pantallas reales,
# sin monitor de 1920px — reemplaza el cajón oculto por defecto) ────────
def test_hud_window_corner_widgets_visible_below_1400px(qapp, hud_window):
    """Bajo 1400px (la pantalla real de esta máquina: 1366x768) lo
    esencial (CPU/RAM, servicios, herramienta) vive SIEMPRE visible en
    las esquinas del escenario — a diferencia del cajón lateral, que en
    este ancho nace cerrado."""
    w = hud_window(1366, 768)
    assert not w._is_wide_layout()
    for corner in (w.corner_system, w.corner_services, w.corner_tool):
        assert corner.isVisible(), f"{corner.objectName() or corner.metaObject().className()} oculto bajo 1400px"


def test_hud_window_corner_widgets_hidden_above_1400px(qapp, hud_window):
    """Por encima de 1400px esa MISMA info ya está en el panel lateral
    permanente: mostrar las esquinas sería duplicarla. El gauge de
    tokens/s NO se apaga por ancho (no vive en ningún panel)."""
    w = hud_window(HudWindow.WIDE_LAYOUT_MIN_WIDTH + 60, 900)
    assert w._is_wide_layout()
    assert w._side_dock.isVisible(), "ancha: el panel lateral es el permanente"
    for corner in (w.corner_system, w.corner_services, w.corner_tool):
        assert not corner.isVisible(), f"{corner.metaObject().className()} duplica al panel lateral"

    w.set_state(OrbState.THINKING)
    qapp.processEvents()
    assert w.token_gauge.isVisible(), "tokens/s+TTFT no viven en ningún panel: se ven también en ancha"

    # y al volver a angosta, las esquinas reaparecen solas
    w.resize(1366, 768)
    qapp.processEvents()
    for corner in (w.corner_system, w.corner_services, w.corner_tool):
        assert corner.isVisible()


def test_hud_window_corner_widgets_hidden_in_focus_mode(qapp, hud_window):
    """Modo enfoque (F10): esconde TODA la cromática, esquinas incluidas."""
    w = hud_window(1366, 768)
    assert w.corner_system.isVisible()
    w._toggle_focus_mode()
    qapp.processEvents()
    for corner in (w.corner_system, w.corner_services, w.corner_tool):
        assert not corner.isVisible()
    w._toggle_focus_mode()
    qapp.processEvents()
    assert w.corner_system.isVisible()


def test_hud_window_corner_widgets_never_overlap_the_orb(qapp, hud_window):
    """Ningún widget de esquina puede pisar el orbe: se comprueba contra
    el círculo VISUAL (no la caja de layout, que es mucho más ancha) —
    centro de luz + radio del shader con el sangrado del bloom (1.8x,
    mismo factor que usa `_position_status_below_rings`)."""
    w = hud_window(1366, 768)
    w.set_state(OrbState.THINKING)  # muestra también el token_gauge
    w.tool_start("leer_archivo")
    qapp.processEvents()

    g = w.orb.geometry()
    cx, cy = g.center().x(), g.top() + g.height() * 0.42
    r = 0.30 * min(g.width(), g.height()) * 1.8  # radio shader + bloom
    orb_visual = QtCore.QRectF(cx - r, cy - r, 2 * r, 2 * r)
    for corner in (w.corner_system, w.corner_services, w.corner_tool, w.token_gauge):
        if not corner.isVisible():
            continue
        rect = QtCore.QRectF(corner.geometry())
        assert not rect.intersects(orb_visual), (
            f"{corner.metaObject().className()} {rect} pisa el orbe {orb_visual}"
        )


def test_hud_window_corner_widgets_update_only_when_data_changes(qapp, hud_window):
    """CPU EN REPOSO (tarea A): con un QOpenGLWidget debajo, cada repaint
    de un widget obliga a recomponer TODA la ventana — «actualizar» con
    el mismo dato no puede repintar. Se mide con el contador real de
    QEvent.Paint (hud_pro.paint_stats)."""
    from hud_pro.paint_stats import PaintStatsFilter

    filtro = PaintStatsFilter(qapp, interval_s=0)
    qapp.installEventFilter(filtro)
    try:
        w = hud_window(1366, 768)
        w._startup_checklist_shown = True  # que no arranque el checklist (ruido de paints)
        qapp.processEvents()

        svc = w.corner_services
        svc.set_mic(True)
        qapp.processEvents()
        filtro.reset()
        svc.set_mic(True)  # MISMO dato: no puede repintar nada
        svc.set_mic(True)
        qapp.processEvents()
        assert filtro.rate_for(svc._mic_label) == 0.0, (
            f"set_mic con el mismo dato repintó: {filtro.rates()}"
        )

        ring = w.corner_system._cpu_ring
        ring.push(41.2)
        qapp.processEvents()
        filtro.reset()
        ring.push(41.4)  # mismo entero visible (41): no redibuja
        ring.push(40.9)  # mismo entero visible (41): no redibuja
        qapp.processEvents()
        assert filtro.rate_for(ring) == 0.0, (
            f"push sin cambio visible redibujó el anillo: {filtro.rates()}"
        )
        ring.push(72.0)  # cambio real: sí redibuja
        qapp.processEvents()
        assert filtro.rate_for(ring) > 0.0
    finally:
        qapp.removeEventFilter(filtro)
        filtro.deleteLater()


def test_hud_window_corner_tool_spinner_lifecycle_and_colors(qapp, hud_window):
    """La tool en curso muestra un spinner real (timer vivo) y al terminar
    se para: ✓ sin rojo si ok, ✗ en rojo (único rojo del HUD) si error."""
    from hud_pro import theme

    w = hud_window(1366, 768)
    tool = w.corner_tool
    assert not tool._spinner.is_spinning()

    w.tool_start("buscar_en_la_web")
    qapp.processEvents()
    assert tool._spinner.is_spinning(), "tool en curso: el spinner debe girar"
    assert "buscar_en_la_web" in tool._label.text()

    w.tool_end("buscar_en_la_web", 230.0, True)
    qapp.processEvents()
    assert not tool._spinner.is_spinning(), "tool terminada: el spinner se para (CPU)"
    assert "✓" in tool._label.text() and "230" in tool._label.text()
    assert theme.DANGER not in tool._label.styleSheet()

    w.tool_start("borrar_archivo")
    w.tool_end("borrar_archivo", 50.0, False)
    qapp.processEvents()
    assert "✗" in tool._label.text()
    assert theme.DANGER in tool._label.styleSheet(), "el error es lo único rojo del HUD"


def test_hud_window_corner_widgets_stay_within_window_bounds_after_content_grows(qapp, hud_window):
    """Regresión directa: `corner_tool`/`token_gauge` (anclados a la
    derecha) se posicionaban con un ancho VIEJO antes de que el texto
    creciera (p. ej. al cerrar una herramienta con un nombre largo) y
    terminaban con el borde derecho fuera de la ventana. `tool_start`/
    `tool_end`/`update_metrics` deben reposicionar tras cada cambio."""
    w = hud_window(1366, 768)

    w.tool_start("una_herramienta_con_un_nombre_bastante_largo_de_verdad")
    qapp.processEvents()
    assert w.corner_tool.geometry().right() <= w._root.width(), (
        "el widget de herramienta se sale de la ventana al crecer el texto"
    )

    w.tool_end("una_herramienta_con_un_nombre_bastante_largo_de_verdad", 12345.0, True)
    qapp.processEvents()
    assert w.corner_tool.geometry().right() <= w._root.width()

    w.update_metrics({"tokensPerSecond": 123.4, "ttftMs": 9876.0})
    qapp.processEvents()
    assert w.token_gauge.geometry().right() <= w._root.width()


def test_hud_window_corner_widgets_do_not_overlap_services_row(qapp, hud_window):
    """Regresión directa: `corner_system` (arriba-izq, mini anillos CPU/
    RAM) se posicionaba a la misma altura que la fila de chips MIC/WAKE/
    TTS/MEM y quedaba tapado por ella."""
    w = hud_window(1366, 768)
    assert w.corner_system.geometry().top() >= w._services_row_widget.geometry().bottom(), (
        "el widget de CPU/RAM se superpone con la fila de chips de servicio"
    )


def test_hud_window_corner_services_reflects_real_metrics(qapp, hud_window):
    w = hud_window(show=False)
    w.update_metrics({
        "online": True, "pingMs": 8.5,
        "voice": {"mic": "available", "tts": True},
        "memory": {"count": 3},
    })
    assert "8" in w.corner_services._ollama_label.text()
    assert "●" in w.corner_services._mic_label.text()
    assert "●" in w.corner_services._tts_label.text()
    assert "3" in w.corner_services._memory_label.text()


# ── Repintado sólo al cambiar el dato (tarea A: cualquier update() con
# un QOpenGLWidget debajo obliga a recomponer TODA la ventana) ─────────
@pytest.fixture
def paint_clock(qapp):
    from hud_pro.paint_stats import PaintStatsFilter

    filtro = PaintStatsFilter(qapp, interval_s=0)
    qapp.installEventFilter(filtro)
    yield filtro
    qapp.removeEventFilter(filtro)
    filtro.deleteLater()


def test_dot_set_color_same_color_does_not_repaint(qapp, paint_clock):
    from hud_pro.widgets import _Dot

    dot = _Dot("#38BDF8")
    dot.show()
    qapp.processEvents()
    paint_clock.reset()
    dot.set_color("#38BDF8")  # MISMO color: prohibido repintar
    dot.set_color("#38BDF8")
    qapp.processEvents()
    assert paint_clock.rate_for(dot) == 0.0
    dot.set_color("#22D3EE")  # cambio real: sí repinta
    qapp.processEvents()
    assert paint_clock.rate_for(dot) > 0.0
    dot.close()
    dot.deleteLater()


def test_service_chip_set_state_repeat_does_not_repaint(qapp, paint_clock):
    from hud_pro.widgets import ServiceChip

    chip = ServiceChip("mic", "MIC")
    chip.show()
    chip.set_state(on=True, active=False, tip="Micrófono")
    qapp.processEvents()
    paint_clock.reset()
    for _ in range(3):  # el muestreo de métricas repite el MISMO estado cada ~2s
        chip.set_state(on=True, active=False, tip="Micrófono")
    qapp.processEvents()
    assert paint_clock.rate_for(chip) == 0.0
    assert paint_clock.rate_for(chip._dot) == 0.0
    chip.set_state(on=False, active=False, tip="Micrófono")  # cambio real
    qapp.processEvents()
    assert paint_clock.rate_for(chip._dot) > 0.0
    chip.close()
    chip.deleteLater()


def test_topbar_refresh_same_minute_does_not_repaint_clock(qapp, paint_clock, monkeypatch):
    from hud_pro import widgets
    from hud_pro.widgets import TopBar

    bar = TopBar()
    bar.show()
    monkeypatch.setattr(widgets.time, "strftime", lambda fmt: "14:32")
    bar._refresh()
    qapp.processEvents()
    paint_clock.reset()
    bar._refresh()  # mismo minuto: ni reloj ni (probablemente) métricas cambian
    bar._refresh()
    qapp.processEvents()
    assert paint_clock.rate_for(bar.clock) == 0.0, (
        f"el reloj repintó sin cambiar el minuto: {paint_clock.rates()}"
    )
    monkeypatch.setattr(widgets.time, "strftime", lambda fmt: "14:33")
    bar._refresh()  # cambio de minuto real: sí repinta
    qapp.processEvents()
    assert paint_clock.rate_for(bar.clock) > 0.0
    bar.close()
    bar.deleteLater()


def test_topbar_update_metrics_repeat_does_not_repaint(qapp, paint_clock):
    from hud_pro.widgets import TopBar

    bar = TopBar()
    bar.show()
    data = {"online": True, "pingMs": 9, "tokensPerSecond": 12.0}
    bar.update_metrics(data)
    qapp.processEvents()
    paint_clock.reset()
    for _ in range(3):  # el muestreo repite el MISMO dict cada ~2s
        bar.update_metrics(data)
    qapp.processEvents()
    assert paint_clock.rate_for(bar.ollama_label) == 0.0, (
        f"update_metrics con el mismo dato repintó: {paint_clock.rates()}"
    )
    assert paint_clock.rate_for(bar.ollama_dot) == 0.0
    bar.close()
    bar.deleteLater()
