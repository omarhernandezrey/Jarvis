"""Tests del HUD pro (offscreen). Ejecutar: QT_QPA_PLATFORM=offscreen pytest -q tests/"""

from __future__ import annotations

import math
import threading
import time

import pytest

from hud_pro import HudBridge, HudWindow, OrbRenderer, OrbState, OrbWidget, parse_state
from hud_pro.chat import MAX_INPUT_CHARS, MAX_MESSAGES, render_markdown_safe, sanitize_input
from hud_pro.qt_compat import QtCore, QtGui
from hud_pro.theme import CHAT_MAX_WIDTH


def pump(app, ms: int = 30) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.002)


def wait_until(app, cond, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return cond()


@pytest.fixture
def win(qapp):
    w = HudWindow()
    w.resize(1920, 1080)
    w.show()
    pump(qapp, 60)
    yield w
    w.close()
    w.deleteLater()
    pump(qapp, 10)


# ── Estados ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "alias,expected",
    [
        ("listo", OrbState.IDLE),
        ("idle", OrbState.IDLE),
        ("ESCUCHANDO", OrbState.LISTENING),
        (" procesando ", OrbState.THINKING),
        ("thinking", OrbState.THINKING),
        ("hablando", OrbState.SPEAKING),
        ("error", OrbState.ERROR),
        (OrbState.SPEAKING, OrbState.SPEAKING),
    ],
)
def test_parse_state_aliases(alias, expected):
    assert parse_state(alias) is expected


@pytest.mark.parametrize("bad", ["", "dormido", None, 3])
def test_parse_state_invalid(bad):
    with pytest.raises(ValueError):
        parse_state(bad)


# ── Renderer ──────────────────────────────────────────────────────────────
def test_level_is_clamped_and_nan_safe():
    r = OrbRenderer()
    for raw, expected in (
        (5, 1.0),
        (-2, 0.0),
        (float("nan"), 0.0),
        (float("inf"), 0.0),
        ("x", 0.0),
        (0.4, 0.4),
    ):
        r.set_level(raw)
        assert r._level_target == pytest.approx(expected)


def test_transition_converges_smoothly():
    r = OrbRenderer()
    start = r.param("ring_speed")
    r.set_state(OrbState.THINKING)
    r.advance(1 / 60)
    mid = r.param("ring_speed")
    assert start < mid < 2.6  # interpola, no salta
    for _ in range(120):
        r.advance(1 / 60)
    assert r.param("ring_speed") == pytest.approx(2.6, rel=0.01)


def test_speaking_without_external_level_synthesizes_motion():
    r = OrbRenderer()
    r.set_state(OrbState.SPEAKING)
    levels = []
    for _ in range(90):
        r.advance(1 / 60)
        levels.append(r.level)
    assert max(levels) > 0.1


def test_ripples_bounded_and_reduced_motion():
    r = OrbRenderer()
    r.set_state(OrbState.SPEAKING)
    r.snap()
    for _ in range(600):
        r.set_level(1.0)
        r.advance(1 / 60)
        assert len(r._ripples) <= r.MAX_RIPPLES
    r.reduced_motion = True
    r.advance(1 / 60)
    assert r._ripples == []


@pytest.mark.parametrize("state", list(OrbState))
def test_render_each_state_draws_centered(qapp, state):
    r = OrbRenderer()
    r.set_state(state)
    r.snap()
    for _ in range(20):
        r.advance(1 / 60)
    img = QtGui.QImage(500, 400, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QtGui.QColor(0, 0, 0))
    p = QtGui.QPainter(img)
    r.paint(p, img.width(), img.height())
    p.end()
    center = QtGui.QColor(img.pixel(250, 200))
    corner = QtGui.QColor(img.pixel(2, 2))
    assert center.lightness() > 120 > corner.lightness()
    # simetría horizontal aproximada del brillo (orbe centrado)
    left = QtGui.QColor(img.pixel(250 - 60, 200)).lightness()
    right = QtGui.QColor(img.pixel(250 + 60, 200)).lightness()
    assert abs(left - right) < 90


