"""Modelo de la consola conversacional.

`ConversationModel` es un `QAbstractListModel` de *turnos*. Lo alimenta
`ChatService` (no el núcleo): añade el turno del usuario, abre un turno de
JARVIS vacío, le va anexando tokens según llegan del stream y lo cierra con los
metadatos reales (latencia, tokens/s). Un turno con `streaming=True` dibuja el
cursor de bloque; al cerrarse, desaparece.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot

_ROLE_BASE = Qt.UserRole + 1
ROLE_CHANNEL = _ROLE_BASE + 0      # "user" | "jarvis"
ROLE_TEXT = _ROLE_BASE + 1
ROLE_TIMESTAMP = _ROLE_BASE + 2
ROLE_STREAMING = _ROLE_BASE + 3
ROLE_META = _ROLE_BASE + 4        # p.ej. "820 ms · 14.2 tok/s"
ROLE_KIND = _ROLE_BASE + 5        # "chat" | "tool" | "error"


class ConversationModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._turns: list[dict] = []

    # ── API Qt ────────────────────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._turns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._turns)):
            return None
        t = self._turns[index.row()]
        return {
            ROLE_CHANNEL: t["channel"],
            ROLE_TEXT: t["text"],
            ROLE_TIMESTAMP: t["ts"],
            ROLE_STREAMING: t["streaming"],
            ROLE_META: t["meta"],
            ROLE_KIND: t["kind"],
        }.get(role)

    def roleNames(self):
        return {
            ROLE_CHANNEL: b"channel",
            ROLE_TEXT: b"body",
            ROLE_TIMESTAMP: b"timestamp",
            ROLE_STREAMING: b"streaming",
            ROLE_META: b"meta",
            ROLE_KIND: b"kind",
        }

    # ── API para ChatService (hilo de la GUI vía QueuedConnection) ─────────
    @staticmethod
    def _now() -> str:
        return time.strftime("%H:%M:%S")

    @Slot(str)
    def add_user(self, text: str) -> None:
        self._append("user", text, streaming=False, kind="chat")

    @Slot()
    def begin_assistant(self) -> None:
        self._append("jarvis", "", streaming=True, kind="chat")

    @Slot(str)
    def append_token(self, token: str) -> None:
        if not self._turns or not self._turns[-1]["streaming"]:
            return
        self._turns[-1]["text"] += token
        row = len(self._turns) - 1
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [ROLE_TEXT])

    @Slot(str, str, str)
    def end_assistant(self, full_text: str, meta: str, kind: str = "chat") -> None:
        if not self._turns or not self._turns[-1]["streaming"]:
            self._append("jarvis", full_text, streaming=False, kind=kind, meta=meta)
            return
        t = self._turns[-1]
        if full_text:
            t["text"] = full_text
        t["streaming"] = False
        t["meta"] = meta
        t["kind"] = kind
        row = len(self._turns) - 1
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx,
                              [ROLE_TEXT, ROLE_STREAMING, ROLE_META, ROLE_KIND])

    @Slot(str)
    def add_error(self, message: str) -> None:
        if self._turns and self._turns[-1]["streaming"]:
            self.end_assistant(message, "", "error")
        else:
            self._append("jarvis", message, streaming=False, kind="error")

    @Slot()
    def clear(self) -> None:
        self.beginResetModel()
        self._turns.clear()
        self.endResetModel()

    # ── interno ──────────────────────────────────────────────────────────
    def _append(self, channel, text, *, streaming, kind, meta="") -> None:
        row = len(self._turns)
        self.beginInsertRows(QModelIndex(), row, row)
        self._turns.append({
            "channel": channel, "text": text, "ts": self._now(),
            "streaming": streaming, "meta": meta, "kind": kind,
        })
        self.endInsertRows()
