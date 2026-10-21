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
from pathlib import Path

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
        "static_bg.frag",
        "dynamic_bg.frag",
        "bloom_extract.frag",
        "godray.frag",
        "kawase_down.frag",
        "kawase_up.frag",
        "streak.frag",
        "composite.frag",
        "orb.frag",
        "blit.frag",
        "bg_composite.frag",
        "glass_blur.frag",
        "glass_apply.frag",
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


def test_auto_quality_does_not_oscillate_inside_the_hysteresis_gap():
    """Tiempos de frame REALISTAS (con ruido) que se quedan entre
    RECOVER_MS (10) y TARGET_MS (14) — la "zona muerta" entre bajar y
    subir — NUNCA deben mover la escala, ni una vez. Simula 40 ventanas
    (800 frames) con ruido ±1ms alrededor de 12ms."""
    import random

    rng = random.Random(20260926)
    ctl = AutoQualityController()
    scales_seen = set()
    for _ in range(ctl.WINDOW * 40):
        frame_ms = 12.0 + rng.uniform(-1.0, 1.0)  # 11..13, dentro de la zona muerta
        ctl.update(frame_ms)
        scales_seen.add(round(ctl.scale, 6))
    assert scales_seen == {1.0}, (
        f"la escala se movió dentro de la zona muerta (10-14ms): {scales_seen}"
    )


