"""Consola de conversación: burbujas, markdown seguro, streaming y barra de entrada."""

from __future__ import annotations

import re
import time
from typing import Optional

from . import theme
from .qt_compat import IS_QT5, Qt, QtCore, QtGui, QtWidgets, Signal
from .widgets import make_icon

MAX_INPUT_CHARS = 4000
MAX_MESSAGES = 300
SUBMIT_MIN_INTERVAL_MS = 300
STREAM_RENDER_MS = 45

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ANCHOR_RE = re.compile(r'<a\s+href="([^"]*)"\s*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_SAFE_SCHEMES = ("http://", "https://")


# ── Sanitización ──────────────────────────────────────────────────────────
def sanitize_input(text: str) -> str:
    """Elimina caracteres de control, recorta espacios y limita longitud."""
    if not isinstance(text, str):
        return ""
    return _CONTROL_RE.sub("", text).strip()[:MAX_INPUT_CHARS]


def _markdown_features():
    td = QtGui.QTextDocument
    if IS_QT5:
        return td.MarkdownFeatures(td.MarkdownDialectGitHub | td.MarkdownNoHTML)
    mf = td.MarkdownFeature
    return mf.MarkdownDialectGitHub | mf.MarkdownNoHTML


def render_markdown_safe(text: str) -> str:
    """Markdown → HTML para QLabel sin HTML crudo, sin imágenes y solo enlaces http(s)."""
    doc = QtGui.QTextDocument()
    doc.setDefaultFont(theme.font(theme.FONT_UI, 14))
    doc.setMarkdown(text or "", _markdown_features())
    html = doc.toHtml()
    html = _IMG_RE.sub("", html)

    def _anchor(m: re.Match[str]) -> str:
        href, inner = m.group(1), m.group(2)
        if href.lower().startswith(_SAFE_SCHEMES):
            return f'<a href="{href}">{inner}</a>'
        return inner

    html = _ANCHOR_RE.sub(_anchor, html)
    html = html.replace("color:#0000ff;", f"color:{theme.ACCENT};")
    html = html.replace("font-family:'monospace';", f"font-family:'{theme.FONT_MONO}'; color:#BFE6FF;")
    return html


# ── Burbujas ──────────────────────────────────────────────────────────────
class MessageBubble(QtWidgets.QFrame):
    ROLES = ("user", "assistant", "system")

    def __init__(self, role: str, text: str = "", parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        if role not in self.ROLES:
            raise ValueError(f"Rol inválido: {role!r}")
        self.role = role
        self._raw = text or ""
        self._streaming = False
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render)

        self.setObjectName(
            {"user": "BubbleUser", "assistant": "BubbleAssistant", "system": "BubbleSystem"}[role]
        )
        lay = QtWidgets.QVBoxLayout(self)

        self.body = QtWidgets.QLabel(self)
        self.body.setWordWrap(True)
        self.body.setOpenExternalLinks(False)
        self.body.linkActivated.connect(self._open_link)
        self.body.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum)

        if role == "system":
            lay.setContentsMargins(0, 2, 0, 2)
            self.body.setObjectName("SystemText")
            self.body.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.body.setTextFormat(Qt.TextFormat.PlainText)
            lay.addWidget(self.body)
        else:
            lay.setContentsMargins(14, 9, 14, 11)
            lay.setSpacing(4)
            head = QtWidgets.QHBoxLayout()
            head.setSpacing(8)
            who = QtWidgets.QLabel("TÚ" if role == "user" else "JARVIS", self)
            who.setObjectName("BubbleRoleUser" if role == "user" else "BubbleRole")
            stamp = QtWidgets.QLabel(time.strftime("%H:%M"), self)
            stamp.setObjectName("BubbleTime")
            head.addWidget(who)
            head.addStretch(1)
            head.addWidget(stamp)
            lay.addLayout(head)
            self.body.setObjectName("BubbleBody")
            self.body.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            self.body.setTextFormat(Qt.TextFormat.PlainText if role == "user" else Qt.TextFormat.RichText)
            lay.addWidget(self.body)
        self._render()

    # API
    @property
    def text(self) -> str:
        return self._raw

    def append_text(self, chunk: str) -> None:
        if not chunk:
            return
        self._raw += chunk
        self._streaming = True
        if not self._render_timer.isActive():
            self._render_timer.start(STREAM_RENDER_MS)

    def finish(self) -> None:
        self._streaming = False
        self._render_timer.stop()
        self._render()

    # interno
    def _render(self) -> None:
        if self.role == "assistant":
            text = self._raw + (" ▍" if self._streaming else "")
            self.body.setText(render_markdown_safe(text))
        else:
            self.body.setText(self._raw)

    @staticmethod
    def _open_link(url: str) -> None:
        if url.lower().startswith(_SAFE_SCHEMES):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class ChatView(QtWidgets.QScrollArea):
    """Lista de mensajes con autoscroll inteligente (no roba el scroll si el usuario subió)."""

    STICK_THRESHOLD = 32

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.viewport().setObjectName("ChatViewport")
        self.viewport().setAutoFillBackground(False)

        self._list = QtWidgets.QWidget()
        self._list.setObjectName("MessageList")
        self._layout = QtWidgets.QVBoxLayout(self._list)
        self._layout.setContentsMargins(2, 6, 10, 6)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)  # mensajes anclados abajo, como una terminal
        self.setWidget(self._list)

        # estado vacío como overlay: no participa en el layout ni deja huecos
        self._empty = QtWidgets.QLabel("Sin mensajes todavía.\nEscribe abajo o di «Jarvis».", self)
        self._empty.setObjectName("EmptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._empty.raise_()

        self._bubbles: list[MessageBubble] = []
        self._stick = True
        bar = self.verticalScrollBar()
        bar.valueChanged.connect(self._on_scroll)
        bar.rangeChanged.connect(self._on_range)

    @property
    def bubbles(self) -> list[MessageBubble]:
        return list(self._bubbles)

    def add(self, role: str, text: str = "") -> MessageBubble:
        self._empty.setVisible(False)
        bubble = MessageBubble(role, text)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble, 1)
        holder = QtWidgets.QWidget(self._list)
        holder.setLayout(row)
        self._layout.addWidget(holder)
        self._bubbles.append(bubble)
        self._apply_widths(bubble)
        self._trim()
        return bubble

    def clear(self) -> None:
        for b in self._bubbles:
            holder = b.parentWidget()
            self._layout.removeWidget(holder)
            holder.deleteLater()
        self._bubbles.clear()
        self._empty.setVisible(True)
        self._stick = True

    def scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _trim(self) -> None:
        while len(self._bubbles) > MAX_MESSAGES:
            old = self._bubbles.pop(0)
            holder = old.parentWidget()
            self._layout.removeWidget(holder)
            holder.deleteLater()

    def _apply_widths(self, bubble: Optional[MessageBubble] = None) -> None:
        """Burbujas de usuario ajustadas al texto (evita el wrap estrecho de QLabel)."""
        width = self.viewport().width() - 14
        max_w = max(180, int(width * 0.78))
        targets = [bubble] if bubble else self._bubbles
        for b in targets:
            if b.role != "user":
                continue
            b.ensurePolished()
            b.body.ensurePolished()
            fm = b.body.fontMetrics()
            lines = b.text.splitlines() or [""]
            text_w = max(fm.horizontalAdvance(line) for line in lines)
            ideal = text_w + 28 + 6  # márgenes internos + holgura
            b.setFixedWidth(max(140, min(max_w, ideal)))

    def _on_scroll(self, value: int) -> None:
        bar = self.verticalScrollBar()
        self._stick = value >= bar.maximum() - self.STICK_THRESHOLD

    def _on_range(self, _min: int, _max: int) -> None:
        if self._stick:
            self.scroll_to_bottom()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._empty.setGeometry(self.viewport().geometry())
        self._apply_widths()


