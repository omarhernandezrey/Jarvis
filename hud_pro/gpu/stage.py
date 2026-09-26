"""``HoloStage`` — el fondo GPU del HUD (FASE A: motor + pipeline genérico;
el contenido cinematográfico real llega en las FASES B/C).

Ocupa todo el fondo de la ventana; los widgets normales (barra superior,
chips, consola) van ENCIMA como capas translúcidas — ver `window.py`.

Pipeline por frame: escena → extracción de brillos → bloom dual-Kawase (N
niveles, según calidad) → destello anamórfico horizontal → composición
(aberración cromática + tone mapping ACES + grano + viñeta) → pantalla.
"""

from __future__ import annotations

import logging
import os
import time

from ..qt_compat import QtCore, QtGui, QtOpenGL, QtOpenGLWidgets, Signal
from ..state import OrbState
from ..theme import STATE_STYLES
from .quality import QUALITY_PRESETS, AutoQualityController, Quality, QualitySettings, parse_quality
from .shader_loader import ShaderCompileError, ShaderProgram

log = logging.getLogger("jarvis.hud_pro.gpu")

_GL_COLOR_BUFFER_BIT = 0x4000
_GL_TEXTURE_2D = 0x0DE1
_GL_TEXTURE0 = 0x84C0


class HoloStageError(RuntimeError):
    """Fallo de arranque del motor GPU (contexto o shaders) — quien
    construye `HoloStage` debe capturar esto y usar el fondo raster."""


class HoloStage(QtOpenGLWidgets.QOpenGLWidget if QtOpenGLWidgets else object):
    frameRendered = Signal(float)  # ms de CPU del último frame (paintGL)
    initError = Signal(str)        # falló DESPUÉS de mostrarse (poco común); ver también HoloStageError

    def __init__(self, parent=None) -> None:
        if QtOpenGLWidgets is None:
            raise HoloStageError("binding Qt sin módulo QtOpenGLWidgets")
        super().__init__(parent)
        fmt = QtGui.QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSwapInterval(1)
        self.setFormat(fmt)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._reduced_motion = os.environ.get("JARVIS_REDUCED_MOTION", "") == "1"
        fixed_q = parse_quality(os.environ.get("JARVIS_HUD_QUALITY", ""))
        self._auto = None if fixed_q else AutoQualityController(QUALITY_PRESETS[Quality.HIGH])
        self._settings: QualitySettings = (
            QUALITY_PRESETS[fixed_q] if fixed_q else self._auto.current
        )
        self._quality_fixed = fixed_q

        self._time = 0.0
        self._energy = 0.0
        self._state = OrbState.IDLE
        self._paused = False
        self._init_ok = False
        self._init_error = ""

        self._programs: dict[str, ShaderProgram] = {}
        self._fbos: dict[str, QtOpenGL.QOpenGLFramebufferObject] = {}
        self._vao = None
        self._gl = None
        self._timer_query = None  # QOpenGLTimerQuery, si la extensión existe

        self._clock = QtCore.QElapsedTimer()
        self._frame_timer = QtCore.QTimer(self)
        self._frame_timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self._frame_timer.timeout.connect(self.update)
        self._last_cpu_ms = 0.0
        self._last_gpu_ms: float | None = None
        self._pending_gpu_query = None  # QOpenGLTimerQuery del frame anterior

    # ── API pública ───────────────────────────────────────────────────────
    @property
    def ok(self) -> bool:
        return self._init_ok

    @property
    def init_error(self) -> str:
        return self._init_error

    @property
    def quality(self) -> QualitySettings:
        return self._settings

    def set_quality(self, quality: Quality | None) -> None:
        """`None` = AUTO."""
        self._quality_fixed = quality
        if quality is None:
            self._auto = self._auto or AutoQualityController(QUALITY_PRESETS[Quality.HIGH])
        else:
            self._settings = QUALITY_PRESETS[quality]

    def set_state(self, state: OrbState) -> None:
        self._state = state

    def set_energy(self, energy: float) -> None:
        self._energy = max(0.0, min(1.0, float(energy)))

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self._sync_timer()

    def last_frame_ms(self) -> tuple[float, float | None]:
        """(cpu_ms, gpu_ms|None) del último frame ya renderizado."""
        return self._last_cpu_ms, self._last_gpu_ms

    # ── Ciclo GL ──────────────────────────────────────────────────────────
    def initializeGL(self) -> None:  # noqa: N802
        try:
            self._gl = self.context().functions()
            self._gl.initializeOpenGLFunctions()
            self._vao = QtOpenGL.QOpenGLVertexArrayObject(self)
            if not self._vao.create():
                raise HoloStageError("QOpenGLVertexArrayObject.create() falló")
            self._compile_programs()
            if self.context().hasExtension(b"GL_ARB_timer_query"):
                self._timer_query = QtOpenGL.QOpenGLTimerQuery(self)
                self._timer_query.create()
            # `QOpenGLTimerQuery` (y cualquier otro recurso GL con
            # wrapper Qt) tiene que destruirse MIENTRAS el contexto sigue
            # vivo: si Python lo recolecta después (p. ej. al cerrar la
            # app), su destructor toca un contexto ya muerto y revienta
            # el proceso — SIGSEGV real, confirmado con faulthandler en
            # esta máquina, no una hipótesis. `aboutToBeDestroyed` es la
            # única señal que dispara ANTES de que eso pase.
            #
            # OJO: conectar directamente el MÉTODO LIGADO
            # (`self._cleanup_gl`, sin envolver) NO sirve — PySide trata
            # ese `self` como "receptor" y auto-desconecta la señal en
            # cuanto el propio widget empieza a destruirse, así que el
            # slot nunca llega a ejecutarse (verificado empíricamente:
            # con el método ligado el print de dentro del slot no
            # aparece nunca y el segfault persiste). Envuelto en una
            # lambda, la conexión no se asocia a `self` como receptor y
            # SÍ dispara a tiempo.
            self.context().aboutToBeDestroyed.connect(lambda: self._cleanup_gl())
            self._clock.start()
            self._init_ok = True
        except ShaderCompileError as exc:
            self._init_ok = False
            self._init_error = str(exc)
            log.error("HoloStage: fallo al compilar shaders, se usará el orbe raster: %s", exc)
        except Exception as exc:  # pragma: no cover - defensivo, cualquier fallo de init es fatal para el motor GPU
            self._init_ok = False
            self._init_error = str(exc)
            log.error("HoloStage: fallo de inicialización GL, se usará el orbe raster: %s", exc)

    def _cleanup_gl(self) -> None:
        """Conectado a `context().aboutToBeDestroyed` — dispara MIENTRAS el
        contexto sigue vivo (contrato de esa señal), el único momento
        seguro para tirar wrappers Qt de recursos GL. `_timer_query` y
        `_vao` son QObject hijos de `self`: si se deja que Qt los destruya
        solo, al cerrar la ventana, su destructor C++ corre después de
        muerto el contexto y revienta el proceso (confirmado con
        faulthandler: SIGSEGV en `QOpenGLTimerQuery::~QOpenGLTimerQuery`
        → `QOpenGLContext::surface()`). Los FBOs no son QObject — vaciar
        el dict aquí basta para que su destructor corra ahora, no después.
        """
        if self._timer_query is not None:
            self._timer_query.destroy()
            self._timer_query = None
        if self._vao is not None:
            self._vao.destroy()
            self._vao = None
        self._fbos.clear()

    def _compile_programs(self) -> None:
        specs = {
            "scene": "scene.frag",
            "extract": "bloom_extract.frag",
            "kawase_down": "kawase_down.frag",
            "kawase_up": "kawase_up.frag",
            "streak": "streak.frag",
            "composite": "composite.frag",
        }
        for key, frag in specs.items():
            self._programs[key] = ShaderProgram("fullscreen.vert", frag)

    def resizeGL(self, w: int, h: int) -> None:  # noqa: N802
        if not self._init_ok:
            return
        self._rebuild_fbos(max(1, w), max(1, h))

    def _rebuild_fbos(self, w: int, h: int) -> None:
        for fbo in self._fbos.values():
            fbo.release() if hasattr(fbo, "release") else None
        self._fbos.clear()

        fmt = QtOpenGL.QOpenGLFramebufferObjectFormat()
        fmt.setInternalTextureFormat(0x881A)  # GL_RGBA16F: rango HDR para el bloom/tonemap
        self._fbos["scene"] = QtOpenGL.QOpenGLFramebufferObject(w, h, fmt)

        bw = max(4, round(w * self._settings.bloom_scale))
        bh = max(4, round(h * self._settings.bloom_scale))
        self._bloom_base_size = (bw, bh)
        levels = max(1, self._settings.kawase_levels)
        self._kawase_sizes = [(max(2, bw >> i), max(2, bh >> i)) for i in range(levels)]
        for i, (lw, lh) in enumerate(self._kawase_sizes):
            self._fbos[f"kawase{i}"] = QtOpenGL.QOpenGLFramebufferObject(lw, lh, fmt)
        self._fbos["streak"] = QtOpenGL.QOpenGLFramebufferObject(bw, bh, fmt)

    def paintGL(self) -> None:  # noqa: N802
        if not self._init_ok:
            return
        if self._pending_gpu_query is not None:
            # resultado del frame ANTERIOR (una vuelta de por medio: pedirlo
            # en el mismo frame en que se cerró bloquearía la GPU). Si para
            # esta vuelta el driver todavía no lo tiene listo, se deja
            # `_last_gpu_ms` con el valor previo — nunca se inventa uno ni
            # se bloquea esperándolo.
            if self._pending_gpu_query.isResultAvailable():
                self._last_gpu_ms = self._pending_gpu_query.waitForResult() / 1e6
            self._pending_gpu_query = None
        t0 = time.perf_counter()
        dt = self._clock.restart() / 1000.0
        if not self._reduced_motion:
            self._time += dt

        gl_started = False
        if self._timer_query is not None:
            self._timer_query.begin()
            gl_started = True

        self._vao.bind()
        self._render_scene()
        self._render_bloom_chain()
        if self._settings.streak_enabled:
            self._render_streak()
        self._render_composite()
        self._vao.release()

        if gl_started:
            self._timer_query.end()
            # el resultado de ESTE frame no está listo hasta el próximo: se
            # recoge en el frame siguiente (waitForResult bloquearía la GPU).
            self._pending_gpu_query = self._timer_query

        self._last_cpu_ms = (time.perf_counter() - t0) * 1000.0
        if self._auto is not None and self._quality_fixed is None:
            new_settings = self._auto.update(self._last_cpu_ms)
            if new_settings != self._settings:
                self._settings = new_settings
                self._rebuild_fbos(self.width(), self.height())
        self.frameRendered.emit(self._last_cpu_ms)

    # ── Pasadas ───────────────────────────────────────────────────────────
    def _draw_fullscreen(self) -> None:
        self._gl.glDrawArrays(0x0004, 0, 3)  # GL_TRIANGLES

    def _bind_texture(self, program: ShaderProgram, uniform: str, unit: int, tex_id: int) -> None:
        self._gl.glActiveTexture(_GL_TEXTURE0 + unit)
        self._gl.glBindTexture(_GL_TEXTURE_2D, tex_id)
        program.set_uniform(uniform, unit)

    def _render_scene(self) -> None:
        fbo = self._fbos["scene"]
        fbo.bind()
        self._gl.glViewport(0, 0, fbo.width(), fbo.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p = self._programs["scene"]
        p.maybe_reload()
        p.bind()
        style = STATE_STYLES[self._state]
        tint = tuple(c / 255.0 for c in style.primary) if self._state != OrbState.ERROR else (1.0, 0.25, 0.32)
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_energy", self._energy)
        p.set_uniform("u_resolution", float(fbo.width()), float(fbo.height()))
        p.set_uniform("u_tint", *tint)
        self._draw_fullscreen()
        p.release()
        fbo.release()

    def _render_bloom_chain(self) -> None:
        extract = self._programs["extract"]
        extract.maybe_reload()
        extract.bind()
        target = self._fbos["kawase0"]
        target.bind()
        self._gl.glViewport(0, 0, target.width(), target.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        self._bind_texture(extract, "u_source", 0, self._fbos["scene"].texture())
        extract.set_uniform("u_threshold", 0.72)
        extract.set_uniform("u_knee", 0.45)
        self._draw_fullscreen()
        target.release()
        extract.release()

        down = self._programs["kawase_down"]
        down.maybe_reload()
        n = len(self._kawase_sizes)
        for i in range(1, n):
            src, dst = self._fbos[f"kawase{i - 1}"], self._fbos[f"kawase{i}"]
            dst.bind()
            self._gl.glViewport(0, 0, dst.width(), dst.height())
            down.bind()
            self._bind_texture(down, "u_source", 0, src.texture())
            down.set_uniform("u_halfpixel", 0.5 / src.width(), 0.5 / src.height())
            self._draw_fullscreen()
            down.release()
            dst.release()

        up = self._programs["kawase_up"]
        up.maybe_reload()
        for i in range(n - 1, 0, -1):
            src, dst = self._fbos[f"kawase{i}"], self._fbos[f"kawase{i - 1}"]
            dst.bind()
            self._gl.glViewport(0, 0, dst.width(), dst.height())
            up.bind()
            self._bind_texture(up, "u_source", 0, src.texture())
            up.set_uniform("u_halfpixel", 0.5 / src.width(), 0.5 / src.height())
            self._draw_fullscreen()
            up.release()
            dst.release()

    def _render_streak(self) -> None:
        p = self._programs["streak"]
        p.maybe_reload()
        target = self._fbos["streak"]
        target.bind()
        self._gl.glViewport(0, 0, target.width(), target.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p.bind()
        self._bind_texture(p, "u_source", 0, self._fbos["kawase0"].texture())
        p.set_uniform("u_texelX", 1.0 / target.width())
        p.set_uniform("u_stretch", 3.0)
        self._draw_fullscreen()
        p.release()
        target.release()

    def _render_composite(self) -> None:
        self._gl.glBindFramebuffer(0x8D40, self.defaultFramebufferObject())  # GL_FRAMEBUFFER
        self._gl.glViewport(0, 0, self.width(), self.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p = self._programs["composite"]
        p.maybe_reload()
        p.bind()
        self._bind_texture(p, "u_scene", 0, self._fbos["scene"].texture())
        self._bind_texture(p, "u_bloom", 1, self._fbos["kawase0"].texture())
        streak_tex = self._fbos["streak"].texture() if self._settings.streak_enabled else self._fbos["kawase0"].texture()
        self._bind_texture(p, "u_streak", 2, streak_tex)
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_bloomStrength", 0.9)
        p.set_uniform("u_streakStrength", 0.5 if self._settings.streak_enabled else 0.0)
        p.set_uniform("u_aberration", 0.0 if self._reduced_motion else self._settings.aberration)
        p.set_uniform("u_grain", 0.0 if self._reduced_motion else self._settings.grain)
        p.set_uniform("u_vignette", self._settings.vignette)
        p.set_uniform("u_texel", 1.0 / max(1, self.width()), 1.0 / max(1, self.height()))
        self._draw_fullscreen()
        p.release()

    # ── Ciclo Qt ──────────────────────────────────────────────────────────
    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._sync_timer()

    def _current_fps(self) -> int:
        if self._state is OrbState.IDLE:
            return 30
        return 60

    def _sync_timer(self) -> None:
        should_run = self.isVisible() and not self._paused
        if should_run and not self._frame_timer.isActive():
            self._frame_timer.start(max(1, round(1000 / self._current_fps())))
        elif not should_run and self._frame_timer.isActive():
            self._frame_timer.stop()
