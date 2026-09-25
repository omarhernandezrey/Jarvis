"""Ventana principal del HUD de escritorio."""

from __future__ import annotations

from typing import Optional

from . import theme
from .chat import ChatPanel, MessageBubble
from .orb import OrbWidget
from .qt_compat import Qt, QtCore, QtGui, QtWidgets, Signal
from .state import OrbState, StateLike, parse_state
from .widgets import BackgroundWidget, StatusBlock, TopBar


class HudWindow(QtWidgets.QMainWindow):
    """HUD de JARVIS: orbe centrado + estado + consola con ancho máximo.

    Todos los métodos públicos deben llamarse desde el hilo de la GUI.
    Desde otros hilos (STT, LLM, TTS) usa :class:`hud_pro.bridge.HudBridge`.
    """

    message_submitted = Signal(str)  # texto ya saneado
    mic_toggled = Signal(bool)
    console_toggled = Signal(bool)
    closing = Signal()

    CHAT_MAX_HEIGHT = 470
    CHAT_MIN_HEIGHT = 250

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        echo_user_messages: bool = True,
        title: str = "J.A.R.V.I.S",
    ) -> None:
        super().__init__(parent)
        theme.load_fonts()
        self._echo = echo_user_messages
        self.setWindowTitle(title)
        self.setMinimumSize(900, 620)
        self.resize(1280, 820)
        self.setStyleSheet(theme.stylesheet())

        root = BackgroundWidget(self)
        self.setCentralWidget(root)
        self._root = root

        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(22, 10, 22, 18)
        outer.setSpacing(6)

        self.top_bar = TopBar(root)
        outer.addWidget(self.top_bar)

        stage = QtWidgets.QVBoxLayout()
        stage.setSpacing(4)
        self.orb = OrbWidget(root)
        self.status = StatusBlock(root)
        stage.addWidget(self.orb, 1)
        stage.addWidget(self.status)
        outer.addLayout(stage, 1)

        self.chat = ChatPanel(root)
        chat_row = QtWidgets.QHBoxLayout()
        chat_row.setContentsMargins(0, 8, 0, 0)
        chat_row.addStretch(1)
        chat_row.addWidget(self.chat, 100)
        chat_row.addStretch(1)
        outer.addLayout(chat_row, 0)
        self._fit_chat_height()

        self.chat.submitted.connect(self._on_submitted)
        self.chat.mic_toggled.connect(self.mic_toggled.emit)
        self.orb.installEventFilter(self)

        self._install_shortcuts()
        self.set_state(OrbState.IDLE)

    # ── API pública ───────────────────────────────────────────────────────
    @property
    def state(self) -> OrbState:
        return self.orb.state

    def set_state(self, state: StateLike, detail: Optional[str] = None) -> None:
        """Cambia el estado global (orbe, chip, título). Acepta ES/EN: 'escuchando', 'thinking'…"""
        st = parse_state(state)
        previous = self.orb.state
        self.orb.set_state(st)
        self.status.set_state(st, detail)
        self.top_bar.chip.set_state(st)
        self.chat.input.set_mic_checked(st is OrbState.LISTENING)
        if st is OrbState.LISTENING and previous is not OrbState.LISTENING:
            self.status.set_transcript("")
        elif st is OrbState.IDLE:
            self.status.set_transcript("")

    def set_audio_level(self, level: float) -> None:
        """Nivel de audio normalizado 0..1 (RMS del micrófono o del TTS)."""
        self.orb.set_level(level)

    def set_transcript(self, text: str) -> None:
        """Transcripción parcial/final del STT bajo el orbe."""
        self.status.set_transcript(text)

    def add_user_message(self, text: str) -> MessageBubble:
        return self.chat.add_message("user", text)

    def add_assistant_message(self, text: str) -> MessageBubble:
        return self.chat.add_message("assistant", text)

    def add_system_message(self, text: str) -> MessageBubble:
        return self.chat.add_message("system", text)

    def stream_assistant(self, chunk: str) -> None:
        """Agrega tokens a la respuesta en curso (crea la burbuja si no existe)."""
        self.chat.stream(chunk)

    def end_assistant_stream(self) -> None:
        self.chat.end_stream()

    def clear_chat(self) -> None:
        self.chat.clear()

    def set_model_name(self, name: str) -> None:
        self.top_bar.set_model(name)

    def toggle_console(self, visible: Optional[bool] = None) -> None:
        show = (not self.chat.isVisible()) if visible is None else bool(visible)
        self.chat.setVisible(show)
        if show:
            self.chat.focus_input()
        self.console_toggled.emit(show)

    # ── Internos ──────────────────────────────────────────────────────────
    def _on_submitted(self, text: str) -> None:
        if self._echo:
            self.chat.add_message("user", text)
        self.message_submitted.emit(text)

    def _install_shortcuts(self) -> None:
        def sc(seq: str, slot) -> None:
            s = (
                QtGui.QShortcut(QtGui.QKeySequence(seq), self)
                if hasattr(QtGui, "QShortcut")
                else QtWidgets.QShortcut(QtGui.QKeySequence(seq), self)
            )
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(slot)

        sc("Ctrl+M", self.chat.input.mic.click)
        sc("Ctrl+L", self.chat.clear)
        sc("Ctrl+J", self.toggle_console)
        sc("Ctrl+K", self.chat.focus_input)
        sc("F11", self._toggle_fullscreen)

    def _toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self.orb and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Move):
            g = self.orb.geometry()
            self._root.set_focus_point(QtCore.QPointF(g.center().x(), g.center().y()))
        return super().eventFilter(obj, event)

    def _fit_chat_height(self) -> None:
        """Consola con altura proporcional a la ventana; el orbe se queda con el resto."""
        target = int(max(self.CHAT_MIN_HEIGHT, min(self.CHAT_MAX_HEIGHT, self.height() * 0.36)))
        if self.chat.height() != target or self.chat.minimumHeight() != target:
            self.chat.setFixedHeight(target)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_chat_height()

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self.orb.set_paused(self.isMinimized())
        elif event.type() == QtCore.QEvent.Type.ActivationChange:
            self.orb.refresh_frame_rate()
        super().changeEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self.orb.set_paused(True)
        self.closing.emit()
        super().closeEvent(event)
