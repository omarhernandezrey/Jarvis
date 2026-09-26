"""Compila programas GLSL desde archivo con `QOpenGLShaderProgram` (clase
Qt, no OpenGL crudo) y, en modo dev, los recarga solos si el archivo cambia.

``JARVIS_HUD_DEV=1`` activa la recarga en caliente: cada `maybe_reload()`
(llamado una vez por frame desde `HoloStage`) compara el mtime de los
``.glsl``/``.vert``/``.frag`` contra la última compilación. Si cambiaron,
intenta recompilar a un programa NUEVO — sólo si compila y linkea limpio
reemplaza al anterior; un error de sintaxis mientras se edita en vivo no
tira el pipeline, se registra y se sigue con el programa que ya funcionaba.

Envío de uniforms — auditoría completa (2026-09-26)
====================================================
`QOpenGLShaderProgram.setUniformValue(loc, <float de Python>)` para un
escalar SUELTO está roto en esta versión de PySide6: el valor queda en
0.0 dentro del shader, sin lanzar ninguna excepción ni avisar de ningún
modo (confirmado aislado con un shader de una sola línea). Se auditaron
TODOS los overloads que este módulo usa, comparando `setUniformValue`
contra el `glUniform*` crudo equivalente, leyendo el resultado real
pintado en un framebuffer (no `glGetUniformfv`/`glGetUniformiv`: esta
build de PySide6 no escribe de vuelta en la lista/array de Python que se
le pasa como parámetro de salida — se probó con `list`, `array.array` y
un `VoidPtr` sobre un buffer `ctypes`, ninguno funciona; ver
`test/test_hud_pro_gpu.py::test_scalar_float_uniform_actually_reaches_the_shader`
para el método de verificación real que sí funciona).

Resultado de la auditoría (float/int/bool/vec2/vec3/vec4 — no hay
uniforms `mat*` en ningún shader de este proyecto todavía):
  - float escalar: `setUniformValue` ROTO → usa `glUniform1f`.
  - int escalar / bool: `setUniformValue` funciona bien, pero se pasó
    igualmente a `glUniform1i` crudo por consistencia — un solo camino
    para las cuatro variantes, sin depender de qué overload de
    `setUniformValue` decida resolver shiboken en cada caso.
  - vec2/vec3/vec4: `setUniformValue` funciona bien → se pasaron a
    `glUniform2f/3f/4f` crudos por la misma razón de consistencia.
  - array de floats (`uniform float x[N]`): `setUniformValueArray`
    funciona bien, pero se cambió a `glUniform1fv` crudo (acepta una
    lista de Python normal, sin necesitar `VoidPtr`) — mismo criterio.

En resumen: TODO el envío de uniforms de este módulo pasa por
`glUniform*` crudo, nunca por `QOpenGLShaderProgram.setUniformValue*`.
Las locations se cachean por nombre (se invalida el caché en cada
recompilación, ya que un programa nuevo puede reasignarlas) — evita
llamar a `uniformLocation()` en cada frame para cada uniform. Con
``JARVIS_HUD_DEV=1``, la primera vez que una location cachea en -1 se
registra un aviso (una sola vez por nombre): puede ser un typo del lado
Python, o un uniform declarado pero optimizado fuera por no usarse en el
shader — cualquiera de los dos vale la pena revisar en desarrollo, pero
no tiene sentido interrumpir producción por eso.
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
        self._loc_cache: dict[str, int] = {}
        self._warned_missing: set[str] = set()
        self._gl_funcs = None
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
        # un programa nuevo puede reasignar locations — nunca reutilizar
        # el caché de uno viejo.
        self._loc_cache.clear()
        self._warned_missing.clear()

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

    def _functions(self):
        """`QOpenGLFunctions` del contexto actual — se cachea una vez por
        instancia (el contexto de un `ShaderProgram` no cambia en su vida)."""
        if self._gl_funcs is None:
            ctx = qt_compat.QtGui.QOpenGLContext.currentContext()
            self._gl_funcs = ctx.functions()
        return self._gl_funcs

    def _location(self, name: str) -> int:
        loc = self._loc_cache.get(name)
        if loc is None:
            loc = self._program.uniformLocation(name)
            self._loc_cache[name] = loc
            if loc < 0 and self._dev and name not in self._warned_missing:
                self._warned_missing.add(name)
                log.warning(
                    "uniform '%s' con location -1 en %s/%s — typo del lado "
                    "Python, o declarado pero optimizado fuera por no "
                    "usarse en el shader.",
                    name, self._vert_path.name, self._frag_path.name,
                )
        return loc

    def set_uniform(self, name: str, *value) -> None:
        """Despacha por tipo/aridad a `glUniform*` crudo — nunca
        `QOpenGLShaderProgram.setUniformValue*` (ver auditoría al inicio
        del archivo: el overload de escalar float de esa API está roto en
        esta versión de PySide6, así que todo pasa por el mismo camino
        crudo por consistencia, no sólo el caso que falla)."""
        loc = self._location(name)
        if loc < 0:
            return
        gl = self._functions()
        if len(value) == 1:
            v = value[0]
            if isinstance(v, bool):
                gl.glUniform1i(loc, int(v))
            elif isinstance(v, int):
                gl.glUniform1i(loc, v)
            elif isinstance(v, float):
                gl.glUniform1f(loc, v)
            else:
                raise TypeError(f"set_uniform: tipo no soportado para '{name}': {type(v)!r}")
        elif len(value) == 2:
            gl.glUniform2f(loc, float(value[0]), float(value[1]))
        elif len(value) == 3:
            gl.glUniform3f(loc, float(value[0]), float(value[1]), float(value[2]))
        elif len(value) == 4:
            gl.glUniform4f(loc, float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        else:
            raise ValueError(f"set_uniform: {len(value)} componentes no soportado para '{name}'")

    def set_uniform_array(self, name: str, values: list) -> None:
        """`uniform float name[N]` — FASE C (espectro real en el anillo)."""
        loc = self._location(name)
        if loc < 0:
            return
        floats = [float(v) for v in values]
        self._functions().glUniform1fv(loc, len(floats), floats)
