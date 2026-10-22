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
from . import filaments, noise3d
from .quality import QUALITY_PRESETS, AutoQualityController, Quality, QualitySettings, parse_quality
from .shader_loader import ShaderCompileError, ShaderProgram

log = logging.getLogger("jarvis.hud_pro.gpu")

_GL_COLOR_BUFFER_BIT = 0x4000
_GL_TEXTURE_2D = 0x0DE1
_GL_TEXTURE0 = 0x84C0
_GL_TEXTURE_MIN_FILTER = 0x2801
_GL_TEXTURE_MAG_FILTER = 0x2800
_GL_TEXTURE_WRAP_S = 0x2802
_GL_TEXTURE_WRAP_T = 0x2803
_GL_LINEAR = 0x2601
_GL_CLAMP_TO_EDGE = 0x812F
_GL_BLEND = 0x0BE1
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_PROGRAM_POINT_SIZE = 0x8642
_GL_POINTS = 0x0000
_GL_FLOAT = 0x1406
_GL_ARRAY_BUFFER = 0x8892
_GL_SCISSOR_TEST = 0x0C11

_DUST_COUNT = 300
_SCAN_STATE_GAP_S = 999.0  # "hace mucho" — apaga el término de la onda en el shader
_ORB_MARGIN = 1.6  # margen alrededor del radio real del orbe para el fresnel/glow del borde

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

    # Preset de THINKING (GOBERNADOR DE RENDER) — ver `_maybe_downgrade_
    # for_llm` para el porqué. Deliberadamente más agresivo que el LOW
    # normal: 1 sola iteración de Kawase (mandato explícito), no las 2 de
    # LOW; el resto de los campos comparten el piso de LOW.
    _THINKING_SETTINGS = QualitySettings(
        bloom_scale=0.125, kawase_levels=1, streak_enabled=False,
        grain=0.018, aberration=0.6, vignette=0.22,
        godray_samples=32, raymarch_steps=16, bg_dynamic_scale=0.35,
    )
    _THINKING_RENDER_SCALE = 0.66

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
        self._auto = None if fixed_q else AutoQualityController(QUALITY_PRESETS[Quality.MEDIUM])
        self._settings: QualitySettings = (
            QUALITY_PRESETS[fixed_q] if fixed_q else self._auto.current
        )
        self._quality_fixed = fixed_q
        # bajada temporal a MEDIUM mientras el LLM genera (PROCESANDO):
        # medido con Ollama real — con la GPU activa, generar compite por
        # ancho de banda de RAM con la gráfica integrada y pierde tokens/s
        # bastante más de lo tolerable. Sólo aplica si el nivel fijo actual
        # es más caro que MEDIUM (HIGH/ULTRA); AUTO ya nunca pasa de
        # MEDIUM, así que no tiene nada que bajar.
        self._settings_before_llm: QualitySettings | None = None
        self._llm_override_active = False
        # GOBERNADOR DE RENDER: fps por estado + foco de la ventana
        # (`_current_fps`/`_sync_timer`), fondo CONGELADO durante THINKING
        # (`_bg_frozen` — reutiliza el último frame de fondo, ver
        # `_render_scene`) y escala interna reducida de "scene" mientras
        # el LLM genera (`_render_scale`, ver `_rebuild_fbos`).
        self._window_focused = True
        self._bg_frozen = False
        self._render_scale = 1.0

        self._time = 0.0
        self._energy = 0.0
        self._prev_energy = 0.0
        # pulso transitorio del interior: tecleo, envío, respuesta o
        # cambio de estado; decae solo en `paintGL` (ver `pulse_activity`)
        self._activity_boost = 0.0
        # los neutrones guardan inercia propia: un pulso de interacción
        # los acelera durante ~1s aunque el brillo del orbe ya se haya
        # apagado. Así el movimiento se nota de verdad al teclear/enviar.
        self._neutron_kick = 0.0
        # fase acumulada: en reposo NO avanza, así que las partículas
        # quedan suspendidas hasta que Jarvis interactúa de verdad.
        self._neutron_flow = 0.0
        self._neutron_motion = 0.0
        self._state = OrbState.IDLE
        self._paused = False
        self._init_ok = False
        self._init_error = ""
        self._light_uv = (0.5, 0.42)
        self._light_radius = 0.16
        self._hover = False
        self._spectrum: list[float] | None = None
        self._scan_start = -_SCAN_STATE_GAP_S
        self._orb_fbo_size = (0, 0)
        self._last_logged_settings = None
        self._last_logged_size: tuple[int, int] | None = None
        self._static_bg_size = (0, 0)
        self._dynamic_bg_size = (0, 0)
        # FASE D — vidrio de paneles: rect en UV de ventana (Qt, origen
        # arriba-izquierda), lo alimenta `window.py` desde la geometría
        # real del panel — `None` mientras no se haya fijado ninguno.
        self._glass_rect: tuple[float, float, float, float] | None = None
        self._glass_fbo_size = (0, 0)
        self._glass_last_update = -999.0
        self._glass_interval_s = 1.0 / 20.0  # 20Hz — el fondo tras el panel cambia despacio

        self._programs: dict[str, ShaderProgram] = {}
        self._fbos: dict[str, QtOpenGL.QOpenGLFramebufferObject] = {}
        self._vao = None
        self._dust_vao = None
        self._dust_vbo = None
        self._noise_tex = None
        self._filament_tex = None
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
            self._auto = self._auto or AutoQualityController(QUALITY_PRESETS[Quality.MEDIUM])
        else:
            self._settings = QUALITY_PRESETS[quality]

    def set_state(self, state: OrbState) -> None:
        if state != self._state:
            self._trigger_scan()
            # cada cambio de estado enciende el interior (escucha, habla,
            # generación, error) con un pulso que se apaga solo
            self._activity_boost = max(self._activity_boost, 0.45)
            self._neutron_kick = max(self._neutron_kick, 0.55)
        entering_thinking = state is OrbState.THINKING and self._state is not OrbState.THINKING
        leaving_thinking = state is not OrbState.THINKING and self._state is OrbState.THINKING
        self._state = state
        if entering_thinking:
            self._maybe_downgrade_for_llm()
        elif leaving_thinking:
            self._restore_quality_after_llm()
        self._sync_timer()  # el fps objetivo depende del estado — ver `_current_fps`

    def _maybe_downgrade_for_llm(self) -> None:
        """GOBERNADOR DE RENDER: diagnóstico con Ollama real + pidstat
        confirmó que el cuello es CPU de 2 núcleos físicos compartidos,
        no la calidad de sombreado — dos intentos previos (bajar sólo a
        MEDIUM, luego a LOW, ambos sin tocar el fps) midieron ~33-42% de
        pérdida de tokens/s, sin mejora real. `_THINKING_SETTINGS` +
        24fps (`_current_fps`) + fondo congelado (`_bg_frozen`) + escala
        interna reducida (`_render_scale`) es el intento que sí ataca la
        causa real. `_rebuild_fbos` exige contexto GL corriente —
        `_apply_settings_change_safely` lo envuelve en `makeCurrent()`/
        `doneCurrent()`, el patrón que la propia documentación de Qt
        indica para tocar GL fuera de paintGL/resizeGL. Esto es DISTINTO
        del caso de `_cleanup_gl` (ver ese comentario): ahí revienta
        porque el contexto se está DESTRUYENDO; aquí el widget sigue
        vivo y visible."""
        self._llm_override_active = True
        self._settings_before_llm = self._settings
        self._settings = self._THINKING_SETTINGS
        self._bg_frozen = True
        self._render_scale = self._THINKING_RENDER_SCALE
        tag = self._quality_fixed.value if self._quality_fixed else "auto"
        log.info(
            "HUD GPU: bajando a preset THINKING (24fps, escala %.2f, fondo congelado, era %s)",
            self._render_scale, tag,
        )
        self._apply_settings_change_safely()

    def _restore_quality_after_llm(self) -> None:
        if not self._llm_override_active:
            return
        self._llm_override_active = False
        self._bg_frozen = False
        self._render_scale = 1.0
        if self._quality_fixed is not None:
            self._settings = self._settings_before_llm
            log.info("HUD GPU: calidad restaurada a %s tras terminar de generar", self._quality_fixed.value)
        else:
            # AUTO: aplica YA su nivel real (no el snapshot de antes de
            # entrar a THINKING, que podría estar obsoleto) — su propia
            # histéresis (`_auto.update()`) siguió corriendo todo este
            # tiempo con tiempos de frame reales, nunca se pausó.
            self._settings = self._auto.current
            log.info("HUD GPU: AUTO retoma su nivel real tras terminar de generar")
        self._settings_before_llm = None
        self._apply_settings_change_safely()

    def _apply_settings_change_safely(self) -> None:
        """`_rebuild_fbos` exige contexto GL corriente. `set_state` (de
        donde cuelgan los dos métodos de arriba) puede llegar desde fuera
        del ciclo de pintado — `makeCurrent()`/`doneCurrent()` es el
        patrón que Qt documenta para eso."""
        if not self._init_ok:
            return
        self.makeCurrent()
        try:
            self._rebuild_fbos(*self._device_size())
        finally:
            self.doneCurrent()

    def pulse_activity(self, amount: float = 0.25) -> None:
        """Enciende el interior del orbe con un pulso transitorio (0..1).

        Lo alimenta el HUD con actividad REAL del sistema: cada tecla en
        el campo de texto, el envío de un mensaje, cada trozo de respuesta
        del LLM y los cambios de estado. `paintGL` lo hace decaer, así que
        no se acumula sin límite. Además arma `_neutron_kick`, que decae
        más despacio: los neutrones siguen acelerados aunque el brillo del
        orbe ya se haya apagado."""
        value = max(0.0, min(1.0, float(amount)))
        self._activity_boost = max(self._activity_boost, value)
        self._neutron_kick = max(self._neutron_kick, value)

    def _orb_activity(self) -> float:
        """Actividad 0..1.6 del interior por estado + pulso transitorio."""
        if self._state is OrbState.THINKING:
            base = 0.85
        elif self._state is OrbState.LISTENING:
            base = 0.32 + 0.55 * self._energy
        elif self._state is OrbState.SPEAKING:
            base = 0.38 + 0.55 * self._energy
        elif self._state is OrbState.ERROR:
            base = 0.45
        else:
            base = 0.18
        return max(0.0, min(1.6, base + self._activity_boost))

    def _neutron_speed(self) -> float:
        """Velocidad de los neutrones: cero en reposo, alta al interactuar.

        La posición no depende directamente del reloj: `_advance_neutrons`
        acumula una fase sólo mientras hay interacción real. En IDLE sin
        ningún pulso la fase se congela; al teclear/enviar o mientras el
        orbe está escuchando/hablando/pensando, avanza."""
        if self._state is OrbState.THINKING:
            base = 2.45
        elif self._state is OrbState.LISTENING:
            base = 0.75 + 1.40 * self._energy
        elif self._state is OrbState.SPEAKING:
            base = 0.80 + 1.40 * self._energy
        elif self._state is OrbState.ERROR:
            base = 1.20
        else:
            base = 0.0
        return base + 4.20 * self._neutron_kick

    def _advance_neutrons(self, dt: float) -> None:
        if self._reduced_motion:
            self._neutron_motion = 0.0
            return
        speed = self._neutron_speed()
        self._neutron_motion = min(1.0, speed / 0.90)
        self._neutron_flow += dt * speed

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

    def set_light_radius(self, radius: float) -> None:
        """Radio real del orbe (unidades de `centered`, ver `scene.frag`:
        mismo sistema que `u_lightUv`) — 0.30 del lado menor del propio
        widget del orbe, calculado en `window.py` desde su geometría real."""
        self._light_radius = max(0.01, float(radius))

    def set_glass_rect(self, x: float, y: float, w: float, h: float) -> None:
        """Rect del panel de vidrio (FASE D) en UV de VENTANA — Qt, origen
        arriba-izquierda, igual convención que `set_light_uv`. `w`/`h`
        nulos o negativos apagan el efecto (panel oculto/sin geometría
        todavía) en vez de dejar un rect inválido a medio fijar."""
        if w <= 0.0 or h <= 0.0:
            self._glass_rect = None
            return
        self._glass_rect = (float(x), float(y), float(w), float(h))

    def set_hover(self, hovering: bool) -> None:
        """+20% de brillo del orbe — mismo gesto que ya soporta el orbe
        raster (`OrbRenderer.set_hover`)."""
        self._hover = bool(hovering)

    def set_spectrum(self, bands: list[float] | None) -> None:
        """Espectro real (FFT) para las barras del anillo. `None`/vacío lo
        apaga — nunca se inventa una forma cuando no hay datos."""
        if not bands:
            self._spectrum = None
        else:
            self._spectrum = [max(0.0, min(1.0, float(b))) for b in bands][:64]

    def _trigger_scan(self) -> None:
        self._scan_start = self._time

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self._sync_timer()

    def set_focused(self, focused: bool) -> None:
        """Ventana sin foco: 15fps (GOBERNADOR DE RENDER) — la sigue
        pintando por si se ve de reojo, pero sin competir en serio por
        CPU con lo que sea que SÍ tiene el foco. "Minimizada u oculta:
        pausa total" YA estaba cubierto antes de esta tarea — `window.py`
        ya llama `set_paused(isMinimized())` en `WindowStateChange`, y
        `_sync_timer` ya mira `self.isVisible()` — no hacía falta un
        mecanismo nuevo para eso."""
        self._window_focused = bool(focused)
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
            self._init_filament_texture()
            self._init_dust_buffers()
            # determinista: existe aunque el primer frame aún no haya
            # llegado (el camino congelado de `_render_scene` también lo
            # garantiza, pero no si THINKING entra antes del primer paint)
            self._ensure_dynamic_bg_fbo()
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
        if self._filament_tex is not None:
            self._filament_tex.destroy()
            self._filament_tex = None
        self._fbos.clear()

    def _compile_programs(self) -> None:
        specs = {
            "static_bg": "static_bg.frag",
            "dynamic_bg": "dynamic_bg.frag",
            "extract": "bloom_extract.frag",
            "godray": "godray.frag",
            "kawase_down": "kawase_down.frag",
            "kawase_up": "kawase_up.frag",
            "streak": "streak.frag",
            "composite": "composite.frag",
            "orb": "orb.frag",
            "blit": "blit.frag",
            "bg_composite": "bg_composite.frag",
            "glass_blur": "glass_blur.frag",
            "glass_apply": "glass_apply.frag",
            "rings": "rings.frag",
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

    def _init_filament_texture(self) -> None:
        size = filaments.DEFAULT_SIZE
        data = filaments.generate_or_load(size)
        tex = QtOpenGL.QOpenGLTexture(QtOpenGL.QOpenGLTexture.Target.Target2D)
        tex.setFormat(QtOpenGL.QOpenGLTexture.TextureFormat.RGBA8_UNorm)
        tex.setSize(size, size)
        tex.setMipLevels(size.bit_length())
        tex.setWrapMode(QtOpenGL.QOpenGLTexture.WrapMode.ClampToEdge)
        tex.setMinMagFilters(
            QtOpenGL.QOpenGLTexture.Filter.LinearMipMapLinear, QtOpenGL.QOpenGLTexture.Filter.Linear,
        )
        tex.allocateStorage(
            QtOpenGL.QOpenGLTexture.PixelFormat.RGBA, QtOpenGL.QOpenGLTexture.PixelType.UInt8,
        )
        tex.setData(
            QtOpenGL.QOpenGLTexture.PixelFormat.RGBA, QtOpenGL.QOpenGLTexture.PixelType.UInt8, data,
        )
        tex.generateMipMaps()
        self._filament_tex = tex

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
        # el FBO del orbe vive fuera de este método (`_ensure_orb_fbo`, se
        # reconstruye sólo si su tamaño cambia) — pero ESTE método acaba
        # de borrarlo del dict igual; sin este reset, `_ensure_orb_fbo`
        # cree que el tamaño no cambió y NO lo vuelve a crear → KeyError
        # la primera vez que se pinta después de un resize/cambio de
        # calidad (confirmado: reproducible, no es hipotético).
        self._orb_fbo_size = (0, 0)
        # mismo motivo que el del orbe arriba: este método acaba de
        # borrar "static_bg"/"dynamic_bg" del dict — sin resetear su
        # tamaño registrado, `_ensure_static_bg`/`_ensure_dynamic_bg_fbo`
        # creerían que no cambió nada y no los recrearían.
        self._static_bg_size = (0, 0)
        self._dynamic_bg_size = (0, 0)
        # mismo motivo, para la FBO del vidrio de paneles (FASE D).
        self._glass_fbo_size = (0, 0)

        # GOBERNADOR DE RENDER: `_render_scale` (0.66 durante THINKING,
        # 1.0 el resto del tiempo) reduce la resolución INTERNA de
        # "scene" y todo lo que cuelga de ella (bloom/streak/godray, que
        # ya eran fracciones de este tamaño) — el paso final a pantalla
        # completa (`_render_composite`) sigue muestreando "scene" con
        # el filtro bilineal de hardware, así que el upsample es gratis,
        # igual que ya hace el fondo dinámico con su propia escala.
        rw = max(4, round(w * self._render_scale))
        rh = max(4, round(h * self._render_scale))

        fmt = QtOpenGL.QOpenGLFramebufferObjectFormat()
        fmt.setInternalTextureFormat(0x881A)  # GL_RGBA16F: rango HDR para el bloom/tonemap
        self._fbos["scene"] = QtOpenGL.QOpenGLFramebufferObject(rw, rh, fmt)
        self._set_fbo_linear(self._fbos["scene"])

        # el resto de las FBOs son buffers intermedios de post-proceso —
        # nunca se leen para el tone mapping en sí (eso sólo pasa una vez,
        # sobre "scene"), así que no necesitan rango HDR: RGBA8 les basta
        # y es la mitad de ancho de banda de memoria por cada lectura/
        # escritura — importa en esta GPU/RAM compartida (GOBERNADOR DE
        # RENDER, diagnóstico: el cuello real es CPU/núcleos, pero cada
        # byte de menos también ayuda al presupuesto de memoria).
        fmt8 = QtOpenGL.QOpenGLFramebufferObjectFormat()
        fmt8.setInternalTextureFormat(0x8058)  # GL_RGBA8

        bw = max(4, round(rw * self._settings.bloom_scale))
        bh = max(4, round(rh * self._settings.bloom_scale))
        self._bloom_base_size = (bw, bh)
        levels = max(1, self._settings.kawase_levels)
        self._kawase_sizes = [(max(2, bw >> i), max(2, bh >> i)) for i in range(levels)]
        for i, (lw, lh) in enumerate(self._kawase_sizes):
            self._fbos[f"kawase{i}"] = QtOpenGL.QOpenGLFramebufferObject(lw, lh, fmt8)
            self._set_fbo_linear(self._fbos[f"kawase{i}"])
        # flare a 1/8 de la resolución de PANTALLA (no de `bloom_scale`,
        # que en high ya es 1/4) — es un efecto muy difuminado de por sí,
        # media res extra sobre el bloom no se nota y sólo cuesta fill-rate.
        sw, sh = max(2, round(rw / 8)), max(2, round(rh / 8))
        self._fbos["streak"] = QtOpenGL.QOpenGLFramebufferObject(sw, sh, fmt8)
        self._set_fbo_linear(self._fbos["streak"])
        # los rayos de dios son el pase más caro del pipeline (32-48
        # muestras por píxel, medido: ~2.4ms de los ~7.8ms totales en
        # HIGH) — el piso de muestras es un mandato ("nunca menos de 32"),
        # así que el margen de sobra sale de bajar la RESOLUCIÓN del pase
        # (un cuarto del ya reducido `bloom_scale`), no el conteo de
        # muestras — es un efecto muy difuminado de por sí, la resolución
        # extra no se nota.
        gw, gh = max(4, bw // 4), max(4, bh // 4)
        self._fbos["godray"] = QtOpenGL.QOpenGLFramebufferObject(gw, gh, fmt8)
        self._set_fbo_linear(self._fbos["godray"])

        self._log_effective_config(w, h, bw, bh, levels, gw, gh)

        # "dynamic_bg" acaba de borrarse arriba; el camino CONGELADO de
        # THINKING sólo lo recrea al pintar. Si no llega un frame antes de
        # que alguien consulte `_fbos` (o si el widget queda oculto), el
        # dict queda incompleto. Crearlo aquí, con el contexto ya corriente
        # (ver `_apply_settings_change_safely`), mantiene el invariante.
        self._ensure_dynamic_bg_fbo()

    def _log_effective_config(
        self, w: int, h: int, bw: int, bh: int, kawase_levels: int, gw: int, gh: int,
    ) -> None:
        """Config real de ESTE nivel, una vez por cambio (no en cada
        resize idéntico) — para poder confirmar que low/high/ultra de
        verdad difieren, no sólo de nombre."""
        s = self._settings
        if s == self._last_logged_settings and (w, h) == self._last_logged_size:
            return
        self._last_logged_settings = s
        self._last_logged_size = (w, h)
        tag = self._quality_fixed.value if self._quality_fixed else "auto"
        log.info(
            "HUD GPU config efectiva [%s] ventana=%dx%d | escena=%dx%d | "
            "bloom/kawase=%dx%d x%d niveles | rayos_dios=%dx%d muestras=%d | "
            "orbe pasos_raymarch=%d | polvo_partículas=%d | streak=%s",
            tag, w, h, w, h, bw, bh, kawase_levels, gw, gh, s.godray_samples,
            s.raymarch_steps, _DUST_COUNT, s.streak_enabled,
        )

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
        # el pulso del interior se apaga solo (tecleo/envío/respuesta)
        self._activity_boost = max(0.0, self._activity_boost - dt * 2.2)
        self._neutron_kick = max(0.0, self._neutron_kick - dt * 0.65)
        self._advance_neutrons(dt)

        gl_started = False
        if self._timer_query is not None:
            self._timer_query.begin()
            gl_started = True

        self._render_scene()
        self._render_orb()
        self._render_rings()
        self._render_glass()
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
            # `_auto.update()` sigue corriendo SIEMPRE (alimenta su
            # histéresis con tiempos reales) aunque el override de LLM
            # esté activo — sólo se SUPRIME aplicar su resultado a
            # `self._settings` mientras tanto; al terminar la generación
            # (`_llm_override_active` vuelve a False), este mismo bloque
            # lo retoma solo en el frame siguiente, sin necesitar un
            # snapshot propio para el caso AUTO (ver `_restore_quality_
            # after_llm`).
            new_settings = self._auto.update(self._last_cpu_ms)
            if not self._llm_override_active and new_settings != self._settings:
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

    def _set_fbo_linear(self, fbo) -> None:
        """Filtro bilineal explícito para TODA textura de FBO.

        En esta build de Qt, las texturas de `QOpenGLFramebufferObject`
        nacen con GL_NEAREST. Los pases que se muestrean a otra resolución
        (bloom, rayos de dios, escena con `_render_scale`, vidrio) asumen
        GL_LINEAR — sin esto, cada texel del buffer reducido se ve como un
        bloque recto (confirmado en capturas: cuadros blancos sobre el orbe
        en PENSANDO). El coste de GL_LINEAR es despreciable."""
        gl = self._gl
        gl.glActiveTexture(_GL_TEXTURE0)
        gl.glBindTexture(_GL_TEXTURE_2D, fbo.texture())
        gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MIN_FILTER, _GL_LINEAR)
        gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MAG_FILTER, _GL_LINEAR)
        gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_WRAP_S, _GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_WRAP_T, _GL_CLAMP_TO_EDGE)
        gl.glBindTexture(_GL_TEXTURE_2D, 0)

    def _bind_texture(self, program: ShaderProgram, uniform: str, unit: int, tex_id: int) -> None:
        self._gl.glActiveTexture(_GL_TEXTURE0 + unit)
        self._gl.glBindTexture(_GL_TEXTURE_2D, tex_id)
        program.set_uniform(uniform, unit)

    def _ensure_static_bg(self) -> None:
        """Capa ESTÁTICA (gradiente + retícula hexagonal + viñeta): se
        renderiza a una textura propia UNA sola vez por tamaño — nunca
        depende del estado/tiempo, así que no hace falta invalidarla por
        eso. El resto de los frames la reutilizan con una sola lectura de
        textura (`blit.frag`), sin recalcular el SDF del hexágono."""
        dw, dh = self._device_size()
        if self._static_bg_size == (dw, dh) and "static_bg" in self._fbos:
            return
        fmt = QtOpenGL.QOpenGLFramebufferObjectFormat()
        fmt.setInternalTextureFormat(0x8058)  # GL_RGBA8 — nunca HDR, sólo compositing
        self._fbos["static_bg"] = QtOpenGL.QOpenGLFramebufferObject(dw, dh, fmt)
        self._set_fbo_linear(self._fbos["static_bg"])
        self._static_bg_size = (dw, dh)
        fbo = self._fbos["static_bg"]
        fbo.bind()
        self._gl.glViewport(0, 0, dw, dh)
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p = self._programs["static_bg"]
        p.maybe_reload()
        p.bind()
        p.set_uniform("u_resolution", float(dw), float(dh))
        self._draw_fullscreen()
        p.release()
        fbo.release()

    def _ensure_dynamic_bg_fbo(self) -> tuple[int, int]:
        dw, dh = self._device_size()
        scale = self._settings.bg_dynamic_scale
        w, h = max(4, round(dw * scale)), max(4, round(dh * scale))
        if self._dynamic_bg_size != (w, h) or "dynamic_bg" not in self._fbos:
            fmt = QtOpenGL.QOpenGLFramebufferObjectFormat()
            fmt.setInternalTextureFormat(0x8058)  # GL_RGBA8
            fbo = QtOpenGL.QOpenGLFramebufferObject(w, h, fmt)
            self._set_fbo_linear(fbo)
            # el contenido de una textura recién creada es indefinido —
            # si esto pasa con el fondo CONGELADO (`_bg_frozen`, GOBERNADOR
            # DE RENDER), `_composite_background` leería basura de GPU en
            # vez de "sin niebla/reflejo esta vez" hasta el próximo
            # recálculo real; alfa=0 (transparente) es el resultado
            # correcto de "todavía no se dibujó nada encima", no un hack.
            fbo.bind()
            self._gl.glClear(_GL_COLOR_BUFFER_BIT)
            fbo.release()
            self._fbos["dynamic_bg"] = fbo
            self._dynamic_bg_size = (w, h)
        return w, h

    def _render_dynamic_bg(self, tint: tuple, state_mult: float, scan_age: float) -> None:
        """Capa DINÁMICA (niebla, reflejo del orbe, onda de escaneo,
        radar, líneas) — a RESOLUCIÓN REDUCIDA (`bg_dynamic_scale`, según
        calidad), compuesta luego sobre la escena con upsample bilineal
        de hardware al muestrear su textura (ver `_render_scene`)."""
        w, h = self._ensure_dynamic_bg_fbo()
        fbo = self._fbos["dynamic_bg"]
        fbo.bind()
        self._gl.glViewport(0, 0, w, h)
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        p = self._programs["dynamic_bg"]
        p.maybe_reload()
        p.bind()
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_energy", self._energy)
        p.set_uniform("u_resolution", float(w), float(h))
        p.set_uniform("u_tint", *tint)
        p.set_uniform("u_stateMult", state_mult)
        p.set_uniform("u_scanAge", scan_age)
        p.set_uniform("u_lightUv", *self._light_uv)
        self._noise_tex.bind(3)
        p.set_uniform("u_noise3d", 3)
        self._draw_fullscreen()
        self._noise_tex.release()
        p.release()
        fbo.release()

    def _render_scene(self) -> None:
        # ningún pase de este pipeline asume blending activo salvo el
        # polvo (al final de ESTE mismo método) — si por lo que sea quedó
        # encendido de un frame anterior, esto lo reinicia ANTES de dibujar
        # nada; un blend colándose en pases que asumen sobreescritura
        # opaca acumula sin tope frame tras frame.
        self._gl.glDisable(_GL_BLEND)
        self._ensure_static_bg()

        style = STATE_STYLES[self._state]
        tint = tuple(c / 255.0 for c in style.primary) if self._state != OrbState.ERROR else (1.0, 0.25, 0.32)
        state_mult = 1.8 if self._state is OrbState.THINKING else 1.0
        scan_age = self._time - self._scan_start
        if self._bg_frozen:
            # `_bg_frozen` (GOBERNADOR DE RENDER, THINKING): se salta el
            # recálculo del shader dinámico (niebla/reflejo/radar) — el
            # fondo detrás no cambia frame a frame mientras el LLM
            # genera, sólo el orbe y los anillos. `_composite_background`
            # de abajo sigue corriendo (reusa el ÚLTIMO contenido ya
            # calculado de "dynamic_bg"), así "scene" queda limpio cada
            # frame para que orb/rings no se acumulen encima por el
            # blend alfa. SÍ hay que garantizar que la FBO exista —
            # `_rebuild_fbos` (disparado al entrar a THINKING, para
            # aplicar `_render_scale`) la borró; sin este `_ensure_*`
            # suelto, `_composite_background` revienta con KeyError en
            # el primer frame congelado.
            self._ensure_dynamic_bg_fbo()
        else:
            self._render_dynamic_bg(tint, state_mult, scan_age)

        fbo = self._fbos["scene"]
        fbo.bind()
        self._gl.glViewport(0, 0, fbo.width(), fbo.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)

        self._composite_background()
        self._render_dust(tint)
        fbo.release()

    def _composite_background(self) -> None:
        """Funde estático + dinámico en UN solo draw call (`bg_composite.
        frag`, mezcla por alpha hecha en el shader con `mix`, sin blending
        de hardware). Antes eran dos blits separados con un toggle de
        `glBlendFunc` en medio — medido: ese segundo draw call + cambio de
        estado de blend costaba más, en esta GPU, de lo que ahorraba
        renderizar la capa dinámica a resolución reducida; fusionarlos
        recuperó ese costo sin perder la resolución reducida de la capa
        dinámica (su sampler sigue haciendo el upsample bilineal)."""
        bc = self._programs["bg_composite"]
        bc.maybe_reload()
        bc.bind()
        self._bind_texture(bc, "u_static", 0, self._fbos["static_bg"].texture())
        self._bind_texture(bc, "u_dynamic", 1, self._fbos["dynamic_bg"].texture())
        self._draw_fullscreen()
        bc.release()

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

    def _ensure_orb_fbo(self) -> None:
        """FBO propio del orbe (FASE C), cuadrado, a la resolución de su
        propio cuadro en pantalla — el pase del orbe (red de filamentos +
        ruido 3D) sólo cuesta ahí, nunca en el resto de la escena, y a
        1:1 los filamentos finos sobreviven en vez de convertirse en
        motas al minificar. Se reconstruye SOLO si el tamaño cambia (orbe
        se mueve/cambia de tamaño con la ventana), no cada frame."""
        _, dh = self._device_size()
        diameter_px = self._light_radius * dh * 2.0 * _ORB_MARGIN
        size = max(8, min(round(diameter_px), dh * 2))
        if self._orb_fbo_size != (size, size):
            fmt = QtOpenGL.QOpenGLFramebufferObjectFormat()
            fmt.setInternalTextureFormat(0x8058)  # GL_RGBA8
            self._fbos["orb"] = QtOpenGL.QOpenGLFramebufferObject(size, size, fmt)
            self._set_fbo_linear(self._fbos["orb"])
            self._orb_fbo_size = (size, size)

    def _scissor_rect_around_orb(self, margin: float, fbo_w: int, fbo_h: int) -> tuple[int, int, int, int]:
        """Rectángulo (x, y, w, h) en coordenadas de `glScissor` (origen
        abajo-izquierda) que encierra al orbe con el margen dado — evita
        invocar el fragment shader de rayos/anillos fuera de esa zona:
        medido, el pase de anillos a pantalla completa SIN esto costaba
        más que el propio raymarch del orbe (fill-rate, no el shader en
        sí — barato mate por píxel, pero cada píxel de la PANTALLA
        ENTERA). `u_resolution`/`centered` en los shaders siguen usando
        UV normal — esto sólo acota qué píxeles se procesan."""
        half_px = self._light_radius * margin * fbo_h
        cx_px = self._light_uv[0] * fbo_w
        cy_top_px = self._light_uv[1] * fbo_h
        cy_bottom_px = fbo_h - cy_top_px  # glScissor: origen abajo-izquierda
        x0 = max(0, int(cx_px - half_px))
        y0 = max(0, int(cy_bottom_px - half_px))
        x1 = min(fbo_w, int(cx_px + half_px))
        y1 = min(fbo_h, int(cy_bottom_px + half_px))
        return x0, y0, max(1, x1 - x0), max(1, y1 - y0)

    def _render_orb(self) -> None:
        """Orbe de plasma: red de filamentos luminosos sobre vidrio
        índigo, núcleo que late, órbitas con estela y pulsos ligados a la
        energía real (`u_energy`). La textura 2D cacheada (dos redes +
        halo) se deforma por capas con el ruido 3D; el pase vive en el
        FBO 1:1 de `_ensure_orb_fbo` y se compone sobre la escena (ver
        `blit.frag`)."""
        self._gl.glDisable(_GL_BLEND)
        self._ensure_orb_fbo()
        fbo = self._fbos["orb"]
        fbo.bind()
        self._gl.glViewport(0, 0, fbo.width(), fbo.height())
        self._gl.glClear(_GL_COLOR_BUFFER_BIT)
        style = STATE_STYLES[self._state]
        if self._state != OrbState.ERROR:
            tint = tuple(c / 255.0 for c in style.primary)
            tint2 = tuple(c / 255.0 for c in style.secondary)
            accent = tuple(c / 255.0 for c in style.accent)
        else:
            tint = (1.0, 0.25, 0.32)
            tint2 = (0.50, 0.05, 0.12)
            accent = (1.0, 0.80, 0.85)
        state_mult = 1.8 if self._state is OrbState.THINKING else 1.0
        p = self._programs["orb"]
        p.maybe_reload()
        p.bind()
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_energy", self._energy)
        p.set_uniform("u_activity", self._orb_activity())
        p.set_uniform("u_neutronKick", self._neutron_kick)
        p.set_uniform("u_neutronFlow", self._neutron_flow)
        p.set_uniform("u_neutronMotion", self._neutron_motion)
        p.set_uniform("u_tint", *tint)
        p.set_uniform("u_tint2", *tint2)
        p.set_uniform("u_accent", *accent)
        p.set_uniform("u_stateMult", state_mult)
        p.set_uniform("u_hover", 1.0 if self._hover else 0.0)
        p.set_uniform("u_steps", self._settings.raymarch_steps)
        self._noise_tex.bind(3)
        p.set_uniform("u_noise3d", 3)
        if self._filament_tex is not None:
            self._filament_tex.bind(4)
            p.set_uniform("u_filaments", 4)
        self._draw_fullscreen()
        self._noise_tex.release()
        if self._filament_tex is not None:
            self._filament_tex.release()
        p.release()
        fbo.release()

        scene = self._fbos["scene"]
        scene.bind()
        self._gl.glViewport(0, 0, scene.width(), scene.height())
        # Margen 1.8x (antes 1.1x): confirmado con capturas reales +
        # muestreo de píxeles que a 1.1x este glScissor cortaba en seco
        # (una sola fila de píxeles, de brillo ~95 a ~4) el glow/rim del
        # orbe ANTES de que su propio alpha llegara a cero -- se veía como
        # un corte recto justo debajo del orbe, "no aparece el círculo
        # completo, tapado abajo", reportado en uso real. 1.8x deja ese
        # alpha apagarse solo (fade suave contra el piso hexagonal),
        # consistente con el "2.8x" de sangrado de bloom ya documentado en
        # `_position_status_below_rings` (window.py).
        sx, sy, sw, sh = self._scissor_rect_around_orb(_ORB_MARGIN * 1.8, scene.width(), scene.height())
        self._gl.glEnable(_GL_SCISSOR_TEST)
        self._gl.glScissor(sx, sy, sw, sh)
        self._gl.glEnable(_GL_BLEND)
        self._gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        bp = self._programs["blit"]
        bp.maybe_reload()
        bp.bind()
        self._bind_texture(bp, "u_source", 0, fbo.texture())
        bp.set_uniform("u_lightUv", *self._light_uv)
        bp.set_uniform("u_lightRadius", self._light_radius)
        bp.set_uniform("u_resolution", float(scene.width()), float(scene.height()))
        bp.set_uniform("u_margin", _ORB_MARGIN)
        self._draw_fullscreen()
        bp.release()
        self._gl.glDisable(_GL_BLEND)
        self._gl.glDisable(_GL_SCISSOR_TEST)
        scene.release()

    def _render_rings(self) -> None:
        """Anillos HUD + espectro real, SDF en un pase aparte a
        resolución completa (nítido pese a que el orbe vaya a media res).
        Acotado con `glScissor` a la zona real del orbe — medido: sin
        esto, este pase (matemática barata por píxel, pero sobre la
        PANTALLA ENTERA) costaba más que el propio raymarch."""
        scene = self._fbos["scene"]
        scene.bind()
        self._gl.glViewport(0, 0, scene.width(), scene.height())
        sx, sy, sw, sh = self._scissor_rect_around_orb(1.9, scene.width(), scene.height())
        self._gl.glEnable(_GL_SCISSOR_TEST)
        self._gl.glScissor(sx, sy, sw, sh)
        self._gl.glEnable(_GL_BLEND)
        self._gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        style = STATE_STYLES[self._state]
        tint = tuple(c / 255.0 for c in style.primary) if self._state != OrbState.ERROR else (1.0, 0.25, 0.32)
        state_mult = 1.8 if self._state is OrbState.THINKING else 1.0
        p = self._programs["rings"]
        p.maybe_reload()
        p.bind()
        p.set_uniform("u_time", self._time)
        p.set_uniform("u_stateMult", state_mult)
        p.set_uniform("u_resolution", float(scene.width()), float(scene.height()))
        p.set_uniform("u_lightUv", *self._light_uv)
        p.set_uniform("u_lightRadius", self._light_radius)
        p.set_uniform("u_tint", *tint)
        if self._spectrum:
            p.set_uniform("u_hasSpectrum", 1)
            p.set_uniform("u_spectrumCount", len(self._spectrum))
            p.set_uniform_array("u_spectrum", self._spectrum)
        else:
            p.set_uniform("u_hasSpectrum", 0)
            p.set_uniform("u_spectrumCount", 0)
        self._draw_fullscreen()
        p.release()
        self._gl.glDisable(_GL_BLEND)
        self._gl.glDisable(_GL_SCISSOR_TEST)
        scene.release()

    def _glass_pixel_rect(self, dw: int, dh: int) -> tuple[int, int, int, int]:
        """Convierte `_glass_rect` (UV de ventana, Qt: origen arriba-
        izquierda) a píxeles bottom-up (origen abajo-izquierda) — misma
        conversión que `_scissor_rect_around_orb` para `_light_uv`, la
        convención de TODO el contenido dibujado por este pipeline."""
        x_uv, y_uv, w_uv, h_uv = self._glass_rect
        x0 = round(x_uv * dw)
        w = max(1, round(w_uv * dw))
        top_px = round(y_uv * dh)
        h = max(1, round(h_uv * dh))
        y0 = dh - top_px - h  # Qt (arriba-izq) → GL (abajo-izq)
        return x0, y0, w, h

    def _ensure_glass_fbo(self, pw: int, ph: int) -> tuple[int, int]:
        gw, gh = max(2, pw // 4), max(2, ph // 4)
        if self._glass_fbo_size != (gw, gh) or "glass" not in self._fbos:
            fmt = QtOpenGL.QOpenGLFramebufferObjectFormat()
            fmt.setInternalTextureFormat(0x8058)  # GL_RGBA8
            self._fbos["glass"] = QtOpenGL.QOpenGLFramebufferObject(gw, gh, fmt)
            self._set_fbo_linear(self._fbos["glass"])
            self._glass_fbo_size = (gw, gh)
        return gw, gh

    def _render_glass(self) -> None:
        """FASE D — vidrio esmerilado del panel de consola: desenfoque de
        lo que hay detrás, calculado SÓLO en la región del panel (nunca
        pantalla completa) y a 1/4 de SU resolución — el upsample de
        vuelta es el filtro bilineal de hardware del sampler, igual que
        el fondo dinámico. La parte cara (el blur en sí) sólo se
        recalcula a 20Hz (`_glass_interval_s`): el fondo detrás de un
        panel cambia despacio frame a frame, recalcularlo a 60fps sería
        gastar presupuesto de GPU en algo imperceptible. Cuando toca
        saltarse el recálculo, el blit de abajo sigue componiendo la
        ÚLTIMA versión ya calculada — nunca deja el panel sin vidrio."""
        if self._glass_rect is None:
            return
        # el rect del panel se calcula sobre el tamaño REAL de "scene" —
        # nunca el tamaño de dispositivo crudo. Con `_render_scale` < 1.0
        # (GOBERNADOR DE RENDER, THINKING) "scene" es más chica que el
        # dispositivo; usar `_device_size()` aquí desincronizaba el
        # `glViewport` de abajo del tamaño real del framebuffer donde se
        # aplica — el resultado era un rect mal recortado (visto como una
        # franja horizontal rota en la captura de FASE D con THINKING).
        scene_w, scene_h = self._fbos["scene"].width(), self._fbos["scene"].height()
        x0, y0, pw, ph = self._glass_pixel_rect(scene_w, scene_h)
        if pw < 8 or ph < 8:
            return  # panel casi invisible (colapsando/animando) — no vale la pena
        gw, gh = self._ensure_glass_fbo(pw, ph)

        due = (self._time - self._glass_last_update) >= self._glass_interval_s
        if due:
            self._glass_last_update = self._time
            scene = self._fbos["scene"]
            glass_fbo = self._fbos["glass"]
            glass_fbo.bind()
            self._gl.glViewport(0, 0, gw, gh)
            p = self._programs["glass_blur"]
            p.maybe_reload()
            p.bind()
            self._bind_texture(p, "u_source", 0, scene.texture())
            # UV bottom-up del rect dentro de `scene` (misma conversión
            # que `_glass_pixel_rect`, pero en UV 0..1 en vez de píxeles).
            rect_min_v = 1.0 - self._glass_rect[1] - self._glass_rect[3]
            p.set_uniform("u_rectMin", self._glass_rect[0], rect_min_v)
            p.set_uniform("u_rectSize", self._glass_rect[2], self._glass_rect[3])
            p.set_uniform("u_texel", 1.0 / scene.width(), 1.0 / scene.height())
            self._draw_fullscreen()
            p.release()
            glass_fbo.release()

        scene = self._fbos["scene"]
        scene.bind()
        self._gl.glViewport(x0, y0, pw, ph)
        ap = self._programs["glass_apply"]
        ap.maybe_reload()
        ap.bind()
        self._bind_texture(ap, "u_glass", 0, self._fbos["glass"].texture())
        self._draw_fullscreen()
        ap.release()
        scene.release()

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
        # El bloom/rayos se muestrean con GL_LINEAR (ver `_set_fbo_linear`):
        # con el filtro nearest anterior, 0.9/0.7 se veía bien porque los
        # texels brillantes quedaban concentrados; al difuminarlos de verdad,
        # esos mismos valores lavaban los filamentos del orbe. 0.55/0.35
        # conserva el detalle y mantiene el glow exterior.
        p.set_uniform("u_bloomStrength", 0.55)
        p.set_uniform("u_streakStrength", 0.5 if self._settings.streak_enabled else 0.0)
        p.set_uniform("u_godrayStrength", 0.35)
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

    # fps objetivo por estado (GOBERNADOR DE RENDER) — diagnóstico con
    # Ollama real + pidstat: el cuello es CPU de 2 núcleos físicos
    # compartidos con Ollama, no la calidad de sombreado; a 60fps LOW el
    # propio proceso + el compositor sumaban ~99% de UN núcleo completo,
    # a 15fps bajaba a ~51% — el fps SÍ es la palanca que mueve la aguja.
    _FPS_BY_STATE = {
        OrbState.THINKING: 24,   # el LLM está generando — máxima prioridad para Ollama
        OrbState.LISTENING: 60,  # fluidez real mientras el usuario habla
        OrbState.SPEAKING: 45,   # el LLM ya terminó; el TTS puede seguir pesando en CPU
        OrbState.IDLE: 30,
        OrbState.ERROR: 30,
    }

    def _current_fps(self) -> int:
        if not self._window_focused:
            return 15
        return self._FPS_BY_STATE.get(self._state, 30)

    def _sync_timer(self) -> None:
        should_run = self.isVisible() and not self._paused
        if not should_run:
            if self._frame_timer.isActive():
                self._frame_timer.stop()
            return
        interval = max(1, round(1000 / self._current_fps()))
        # `QTimer.start(ms)` en un timer YA activo lo reinicia con el
        # nuevo intervalo — sin este chequeo, un cambio de estado que
        # sólo debía CAMBIAR el fps (p.ej. IDLE 30 -> THINKING 24) nunca
        # se aplicaba porque `isActive()` ya era `True` de antes.
        if not self._frame_timer.isActive() or self._frame_timer.interval() != interval:
            self._frame_timer.start(interval)
