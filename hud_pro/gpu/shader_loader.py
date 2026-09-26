"""Compila programas GLSL desde archivo con `QOpenGLShaderProgram` (clase
Qt, no OpenGL crudo) y, en modo dev, los recarga solos si el archivo cambia.

``JARVIS_HUD_DEV=1`` activa la recarga en caliente: cada `maybe_reload()`
(llamado una vez por frame desde `HoloStage`) compara el mtime de los
``.glsl``/``.vert``/``.frag`` contra la última compilación. Si cambiaron,
intenta recompilar a un programa NUEVO — sólo si compila y linkea limpio
reemplaza al anterior; un error de sintaxis mientras se edita en vivo no
tira el pipeline, se registra y se sigue con el programa que ya funcionaba.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .. import qt_compat

log = logging.getLogger("jarvis.hud_pro.gpu")

SHADERS_DIR = Path(__file__).resolve().parent / "shaders"


class ShaderCompileError(RuntimeError):
    pass


class ShaderProgram:
    """Un `QOpenGLShaderProgram` (vertex + fragment) más el mtime de sus
    fuentes, para poder decidir si hace falta recompilar."""

    def __init__(self, vert_name: str, frag_name: str) -> None:
        self._vert_path = SHADERS_DIR / vert_name
        self._frag_path = SHADERS_DIR / frag_name
        self._program = None
        self._mtimes: tuple[float, float] = (0.0, 0.0)
        self._dev = os.environ.get("JARVIS_HUD_DEV", "") == "1"
        self._compile(initial=True)

    @property
    def qt_program(self):
        return self._program

    def _source_mtimes(self) -> tuple[float, float]:
        try:
            return (self._vert_path.stat().st_mtime, self._frag_path.stat().st_mtime)
        except OSError:
            return self._mtimes

    def _compile(self, initial: bool = False) -> None:
        QtOpenGL = qt_compat.QtOpenGL
        prog = QtOpenGL.QOpenGLShaderProgram()
        ok_v = prog.addShaderFromSourceFile(
            QtOpenGL.QOpenGLShader.ShaderTypeBit.Vertex, str(self._vert_path))
        ok_f = prog.addShaderFromSourceFile(
            QtOpenGL.QOpenGLShader.ShaderTypeBit.Fragment, str(self._frag_path))
        if not (ok_v and ok_f) or not prog.link():
            msg = f"{self._vert_path.name}/{self._frag_path.name}: {prog.log().strip()}"
            if initial:
                raise ShaderCompileError(msg)
            log.error("hot-reload de shader falló, se conserva el programa anterior: %s", msg)
            return
        self._program = prog
        self._mtimes = self._source_mtimes()

    def maybe_reload(self) -> bool:
        """Sólo hace algo si JARVIS_HUD_DEV=1. Devuelve True si recargó."""
        if not self._dev:
            return False
        current = self._source_mtimes()
        if current == self._mtimes:
            return False
        before = self._program
        self._compile(initial=False)
        return self._program is not before

    def bind(self) -> None:
        self._program.bind()

    def release(self) -> None:
        self._program.release()

    def set_uniform(self, name: str, *value) -> None:
        loc = self._program.uniformLocation(name)
        if loc < 0:
            return
        if len(value) == 1:
            v = value[0]
            if isinstance(v, bool):
                self._program.setUniformValue(loc, int(v))
            elif isinstance(v, int):
                self._program.setUniformValue(loc, v)
            elif isinstance(v, float):
                # `QOpenGLShaderProgram.setUniformValue(loc, <float>)` está
                # roto en esta versión de PySide6: el valor llega a 0.0 EN
                # EL SHADER siempre, sin lanzar excepción ni avisar — se
                # detectó comparando el resultado real en pantalla (nada
                # se animaba pese a que `u_time` sí avanzaba del lado
                # Python; confirmado aislado con un shader mínimo:
                # `setUniformValue` da 0.0, `glUniform1f` crudo da el
                # valor correcto). Los overloads vec2/vec3/vec4 e int SÍ
                # funcionan bien — sólo el escalar float usa la ruta cruda.
                qt_compat.QtGui.QOpenGLContext.currentContext().functions().glUniform1f(loc, v)
            else:
                self._program.setUniformValue(loc, v)
        elif len(value) == 2:
            self._program.setUniformValue(loc, float(value[0]), float(value[1]))
        elif len(value) == 3:
            self._program.setUniformValue(loc, float(value[0]), float(value[1]), float(value[2]))
        elif len(value) == 4:
            self._program.setUniformValue(
                loc, float(value[0]), float(value[1]), float(value[2]), float(value[3]))

    def set_uniform_array(self, name: str, values: list) -> None:
        """`uniform float name[N]` — FASE C (espectro real en el anillo)."""
        loc = self._program.uniformLocation(name)
        if loc < 0:
            return
        floats = [float(v) for v in values]
        self._program.setUniformValueArray(loc, floats, len(floats), 1)
