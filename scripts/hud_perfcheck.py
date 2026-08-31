"""Medición del presupuesto de rendimiento de la vista (addendum §7).

    python scripts/hud_perfcheck.py [segundos] [--full]

  · con foco  : ~60 fps estables (lo trabaja la GPU)
  · sin foco  : bucle detenido → 0 fps (verificado, no asumido)
  · RSS       : estable (±5 MB en 10 min; aquí se mide un tramo y se reporta)
  · degradación: si el backend es software o los fps caen <40 durante 3 s se
                 desactivan bloom y atmósfera. `--full` fuerza el pipeline
                 completo (perfOverride=-1) para medirlo aunque sea software.

Sin `QT_QPA_PLATFORM` fijado usa `offscreen` (no abre ventana); en offscreen el
backend es software y por tanto se mide la RUTA DE DEGRADACIÓN. Para medir en
GPU real: `QT_QPA_PLATFORM=wayland python scripts/hud_perfcheck.py --full`.
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QObject, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

FULL = "--full" in sys.argv
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
DURATION = float(_args[0]) if _args else 40.0


def _by_name(root, name):
    for o in root.findChildren(QObject):
        if o.objectName() == name:
            return o
    raise SystemExit(f"no se encontró '{name}'")


def main() -> int:
    import psutil

    from jarvis_local.ui.hud.app import create_engine
    from jarvis_local.ui.hud.viewmodel import ViewModel
    proc = psutil.Process()

    app = QGuiApplication([])
    engine = create_engine(app, ViewModel())
    win = engine.rootObjects()[0]
    root = _by_name(win, "rootItem")
    loop = _by_name(win, "coreLoop")

    if FULL:
        root.setProperty("perfOverride", -1)

    ticks = {"n": 0}
    loop.triggered.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))

    r = {"marks": []}
    mb = 1024 * 1024

    def phase_focused():
        time.sleep(1.0)                        # deja pasar el ramp de arranque
        proc.cpu_percent(None)
        r["degraded"] = bool(root.property("degraded"))
        r["sw"] = bool(root.property("_softwareBackend"))
        ticks["n"] = 0
        r["t0"] = time.monotonic()
        mk = QTimer()
        mk.timeout.connect(lambda: r["marks"].append(proc.memory_info().rss / mb))
        mk.start(10000)
        r["mk"] = mk
        QTimer.singleShot(int(DURATION * 1000), phase_done_focused)

    def phase_done_focused():
        r["mk"].stop()
        r["fps_focused"] = ticks["n"] / (time.monotonic() - r["t0"])
        r["cpu"] = proc.cpu_percent(None)
        root.setProperty("paused", True)       # simula perder el foco
        ticks["n"] = 0
        r["t1"] = time.monotonic()
        QTimer.singleShot(4000, phase_done_unfocused)

    def phase_done_unfocused():
        r["fps_unfocused"] = ticks["n"] / (time.monotonic() - r["t1"])
        app.quit()

    QTimer.singleShot(200, phase_focused)
    app.exec()
    engine._runtime.shutdown()  # noqa: SLF001

    stable = r["marks"][1:] if len(r["marks"]) > 2 else r["marks"]
    drift = (max(stable) - min(stable)) if stable else 0.0
    pipe = "COMPLETO (forzado)" if FULL else ("DEGRADADO" if r["degraded"] else "completo")
    print(f"plataforma Qt          : {os.environ.get('QT_QPA_PLATFORM', 'auto')}")
    print(f"backend software       : {r['sw']}")
    print(f"pipeline medido        : {pipe}")
    print(f"duración medición      : {DURATION:.0f} s")
    print(f"fps (con foco)         : {r['fps_focused']:.1f}   (objetivo ~60)")
    print(f"fps (sin foco)         : {r['fps_unfocused']:.2f}   (esperado 0)")
    print(f"CPU proceso            : {r['cpu']:.1f} %   (1 núcleo = 100 %)")
    print(f"RSS marcas (cada 10 s) : {' '.join(f'{m:.0f}' for m in r['marks'])} MB")
    print(f"deriva RSS             : {drift:+.2f} MB")
    ok = (r["fps_unfocused"] < 0.5 and abs(drift) < 5.0
          and r["fps_focused"] >= 25)
    print("RESULTADO              :", "OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
