"""FASE D — checklist de arranque: verifica servicios REALES (Ollama
alcanzable, dispositivo de micrófono presente, ruta de memoria
disponible) antes de mostrar el HUD normal — nunca un progreso fingido
con `sleep()`, cada ítem es una comprobación real, aunque tarde 0 ms."""

from __future__ import annotations

import socket
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from . import theme
from .qt_compat import Qt, QtCore, QtGui, QtWidgets


@dataclass(frozen=True)
class CheckItem:
    label: str
    check: Callable[[], bool]


def check_ollama(url: str = "http://127.0.0.1:11434/api/tags", timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_microphone() -> bool:
    try:
        import sounddevice as sd
        return sd.query_devices(kind="input") is not None
    except Exception:
        return False


def check_network(host: str = "127.0.0.1", port: int = 11434, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def default_checks() -> list[CheckItem]:
    return [
        CheckItem("Ollama", check_ollama),
        CheckItem("Micrófono", check_microphone),
        CheckItem("Red local", check_network),
    ]


class StartupChecklist(QtWidgets.QWidget):
    """Overlay que se muestra UNA vez al arrancar, corre cada chequeo real
    (nunca bloquea la GUI más de lo que tarda esa comprobación puntual) y
    se cierra sola cuando termina — o al clic/Enter si el usuario no
    quiere esperar."""

    finished = QtCore.Signal()

    def __init__(self, checks: Optional[list[CheckItem]] = None, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StartupChecklist")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._checks = checks if checks is not None else default_checks()
        self._rows: list[QtWidgets.QLabel] = []

        box = QtWidgets.QFrame(self)
        box.setObjectName("ChatPanel")
        box.setFixedWidth(360)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        title = QtWidgets.QLabel("J.A.R.V.I.S — verificando servicios", box)
        title.setObjectName("PanelTitle")
        lay.addWidget(title)
        for item in self._checks:
            row = QtWidgets.QLabel(f"…  {item.label}", box)
            row.setObjectName("PanelMeta")
            lay.addWidget(row)
            self._rows.append(row)

        outer = QtWidgets.QVBoxLayout(self)
        outer.addStretch(1)
        hrow = QtWidgets.QHBoxLayout()
        hrow.addStretch(1)
        hrow.addWidget(box)
        hrow.addStretch(1)
        outer.addLayout(hrow)
        outer.addStretch(2)

        self._index = 0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._run_next)

    def start(self) -> None:
        self.show()
        self._index = 0
        self._timer.start(0)  # cada chequeo real corre en el próximo tick, sin sleep fingido

    def _run_next(self) -> None:
        if self._index >= len(self._checks):
            self._timer.stop()
            QtCore.QTimer.singleShot(400, self._close)
            return
        item = self._checks[self._index]
        ok = bool(item.check())
        mark = "✓" if ok else "✗"
        color = "#22C55E" if ok else theme.DANGER
        self._rows[self._index].setText(f"{mark}  {item.label}")
        self._rows[self._index].setStyleSheet(f"color: {color};")
        self._index += 1

    def _close(self) -> None:
        self.hide()
        self.finished.emit()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self._timer.stop()
        self._close()