class InputBar(QtWidgets.QFrame):
    submitted = Signal(str)
    mic_toggled = Signal(bool)

    HISTORY = 50

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("InputBar")
        self.setProperty("focused", False)
        self.setFixedHeight(52)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 7, 7, 7)
        lay.setSpacing(8)

        self.mic = QtWidgets.QToolButton(self)
        self.mic.setObjectName("MicButton")
        self.mic.setCheckable(True)
        self.mic.setIcon(make_icon("mic", theme.ACCENT_2, 20))
        self.mic.setIconSize(QtCore.QSize(20, 20))
        self.mic.setFixedSize(38, 38)
        self.mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic.setToolTip("Micrófono  (Ctrl+M)")
        self.mic.setAccessibleName("Activar micrófono")
        self.mic.toggled.connect(self.mic_toggled.emit)

        self.edit = QtWidgets.QLineEdit(self)
        self.edit.setObjectName("ChatInput")
        self.edit.setPlaceholderText("Escribe un mensaje…   (Enter para enviar)")
        self.edit.setMaxLength(MAX_INPUT_CHARS)
        self.edit.setClearButtonEnabled(False)
        self.edit.setAccessibleName("Mensaje para JARVIS")
        self.edit.returnPressed.connect(self.submit)
        self.edit.textChanged.connect(self._on_text)
        self.edit.installEventFilter(self)

        self.send = QtWidgets.QToolButton(self)
        self.send.setObjectName("SendButton")
        self.send.setIcon(make_icon("send", "#04121F", 20))
        self.send.setIconSize(QtCore.QSize(20, 20))
        self.send.setFixedSize(38, 38)
        self.send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send.setToolTip("Enviar  (Enter)")
        self.send.setAccessibleName("Enviar mensaje")
        self.send.setEnabled(False)
        self.send.clicked.connect(self.submit)

        lay.addWidget(self.mic)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.send)

        self._last_submit = QtCore.QElapsedTimer()
        self._history: list[str] = []
        self._hist_idx = 0

    def submit(self) -> None:
        text = sanitize_input(self.edit.text())
        if not text:
            return
        if self._last_submit.isValid() and self._last_submit.elapsed() < SUBMIT_MIN_INTERVAL_MS:
            return  # anti doble envío / auto-repeat
        self._last_submit.restart()
        self._history.append(text)
        self._history = self._history[-self.HISTORY :]
        self._hist_idx = len(self._history)
        self.edit.clear()
        self.submitted.emit(text)

    def set_mic_checked(self, checked: bool) -> None:
        blocker = QtCore.QSignalBlocker(self.mic)
        self.mic.setChecked(checked)
        del blocker

    def _on_text(self, text: str) -> None:
        self.send.setEnabled(bool(text.strip()))

    def _set_focused(self, value: bool) -> None:
        self.setProperty("focused", value)
        self.style().unpolish(self)
        self.style().polish(self)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        et = event.type()
        if obj is self.edit:
            if et == QtCore.QEvent.Type.FocusIn:
                self._set_focused(True)
            elif et == QtCore.QEvent.Type.FocusOut:
                self._set_focused(False)
            elif et == QtCore.QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Up and self._history:
                    self._hist_idx = max(0, self._hist_idx - 1)
                    self.edit.setText(self._history[self._hist_idx])
                    return True
                if key == Qt.Key.Key_Down and self._history:
                    self._hist_idx = min(len(self._history), self._hist_idx + 1)
                    self.edit.setText(
                        self._history[self._hist_idx] if self._hist_idx < len(self._history) else ""
                    )
                    return True
                if key == Qt.Key.Key_Escape:
                    self.edit.clear()
                    return True
        return super().eventFilter(obj, event)


