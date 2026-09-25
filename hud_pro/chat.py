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

def _fade_slide_in(widget: QtWidgets.QWidget) -> None:
    """Entrada sutil de mensajes/tarjetas nuevas: fade ~180 ms (OutCubic).
    Sin deslizamiento de posición real: un QWidget dentro de un QVBoxLayout
    pelea con cualquier animación de `pos`/`geometry` (el layout la
    reafirma en cada pasada) — el fade solo es la versión robusta."""
    effect = QtWidgets.QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QtCore.QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(180)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    widget._fade_anim = anim  # referencia fuerte: si no, el GC la corta a medias


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


class _Spinner(QtWidgets.QWidget):
    """Spinner giratorio (sin porcentaje: no hay progreso real que mostrar,
    sólo que la herramienta está corriendo)."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self._angle = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self) -> None:
        self._angle = (self._angle + 18) % 360
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(QtGui.QColor(theme.ACCENT))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        qp.setPen(pen)
        r = QtCore.QRectF(1.5, 1.5, self.width() - 3, self.height() - 3)
        qp.drawArc(r, int(-self._angle * 16), int(230 * 16))
        qp.end()


class ToolCard(QtWidgets.QFrame):
    """Actividad de herramienta en vivo: ícono + nombre + spinner mientras
    corre → duración real + resultado ok/error al terminar. Dato real: la
    duración y el resultado vienen de HudBridge.tool_end(), no se inventan."""

    def __init__(self, name: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolCard")
        self.setProperty("state", "running")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self._icon = QtWidgets.QLabel(self)
        self._icon.setPixmap(make_icon("tool", theme.ACCENT, 16).pixmap(16, 16))
        lay.addWidget(self._icon)

        self._name = QtWidgets.QLabel(name or "herramienta", self)
        self._name.setObjectName("ToolCardName")
        self._name.setFont(theme.font(theme.FONT_MONO, 12, QtGui.QFont.Weight.Medium))
        lay.addWidget(self._name)
        lay.addStretch(1)

        self._spinner = _Spinner(self)
        lay.addWidget(self._spinner)

        self._status = QtWidgets.QLabel("", self)
        self._status.setObjectName("ToolCardStatus")
        self._status.setFont(theme.font(theme.FONT_MONO, 11))
        self._status.setVisible(False)
        lay.addWidget(self._status)

    def finish(self, ms: float, ok: bool) -> None:
        self._spinner.stop()
        self._spinner.setVisible(False)
        self.setProperty("state", "ok" if ok else "error")
        self.style().unpolish(self)
        self.style().polish(self)
        icon_kind = "check" if ok else "error"
        self._icon.setPixmap(
            make_icon(icon_kind, theme.ACCENT if ok else theme.DANGER, 16).pixmap(16, 16)
        )
        label = "ok" if ok else "error"
        self._status.setText(f"{ms:.0f} ms · {label}")
        self._status.setStyleSheet(f"color: {theme.ACCENT if ok else theme.DANGER};")
        self._status.setVisible(True)


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
        _fade_slide_in(bubble)
        return bubble

    def add_tool_card(self, name: str) -> ToolCard:
        """Tarjeta viva de actividad de herramienta — no es un mensaje (no
        entra en `bubbles`/history), sólo actividad visible en la consola."""
        self._empty.setVisible(False)
        card = ToolCard(name, self._list)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(card, 1)
        holder = QtWidgets.QWidget(self._list)
        holder.setLayout(row)
        self._layout.addWidget(holder)
        _fade_slide_in(card)
        return card

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


class _ClickableBar(QtWidgets.QWidget):
    """Encabezado clicable: alterna consola compacta/expandida (Ctrl+J hace
    lo mismo). Los hijos (botón de limpiar) consumen su propio clic antes de
    que llegue aquí — Qt no lo propaga si el hijo lo aceptó."""

    clicked = Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ChatPanel(QtWidgets.QFrame):
    """Panel de consola centrado con ancho máximo controlado."""

    submitted = Signal(str)
    mic_toggled = Signal(bool)
    cleared = Signal()
    header_clicked = Signal()

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

        head_widget = _ClickableBar(self)
        head_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        head_widget.setToolTip("Consola compacta / expandida  (Ctrl+J)")
        head_widget.clicked.connect(self.header_clicked.emit)
        head = QtWidgets.QHBoxLayout(head_widget)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(10)
        title = QtWidgets.QLabel("CONSOLA", head_widget)
        title.setObjectName("PanelTitle")
        title.setFont(theme.font(theme.FONT_DISPLAY, 10, QtGui.QFont.Weight.DemiBold, 3.0))
        self.meta = QtWidgets.QLabel("", head_widget)
        self.meta.setObjectName("PanelMeta")
        self.mode_chevron = QtWidgets.QLabel("▾", head_widget)
        self.mode_chevron.setObjectName("PanelMeta")
        self.clear_btn = QtWidgets.QToolButton(head_widget)
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
        head.addWidget(self.mode_chevron)
        head.addWidget(self.clear_btn)
        lay.addWidget(head_widget)

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
        self._tool_card: Optional[ToolCard] = None
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

    def tool_start(self, name: str) -> None:
        """Arranca la tarjeta viva de la herramienta que JARVIS está usando."""
        self.end_stream()
        self._tool_card = self.view.add_tool_card(name)
        self._update_meta()

    def tool_end(self, name: str, ms: float, ok: bool) -> None:
        """Cierra la tarjeta con la duración real y el resultado."""
        if self._tool_card is not None:
            self._tool_card.finish(ms, ok)
            self._tool_card = None

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

    # Property animable (QPropertyAnimation) para la transición de ~250 ms
    # entre consola compacta/expandida — `setFixedHeight` normal no se anima.
    def _get_panel_height(self) -> int:
        return self.height()

    def _set_panel_height(self, value: int) -> None:
        self.setFixedHeight(int(value))

    panelHeight = QtCore.Property(int, _get_panel_height, _set_panel_height)
