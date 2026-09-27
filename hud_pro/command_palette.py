"""FASE D — paleta de comandos (Ctrl+Shift+P): acciones reales, nunca
decorativas — cada entrada llama directo a un método/señal que ya existe
en `HudWindow` (nueva conversación, silenciar, memoria, consola, modo
enfoque…), el mismo camino que ya usan los botones/atajos existentes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .qt_compat import Qt, QtCore, QtGui, QtWidgets


@dataclass(frozen=True)
class Command:
    title: str
    hint: str
    action: Callable[[], None]


class CommandPalette(QtWidgets.QWidget):
    closed = QtCore.Signal()

    def __init__(self, commands: list[Command], parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandPalette")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._commands = commands
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        box = QtWidgets.QFrame(self)
        box.setObjectName("ChatPanel")
        box.setFixedWidth(480)
        box_lay = QtWidgets.QVBoxLayout(box)
        box_lay.setContentsMargins(12, 12, 12, 12)
        box_lay.setSpacing(8)

        self._input = QtWidgets.QLineEdit(box)
        self._input.setObjectName("ChatInput")
        self._input.setPlaceholderText("Escribe un comando…")
        self._input.textChanged.connect(self._filter)
        box_lay.addWidget(self._input)

        self._list = QtWidgets.QListWidget(box)
        self._list.setObjectName("ActivityList")
        self._list.setFixedHeight(260)
        self._list.itemActivated.connect(lambda _item: self._run_selected())
        box_lay.addWidget(self._list)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(box)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(3)

        self._populate("")
        self.hide()

    def open(self) -> None:
        self._input.clear()
        self._populate("")
        self.show()
        self.raise_()
        self._input.setFocus(Qt.FocusReason.PopupFocusReason)

    def _populate(self, query: str) -> None:
        q = query.strip().lower()
        self._list.clear()
        for cmd in self._commands:
            if q and q not in cmd.title.lower() and q not in cmd.hint.lower():
                continue
            item = QtWidgets.QListWidgetItem(f"{cmd.title}   —   {cmd.hint}")
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _filter(self, text: str) -> None:
        self._populate(text)

    def _run_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        cmd: Command = item.data(Qt.ItemDataRole.UserRole)
        self._close()
        cmd.action()

    def _close(self) -> None:
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._close()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._run_selected()
            return
        if event.key() == Qt.Key.Key_Down:
            self._list.setCurrentRow(min(self._list.count() - 1, self._list.currentRow() + 1))
            return
        if event.key() == Qt.Key.Key_Up:
            self._list.setCurrentRow(max(0, self._list.currentRow() - 1))
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        # clic fuera de la caja central = cerrar (mismo gesto que cualquier overlay modal)
        self._close()