class ChatPanel(QtWidgets.QFrame):
    """Panel de consola centrado con ancho máximo controlado."""

    submitted = Signal(str)
    mic_toggled = Signal(bool)
    cleared = Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatPanel")
        self.setMaximumWidth(theme.CHAT_MAX_WIDTH)
        self.setMinimumWidth(theme.CHAT_MIN_WIDTH)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        # Sin QGraphicsDropShadowEffect a propósito: fuerza render offscreen en cada repintado.

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 14)
        lay.setSpacing(10)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(10)
        title = QtWidgets.QLabel("CONSOLA", self)
        title.setObjectName("PanelTitle")
        title.setFont(theme.font(theme.FONT_DISPLAY, 10, QtGui.QFont.Weight.DemiBold, 3.0))
        self.meta = QtWidgets.QLabel("", self)
        self.meta.setObjectName("PanelMeta")
        self.clear_btn = QtWidgets.QToolButton(self)
        self.clear_btn.setObjectName("IconButton")
        self.clear_btn.setIcon(make_icon("trash", theme.TEXT_DIM, 16))
        self.clear_btn.setIconSize(QtCore.QSize(16, 16))
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Limpiar conversación  (Ctrl+L)")
        self.clear_btn.setAccessibleName("Limpiar conversación")
        self.clear_btn.clicked.connect(self.clear)
        head.addWidget(title)
        head.addWidget(self.meta)
        head.addStretch(1)
        head.addWidget(self.clear_btn)
        lay.addLayout(head)

        sep = QtWidgets.QFrame(self)
        sep.setObjectName("PanelSeparator")
        lay.addWidget(sep)

        self.view = ChatView(self)
        lay.addWidget(self.view, 1)

        self.input = InputBar(self)
        self.input.submitted.connect(self.submitted.emit)
        self.input.mic_toggled.connect(self.mic_toggled.emit)
        lay.addWidget(self.input)

        self._stream: Optional[MessageBubble] = None
        self._update_meta()

    # API
    def add_message(self, role: str, text: str) -> MessageBubble:
        self.end_stream()
        text = str(text or "")
        if role == "user":
            text = sanitize_input(text)
        bubble = self.view.add(role, text)
        self._update_meta()
        return bubble

    def stream(self, chunk: str) -> None:
        if self._stream is None:
            self._stream = self.view.add("assistant", "")
            self._update_meta()
        self._stream.append_text(chunk)

    def end_stream(self) -> None:
        if self._stream is not None:
            self._stream.finish()
            self._stream = None

    def is_streaming(self) -> bool:
        return self._stream is not None

    def clear(self) -> None:
        self._stream = None
        self.view.clear()
        self._update_meta()
        self.cleared.emit()

    def focus_input(self) -> None:
        self.input.edit.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _update_meta(self) -> None:
        n = len(self.view.bubbles)
        self.meta.setText(f"· {n} mensaje{'s' if n != 1 else ''}" if n else "")
