"""Arranque de la vista Qt Quick.

`main()` crea la QGuiApplication y el motor QML, carga `qml/Main.qml` y entra
en el bucle de eventos de Qt. En fases siguientes aquí se instancia el
ViewModel y se expone al contexto QML; por ahora solo levanta el lienzo del
sistema de diseño.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_QML_DIR = Path(__file__).parent / "qml"


def _configure_environment() -> None:
    """Ajustes previos a crear la QGuiApplication.

    - En sesión Wayland, Qt usa el plugin `wayland` si está; si no, cae a
      XWayland automáticamente. No forzamos plataforma para no romper el
      arranque en equipos sin el plugin wayland de Qt.
    - Escala de fuentes: dejamos que Qt siga el factor del sistema.
    """
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def create_engine(app):
    """Crea y devuelve el QQmlApplicationEngine ya con Main.qml cargado.

    Separado de `main()` para poder instanciarlo en tests sin `app.exec()`.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(_QML_DIR))
    engine.load(QUrl.fromLocalFile(str(_QML_DIR / "Main.qml")))
    return engine


def main() -> int:
    _configure_environment()

    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setOrganizationName("JARVIS")

    engine = create_engine(app)
    if not engine.rootObjects():
        print("[hud] No se pudo cargar la interfaz QML.", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
