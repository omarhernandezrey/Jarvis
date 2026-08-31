"""Medición del presupuesto de rendimiento de la vista (Fase 7).

Uso:
    QT_QPA_PLATFORM=offscreen python scripts/hud_perfcheck.py [segundos]

Reporta, en IDLE:
  - fps efectivo del único FrameAnimation (techo esperado: 30)
  - fps con la ventana "inactiva" (esperado: 0)
  - CPU% del proceso
  - deriva de RSS sobre la ventana de medición (esperado: ±5 MB en 10 min)

La ejecución completa de 10 min la hace el usuario en pantalla real; este script
sirve como proxy rápido y como comprobación empírica del 0 fps sin foco.
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QObject, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from jarvis_local.ui.hud.app import create_engine  # noqa: E402
from jarvis_local.ui.hud.viewmodel import ViewModel  # noqa: E402

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 45.0


def _core_loop(root):
    for o in root.findChildren(QObject):
        if o.objectName() == "coreLoop":
            return o
    raise SystemExit("no se encontró el bucle del núcleo")


def main() -> int:
    import psutil
    proc = psutil.Process()

    app = QGuiApplication([])
    engine = create_engine(app, ViewModel())
    win = engine.rootObjects()[0]
    fa = _core_loop(win)

    ticks = {"n": 0}
    fa.triggered.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))

    r = {"marks": []}
    mb = 1024 * 1024

    def phase_focused():
        proc.cpu_percent(None)
        time.sleep(1.0)                       # deja pasar el ramp de arranque
        r["rss0"] = proc.memory_info().rss
        ticks["n"] = 0
        r["t0"] = time.monotonic()
        mark = QTimer()
        mark.timeout.connect(lambda: r["marks"].append(proc.memory_info().rss / mb))
        mark.start(10000)
        r["mark"] = mark
        QTimer.singleShot(int(DURATION * 1000), phase_done_focused)

    def phase_done_focused():
        r["mark"].stop()
        dt = time.monotonic() - r["t0"]
        r["fps_focused"] = ticks["n"] / dt
        r["cpu"] = proc.cpu_percent(None)
        r["rss1"] = proc.memory_info().rss
        _set_inactive(win)                    # loopRunning=false → 0 fps
        ticks["n"] = 0
        r["t1"] = time.monotonic()
        QTimer.singleShot(4000, phase_done_unfocused)

    def phase_done_unfocused():
        r["fps_unfocused"] = ticks["n"] / (time.monotonic() - r["t1"])
        app.quit()

    def _set_inactive(w):
        for o in w.findChildren(QObject):
            if "CoreField" in o.metaObject().className():
                o.setProperty("loopRunning", False)
                return

    QTimer.singleShot(200, phase_focused)
    app.exec()
    engine._runtime.shutdown()  # noqa: SLF001

    # deriva real = oscilación entre marcas estables (ignora el ramp de arranque)
    stable = r["marks"][1:] if len(r["marks"]) > 2 else r["marks"]
    drift = (max(stable) - min(stable)) if stable else (r["rss1"] - r["rss0"]) / mb
    print(f"plataforma Qt          : {os.environ.get('QT_QPA_PLATFORM', 'auto')}")
    print(f"duración medición      : {DURATION:.0f} s")
    print(f"fps (con foco)         : {r['fps_focused']:.1f}  (techo 30)")
    print(f"fps (sin foco)         : {r['fps_unfocused']:.2f}  (esperado 0)")
    print(f"CPU proceso            : {r['cpu']:.1f} %  (1 núcleo = 100 %)")
    print(f"RSS marcas (cada 10 s) : {' '.join(f'{m:.0f}' for m in r['marks'])} MB")
    print(f"deriva RSS             : {drift:+.2f} MB en {DURATION:.0f} s")
    ok = (r["fps_focused"] <= 31 and r["fps_unfocused"] < 0.5 and abs(drift) < 5.0)
    print("RESULTADO              :", "OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
