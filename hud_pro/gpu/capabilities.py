"""Detección real de capacidades OpenGL — nunca asumida, siempre medida.

`detect()` crea un `QOpenGLContext` + `QOffscreenSurface` reales (el mismo
combo que usan los tests bajo `QT_QPA_PLATFORM=offscreen`: a diferencia de
`QOpenGLWidget`, que Qt marca explícitamente como "not supported" en ese
backend, un contexto + superficie offscreen sí negocia un contexto real en
cualquier backend). Eso basta para leer vendor/renderer/versión/extensiones
— exactamente lo que hace falta para decidir si vale la pena intentar
`HoloStage`, sin necesitar una ventana visible todavía.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import qt_compat
from ..qt_compat import QtCore, QtGui


@dataclass
class GLCapabilities:
    """Resultado de una detección real. `available=False` + `error` si algo
    falló — nunca se rellenan campos con un valor inventado."""

    available: bool
    vendor: str = ""
    renderer: str = ""
    gl_version: str = ""
    glsl_version: str = ""
    major: int = 0
    minor: int = 0
    profile: str = ""
    has_fbo: bool = False
    has_timer_query: bool = False
    has_disjoint_timer_query: bool = False
    error: str = ""
    extensions: set = field(default_factory=set)

    def summary(self) -> str:
        if not self.available:
            return f"GPU no disponible: {self.error}"
        return (
            f"{self.vendor} — {self.renderer}\n"
            f"OpenGL {self.gl_version} ({self.profile})  ·  GLSL {self.glsl_version}\n"
            f"FBO={self.has_fbo}  timer_query={self.has_timer_query}"
            f"{' (ARB)' if self.has_timer_query else ''}"
            f"{'  disjoint_timer_query (EXT)' if self.has_disjoint_timer_query else ''}"
        )


_GL_VENDOR = 0x1F00
_GL_RENDERER = 0x1F01
_GL_VERSION = 0x1F02
_GL_SHADING_LANGUAGE_VERSION = 0x8B8C

_PROFILE_NAMES = {
    QtGui.QSurfaceFormat.OpenGLContextProfile.NoProfile: "sin perfil",
    QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile: "core",
    QtGui.QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile: "compatibility",
}


def _min_format(major: int = 3, minor: int = 3) -> QtGui.QSurfaceFormat:
    fmt = QtGui.QSurfaceFormat()
    fmt.setVersion(major, minor)
    fmt.setProfile(QtGui.QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setRenderableType(QtGui.QSurfaceFormat.RenderableType.OpenGL)
    return fmt


def detect(min_major: int = 3, min_minor: int = 3) -> GLCapabilities:
    """Crea un contexto GL real (offscreen), lo hace corriente y lee sus
    capacidades. Requiere una QGuiApplication/QApplication ya viva — si no
    la hay, `available=False` con el motivo, nunca lanza."""
    if qt_compat.QtOpenGL is None:
        return GLCapabilities(available=False, error="binding sin módulo QtOpenGL")

    app = QtGui.QGuiApplication.instance()
    if app is None:
        return GLCapabilities(available=False, error="sin QGuiApplication/QApplication activa")

    fmt = _min_format(min_major, min_minor)
    surface = QtGui.QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid():
        return GLCapabilities(available=False, error="QOffscreenSurface no válida en este backend")

    ctx = QtGui.QOpenGLContext()
    ctx.setFormat(fmt)
    if not ctx.create():
        surface.destroy()
        return GLCapabilities(available=False, error="QOpenGLContext.create() falló")

    if not ctx.makeCurrent(surface):
        surface.destroy()
        return GLCapabilities(available=False, error="makeCurrent() falló sobre la superficie offscreen")

    try:
        f = ctx.functions()
        negotiated = ctx.format()
        caps = GLCapabilities(
            available=True,
            vendor=str(f.glGetString(_GL_VENDOR) or ""),
            renderer=str(f.glGetString(_GL_RENDERER) or ""),
            gl_version=str(f.glGetString(_GL_VERSION) or ""),
            glsl_version=str(f.glGetString(_GL_SHADING_LANGUAGE_VERSION) or ""),
            major=negotiated.majorVersion(),
            minor=negotiated.minorVersion(),
            profile=_PROFILE_NAMES.get(negotiated.profile(), str(negotiated.profile())),
            has_fbo=ctx.hasExtension(b"GL_ARB_framebuffer_object") or negotiated.majorVersion() >= 3,
            has_timer_query=ctx.hasExtension(b"GL_ARB_timer_query"),
            has_disjoint_timer_query=ctx.hasExtension(b"GL_EXT_disjoint_timer_query"),
        )
        if (caps.major, caps.minor) < (min_major, min_minor):
            caps.available = False
            caps.error = (
                f"OpenGL {caps.major}.{caps.minor} negociado, se necesita "
                f">= {min_major}.{min_minor} para el pipeline multipasada"
            )
        return caps
    finally:
        ctx.doneCurrent()
        surface.destroy()


def qopenglwidget_supported_here() -> tuple[bool, str]:
    """`QOpenGLWidget` necesita compositar sobre un FBO propio del widget:
    en el backend `offscreen` de Qt eso no está soportado (Qt lo avisa por
    stderr: "QOpenGLWidget is not supported on this platform") aunque el
    CONTEXTO GL subyacente sí funcione — `detect()` no lo ve porque prueba
    con QOffscreenSurface, no con el widget. Esta función existe para que
    el arranque real (no los tests) sepa distinguir los dos casos."""
    platform = QtCore.QCoreApplication.instance()
    name = platform.platformName() if platform is not None else ""
    if name == "offscreen":
        return False, "QOpenGLWidget no soporta el backend Qt 'offscreen' (confirmado por Qt)"
    return True, ""
