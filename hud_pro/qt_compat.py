"""Capa de compatibilidad Qt: PySide6 → PyQt6 → PyQt5.

Forzar un binding concreto: variable de entorno ``QT_API`` = pyside6 | pyqt6 | pyqt5.
Todo el paquete importa Qt SOLO desde aquí.
"""

from __future__ import annotations

import os
from typing import Any

_REQUESTED = os.environ.get("QT_API", "").strip().lower()
_ORDER = [_REQUESTED] if _REQUESTED else ["pyside6", "pyqt6", "pyqt5"]

QT_API: str = ""
_errors: list[str] = []

for _api in _ORDER:
    try:
        if _api == "pyside6":
            from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[no-redef]

            Signal = QtCore.Signal
            Slot = QtCore.Slot
        elif _api == "pyqt6":
            from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore[no-redef]

            Signal = QtCore.pyqtSignal  # type: ignore[attr-defined]
            Slot = QtCore.pyqtSlot  # type: ignore[attr-defined]
        elif _api == "pyqt5":
            from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore[no-redef]

            Signal = QtCore.pyqtSignal  # type: ignore[attr-defined]
            Slot = QtCore.pyqtSlot  # type: ignore[attr-defined]
        else:
            raise ImportError(f"QT_API desconocido: {_api!r}")
        QT_API = _api
        break
    except ImportError as exc:  # pragma: no cover - depende del entorno
        _errors.append(f"{_api}: {exc}")
else:  # pragma: no cover
    raise ImportError("No se encontró binding Qt (PySide6, PyQt6 o PyQt5). Detalle: " + " | ".join(_errors))

IS_QT5 = QT_API == "pyqt5"

Qt = QtCore.Qt


def exec_app(app: Any) -> int:
    """Ejecuta el event loop de forma compatible (exec vs exec_)."""
    runner = getattr(app, "exec", None) or app.exec_
    return int(runner())


def enable_high_dpi() -> None:
    """Qt6 ya escala por defecto; en Qt5 hay que activarlo antes de crear QApplication."""
    if IS_QT5:
        QtCore.QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        QtCore.QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)


__all__ = [
    "QT_API",
    "IS_QT5",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Qt",
    "Signal",
    "Slot",
    "exec_app",
    "enable_high_dpi",
]
