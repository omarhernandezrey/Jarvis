"""Ventana aislada del núcleo (addendum, fase 2) — valida la dirección visual
del shader antes de invertir en el resto.

    python scripts/core_preview.py            # ventana en vivo (teclas 1-6, ESC)
    python scripts/core_preview.py --grab     # renderiza un PNG por estado

Necesita GPU real (ShaderEffect no funciona con el backend 'software').
"""
from __future__ import annotations

import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_GRAB = "--grab" in sys.argv
_QML_DIR = os.path.join(_ROOT, "jarvis_local", "ui", "hud", "qml")
_QML = os.path.join(_QML_DIR, "CorePreview.qml")
_OUT = os.path.join(_ROOT, "scratch_preview")

STATES = ["idle", "listening", "thinking", "speaking", "alert", "offline"]


def main() -> int:
    from PySide6.QtCore import Qt, QTimer, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView

    app = QGuiApplication(sys.argv)
    view = QQuickView()
    view.engine().addImportPath(_QML_DIR)
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.setColor(Qt.black)
    view.setSource(QUrl.fromLocalFile(_QML))
    if view.status() != QQuickView.Ready:
        for e in view.errors():
            print(e.toString())
        return 1

    print("[preview] sceneGraphBackend:", QQuickView.sceneGraphBackend())
    root = view.rootObject()
    view.resize(760, 760)

    if not _GRAB:
        view.show()
        return app.exec()

    os.makedirs(_OUT, exist_ok=True)
    view.show()
    idx = {"i": 0}

    def shot():
        if idx["i"] >= len(STATES):
            app.quit()
            return
        st = STATES[idx["i"]]
        root.setProperty("coreState", st)
        for _ in range(40):
            app.processEvents()
            time.sleep(0.016)
        img = view.grabWindow()
        path = os.path.join(_OUT, f"core_{idx['i']}_{st}.png")
        ok = img.save(path)
        print(f"  {st:10s} -> {path}  ({'ok' if ok else 'FALLO'}, "
              f"{img.width()}x{img.height()})")
        idx["i"] += 1
        QTimer.singleShot(50, shot)

    QTimer.singleShot(400, shot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