def test_render_tiny_size_is_noop(qapp):
    img = QtGui.QImage(20, 20, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QtGui.QPainter(img)
    OrbRenderer().paint(p, 20, 20)
    p.end()


def test_frame_budget(qapp):
    """Guardarraíl de rendimiento: holgado para CI, detecta regresiones graves."""
    r = OrbRenderer()
    r.set_state(OrbState.LISTENING)
    r.snap()
    img = QtGui.QImage(600, 600, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    for _ in range(5):
        r.advance(1 / 60)
        img.fill(0)
        p = QtGui.QPainter(img)
        r.paint(p, 600, 600)
        p.end()
    t0 = time.perf_counter()
    n = 40
    for _ in range(n):
        r.set_level(0.5)
        r.advance(1 / 60)
        img.fill(0)
        p = QtGui.QPainter(img)
        r.paint(p, 600, 600)
        p.end()
    assert (time.perf_counter() - t0) / n < 0.025


# ── Widget del orbe ───────────────────────────────────────────────────────
def test_orb_widget_state_signal_and_timer(qapp):
    w = OrbWidget()
    got: list[str] = []
    w.stateChanged.connect(got.append)
    w.resize(400, 400)
    w.show()
    pump(qapp, 30)
    assert w.is_animating()
    assert w._timer.interval() in (round(1000 / OrbWidget.IDLE_FPS), round(1000 / OrbWidget.BACKGROUND_FPS))
    w.set_state("escuchando")
    w.set_state("listening")  # mismo estado: sin señal duplicada
    assert got == ["listening"]
    assert w._timer.interval() == round(1000 / 60)
    with pytest.raises(ValueError):
        w.set_state("volando")
    w.set_paused(True)
    assert not w.is_animating()
    w.set_paused(False)
    assert w.is_animating()
    w.hide()
    assert not w.is_animating()
    w.deleteLater()


# ── Ventana / layout ──────────────────────────────────────────────────────
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768), (1280, 820), (2560, 1440)])
def test_layout_orb_and_chat_centered(qapp, win, size):
    win.resize(*size)
    pump(qapp, 80)
    root = win.centralWidget()
    cx = root.width() / 2
    orb_c = win.orb.geometry().center()
    chat_g = win.chat.geometry()
    chat_cx = win.chat.mapTo(root, QtCore.QPoint(chat_g.width() // 2, 0)).x()
    assert abs(orb_c.x() - cx) <= 2
    assert abs(chat_cx - cx) <= 2
    assert win.chat.width() <= CHAT_MAX_WIDTH
    assert HudWindow.CHAT_MIN_HEIGHT <= win.chat.height() <= HudWindow.CHAT_MAX_HEIGHT
    assert win.orb.height() >= 240


def test_state_propagates_to_all_indicators(qapp, win):
    win.set_state("escuchando")
    assert win.top_bar.chip.text() == "ESCUCHANDO"
    assert win.status.title.text() == "ESCUCHANDO"
    assert win.chat.input.mic.isChecked()
    win.set_transcript("hola jarvis")
    assert "hola jarvis" in win.status.transcript.text()
    win.set_state("procesando")
    assert not win.chat.input.mic.isChecked()
    assert "hola jarvis" in win.status.transcript.text()  # se conserva al procesar
    win.set_state("listo")
    assert win.status.transcript.text() == ""
    win.set_state("error", "Ollama no responde")
    assert win.status.hint.text() == "Ollama no responde"


def test_mic_button_does_not_echo_when_state_changes(qapp, win):
    toggles: list[bool] = []
    win.mic_toggled.connect(toggles.append)
    win.set_state("escuchando")
    win.set_state("listo")
    assert toggles == []
    win.chat.input.mic.click()
    assert toggles == [True]


def test_submit_echo_sanitize_and_rate_limit(qapp, win):
    sent: list[str] = []
    win.message_submitted.connect(sent.append)
    edit = win.chat.input.edit
    edit.setText("   \x00hola\x07 jarvis  ")
    win.chat.input.submit()
    assert sent == ["hola jarvis"]
    assert win.chat.view.bubbles[-1].text == "hola jarvis"
    edit.setText("otra")
    win.chat.input.submit()  # < 300 ms: ignorado
    assert sent == ["hola jarvis"]
    pump(qapp, 320)
    win.chat.input.submit()
    assert sent[-1] == "otra"
    edit.setText("    ")
    pump(qapp, 320)
    win.chat.input.submit()
    assert len(sent) == 2


def test_input_limits():
    assert sanitize_input("a" * (MAX_INPUT_CHARS + 50)) == "a" * MAX_INPUT_CHARS
    assert sanitize_input(None) == ""  # type: ignore[arg-type]


def test_streaming_single_bubble(qapp, win):
    for tok in ["Hola", ", ", "**Omar**"]:
        win.stream_assistant(tok)
    assert win.chat.is_streaming()
    bubbles = [b for b in win.chat.view.bubbles if b.role == "assistant"]
    assert len(bubbles) == 1 and bubbles[0].text == "Hola, **Omar**"
    win.end_assistant_stream()
    assert not win.chat.is_streaming()
    assert "▍" not in bubbles[0].body.text()
    assert "Omar" in bubbles[0].body.text()


def test_user_message_ends_open_stream(qapp, win):
    win.stream_assistant("parcial")
    win.add_user_message("nuevo")
    assert not win.chat.is_streaming()


def test_history_is_capped(qapp, win):
    for i in range(MAX_MESSAGES + 15):
        win.add_system_message(f"m{i}")
    assert len(win.chat.view.bubbles) == MAX_MESSAGES
    assert win.chat.view.bubbles[0].text == "m15"
    win.clear_chat()
    assert win.chat.view.bubbles == []


def test_toggle_console(qapp, win):
    win.toggle_console(False)
    assert not win.chat.isVisible()
    win.toggle_console()
    assert win.chat.isVisible()


def test_minimize_pauses_animation(qapp, win):
    assert win.orb.is_animating()
    win.orb.set_paused(True)
    assert not win.orb.is_animating()
    win.orb.set_paused(False)


# ── Seguridad del markdown ────────────────────────────────────────────────
def test_markdown_escapes_raw_html_and_strips_images_and_bad_links(qapp):
    html = render_markdown_safe(
        "<b>x</b> <script>alert(1)</script> ![i](file:///etc/passwd) "
        "[bad](javascript:alert(1)) [ok](https://example.com) **bold**"
    )
    assert "<b>" not in html and "&lt;b&gt;" in html
    assert "<script" not in html.lower()
    assert "<img" not in html.lower()
    assert "javascript:" not in html
    assert 'href="https://example.com"' in html
    assert "font-weight" in html  # el markdown legítimo sí se renderiza


# ── Bridge thread-safe ────────────────────────────────────────────────────
def test_bridge_from_worker_thread(qapp, win):
    bridge = HudBridge(win)
    errors: list[BaseException] = []

    def worker():
        try:
            bridge.set_model("llama3.1:8b")
            bridge.set_state("escuchando")
            for i in range(200):
                bridge.set_level(abs(math.sin(i)))
            bridge.set_transcript("qué hora es")
            bridge.add_message("user", "qué hora es")
            bridge.set_state("procesando")
            for tok in ["Son ", "las ", "**10**"]:
                bridge.stream(tok)
            bridge.end_stream()
            bridge.set_state("listo")
            with pytest.raises(ValueError):
                bridge.set_state("nope")
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join(5)
    assert not errors
    assert wait_until(qapp, lambda: win.state is OrbState.IDLE and not win.chat.is_streaming())
    texts = [b.text for b in win.chat.view.bubbles]
    assert "qué hora es" in texts and "Son las **10**" in texts
    assert "llama3.1:8b" in win.top_bar.model_label.text()


def test_bridge_must_be_created_in_gui_thread(qapp, win):
    box: list[BaseException] = []

    def make():
        try:
            HudBridge(win)
        except BaseException as exc:
            box.append(exc)

    t = threading.Thread(target=make)
    t.start()
    t.join(5)
    assert box and isinstance(box[0], RuntimeError)


def test_bridge_relays_user_messages(qapp, win):
    bridge = HudBridge(win)
    got: list[str] = []
    bridge.user_message.connect(got.append)
    win.chat.input.edit.setText("abre el navegador")
    win.chat.input.submit()
    assert got == ["abre el navegador"]


def test_screenshot_grab_not_blank(qapp, win):
    win.set_state("hablando")
    pump(qapp, 120)
    img = win.grab().toImage()
    c = QtGui.QColor(img.pixel(win.orb.mapTo(win, win.orb.rect().center())))
    assert c.lightness() > 100
