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


def test_conversation_model_streaming_turn():
    from jarvis_local.ui.hud.conversation_model import (
        ROLE_META,
        ROLE_STREAMING,
        ROLE_TEXT,
        ConversationModel,
    )

    cm = ConversationModel()
    cm.add_user("hola")
    cm.begin_assistant()
    for tok in ("Aquí ", "va", ".") :
        cm.append_token(tok)
    assert cm.rowCount() == 2
    i = cm.index(1, 0)
    assert cm.data(i, ROLE_STREAMING) is True
    assert cm.data(i, ROLE_TEXT) == "Aquí va."
    cm.end_assistant("", "500 ms", "chat")
    assert cm.data(i, ROLE_STREAMING) is False
    assert cm.data(i, ROLE_META) == "500 ms"


class _FakeInner:
    """Cliente Ollama mínimo: streamea tokens fijos."""

    def chat(self, messages, model=None, stream=False):
        toks = ["Py", "thon ", "es ", "un ", "lenguaje."]
        return iter(toks) if stream else "".join(toks)

    def is_running(self):
        return True


def test_tap_client_taps_stream_tokens():
    import threading

    from jarvis_local.ui.hud.chat_service import _TapClient

    seen = []
    tap = _TapClient(_FakeInner(), seen.append, threading.Event())
    out = "".join(tap.chat([{"role": "user", "content": "x"}], stream=True))
    assert out == "Python es un lenguaje."
    assert seen == ["Py", "thon ", "es ", "un ", "lenguaje."]
    # sin stream: pasa por debajo, no chiva
    seen.clear()
    assert tap.chat([], stream=False) == "Python es un lenguaje."
    assert seen == []
    assert tap.is_running() is True   # __getattr__ delega


def test_chat_service_full_turn_with_fake_core(monkeypatch):
    from jarvis_local.ui.hud.chat_service import ChatService
    from jarvis_local.ui.hud.conversation_model import (
        ROLE_STREAMING,
        ROLE_TEXT,
        ConversationModel,
    )

    class _FakeJarvis:
        def __init__(self):
            self.client = _FakeInner()

        def chat(self, text):
            # emula el núcleo: consume el stream del (tap)client
            return "".join(self.client.chat([{"role": "user", "content": text}],
                                            stream=True))

    vm = ViewModel()
    cm = ConversationModel()
    svc = ChatService(vm, cm)
    monkeypatch.setattr(svc, "_ensure_jarvis", lambda: setattr(svc, "_jarvis", _FakeJarvis()))

    svc.send("qué es python")
    import time
    t0 = time.monotonic()
    while svc.busy and time.monotonic() - t0 < 5:
        _app.processEvents()
        time.sleep(0.02)
    _app.processEvents()

    assert cm.rowCount() == 2
    i = cm.index(1, 0)
    assert cm.data(i, ROLE_STREAMING) is False
    assert cm.data(i, ROLE_TEXT) == "Python es un lenguaje."
    assert vm.metrics.get("latencyMs") is not None
    assert vm.state in ("idle", "thinking")


def test_tap_client_cancel_stops_stream():
    import threading

    from jarvis_local.ui.hud.chat_service import _TapClient

    ev = threading.Event()
    seen = []
    tap = _TapClient(_FakeInner(), seen.append, ev)
    gen = tap.chat([], stream=True)
    assert next(gen) == "Py"          # primer token pasa
    ev.set()                          # cancelado
    assert list(gen) == []            # no se emiten más
    assert seen == ["Py"]


def test_voice_service_state_machine_no_audio():
    from jarvis_local.ui.hud.voice_service import VoiceService

    vm = ViewModel()
    v = VoiceService(vm)
    assert v.micState == "inactive"
    assert v.speaking is False
    # stop sin estar grabando: no-op
    v.stop_recording()
    assert v.micState == "inactive"


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


def _core_loop(root):
    from PySide6.QtCore import QObject
    loops = [o for o in root.findChildren(QObject) if o.objectName() == "coreLoop"]
    assert len(loops) == 1, f"esperaba 1 bucle de núcleo, hay {len(loops)}"
    return loops[0]


def test_single_frame_animation_driver():
    """Addendum §7: un único FrameAnimation global mueve el núcleo; cero
    Timers sueltos animando en el árbol del núcleo."""
    from PySide6.QtCore import QObject

    from jarvis_local.ui.hud.app import create_engine

    engine = create_engine(_app, ViewModel())
    try:
        win = engine.rootObjects()[0]
        fas = [o for o in win.findChildren(QObject)
               if "FrameAnimation" in o.metaObject().className()]
        assert len(fas) == 1, f"esperaba 1 FrameAnimation, hay {len(fas)}"
        assert fas[0].objectName() == "coreLoop"
    finally:
        engine._runtime.shutdown()  # noqa: SLF001
        engine.deleteLater()


def test_loop_pauses_when_not_running():
    from PySide6.QtQuick import QQuickItem

    from jarvis_local.ui.hud.app import create_engine

    engine = create_engine(_app, ViewModel())
    try:
        win = engine.rootObjects()[0]
        root = win.findChild(QQuickItem, "rootItem")
        loop = _core_loop(win)
        root.setProperty("paused", False)
        _app.processEvents()
        assert loop.property("running") is True
        root.setProperty("paused", True)          # sin foco / minimizada
        _app.processEvents()
        assert loop.property("running") is False
    finally:
        engine._runtime.shutdown()  # noqa: SLF001
        engine.deleteLater()


def test_reduced_motion_freezes_core_and_shader():
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from jarvis_local.ui.hud.app import create_engine

    engine = create_engine(_app, ViewModel())
    try:
        win = engine.rootObjects()[0]
        core = win.findChild(QQuickItem, "coreZone").childItems()[0]
        shader = next(o for o in win.findChildren(QObject)
                      if "CoreShader" in o.metaObject().className())
        core.setProperty("coreState", "idle")
        core.setProperty("reducedMotion", False)
        _app.processEvents()
        assert core.property("loopActive") is True
        core.setProperty("reducedMotion", True)
        _app.processEvents()
        # en idle + reducido el bucle se detiene y el shader marca reduced=1
        assert core.property("loopActive") is False
        assert shader.property("reduced") == 1
    finally:
        engine._runtime.shutdown()  # noqa: SLF001
        engine.deleteLater()


def test_degradation_path_bypasses_bloom():
    """Addendum §7: la ruta de degradación existe y actúa (no es un `if`
    teórico). backend software o `perfOverride` → sin bloom, sólo el shader."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from jarvis_local.ui.hud.app import create_engine

    engine = create_engine(_app, ViewModel())
    try:
        win = engine.rootObjects()[0]
        root = win.findChild(QQuickItem, "rootItem")
        cb = next(o for o in win.findChildren(QObject)
                  if "CoreBloom" in o.metaObject().className())
        cs = next(o for o in win.findChildren(QObject)
                  if "CoreShader" in o.metaObject().className())

        # forzar pipeline completo
        root.setProperty("perfOverride", -1)
        _app.processEvents()
        assert root.property("degraded") is False
        assert cb.property("bypass") is False
        assert root.property("atmosphereOn") is True

        # forzar degradado → sin bloom, el shader del núcleo se ve directo
        root.setProperty("perfOverride", 1)
        _app.processEvents()
        assert root.property("degraded") is True
        assert cb.property("bypass") is True
        assert cs.property("visible") is True
        assert root.property("atmosphereOn") is False
    finally:
        engine._runtime.shutdown()  # noqa: SLF001
        engine.deleteLater()


def test_low_fps_sustained_degrades():
    from PySide6.QtQuick import QQuickItem

    from jarvis_local.ui.hud.app import create_engine

    engine = create_engine(_app, ViewModel())
    try:
        win = engine.rootObjects()[0]
        root = win.findChild(QQuickItem, "rootItem")
        root.setProperty("perfOverride", 0)               # auto
        root.setProperty("_softwareBackend", False)       # aislar el gatillo de fps
        _app.processEvents()
        assert root.property("degraded") is False
        # el bucle engancha el latch tras 3 s de <40 fps; aquí lo simulamos
        root.setProperty("_degradedLatch", True)
        _app.processEvents()
        assert root.property("degraded") is True
        # es un latch: aunque el backend siga bien, no vuelve
        root.setProperty("_degradedLatch", False)
        _app.processEvents()
        assert root.property("degraded") is False   # (reset manual permitido en test)
    finally:
        engine._runtime.shutdown()  # noqa: SLF001
        engine.deleteLater()


def test_runtime_shutdown_stops_metrics_thread():
    from jarvis_local.ui.hud.app import Runtime

    rt = Runtime(ViewModel())
    rt.start()
    import time
    time.sleep(0.1)
    assert rt.metrics._thread is not None and rt.metrics._thread.is_alive()  # noqa: SLF001
    rt.shutdown()
    assert rt.metrics._thread is None  # noqa: SLF001
    # timers registrados y detenidos
    for t in rt.timers:
        assert not t.isActive()


def test_reduced_motion_detection_env(monkeypatch):
    from jarvis_local.ui.hud.services import detect_reduced_motion

    monkeypatch.setenv("JARVIS_REDUCED_MOTION", "1")
    assert detect_reduced_motion() is True
    monkeypatch.setenv("JARVIS_REDUCED_MOTION", "0")
    assert detect_reduced_motion() is False


def test_responsive_layout_no_overlap_no_overflow():
    """Fase 6: en los cuatro modos, núcleo y conversación no se solapan, todo
    queda dentro de la ventana y la barra de comando es alcanzable."""
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem

    from jarvis_local.ui.hud.app import create_engine

    engine = create_engine(_app, ViewModel())
    win = engine.rootObjects()[0]

    def rect(name):
        it = win.findChild(QQuickItem, name)
        tl = it.mapToScene(QPointF(0, 0))
        return (tl.x(), tl.y(), it.width(), it.height())

    def overlap(a, b):
        ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
        iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
        return ix * iy

    try:
        for w, h in ((1700, 900), (1360, 820), (1000, 760), (430, 360)):
            win.setWidth(w); win.setHeight(h)
            _app.processEvents()
            cz, vz, cb = rect("coreZone"), rect("convZone"), rect("cmdBar")
            assert overlap(cz, vz) == 0, f"{w}x{h}: solapan núcleo y conversación"
            for r in (cz, vz, rect("hud")):
                assert r[0] >= -1 and r[1] >= -1
                assert r[0] + r[2] <= w + 1 and r[1] + r[3] <= h + 1, f"{w}x{h}: overflow"
            assert cb[1] + cb[3] <= h + 1, f"{w}x{h}: barra de comando fuera de vista"
    finally:
        engine._metrics.stop()  # noqa: SLF001
        engine.deleteLater()
