"""Tests de los componentes de FASE D (paneles, paleta, checklist de
arranque) — offscreen, sin necesitar GPU real: son QWidget normales."""

from __future__ import annotations

from hud_pro.command_palette import Command, CommandPalette
from hud_pro.panels import ActivityPanel, Sparkline, SystemPanel, TokenGauge
from hud_pro.qt_compat import QtCore
from hud_pro.startup_checklist import CheckItem, StartupChecklist
from hud_pro.state import OrbState
from hud_pro.window import HudWindow


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
def test_hud_window_side_dock_respects_wide_threshold(qapp):
    w = HudWindow()
    w.resize(w.WIDE_LAYOUT_MIN_WIDTH - 100, 900)
    w.show()
    qapp.processEvents()
    assert not w._is_wide_layout()
    assert not w._side_dock.isVisible(), "angosta y cajón cerrado: paneles ocultos"

    w._toggle_side_drawer()
    qapp.processEvents()
    assert w._side_dock.isVisible(), "el botón del cajón debe poder abrirlo en modo angosto"


def test_hud_window_focus_mode_hides_chrome_and_restores(qapp):
    w = HudWindow()
    w.show()
    qapp.processEvents()
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


def test_hud_window_token_gauge_visible_only_while_generating(qapp):
    w = HudWindow()
    w.show()
    qapp.processEvents()
    w.set_state(OrbState.IDLE)
    assert not w.token_gauge.isVisible()
    w.set_state(OrbState.THINKING)
    assert w.token_gauge.isVisible()
    w.set_state(OrbState.SPEAKING)
    assert w.token_gauge.isVisible()
    w.set_state(OrbState.LISTENING)
    assert not w.token_gauge.isVisible()


def test_hud_window_tool_end_reaches_activity_panel(qapp):
    w = HudWindow()
    w.tool_start("buscar_memoria")
    w.tool_end("buscar_memoria", 120.0, True)
    assert w.activity_panel._tools_list.count() == 1
    assert "buscar_memoria" in w.activity_panel._tools_list.item(0).text()


def test_hud_window_update_metrics_reaches_token_gauge_and_memory(qapp):
    w = HudWindow()
    w.update_metrics({"tokensPerSecond": 12.0, "ttftMs": 300.0, "memory": {"count": 7}})
    assert "12 tok/s" in w.token_gauge._tps_label.text()
    assert w.activity_panel._memory_label.text() == "Memoria: 7 recuerdos"


def test_hud_window_command_palette_shortcut_and_real_actions(qapp):
    w = HudWindow()
    w.show()
    qapp.processEvents()
    assert not w._command_palette.isVisible()
    w._command_palette.open()
    assert w._command_palette.isVisible()
    titles = [w._command_palette._list.item(i).text() for i in range(w._command_palette._list.count())]
    assert any("enfoque" in t.lower() for t in titles)
