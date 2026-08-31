"""Compila los shaders GLSL del HUD a `.qsb` con pyside6-qsb.

Uso:  python -m jarvis_local.ui.hud.shaders.build
Se ejecuta a mano cuando cambia un `.frag`/`.vert`; los `.qsb` se versionan.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).parent


def _qsb() -> str:
    exe = shutil.which("pyside6-qsb")
    if exe:
        return exe
    cand = Path(sys.executable).parent / "pyside6-qsb"
    if cand.exists():
        return str(cand)
    raise SystemExit("pyside6-qsb no encontrado (instala PySide6).")


def build() -> int:
    qsb = _qsb()
    n = 0
    for src in sorted(_HERE.glob("*.frag")) + sorted(_HERE.glob("*.vert")):
        out = src.with_suffix(src.suffix + ".qsb")
        cmd = [qsb, "--qt6", "-o", str(out), str(src)]
        print(" ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout + r.stderr)
            return r.returncode
        n += 1
    print(f"{n} shader(s) compilados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