def test_auto_quality_settles_without_oscillating_near_the_target_edge():
    """Tiempos de frame que rondan justo TARGET_MS (14ms, con ruido ±0.5ms)
    — un caso más agresivo que la zona muerta completa. Con histéresis de
    verdad, la escala baja unos pocos escalones y se ESTABILIZA (no
    rebota siempre entre dos valores) — nunca vuelve a subir, porque
    12.5-14.5ms nunca baja de RECOVER_MS(10)."""
    import random

    rng = random.Random(20260926)
    ctl = AutoQualityController()
    history = []
    for _ in range(ctl.WINDOW * 60):
        frame_ms = 14.0 + rng.uniform(-0.5, 0.5)
        ctl.update(frame_ms)
        history.append(ctl.scale)
    # una vez estable, los últimos N valores deben ser IDÉNTICOS —
    # nunca sube (nunca cruza RECOVER_MS) y deja de bajar al tocar
    # MIN_SCALE o al promediar justo por debajo de TARGET_MS.
    tail = history[-10:]
    assert len(set(round(v, 6) for v in tail)) == 1, f"no se estabilizó, sigue moviéndose: {tail[-5:]}"
    # y en ningún punto de toda la corrida subió (sería oscilación real).
    assert all(b <= a + 1e-9 for a, b in zip(history[:-1], history[1:], strict=True)), (
        "la escala subió — eso sería oscilación"
    )


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
def test_hud_window_gpu_energy_timer_only_runs_while_listening_or_speaking():
    """CPU EN REPOSO: perfilado con py-spy (JARVIS en LISTO, render
    pausado) mostró este timer de 33ms/30Hz disparando SIEMPRE, sin
    importar el estado — coste real por cero beneficio visual fuera de
    ESCUCHANDO/HABLANDO, los únicos estados donde la energía de audio es
    real (no la síntesis de reposo del orbe)."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.window import HudWindow
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        w = HudWindow()
        w.show()
        for _ in range(15):
            app.processEvents()

        w.set_state(OrbState.IDLE)
        assert not w._gpu_energy_timer.isActive(), "IDLE no debe correr el timer de energía"

        w.set_state(OrbState.LISTENING)
        assert w._gpu_energy_timer.isActive(), "LISTENING sí debe correr el timer de energía"

        w.set_state(OrbState.THINKING)
        assert not w._gpu_energy_timer.isActive(), "THINKING no debe correr el timer de energía"

        w.set_state(OrbState.SPEAKING)
        assert w._gpu_energy_timer.isActive(), "SPEAKING sí debe correr el timer de energía"

        w.set_state(OrbState.IDLE)
        assert not w._gpu_energy_timer.isActive(), "debe pararse de nuevo al volver a IDLE"
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


def test_fbo_filter_helper_uses_bilinear_and_clamp_to_edge():
    """Las texturas de FBO nacen con GL_NEAREST en esta build de Qt; los
    pases reducidos (bloom/rayos/escena) asumen GL_LINEAR. Sin este filtro
    aparecían cuadros rectos sobre el orbe en PENSANDO (bug real)."""
    from hud_pro.gpu import stage as stage_mod

    calls: list[tuple] = []

    class _GL:
        def glActiveTexture(self, unit):
            calls.append(("active", unit))

        def glBindTexture(self, target, tex):
            calls.append(("bind", target, tex))

        def glTexParameteri(self, target, pname, value):
            calls.append(("param", target, pname, value))

    class _FBO:
        def texture(self):
            return 77

    class _Stage:
        _gl = _GL()

    stage_mod.HoloStage._set_fbo_linear(_Stage(), _FBO())

    params = {(call[2], call[3]) for call in calls if call[0] == "param"}
    assert params == {
        (stage_mod._GL_TEXTURE_MIN_FILTER, stage_mod._GL_LINEAR),
        (stage_mod._GL_TEXTURE_MAG_FILTER, stage_mod._GL_LINEAR),
        (stage_mod._GL_TEXTURE_WRAP_S, stage_mod._GL_CLAMP_TO_EDGE),
        (stage_mod._GL_TEXTURE_WRAP_T, stage_mod._GL_CLAMP_TO_EDGE),
    }
    assert ("bind", stage_mod._GL_TEXTURE_2D, 77) in calls
    assert ("bind", stage_mod._GL_TEXTURE_2D, 0) in calls


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
def test_holostage_thinking_applies_governor_preset_regardless_of_prior_quality():
    """GOBERNADOR DE RENDER: diagnóstico con Ollama real + pidstat mostró
    que el cuello es CPU de núcleos compartidos, no la calidad de
    sombreado — dos intentos previos (bajar a MEDIUM, luego a LOW, sin
    tocar el fps) midieron 33-42% de pérdida, sin mejora real. Ahora
    entrar a THINKING SIEMPRE aplica `_THINKING_SETTINGS` (kawase_levels=
    1, el mandato explícito) más 24fps y fondo congelado, venga de donde
    venga (AUTO, HIGH fijo...), y restaura exactamente al salir."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.gpu.quality import Quality, QUALITY_PRESETS
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w._quality_fixed = Quality.HIGH
        w._settings = QUALITY_PRESETS[Quality.HIGH]
        w.set_state(OrbState.LISTENING)

        w.set_state(OrbState.THINKING)
        assert w._settings == HoloStage._THINKING_SETTINGS
        assert w._settings.kawase_levels == 1, "el mandato pide exactamente 1 iteración de bloom"
        assert w._current_fps() == 24
        assert w._bg_frozen is True
        assert w._render_scale == HoloStage._THINKING_RENDER_SCALE

        w.set_state(OrbState.LISTENING)
        assert w._settings == QUALITY_PRESETS[Quality.HIGH], "no restauró HIGH al salir de THINKING"
        assert w._current_fps() == 60
        assert w._bg_frozen is False
        assert w._render_scale == 1.0
        assert w._settings_before_llm is None

        # AUTO (quality_fixed=None): mismo preset, mismo motivo.
        w2 = HoloStage()
        w2._quality_fixed = None
        w2.set_state(OrbState.LISTENING)
        w2.set_state(OrbState.THINKING)
        assert w2._settings == HoloStage._THINKING_SETTINGS
        assert w2._llm_override_active is True
        w2.set_state(OrbState.LISTENING)
        assert w2._llm_override_active is False
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_llm_downgrade_actually_shrinks_scene_and_bloom_fbos():
    """Regresión directa: el primer intento del downgrade sólo cambiaba
    campos leídos por frame SIN redimensionar ningún FBO — medido con
    Ollama real que eso NO ayudaba (medía incluso peor). Ahora
    `_apply_settings_change_safely` llama a `_rebuild_fbos` de verdad
    (con `makeCurrent`/`doneCurrent`): este test verifica que el tamaño
    REAL de "scene" (escala interna 0.66) y de la FBO de bloom
    (`kawase0`) cambian al entrar/salir de THINKING, no sólo el
    `QualitySettings` en papel."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.gpu.quality import Quality, QUALITY_PRESETS
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w.resize(800, 600)
        w._quality_fixed = Quality.HIGH
        w.show()
        for _ in range(15):
            app.processEvents()
        assert w._init_ok, "necesita GL real inicializado"
        w._settings = QUALITY_PRESETS[Quality.HIGH]
        w._rebuild_fbos(*w._device_size())
        high_scene_w = w._fbos["scene"].width()
        high_kawase_w = w._fbos["kawase0"].width()

        w.set_state(OrbState.THINKING)
        for _ in range(3):
            app.processEvents()
        dw, _dh = w._device_size()
        thinking_scene_w = w._fbos["scene"].width()
        thinking_kawase_w = w._fbos["kawase0"].width()
        assert thinking_scene_w == round(dw * HoloStage._THINKING_RENDER_SCALE), (
            f"'scene' no aplicó la escala interna 0.66: {thinking_scene_w} vs dw={dw}"
        )
        assert thinking_kawase_w < high_kawase_w, (
            f"kawase0 no se achicó de verdad: {high_kawase_w} -> {thinking_kawase_w}"
        )

        w.set_state(OrbState.IDLE)
        for _ in range(3):
            app.processEvents()
        assert w._fbos["scene"].width() == high_scene_w, "no volvió a la escala 1.0 al salir de THINKING"
        assert w._fbos["kawase0"].width() == high_kawase_w, "no volvió al tamaño de bloom de HIGH"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_frozen_background_does_not_recompute_dynamic_bg():
    """GOBERNADOR DE RENDER — fondo CONGELADO durante THINKING: el shader
    dinámico (niebla/reflejo/radar) no debe recalcularse frame a frame;
    `_composite_background` sigue componiendo sin crashear (KeyError) ni
    dejar la textura de "dynamic_bg" en basura de GPU sin inicializar."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w.resize(400, 300)
        w.show()
        for _ in range(15):
            app.processEvents()
        assert w._init_ok

        calls = []
        orig = HoloStage._render_dynamic_bg
        def traced(self, *a, **k):
            calls.append(1)
            return orig(self, *a, **k)
        HoloStage._render_dynamic_bg = traced

        import time
        w.set_state(OrbState.THINKING)
        calls.clear()
        for _ in range(10):
            app.processEvents()
            time.sleep(0.05)  # 24fps == ~42ms/frame — deja que el timer dispare de verdad
        assert calls == [], f"_render_dynamic_bg corrió {len(calls)} veces con el fondo congelado"
        assert "dynamic_bg" in w._fbos, "la FBO debe existir igual (creada por _ensure_dynamic_bg_fbo)"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_fps_table_by_state_and_focus():
    """GOBERNADOR DE RENDER: tabla de fps por estado (THINKING=24,
    LISTENING=60, SPEAKING=45, IDLE=30) y el piso de foco (ventana sin
    foco: 15fps, pisa lo que sea que diga el estado)."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        table = {
            OrbState.THINKING: 24,
            OrbState.LISTENING: 60,
            OrbState.SPEAKING: 45,
            OrbState.IDLE: 30,
        }
        for state, fps in table.items():
            w.set_state(state)
            assert w._current_fps() == fps, f"{state}: esperaba {fps}fps, salió {w._current_fps()}"

        w.set_state(OrbState.LISTENING)
        assert w._current_fps() == 60
        w.set_focused(False)
        assert w._current_fps() == 15, "sin foco debe pisar el fps del estado, aunque sea LISTENING"
        w.set_focused(True)
        assert w._current_fps() == 60, "al recuperar el foco vuelve al fps real del estado"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_frame_timer_interval_updates_on_fps_change():
    """Regresión directa: `_sync_timer` sólo ARRANCABA o PARABA el timer,
    nunca le cambiaba el intervalo a uno YA activo — un cambio de estado
    que sólo debía cambiar el fps (p.ej. IDLE 30fps -> THINKING 24fps)
    nunca se aplicaba porque `isActive()` ya era `True` de antes."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        from hud_pro.state import OrbState
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w.resize(400, 300)
        w.show()
        for _ in range(10):
            app.processEvents()
        assert w._init_ok

        w.set_state(OrbState.IDLE)
        assert w._frame_timer.interval() == round(1000 / 30)

        w.set_state(OrbState.LISTENING)
        assert w._frame_timer.interval() == round(1000 / 60), "no actualizó el intervalo a 60fps"

        w.set_state(OrbState.THINKING)
        assert w._frame_timer.interval() == round(1000 / 24), "no actualizó el intervalo a 24fps"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_glass_rect_setter_clamps_invalid_size():
    """FASE D — `set_glass_rect` con ancho/alto <= 0 (panel oculto o
    animando su colapso) apaga el efecto (`None`) en vez de dejar un
    rect a medio fijar que `_render_glass` intentaría usar."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w.set_glass_rect(0.2, 0.6, 0.5, 0.3)
        assert w._glass_rect == (0.2, 0.6, 0.5, 0.3)

        w.set_glass_rect(0.2, 0.6, 0.0, 0.3)
        assert w._glass_rect is None, "ancho 0 debe apagar el efecto"

        w.set_glass_rect(0.2, 0.6, 0.5, -1.0)
        assert w._glass_rect is None, "alto negativo debe apagar el efecto"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_glass_pixel_rect_converts_qt_uv_to_gl_bottom_up():
    """FASE D — `_glass_rect` llega en UV de Qt (origen arriba-izquierda,
    igual que `set_light_uv`); `_glass_pixel_rect` debe convertirlo a
    píxeles GL (origen abajo-izquierda) — mismo esquema ya probado para
    el orbe en `_scissor_rect_around_orb`."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        # panel de 50%x30% de la ventana, pegado a 20% del borde izq y
        # 60% desde ARRIBA (Qt) — en una ventana de 1000x1000 eso es
        # y_top=600..900 en Qt, o sea y=100..400 en GL (abajo-izquierda).
        w.set_glass_rect(0.20, 0.60, 0.50, 0.30)
        x0, y0, pw, ph = w._glass_pixel_rect(1000, 1000)
        assert (x0, pw) == (200, 500)
        assert (y0, ph) == (100, 300), f"y0/ph esperados (100,300), salió ({y0},{ph})"
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_render_glass_uses_scene_size_not_raw_device_size():
    """Regresión directa: con `_render_scale` < 1.0 (GOBERNADOR DE
    RENDER, THINKING) "scene" es más chica que `_device_size()`.
    `_render_glass` calculaba el rect del panel con el tamaño de
    dispositivo CRUDO y luego aplicaba `glViewport` sobre "scene" (más
    chica) — desincronizado, se veía como una franja horizontal rota en
    la captura. Debe usar el tamaño REAL de "scene", igual que ya hace
    `_scissor_rect_around_orb` para el orbe."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w.resize(800, 600)
        w.set_glass_rect(0.2, 0.6, 0.5, 0.3)
        w.show()
        for _ in range(15):
            app.processEvents()
        assert w._init_ok

        w._render_scale = 0.66
        w.makeCurrent()
        try:
            w._rebuild_fbos(*w._device_size())
            scene_w, scene_h = w._fbos["scene"].width(), w._fbos["scene"].height()
            dw, dh = w._device_size()
            assert scene_w < dw and scene_h < dh, "la prueba necesita que scene sea de verdad más chica"

            x0, y0, pw, ph = w._glass_pixel_rect(scene_w, scene_h)
            assert x0 + pw <= scene_w and y0 + ph <= scene_h, (
                f"el rect ({x0},{y0},{pw},{ph}) se sale de scene ({scene_w}x{scene_h})"
            )
            w._time = 100.0
            w._render_glass()  # no debe reventar ni quedar con un viewport fuera de rango
        finally:
            w.doneCurrent()
        print("OK")
        """,
        {},
    )
    assert result.returncode == 0, f"stderr={result.stderr!r} stdout={result.stdout!r}"
    assert "OK" in result.stdout


