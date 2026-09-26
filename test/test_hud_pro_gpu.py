"""Tests del motor GPU de hud_pro (3ª iteración, FASE A).

`QOpenGLWidget` (la ventana GPU real) NO pinta bajo `QT_QPA_PLATFORM=offscreen`
— Qt lo dice explícito por stderr, no es un bug de este proyecto — así que la
invocación estándar del repo (`QT_QPA_PLATFORM=offscreen pytest -q test`) sólo
puede ejercitar: detección de capacidades (usa QOffscreenSurface, que SÍ
funciona offscreen), compilación de shaders (mismo mecanismo) y el camino de
fallback de `HudWindow` (que bajo offscreen debe quedarse SIEMPRE en `None`).
Las pruebas que necesitan crear una `HoloStage`/`HudWindow` con GPU de verdad
viven en un subproceso aparte con `QT_QPA_PLATFORM` heredado del entorno real
y se saltan si no hay sesión gráfica (ni `DISPLAY` ni `WAYLAND_DISPLAY`).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from hud_pro.gpu import capabilities
from hud_pro.gpu.quality import (
    QUALITY_PRESETS,
    AutoQualityController,
    Quality,
    parse_quality,
)
from hud_pro.gpu.shader_loader import ShaderCompileError, ShaderProgram
from hud_pro.qt_compat import QtGui
from hud_pro.window import HudWindow

HAS_REAL_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def gl_caps(qapp) -> capabilities.GLCapabilities:
    return capabilities.detect()


@pytest.fixture
def gl_context(qapp, gl_caps):
    """Contexto GL real (offscreen) hecho corriente — lo que `ShaderProgram`
    necesita para compilar. Se salta si esta máquina no puede darlo (nunca
    se inventa un resultado de "compiló" sin GPU real detrás)."""
    if not gl_caps.available:
        pytest.skip(f"sin contexto GL real en esta máquina: {gl_caps.error}")
    fmt = QtGui.QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface = QtGui.QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    ctx = QtGui.QOpenGLContext()
    ctx.setFormat(fmt)
    ctx.create()
    ctx.makeCurrent(surface)
    yield ctx
    ctx.doneCurrent()
    surface.destroy()


# ── capacidades ─────────────────────────────────────────────────────────
def test_detect_reports_real_capabilities_never_invented(gl_caps):
    """En esta máquina hay GPU real (Mesa) — si algún día no la hay,
    `available` debe ser False con un motivo, nunca campos inventados."""
    if not gl_caps.available:
        assert gl_caps.error
        assert gl_caps.vendor == "" and gl_caps.renderer == ""
        return
    assert gl_caps.vendor
    assert gl_caps.renderer
    assert (gl_caps.major, gl_caps.minor) >= (3, 3)
    assert "GLCapabilities" not in gl_caps.summary()  # legible, no un repr crudo


def test_summary_failure_branch_never_touches_hardware_fields():
    caps = capabilities.GLCapabilities(available=False, error="humo de prueba")
    assert caps.summary() == "GPU no disponible: humo de prueba"


def test_qopenglwidget_supported_here_matches_platform(qapp):
    """Bajo la invocación estándar del proyecto (offscreen) Qt se niega a
    pintar QOpenGLWidget — confirmado, no asumido. Con sesión gráfica real
    debe devolver True."""
    supported, reason = capabilities.qopenglwidget_supported_here()
    platform = qapp.platformName()
    if platform == "offscreen":
        assert supported is False
        assert "offscreen" in reason
    else:
        assert supported is True


# ── compilación de shaders reales ────────────────────────────────────────
@pytest.mark.parametrize(
    "frag",
    [
        "scene.frag",
        "bloom_extract.frag",
        "godray.frag",
        "kawase_down.frag",
        "kawase_up.frag",
        "streak.frag",
        "composite.frag",
        "orb.frag",
        "blit.frag",
        "rings.frag",
    ],
)
def test_real_shader_compiles_and_links(gl_context, frag):
    program = ShaderProgram("fullscreen.vert", frag)
    assert program.qt_program is not None
    assert program.qt_program.isLinked()


def test_dust_shader_compiles_and_links(gl_context):
    program = ShaderProgram("dust.vert", "dust.frag")
    assert program.qt_program is not None
    assert program.qt_program.isLinked()


def test_broken_shader_raises_compile_error(gl_context, tmp_path, monkeypatch):
    from hud_pro.gpu import shader_loader

    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    (tmp_path / "ok.vert").write_text(
        "#version 330 core\nvoid main(){ gl_Position = vec4(0.0);}\n"
    )
    (tmp_path / "broken.frag").write_text(
        "#version 330 core\nout vec4 fragColor;\nvoid main(){ fragColor = ESTO_NO_EXISTE; }\n"
    )
    with pytest.raises(ShaderCompileError):
        ShaderProgram("ok.vert", "broken.frag")


# ── recarga en caliente (JARVIS_HUD_DEV=1) ──────────────────────────────
def _write_scratch_shaders(tmp_path, tint: str) -> None:
    (tmp_path / "ok.vert").write_text(
        "#version 330 core\nvoid main(){ gl_Position = vec4(0.0);}\n"
    )
    (tmp_path / "scratch.frag").write_text(
        f"#version 330 core\nout vec4 fragColor;\nvoid main(){{ fragColor = {tint}; }}\n"
    )


def test_hot_reload_recompiles_when_dev_flag_set(gl_context, tmp_path, monkeypatch):
    from hud_pro.gpu import shader_loader

    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    monkeypatch.setenv("JARVIS_HUD_DEV", "1")
    _write_scratch_shaders(tmp_path, "vec4(1.0)")

    program = ShaderProgram("ok.vert", "scratch.frag")
    before = program.qt_program
    assert program.maybe_reload() is False  # nada cambió todavía

    future = program._source_mtimes()[1] + 5.0
    _write_scratch_shaders(tmp_path, "vec4(0.5)")
    os.utime(tmp_path / "scratch.frag", (future, future))

    assert program.maybe_reload() is True
    assert program.qt_program is not before


def test_hot_reload_noop_without_dev_flag(gl_context, tmp_path, monkeypatch):
    from hud_pro.gpu import shader_loader

    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    monkeypatch.delenv("JARVIS_HUD_DEV", raising=False)
    _write_scratch_shaders(tmp_path, "vec4(1.0)")

    program = ShaderProgram("ok.vert", "scratch.frag")
    before = program.qt_program
    future = program._source_mtimes()[1] + 5.0
    _write_scratch_shaders(tmp_path, "vec4(0.5)")
    os.utime(tmp_path / "scratch.frag", (future, future))

    assert program.maybe_reload() is False
    assert program.qt_program is before


def test_hot_reload_keeps_previous_program_on_syntax_error(gl_context, tmp_path, monkeypatch):
    from hud_pro.gpu import shader_loader

    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    monkeypatch.setenv("JARVIS_HUD_DEV", "1")
    _write_scratch_shaders(tmp_path, "vec4(1.0)")

    program = ShaderProgram("ok.vert", "scratch.frag")
    before = program.qt_program

    future = program._source_mtimes()[1] + 5.0
    (tmp_path / "scratch.frag").write_text(
        "#version 330 core\nout vec4 fragColor;\nvoid main(){ fragColor = ESTO_ROMPE; }\n"
    )
    os.utime(tmp_path / "scratch.frag", (future, future))

    assert program.maybe_reload() is False  # falló, se queda con el que ya funcionaba
    assert program.qt_program is before


# ── calidad / AUTO ───────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "value,expected",
    [
        ("low", Quality.LOW),
        ("MEDIUM", Quality.MEDIUM),
        (" high ", Quality.HIGH),
        ("ultra", Quality.ULTRA),
        ("auto", None),
        ("", None),
        ("disco-inferno", None),
    ],
)
def test_parse_quality(value, expected):
    assert parse_quality(value) is expected


def test_quality_presets_scale_monotonically_with_level():
    order = [Quality.LOW, Quality.MEDIUM, Quality.HIGH, Quality.ULTRA]
    scales = [QUALITY_PRESETS[q].bloom_scale for q in order]
    levels = [QUALITY_PRESETS[q].kawase_levels for q in order]
    assert scales == sorted(scales)
    assert levels == sorted(levels)


def test_quality_presets_never_undercut_godray_sample_floor():
    """Mandato explícito: nunca menos de 32 muestras para los rayos de
    dios, en ningún nivel fijo ni bajo degradación de AUTO."""
    for settings in QUALITY_PRESETS.values():
        assert settings.godray_samples >= 32
    ctl = AutoQualityController()
    for _ in range(ctl.WINDOW * 50):
        ctl.update(100.0)  # peor caso: fuerza la mínima escala posible
    assert ctl.current.godray_samples >= 32


def test_auto_quality_scales_down_under_sustained_heavy_frames():
    ctl = AutoQualityController()
    start_scale = ctl.scale
    for _ in range(ctl.WINDOW):
        ctl.update(20.0)  # muy por encima de TARGET_MS
    assert ctl.scale < start_scale


def test_auto_quality_recovers_when_frames_are_cheap():
    ctl = AutoQualityController()
    for _ in range(ctl.WINDOW):
        ctl.update(20.0)
    degraded = ctl.scale
    for _ in range(ctl.WINDOW):
        ctl.update(2.0)  # muy por debajo de RECOVER_MS
    assert ctl.scale > degraded


def test_auto_quality_never_exceeds_bounds():
    ctl = AutoQualityController()
    for _ in range(ctl.WINDOW * 30):
        ctl.update(50.0)
    assert ctl.scale >= ctl.MIN_SCALE
    for _ in range(ctl.WINDOW * 30):
        ctl.update(0.1)
    assert ctl.scale <= 1.0


# ── integración con HudWindow (fallback) ─────────────────────────────────
def test_hud_window_gpu_stage_matches_platform_capability(qapp):
    """Bajo `QT_QPA_PLATFORM=offscreen` (la invocación estándar) el fondo
    GPU nunca debe activarse — si esto empieza a fallar bajo offscreen algo
    del gating se rompió, no una mejora."""
    w = HudWindow()
    try:
        if qapp.platformName() == "offscreen":
            assert w.gpu_stage is None
            assert w.gpu_active is False
    finally:
        w.close()
        w.deleteLater()


def test_hud_window_gpu_off_env_short_circuits(qapp, monkeypatch):
    monkeypatch.setenv("JARVIS_HUD_GPU", "off")
    w = HudWindow()
    try:
        assert w.gpu_stage is None
        assert w.gpu_active is False
    finally:
        w.close()
        w.deleteLater()


# ── sesión gráfica real: el propio segfault que motivó esta FASE A ──────
def _run_subprocess_script(body: str, env_overrides: dict) -> subprocess.CompletedProcess:
    script = textwrap.dedent(body)
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)  # hereda la sesión gráfica real, no offscreen
    env.update(env_overrides)
    env["PYTHONPATH"] = REPO_ROOT
    return subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_does_not_segfault_on_close_with_real_gpu():
    """Regresión directa del segfault diagnosticado en `HoloStage`:
    `QOpenGLTimerQuery`/`QOpenGLVertexArrayObject` son QObject hijos del
    widget — destruirlos DESPUÉS de que su `QOpenGLContext` muere revienta
    el proceso (confirmado con faulthandler). El fix conecta la limpieza a
    `context().aboutToBeDestroyed` envuelta en una lambda (ver comentario en
    `stage.py::initializeGL` — un método ligado no sirve, Qt lo
    auto-desconecta al empezar a destruirse el propio widget)."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HoloStage()
        w.resize(300, 200)
        w.show()
        for _ in range(15):
            app.processEvents()
        assert w.ok, w.init_error
        w.close()
        del w
        app.processEvents()
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_hud_window_activates_real_gpu_background():
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.window import HudWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HudWindow()
        w.show()
        for _ in range(15):
            app.processEvents()
        assert w.gpu_active, w.gpu_stage.init_error if w.gpu_stage else "sin gpu_stage"
        w.close()
        del w
        app.processEvents()
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_hud_window_respects_gpu_off_with_real_display():
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.window import HudWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HudWindow()
        w.show()
        for _ in range(10):
            app.processEvents()
        assert w.gpu_stage is None
        w.close()
        del w
        app.processEvents()
        print("OK")
        """,
        {"JARVIS_HUD_GPU": "off"},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


# ── FASE B: ruido 3D (puro Python, sin GL — determinista y tileable) ────
def test_noise3d_is_deterministic_and_cached(tmp_path, monkeypatch):
    from hud_pro.gpu import noise3d

    monkeypatch.setattr(noise3d, "CACHE_DIR", tmp_path)
    data1 = noise3d.generate_or_load(16)
    cached_path = tmp_path / "noise3d_16.bin"
    assert cached_path.exists()
    data2 = noise3d.generate_or_load(16)  # debe leer la caché, no regenerar
    assert data1 == data2
    assert len(data1) == 16 * 16 * 16 * 2


def test_noise3d_tiles_without_seams():
    import numpy as np

    from hud_pro.gpu import noise3d

    data = noise3d._generate(24)
    arr = np.frombuffer(data, dtype=np.uint8).reshape(24, 24, 24, 2).astype(int)
    edge_diff = np.abs(arr[0, :, :, :] - arr[-1, :, :, :]).mean()
    interior_diff = np.abs(arr[12, :, :, :] - arr[11, :, :, :]).mean()
    # el borde (que envuelve) no debe ser drásticamente más brusco que
    # cualquier transición interior — si hubiera costura sería un salto
    # mucho mayor, no un valor del mismo orden.
    assert edge_diff < interior_diff * 3 + 5


# ── FASE B: comportamiento real de HoloStage (necesita sesión gráfica) ──
@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_scan_wave_triggers_on_state_change_and_energy_onset():
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HoloStage()
        w.resize(300, 200)
        w.show()
        for _ in range(10):
            app.processEvents()
        assert w._scan_start <= -900.0, "no debe haber onda activa al arrancar"

        w.set_state(OrbState.LISTENING)
        assert w._scan_start == w._time, "cambiar de estado debe disparar la onda"

        w._scan_start = -900.0
        w.set_energy(0.0)
        w.set_energy(0.9)  # pico real de energía mientras escucha
        assert w._scan_start == w._time, "un pico real de energía en ESCUCHANDO debe disparar la onda"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_hud_window_background_is_not_corrupted_after_many_frames():
    """Regresión directa: `glBlendFunc(sfactor, GL_ONE)` (aditivo real)
    en el pase de polvo reventaba TODO el resto del pipeline en esta GPU
    (Intel HD 520 / Mesa) — no con un error visible, sino con valores no
    representables (Inf/NaN) que colapsan bloom/rayos de dios/streak a
    negro o blanco sólido tras unas ~30 vueltas del pipeline. El fix
    usa alpha estándar (`GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA`) — ver el
    comentario en `HoloStage._render_dust`. Corre muchos frames (más de
    los que hacía falta para reproducirlo) y confirma que el centro de la
    pantalla NO quedó en negro puro."""
    result = _run_subprocess_script(
        """
        import sys, time
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.window import HudWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HudWindow()
        w.resize(960, 540)
        w.show()
        for _ in range(60):
            app.processEvents()
            time.sleep(0.01)
        assert w.gpu_active, "el fondo GPU debía seguir activo"
        img = w.gpu_stage.grabFramebuffer()
        c = img.pixelColor(img.width() // 2, img.height() // 2)
        assert (c.red(), c.green(), c.blue()) != (0, 0, 0), (
            f"fondo colapsado a negro puro tras muchos frames: {c.red()},{c.green()},{c.blue()}"
        )
        w.close()
        del w
        app.processEvents()
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


# ── FASE C: setters del orbe raymarched ─────────────────────────────────
@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_orb_setters_clamp_and_toggle():
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HoloStage()
        w.resize(300, 200)
        w.show()
        for _ in range(10):
            app.processEvents()

        w.set_light_radius(-5.0)
        assert w._light_radius > 0.0, "el radio nunca debe quedar en 0 o negativo"

        w.set_hover(True)
        assert w._hover is True
        w.set_hover(False)
        assert w._hover is False

        w.set_spectrum([0.5, 1.5, -1.0])  # fuera de rango: debe recortarse a 0..1
        assert w._spectrum == [0.5, 1.0, 0.0]
        w.set_spectrum(None)
        assert w._spectrum is None
        w.set_spectrum([])
        assert w._spectrum is None
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_orb_survives_resize_after_quality_change():
    """Regresión directa: `_rebuild_fbos` (disparado por un resize o por
    un cambio de calidad de AUTO) borraba el FBO propio del orbe del
    dict sin avisarle a `_ensure_orb_fbo`, que veía el tamaño "sin
    cambios" y no lo recreaba — `KeyError: 'orb'` en el frame siguiente.
    Fuerza varios resizes + cambios de calidad y sigue pintando."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.gpu.quality import Quality
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HoloStage()
        w.resize(400, 300)
        w.show()
        for _ in range(10):
            app.processEvents()
        assert w.ok, w.init_error

        for size, q in [
            (500, Quality.LOW), (300, Quality.ULTRA),
            (600, Quality.MEDIUM), (350, Quality.HIGH),
        ]:
            w.resize(size, 300)
            w.set_quality(q)
            for _ in range(5):
                app.processEvents()
        assert w.ok, "no debía haber caído tras los cambios"
        w.close()
        del w
        app.processEvents()
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_hud_window_hides_raster_orb_and_forwards_hover_and_spectrum():
    result = _run_subprocess_script(
        """
        import sys, time
        from hud_pro.qt_compat import QtCore, QtWidgets
        from hud_pro.window import HudWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HudWindow()
        w.resize(1000, 640)
        w.show()
        for _ in range(30):
            app.processEvents()
            time.sleep(0.01)
        assert w.gpu_active
        assert w.orb._render_visible is False, "el orbe raster debe quedar invisible con GPU activo"

        enter = QtCore.QEvent(QtCore.QEvent.Type.Enter)
        app.sendEvent(w.orb, enter)
        assert w.gpu_stage._hover is True, "el hover debe reenviarse al orbe GPU"

        w.set_spectrum([0.2, 0.4, 0.9])
        assert w.gpu_stage._spectrum == [0.2, 0.4, 0.9]
        w.set_spectrum(None)
        assert w.gpu_stage._spectrum is None

        assert w.gpu_stage._light_radius > 0.0
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_orb_renders_filled_not_hollow():
    """Regresión del modelo de densidad: la primera versión sólo acumulaba
    densidad muy cerca de la superficie de la esfera (`shell`), lo que
    dejaba el CENTRO casi transparente y sólo el borde visible (un aro
    hueco, no una bola sólida). El fix acumula densidad en TODO el
    interior del recorrido del rayo. Verifica que el centro del FBO del
    orbe queda más opaco que un punto cercano al borde."""
    result = _run_subprocess_script(
        """
        import sys, time
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.window import HudWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HudWindow()
        w.resize(1000, 640)
        w.show()
        for _ in range(30):
            app.processEvents()
            time.sleep(0.01)
        img = w.gpu_stage._fbos["orb"].toImage()
        cw, ch = img.width(), img.height()
        center_alpha = img.pixelColor(cw // 2, ch // 2).alpha()
        edge_alpha = img.pixelColor(int(cw * 0.1), ch // 2).alpha()
        assert center_alpha > edge_alpha, (
            f"el centro del orbe debe verse más opaco que el borde: centro={center_alpha} borde={edge_alpha}"
        )
        assert center_alpha > 40, f"el centro no debe quedar casi transparente: {center_alpha}"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout
