"""``HoloStage`` — el fondo GPU del HUD (FASE A: motor + pipeline genérico;
FASE B: fondo cinematográfico real — niebla, rayos de dios, suelo
hexagonal, polvo bokeh; el orbe raymarched llega en FASE C).

Ocupa todo el fondo de la ventana; los widgets normales (barra superior,
chips, consola) van ENCIMA como capas translúcidas — ver `window.py`.

Pipeline por frame: escena (fondo + polvo) → extracción de brillos → rayos
de dios (radial blur a 1/4 res desde la posición real del orbe) en
paralelo con el bloom dual-Kawase (N niveles, según calidad) → destello
anamórfico horizontal → composición (aberración cromática + tone mapping
ACES + grano + viñeta) → pantalla.
"""

from __future__ import annotations

import logging
import os
import random
import struct
import time

from shiboken6 import VoidPtr

from ..qt_compat import QtCore, QtGui, QtOpenGL, QtOpenGLWidgets, Signal
from ..state import OrbState
from ..theme import STATE_STYLES
from . import noise3d
from .quality import QUALITY_PRESETS, AutoQualityController, Quality, QualitySettings, parse_quality
from .shader_loader import ShaderCompileError, ShaderProgram

log = logging.getLogger("jarvis.hud_pro.gpu")

_GL_COLOR_BUFFER_BIT = 0x4000
_GL_TEXTURE_2D = 0x0DE1
_GL_TEXTURE0 = 0x84C0
_GL_BLEND = 0x0BE1
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_PROGRAM_POINT_SIZE = 0x8642
_GL_POINTS = 0x0000
_GL_FLOAT = 0x1406
_GL_ARRAY_BUFFER = 0x8892

_DUST_COUNT = 300
_SCAN_STATE_GAP_S = 999.0  # "hace mucho" — apaga el término de la onda en el shader

# Energía real por encima de la cual, ESCUCHANDO, se considera "arranque de
# palabra" (subida real de nivel de audio, no un dato inventado) y dispara
# la onda de escaneo — igual que un disparo de estado.
_ENERGY_ONSET_DELTA = 0.22


def _generate_dust_particles(count: int = _DUST_COUNT) -> bytes:
    """`count` partículas × (x0, y0, capa 0..2, fase) — fijo por semilla:
    reproducible entre corridas, no se regenera cada vez que arranca la app."""
    rng = random.Random(20260925)
    rows = []
    for i in range(count):
        layer = float(i % 3)
        rows.extend((rng.random(), rng.random(), layer, rng.random()))
    return struct.pack(f"<{len(rows)}f", *rows)


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
        self._prev_energy = 0.0
        self._state = OrbState.IDLE
        self._paused = False
        self._init_ok = False
        self._init_error = ""
        self._light_uv = (0.5, 0.42)
        self._scan_start = -_SCAN_STATE_GAP_S

        self._programs: dict[str, ShaderProgram] = {}
        self._fbos: dict[str, QtOpenGL.QOpenGLFramebufferObject] = {}
        self._vao = None
        self._dust_vao = None
        self._dust_vbo = None
        self._noise_tex = None
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
        if state != self._state:
            self._trigger_scan()
        self._state = state

    def set_energy(self, energy: float) -> None:
        e = max(0.0, min(1.0, float(energy)))
        # arranque de palabra real (subida brusca de energía real mientras
        # escucha) — nunca un dato inventado, es la misma señal de audio
        # que ya mueve el orbe raster.
        if self._state is OrbState.LISTENING and (e - self._prev_energy) > _ENERGY_ONSET_DELTA:
            self._trigger_scan()
        self._prev_energy = self._energy
        self._energy = e

    def set_light_uv(self, u: float, v: float) -> None:
        """Posición real del orbe en pantalla (0..1) — de dónde salen los
        rayos de dios y el reflejo del piso. La alimenta `window.py` desde
        la geometría real de `OrbWidget`, nunca un valor fijo inventado."""
        self._light_uv = (float(u), float(v))

    def _trigger_scan(self) -> None:
        self._scan_start = self._time

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
            self._init_noise_texture()
            self._init_dust_buffers()
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
            #
            # OJO 2: dentro de `_cleanup_gl` NO se puede llamar a NINGÚN
            # método de `self` ni de `self.context()` — para cuando la
            # señal dispara, ambos ya pueden estar invalidados en el lado
            # shiboken (`RuntimeError: ... already deleted`), incluso
            # guardando la referencia al contexto de antemano. Probado:
            # intentar un `makeCurrent()` ahí para que
            # `QOpenGLTexture.destroy()` no avise por stderr CONVIERTE el
            # aviso cosmético en el mismo segfault original (la excepción
            # escapa del callback y aborta la limpieza a medias). El único
            # código seguro aquí son las llamadas DIRECTAS `.destroy()`
            # sobre los wrappers ya guardados — nada que reconsulte `self`.
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

        `QOpenGLTexture.destroy()` es más estricto que los demás: si el
        contexto no está `current` EN ESTE HILO en el momento exacto de la
        llamada avisa por stderr y no libera la textura (recurso menor,
        una sola vez por instancia — se probó forzar un `makeCurrent()`
        aquí para evitar el aviso y eso SÍ revienta el proceso otra vez,
        ver el comentario en `initializeGL`; el aviso cosmético es
        preferible a un segfault real).
        """
        if self._timer_query is not None:
            self._timer_query.destroy()
            self._timer_query = None
        if self._vao is not None:
            self._vao.destroy()
            self._vao = None
        if self._dust_vao is not None:
            self._dust_vao.destroy()
            self._dust_vao = None
        if self._dust_vbo is not None:
            self._dust_vbo.destroy()
            self._dust_vbo = None
        if self._noise_tex is not None:
            self._noise_tex.destroy()
            self._noise_tex = None
        self._fbos.clear()

    def _compile_programs(self) -> None:
        specs = {
            "scene": "scene.frag",
            "extract": "bloom_extract.frag",
            "godray": "godray.frag",
            "kawase_down": "kawase_down.frag",
            "kawase_up": "kawase_up.frag",
            "streak": "streak.frag",
            "composite": "composite.frag",
        }
        for key, frag in specs.items():
            self._programs[key] = ShaderProgram("fullscreen.vert", frag)
        self._programs["dust"] = ShaderProgram("dust.vert", "dust.frag")

    def _init_noise_texture(self) -> None:
        size = 64
        data = noise3d.generate_or_load(size)
        tex = QtOpenGL.QOpenGLTexture(QtOpenGL.QOpenGLTexture.Target.Target3D)
        tex.setFormat(QtOpenGL.QOpenGLTexture.TextureFormat.RG8_UNorm)
        tex.setSize(size, size, size)
        tex.setWrapMode(QtOpenGL.QOpenGLTexture.WrapMode.Repeat)
        tex.setMinMagFilters(
            QtOpenGL.QOpenGLTexture.Filter.Linear, QtOpenGL.QOpenGLTexture.Filter.Linear,
        )
        tex.allocateStorage(
            QtOpenGL.QOpenGLTexture.PixelFormat.RG, QtOpenGL.QOpenGLTexture.PixelType.UInt8,
        )
        tex.setData(
            QtOpenGL.QOpenGLTexture.PixelFormat.RG, QtOpenGL.QOpenGLTexture.PixelType.UInt8, data,
        )
        self._noise_tex = tex

    def _init_dust_buffers(self) -> None:
        self._dust_vao = QtOpenGL.QOpenGLVertexArrayObject(self)
        self._dust_vao.create()
        self._dust_vao.bind()
        self._dust_vbo = QtOpenGL.QOpenGLBuffer(QtOpenGL.QOpenGLBuffer.Type.VertexBuffer)
        self._dust_vbo.create()
        self._dust_vbo.bind()
        data = _generate_dust_particles(_DUST_COUNT)
        self._dust_vbo.allocate(data, len(data))
        self._gl.glEnableVertexAttribArray(0)
        self._gl.glVertexAttribPointer(0, 4, _GL_FLOAT, 0, 16, VoidPtr(0))
        self._dust_vao.release()
        self._dust_vbo.release()

    def _device_size(self) -> tuple[int, int]:
        """`self.width()/height()` son lógicos (independientes de DPI) en
        este Qt/plataforma — confirmado con trazas: bajo escalado 125% el
        framebuffer real de la ventana es 1.25x más grande, y usar el
        tamaño lógico para el viewport/FBOs deja sin dibujar una franja
        real a la derecha/abajo (visto en captura: negro sólido fuera del
        rect lógico). Todo lo que toque tamaños de FBO/viewport pasa por
        aquí, nunca por `self.width()/height()` directo."""
        dpr = self.devicePixelRatioF()
        return max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr))

    def resizeGL(self, w: int, h: int) -> None:  # noqa: N802
        if not self._init_ok:
            return
        self._rebuild_fbos(*self._device_size())

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
        # los rayos de dios son el pase más caro del pipeline (32-48
        # muestras por píxel, medido: ~2.4ms de los ~7.8ms totales en
        # HIGH) — el piso de muestras es un mandato ("nunca menos de 32"),
        # así que el margen de sobra sale de bajar la RESOLUCIÓN del pase
        # (un cuarto del ya reducido `bloom_scale`), no el conteo de
        # muestras — es un efecto muy difuminado de por sí, la resolución
        # extra no se nota.
        gw, gh = max(4, bw // 4), max(4, bh // 4)
        self._fbos["godray"] = QtOpenGL.QOpenGLFramebufferObject(gw, gh, fmt)

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

        self._render_scene()
        self._render_bloom_chain()
        if self._settings.streak_enabled:
            self._render_streak()
        self._render_composite()

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
                self._rebuild_fbos(*self._device_size())
        self.frameRendered.emit(self._last_cpu_ms)

    # ── Pasadas ───────────────────────────────────────────────────────────
    def _draw_fullscreen(self) -> None:
        # Triángulo de pantalla completa: su VAO (vacío, sin atributos) es
        # compartido por todas las pasadas fullscreen — bind/release aquí
        # mismo, no alrededor del frame entero, porque el paso de polvo
        # (`_dust_vao`) necesita su propio VAO intercalado en medio.
        self._vao.bind()
        self._gl.glDrawArrays(0x0004, 0, 3)  # GL_TRIANGLES
        self._vao.release()

    def _bind_texture(self, program: ShaderProgram, uniform: str, unit: int, tex_id: int) -> None:
        self._gl.glActiveTexture(_GL_TEXTURE0 + unit)
        self._gl.glBindTexture(_GL_TEXTURE_2D, tex_id)
        program.set_uniform(uniform, unit)

    def _render_scene(self) -> None:
        # ningún pase de este pipeline asume blending activo salvo el
        # polvo (aditivo, al final de ESTE mismo método) — si por lo que
        # sea quedó encendido de un frame anterior, esto lo reinicia
        # ANTES de dibujar nada; un blend aditivo colándose en pases que
        # asumen sobreescritura opaca acumula sin tope frame tras frame.
        self._gl.glDisable(_GL_BLEND)
        fbo = self._fbos["scene"]
        fbo.bind()
        self._gl.glViewport(0, 0, fbo.width(), fbo.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p = self._programs["scene"]
        p.maybe_reload()
        p.bind()
        style = STATE_STYLES[self._state]
        tint = tuple(c / 255.0 for c in style.primary) if self._state != OrbState.ERROR else (1.0, 0.25, 0.32)
        state_mult = 1.8 if self._state is OrbState.THINKING else 1.0
        scan_age = self._time - self._scan_start
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_energy", self._energy)
        p.set_uniform("u_resolution", float(fbo.width()), float(fbo.height()))
        p.set_uniform("u_tint", *tint)
        p.set_uniform("u_stateMult", state_mult)
        p.set_uniform("u_scanAge", scan_age)
        p.set_uniform("u_lightUv", *self._light_uv)
        self._noise_tex.bind(3)
        p.set_uniform("u_noise3d", 3)
        self._draw_fullscreen()
        self._noise_tex.release()
        self._render_dust(tint)
        p.release()
        fbo.release()

    def _render_dust(self, tint: tuple) -> None:
        """Polvo bokeh: ~300 point sprites (VBO propio, 3 capas), mezclado
        (alpha estándar, NO aditivo) sobre el fondo ya dibujado en la
        MISMA FBO de escena — nunca un bucle por píxel.

        `glBlendFunc(sfactor, GL_ONE)` (aditivo real, factor destino
        GL_ONE) revienta el resto del pipeline en ESTA GPU (Intel HD 520 /
        Mesa): confirmado experimentalmente aislando cada llamada — con
        GL_ONE como factor destino, TODOS los FBOs posteriores (kawase,
        streak) salen en negro/blanco sólido (valores no representables,
        probablemente Inf/NaN — Qt avisa "QColor::setRgbF: invalid value"
        al leerlos), incluso sin llegar a dibujar nada (basta con llamar
        `glBlendFunc` con ese factor). Con GL_ONE_MINUS_SRC_ALPHA (alpha
        normal) o GL_ZERO no pasa nada — es específico de GL_ONE como
        factor destino en este driver, no un error en esta lógica. Alpha
        estándar en vez de aditivo real es la solución: motas de polvo
        translúcidas en vez de brillo acumulado, visualmente aceptable
        para este elemento y sin el riesgo."""
        p = self._programs["dust"]
        p.maybe_reload()
        p.bind()
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_tint", *tint)
        self._gl.glEnable(_GL_PROGRAM_POINT_SIZE)
        self._gl.glEnable(_GL_BLEND)
        self._gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        self._dust_vao.bind()
        self._gl.glDrawArrays(_GL_POINTS, 0, _DUST_COUNT)
        self._dust_vao.release()
        self._gl.glDisable(_GL_BLEND)
        self._gl.glDisable(_GL_PROGRAM_POINT_SIZE)
        p.release()

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

        # rayos de dios: leen el buffer de brillos RECIÉN extraído (arriba),
        # ANTES de que la cadena dual-Kawase de abajo lo reutilice y lo
        # sobreescriba con el bloom ya difuminado.
        self._render_godrays()

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

    def _render_godrays(self) -> None:
        """Blur radial a 1/4 res desde la posición real del orbe, sobre el
        buffer de brillos ya extraído (`kawase0` en este preciso momento,
        antes del down/up del bloom). El upsample a resolución completa es
        el filtro bilineal de hardware de la propia textura al muestrearla
        en `composite.frag` — sin pasada de upsample aparte."""
        p = self._programs["godray"]
        p.maybe_reload()
        target = self._fbos["godray"]
        target.bind()
        self._gl.glViewport(0, 0, target.width(), target.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p.bind()
        self._bind_texture(p, "u_source", 0, self._fbos["kawase0"].texture())
        p.set_uniform("u_lightUv", *self._light_uv)
        p.set_uniform("u_numSamples", self._settings.godray_samples)
        p.set_uniform("u_density", 0.9)
        p.set_uniform("u_decay", 0.94)
        p.set_uniform("u_exposure", 1.6)
        self._draw_fullscreen()
        p.release()
        target.release()

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
        dw, dh = self._device_size()
        self._gl.glBindFramebuffer(0x8D40, self.defaultFramebufferObject())  # GL_FRAMEBUFFER
        self._gl.glViewport(0, 0, dw, dh)
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p = self._programs["composite"]
        p.maybe_reload()
        p.bind()
        self._bind_texture(p, "u_scene", 0, self._fbos["scene"].texture())
        self._bind_texture(p, "u_bloom", 1, self._fbos["kawase0"].texture())
        streak_tex = self._fbos["streak"].texture() if self._settings.streak_enabled else self._fbos["kawase0"].texture()
        self._bind_texture(p, "u_streak", 2, streak_tex)
        self._bind_texture(p, "u_godray", 3, self._fbos["godray"].texture())
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_bloomStrength", 0.9)
        p.set_uniform("u_streakStrength", 0.5 if self._settings.streak_enabled else 0.0)
        p.set_uniform("u_godrayStrength", 0.7)
        p.set_uniform("u_aberration", 0.0 if self._reduced_motion else self._settings.aberration)
        p.set_uniform("u_grain", 0.0 if self._reduced_motion else self._settings.grain)
        p.set_uniform("u_vignette", self._settings.vignette)
        p.set_uniform("u_texel", 1.0 / dw, 1.0 / dh)
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