@pytest.mark.skipif(not HAS_REAL_DISPLAY, reason="necesita una sesión gráfica real (Wayland/X11)")
def test_holostage_glass_blur_recomputes_only_at_20hz():
    """FASE D — el desenfoque caro sólo se recalcula cada 1/20s; entre
    medio, `_render_glass` debe seguir componiendo la última versión sin
    recalcular (ni crashear) — verificado avanzando `_time` a mano en vez
    de esperar tiempo real de pared."""
    result = _run_subprocess_script(
        """
        import sys
        from hud_pro.qt_compat import QtWidgets
        from hud_pro.gpu.stage import HoloStage
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        w = HoloStage()
        w.resize(400, 300)
        w.set_glass_rect(0.2, 0.6, 0.5, 0.3)
        w.show()
        for _ in range(10):
            app.processEvents()
        assert w._init_ok, "necesita GL real inicializado para ejercitar _render_glass"

        w.makeCurrent()  # fuera de paintGL/resizeGL, el contexto no está corriente solo
        try:
            w._time = 10.0
            w._render_glass()
            first_update = w._glass_last_update
            assert first_update == 10.0

            w._time = 10.01  # bien dentro de la ventana de 1/20s == 0.05s
            w._render_glass()
            assert w._glass_last_update == first_update, "no debía recalcular tan pronto"

            w._time = 10.2  # ya pasó de sobra la ventana de 20Hz
            w._render_glass()
            assert w._glass_last_update == 10.2, "sí debía recalcular pasada la ventana"
        finally:
            w.doneCurrent()
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


# ── auditoría de uniforms: cada tipo/aridad, verificado de verdad ───────
#
# `glGetUniformfv`/`glGetUniformiv` (lo estándar para esto) NO escriben de
# vuelta en el parámetro de salida en esta build de PySide6 — se probó con
# una `list`, un `array.array` y un `VoidPtr` sobre un buffer `ctypes`;
# ninguno funciona (siempre False/valores sin tocar, incluso para tipos
# que SÍ se envían bien). Por eso la verificación real de este archivo
# pinta el valor como color y lo lee del framebuffer — más lento de
# escribir, pero es el único camino que de verdad demuestra que el valor
# llegó al shader en ESTE entorno.
FULLSCREEN_VERT_SRC = (Path(__file__).parent.parent / "hud_pro" / "gpu" / "shaders" / "fullscreen.vert").read_text()


def _render_uniform_probe(gl_context, tmp_path, monkeypatch, frag_uniform_decl, frag_body, setter):
    """Compila un shader mínimo, aplica `setter(program)` y devuelve el
    RGBA (0..1) del píxel central de un FBO de 16x16 — la única forma
    confiable de verificar un uniform en este entorno (ver arriba)."""
    from PySide6 import QtOpenGL as _QtOpenGL

    from hud_pro.gpu import shader_loader

    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    (tmp_path / "probe.vert").write_text(FULLSCREEN_VERT_SRC)
    (tmp_path / "probe.frag").write_text(
        f"#version 330 core\n{frag_uniform_decl}\nout vec4 c;\nvoid main(){{ {frag_body} }}\n"
    )
    program = ShaderProgram("probe.vert", "probe.frag")
    program.bind()
    setter(program)

    vao = _QtOpenGL.QOpenGLVertexArrayObject()
    vao.create()
    target = _QtOpenGL.QOpenGLFramebufferObject(16, 16, _QtOpenGL.QOpenGLFramebufferObjectFormat())
    target.bind()
    gl = gl_context.functions()
    gl.glViewport(0, 0, 16, 16)
    vao.bind()
    gl.glDrawArrays(0x0004, 0, 3)
    vao.release()
    target.release()

    # OJO: `toImage()` da `Format_ARGB32_Premultiplied` y `pixelColor()`
    # des-premultiplica (divide RGB por alfa) — con alfa < 1 en el color
    # de prueba eso INFLA los canales leídos y parece "el uniform no
    # llegó" sin ser cierto. Por eso las pruebas de este archivo siempre
    # fuerzan alfa=1.0 en el color de salida del shader de prueba (el
    # componente que sí hace falta comprobar con alfa real se empaqueta
    # aparte, en un canal con alfa=1 — ver `test_uniform_vec4_...`).
    c = target.toImage().pixelColor(8, 8)
    return (c.red() / 255.0, c.green() / 255.0, c.blue() / 255.0, c.alpha() / 255.0)


def test_uniform_float_scalar_reaches_shader(gl_context, tmp_path, monkeypatch):
    """Regresión directa del bug: escalar float suelto vía
    `setUniformValue` daba 0.0 siempre, sin excepción. `set_uniform` usa
    `glUniform1f` crudo — falla de inmediato si se revierte."""
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform float u_x;", "c = vec4(u_x, 0.0, 0.0, 1.0);",
        lambda p: p.set_uniform("u_x", 0.75),
    )
    assert rgba[0] == pytest.approx(0.75, abs=0.01), rgba


def test_uniform_int_scalar_reaches_shader(gl_context, tmp_path, monkeypatch):
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform int u_x;", "c = vec4(float(u_x) / 10.0, 0.0, 0.0, 1.0);",
        lambda p: p.set_uniform("u_x", 7),
    )
    assert rgba[0] == pytest.approx(0.7, abs=0.01), rgba


def test_uniform_bool_scalar_reaches_shader(gl_context, tmp_path, monkeypatch):
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform bool u_x;", "c = vec4(u_x ? 1.0 : 0.0, 0.0, 0.0, 1.0);",
        lambda p: p.set_uniform("u_x", True),
    )
    assert rgba[0] == pytest.approx(1.0, abs=0.01), rgba


def test_uniform_vec2_reaches_shader(gl_context, tmp_path, monkeypatch):
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform vec2 u_x;", "c = vec4(u_x, 0.0, 1.0);",
        lambda p: p.set_uniform("u_x", 0.3, 0.4),
    )
    assert rgba[0] == pytest.approx(0.3, abs=0.01)
    assert rgba[1] == pytest.approx(0.4, abs=0.01)


def test_uniform_vec3_reaches_shader(gl_context, tmp_path, monkeypatch):
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform vec3 u_x;", "c = vec4(u_x, 1.0);",
        lambda p: p.set_uniform("u_x", 0.1, 0.2, 0.3),
    )
    assert rgba[:3] == pytest.approx((0.1, 0.2, 0.3), abs=0.01)


def test_uniform_vec4_reaches_shader(gl_context, tmp_path, monkeypatch):
    """`c = u_x` directo (con la `w` real como alfa) haría que
    `pixelColor()` des-premultiplique R/G/B por esa alfa al leer —
    artefacto de `QImage`, no del uniform (confirmado: los valores
    leídos son exactamente los enviados divididos por la alfa enviada).
    Se empaqueta cada componente en un canal con alfa=1 para evitarlo."""
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform vec4 u_x;", "c = vec4(u_x.x, u_x.y, u_x.z, 1.0);",
        lambda p: p.set_uniform("u_x", 0.1, 0.2, 0.3, 0.4),
    )
    assert rgba[:3] == pytest.approx((0.1, 0.2, 0.3), abs=0.01)

    rgba_w = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform vec4 u_x;", "c = vec4(u_x.w, 0.0, 0.0, 1.0);",
        lambda p: p.set_uniform("u_x", 0.1, 0.2, 0.3, 0.4),
    )
    assert rgba_w[0] == pytest.approx(0.4, abs=0.01)


def test_uniform_float_array_reaches_shader(gl_context, tmp_path, monkeypatch):
    rgba = _render_uniform_probe(
        gl_context, tmp_path, monkeypatch,
        "uniform float u_arr[4];", "c = vec4(u_arr[2], 0.0, 0.0, 1.0);",
        lambda p: p.set_uniform_array("u_arr", [0.1, 0.2, 0.9, 0.4]),
    )
    assert rgba[0] == pytest.approx(0.9, abs=0.01)


def test_uniform_location_is_cached_not_requeried_every_call(gl_context, tmp_path, monkeypatch):
    """`_location()` debe llamar a `uniformLocation()` UNA sola vez por
    nombre — el resto de las veces usa el caché. Un programa nuevo
    (recompilado) invalida el caché entero."""
    from hud_pro.gpu import shader_loader

    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    (tmp_path / "probe.vert").write_text(FULLSCREEN_VERT_SRC)
    (tmp_path / "probe.frag").write_text(
        "#version 330 core\nuniform float u_x;\nout vec4 c;\nvoid main(){ c = vec4(u_x); }\n"
    )
    program = ShaderProgram("probe.vert", "probe.frag")
    program.bind()

    calls = []
    real_uniform_location = program.qt_program.uniformLocation

    def traced(name):
        calls.append(name)
        return real_uniform_location(name)

    program.qt_program.uniformLocation = traced
    for _ in range(5):
        program.set_uniform("u_x", 0.5)
    assert calls == ["u_x"], f"uniformLocation debía llamarse una sola vez, se llamó: {calls}"


def test_dev_mode_warns_once_on_missing_uniform_location(gl_context, tmp_path, monkeypatch, caplog):
    """`JARVIS_HUD_DEV=1`: la primera vez que un nombre resuelve a
    location -1 (typo, o uniform optimizado fuera por no usarse) se
    registra un aviso — una sola vez por nombre, no en cada frame."""
    from hud_pro.gpu import shader_loader

    monkeypatch.setenv("JARVIS_HUD_DEV", "1")
    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    (tmp_path / "probe.vert").write_text(FULLSCREEN_VERT_SRC)
    # el frag NO declara "u_no_existe" — location será -1 siempre.
    (tmp_path / "probe.frag").write_text(
        "#version 330 core\nout vec4 c;\nvoid main(){ c = vec4(1.0); }\n"
    )
    program = ShaderProgram("probe.vert", "probe.frag")
    assert program._dev is True
    program.bind()
    with caplog.at_level("WARNING", logger="jarvis.hud_pro.gpu"):
        for _ in range(3):
            program.set_uniform("u_no_existe", 1.0)
    warnings = [r for r in caplog.records if "u_no_existe" in r.message]
    assert len(warnings) == 1, f"debía avisar una sola vez, avisó {len(warnings)} veces"


def test_no_dev_mode_never_warns_on_missing_uniform_location(gl_context, tmp_path, monkeypatch, caplog):
    from hud_pro.gpu import shader_loader

    monkeypatch.delenv("JARVIS_HUD_DEV", raising=False)
    monkeypatch.setattr(shader_loader, "SHADERS_DIR", tmp_path)
    (tmp_path / "probe.vert").write_text(FULLSCREEN_VERT_SRC)
    (tmp_path / "probe.frag").write_text(
        "#version 330 core\nout vec4 c;\nvoid main(){ c = vec4(1.0); }\n"
    )
    program = ShaderProgram("probe.vert", "probe.frag")
    assert program._dev is False
    program.bind()
    with caplog.at_level("WARNING", logger="jarvis.hud_pro.gpu"):
        program.set_uniform("u_no_existe", 1.0)
    assert not any("u_no_existe" in r.message for r in caplog.records)
