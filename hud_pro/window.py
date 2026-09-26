"""Ventana principal del HUD de escritorio."""

from __future__ import annotations

import logging
import os
from typing import Optional

from . import theme
from .chat import ChatPanel, MessageBubble
from .gpu import capabilities as gpu_capabilities
from .gpu.stage import HoloStage, HoloStageError
from .orb import OrbWidget
from .qt_compat import Qt, QtCore, QtGui, QtWidgets, Signal
from .state import OrbState, StateLike, parse_state
from .widgets import BackgroundWidget, ServiceChip, StatusBlock, ToastOverlay, TopBar

log = logging.getLogger("jarvis.hud_pro.gpu")


class HudWindow(QtWidgets.QMainWindow):
    """HUD de JARVIS: orbe centrado + estado + consola con ancho máximo.

    Todos los métodos públicos deben llamarse desde el hilo de la GUI.
    Desde otros hilos (STT, LLM, TTS) usa :class:`hud_pro.bridge.HudBridge`.
    """

    message_submitted = Signal(str)  # texto ya saneado
    mic_toggled = Signal(bool)
    console_toggled = Signal(bool)
    new_conversation_requested = Signal()
    mute_toggled = Signal(bool)
    memory_requested = Signal()
    closing = Signal()

    CHAT_MAX_HEIGHT = 470
    CHAT_MIN_HEIGHT = 250
    CHAT_COMPACT_HEIGHT = 150  # consola compacta (por defecto): barra + último intercambio
    STAGE_MIN_FRACTION = 0.55  # el orbe ocupa como mínimo el 55% del alto de la ventana
    CONSOLE_ANIM_MS = 250

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
        self._reduced_motion = os.environ.get("JARVIS_REDUCED_MOTION", "") == "1"
        self._settings = QtCore.QSettings("JarvisLocal", "hud_pro")
        self._console_expanded = bool(self._settings.value("console/expanded", False, type=bool))
        self._muted = False
        self.setWindowTitle(title)
        self.setMinimumSize(900, 620)
        self.resize(1280, 820)
        self.setStyleSheet(theme.stylesheet())

        root = BackgroundWidget(self)
        self.setCentralWidget(root)
        self._root = root

        # Motor GPU (FASE A de la 3ª iteración): fondo de toda la ventana,
        # por DEBAJO de todo lo demás — se crea primero (nace al fondo de
        # la pila en z-order) y ocupa el rect completo de `root`, en
        # sincronía con cada resize (ver `_sync_gpu_stage_geometry`).
        # `JARVIS_HUD_GPU=off` lo desactiva sin más; con `auto` (por
        # defecto) sólo se intenta si hay binding OpenGL, la plataforma no
        # es `offscreen` (ahí QOpenGLWidget se niega a pintar — no es un
        # bug, es la plataforma) y `detect()` ve un contexto usable. Si
        # falla la creación o la compilación de shaders, `HoloStage.ok`
        # queda en `False` y el fondo raster de `BackgroundWidget` (ya
        # existente, sin tocar) sigue siendo lo único visible.
        self.gpu_stage: Optional[HoloStage] = self._create_gpu_stage(root)

        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(22, 10, 22, 18)
        outer.setSpacing(6)

        self.top_bar = TopBar(root)
        outer.addWidget(self.top_bar)

        # Chips de servicios reales (mic/wake/tts/memoria) — ocultos hasta
        # que llega un dato real vía set_service_active().
        services_row = QtWidgets.QHBoxLayout()
        services_row.setContentsMargins(2, 0, 2, 0)
        services_row.setSpacing(8)
        self.chip_mic = ServiceChip("mic", "MIC", root)
        self.chip_wake = ServiceChip("wake", "WAKE", root)
        self.chip_tts = ServiceChip("send", "TTS", root)
        self.chip_memory = ServiceChip("memory", "MEM", root)
        for chip in (self.chip_mic, self.chip_wake, self.chip_tts, self.chip_memory):
            services_row.addWidget(chip)
        services_row.addStretch(1)

        # Acciones rápidas — plegadas por defecto ("menos es más"): un botón
        # de engranaje las despliega. Sólo las que tienen función real detrás.
        self.quick_actions = QtWidgets.QWidget(root)
        qa_lay = QtWidgets.QHBoxLayout(self.quick_actions)
        qa_lay.setContentsMargins(0, 0, 0, 0)
        qa_lay.setSpacing(6)
        self.action_new = self._make_quick_action("new", "Nueva conversación")
        self.action_mute = self._make_quick_action("mute", "Silenciar respuestas habladas")
        self.action_mute.setCheckable(True)
        self.action_memory = self._make_quick_action("memory", "Memoria")
        for btn in (self.action_new, self.action_mute, self.action_memory):
            qa_lay.addWidget(btn)
        self.quick_actions.setVisible(False)
        self.actions_toggle = QtWidgets.QToolButton(root)
        self.actions_toggle.setObjectName("IconButton")
        self.actions_toggle.setText("⋯")
        self.actions_toggle.setFixedSize(26, 26)
        self.actions_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions_toggle.setToolTip("Acciones rápidas")
        self.actions_toggle.setCheckable(True)
        self.actions_toggle.toggled.connect(self.quick_actions.setVisible)
        services_row.addWidget(self.quick_actions)
        services_row.addWidget(self.actions_toggle)
        outer.addLayout(services_row)

        self.action_new.clicked.connect(self.new_conversation_requested.emit)
        self.action_mute.toggled.connect(self._on_mute_toggled)
        self.action_memory.clicked.connect(self.memory_requested.emit)

        # `orb`/`status` cuelgan de `root` DIRECTAMENTE (no de un widget
        # intermedio): `eventFilter` y los tests leen `orb.geometry()` como
        # coordenadas de `root` (el foco del fondo, el centrado). El piso
        # del 55% se aplica con `orb.setMinimumHeight(...)`, no envolviendo
        # el orbe en otro widget.
        stage = QtWidgets.QVBoxLayout()
        stage.setSpacing(4)
        self._stage_layout = stage
        self.orb = OrbWidget(root)
        if self.gpu_stage is not None:
            # FASE C: HoloStage ya dibuja el orbe real (raymarch); este
            # widget se queda invisible pero sigue siendo el control real
            # de push-to-talk (clic/hover/geometría intactos).
            self.orb.set_render_visible(False)
        self.status = StatusBlock(root)
        stage.addWidget(self.orb, 1)
        if self.gpu_stage is None:
            stage.addWidget(self.status)
            self._status_manual_position = False
        else:
            # el orbe GPU (anillos + bloom, que sangra bastante más allá
            # del borde geométrico) puede necesitar más espacio del que
            # el layout automático le deja a `status` sin invadir el resto
            # — la caja del layout de `orb` no tiene margen de sobra para
            # crecer (su minimumHeight ya se lleva el 55% de la ventana),
            # así que aquí se posiciona a mano en cada resize/move de
            # `orb` (ver `eventFilter`) en vez de dejarlo en el layout.
            self._status_manual_position = True
        outer.addLayout(stage, 1)

        self.chat = ChatPanel(root)
        chat_row = QtWidgets.QHBoxLayout()
        chat_row.setContentsMargins(0, 8, 0, 0)
        chat_row.addStretch(1)
        chat_row.addWidget(self.chat, 100)
        chat_row.addStretch(1)
        outer.addLayout(chat_row, 0)
        self._fit_chat_height()
        self._fit_stage_height()
        self._update_mode_chevron()

        self._toasts = ToastOverlay(root)

        self.chat.submitted.connect(self._on_submitted)
        self.chat.mic_toggled.connect(self.mic_toggled.emit)
        self.chat.header_clicked.connect(self.toggle_console_mode)
        self.orb.installEventFilter(self)
        if self.gpu_stage is not None:
            # el nivel del orbe (real cuando hay audio; síntesis de reposo
            # cuando no) varía frame a frame por su propio suavizado — el
            # fondo GPU lo necesita al mismo ritmo, no sólo cuando llega un
            # set_audio_level() externo nuevo. Reutiliza el MISMO valor
            # que ya pinta el orbe raster (`OrbRenderer.level`), nunca uno
            # sintetizado aparte.
            self._gpu_energy_timer = QtCore.QTimer(self)
            self._gpu_energy_timer.setTimerType(QtCore.Qt.TimerType.CoarseTimer)
            self._gpu_energy_timer.timeout.connect(self._sync_gpu_energy)
            self._gpu_energy_timer.start(33)

        self._install_shortcuts()
        self.set_state(OrbState.IDLE)

    def _sync_gpu_energy(self) -> None:
        if self.gpu_stage is not None:
            self.gpu_stage.set_energy(self.orb.renderer.level)

    def _make_quick_action(self, icon_kind: str, tooltip: str) -> QtWidgets.QToolButton:
        from .widgets import make_icon

        btn = QtWidgets.QToolButton(self.quick_actions)
        btn.setObjectName("QuickAction")
        btn.setIcon(make_icon(icon_kind, theme.TEXT_DIM, 14))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(28, 24)
        return btn

    def _on_mute_toggled(self, muted: bool) -> None:
        self._muted = muted
        self.mute_toggled.emit(muted)

    # ── Motor GPU (fondo) ────────────────────────────────────────────────
    def _create_gpu_stage(self, root: QtWidgets.QWidget) -> Optional[HoloStage]:
        mode = os.environ.get("JARVIS_HUD_GPU", "auto").strip().lower()
        if mode == "off":
            log.info("HUD GPU: desactivado por JARVIS_HUD_GPU=off, fondo raster.")
            return None
        supported, reason = gpu_capabilities.qopenglwidget_supported_here()
        if not supported:
            log.info("HUD GPU: %s, fondo raster.", reason)
            return None
        caps = gpu_capabilities.detect()
        if not caps.available:
            log.info("HUD GPU: capacidades insuficientes (%s), fondo raster.", caps.summary())
            return None
        try:
            stage = HoloStage(root)
        except HoloStageError as exc:
            log.error("HUD GPU: fallo al crear HoloStage (%s), fondo raster.", exc)
            return None
        stage.lower()
        stage.setGeometry(root.rect())
        root.set_paint_enabled(False)
        return stage

    def _sync_gpu_stage_geometry(self) -> None:
        if self.gpu_stage is not None:
            self.gpu_stage.setGeometry(self._root.rect())

    def _check_gpu_stage_after_first_paint(self) -> None:
        """Un fallo de compilación de shaders se detecta DENTRO de
        `initializeGL` (síncrono con el primer paint) — por eso basta un
        `singleShot(0, ...)` tras el primer show real, no hace falta
        sondear varios frames."""
        stage = self.gpu_stage
        if stage is None:
            return
        if not stage.ok:
            log.error(
                "HUD GPU: %s — se retira el fondo GPU, queda el raster.",
                stage.init_error or "fallo de inicialización desconocido",
            )
            stage.setParent(None)
            stage.deleteLater()
            self.gpu_stage = None
            self._root.set_paint_enabled(True)
            self.orb.set_render_visible(True)

    @property
    def gpu_active(self) -> bool:
        return self.gpu_stage is not None and self.gpu_stage.ok

    # ── API pública ───────────────────────────────────────────────────────
    @property
    def state(self) -> OrbState:
        return self.orb.state

    def set_state(self, state: StateLike, detail: Optional[str] = None) -> None:
        """Cambia el estado global (orbe, chip, título). Acepta ES/EN: 'escuchando', 'thinking'…"""
        st = parse_state(state)
        previous = self.orb.state
        self.orb.set_state(st)
        if self.gpu_stage is not None:
            self.gpu_stage.set_state(st)
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

    def toggle_console_mode(self) -> None:
        """Alterna consola compacta ↔ expandida (Ctrl+J / clic en el
        encabezado). El orbe cambia de tamaño con una transición suave — la
        preferencia se recuerda con QSettings."""
        self._console_expanded = not self._console_expanded
        self._settings.setValue("console/expanded", self._console_expanded)
        self._update_mode_chevron()
        self._animate_chat_height()
        self.console_toggled.emit(self._console_expanded)

    def set_spectrum(self, bands: Optional[list]) -> None:
        """Espectro real (FFT del micrófono o del TTS) para el anillo del
        orbe. `None`/vacío lo apaga — nunca inventa una forma."""
        self.orb.set_spectrum(bands)
        if self.gpu_stage is not None:
            self.gpu_stage.set_spectrum(bands)

    def update_metrics(self, data: dict) -> None:
        """Métricas reales de la barra superior y de los chips de servicio.
        Mismas claves que `jarvis_local.ui.hud.services.sample_all()`
        (`voice: {mic, tts}`, `memory: {auto_recall, count}`): se reutiliza
        el muestreo real del HUD legado, no se inventa uno nuevo."""
        self.top_bar.update_metrics(data)
        voice = data.get("voice")
        if isinstance(voice, dict):
            mic_on = voice.get("mic") == "available"
            self.chip_mic.set_state(on=mic_on, active=self.chip_mic.is_active(), tip="Micrófono")
            # No hay detector de wake-word en continuo en este pipeline —
            # sólo push-to-talk. El chip "WAKE" refleja ese MISMO mecanismo
            # real (activar el mic), nunca un dato inventado; el tooltip lo
            # deja explícito en vez de insinuar una escucha pasiva.
            self.chip_wake.set_state(
                on=mic_on, active=self.chip_wake.is_active(),
                tip="Activación por voz — mantén pulsado el micrófono (push-to-talk)",
            )
            self.chip_tts.set_state(
                on=bool(voice.get("tts")), active=self.chip_tts.is_active(), tip="Síntesis de voz (TTS)"
            )
        memory = data.get("memory")
        if isinstance(memory, dict) and memory.get("count") is not None:
            self.chip_memory.set_state(on=True, tip=f"Memoria · {memory['count']} recuerdos")

    def set_service_active(self, name: str, active: bool) -> None:
        """El punto del chip late mientras el servicio está trabajando de
        verdad (grabando, hablando…). No decide si el chip se muestra —
        eso lo hace `update_metrics` con el dato real de disponibilidad."""
        chip = {
            "mic": self.chip_mic, "wake": self.chip_wake,
            "tts": self.chip_tts, "memory": self.chip_memory,
        }.get(name)
        if chip is not None:
            chip.set_active(active)

    def show_toast(self, message: str, kind: str) -> None:
        """Aviso no intrusivo (error/recordatorio/info), se apaga solo."""
        self._toasts.add(message, kind)
        self._toasts.reposition(self._root.rect())

    def tool_start(self, name: str) -> None:
        """Tarjeta viva: JARVIS empezó a usar una herramienta real."""
        self.chat.tool_start(name)

    def tool_end(self, name: str, ms: float, ok: bool) -> None:
        """Cierra la tarjeta con la duración real y el resultado."""
        self.chat.tool_end(name, ms, ok)

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
        sc("Ctrl+J", self.toggle_console_mode)
        sc("Ctrl+K", self.chat.focus_input)
        sc("F11", self._toggle_fullscreen)

    def _position_status_below_rings(
        self, orb_geom: QtCore.QRect, cy: float, radius_px: float,
    ) -> None:
        """El texto de estado NUNCA sobre el orbe. Con el orbe GPU, la
        caja de layout de `orb` (fijada por `setMinimumHeight` al 55% de
        la ventana, sin margen de sobra) no tiene espacio libre para que
        el propio layout empuje `status` más abajo — por eso se posiciona
        a mano aquí, fuera del layout de `stage`. El bloom del anillo
        exterior sangra bastante más allá de su borde geométrico (2.8x el
        radio, medido a ojo contra capturas reales — no una fórmula
        exacta del falloff); se acota para no invadir la consola.

        OJO: la consola COMPACTA (modo por defecto) ya está diseñada para
        flotar sobre la parte baja del escenario del orbe — el panel
        semitransparente de `ChatPanel` ya convive ahí con el piso
        hexagonal en toda captura existente. El único tope real es no
        tapar la CABECERA de la consola (su título), no el panel entero."""
        ring_outer_bottom = cy + radius_px * 1.8
        status_h = self.status.sizeHint().height() or 60
        max_y = self.chat.geometry().top() + 18  # deja ver la cabecera "CONSOLA"
        y = min(round(ring_outer_bottom), max_y)
        y = max(y, orb_geom.top())
        self.status.setGeometry(orb_geom.x(), y, orb_geom.width(), status_h)

    def _toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self.orb and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Move):
            g = self.orb.geometry()
            self._root.set_focus_point(QtCore.QPointF(g.center().x(), g.center().y()))
            if self.gpu_stage is not None and self._root.width() > 0 and self._root.height() > 0:
                # el centro geométrico del widget del orbe queda pegado al
                # texto de estado (vive justo debajo, en el mismo layout)
                # — subirlo un poco dentro de su propia caja le da aire
                # antes de tocar ese texto.
                cx = g.center().x()
                cy = g.top() + g.height() * 0.42
                self.gpu_stage.set_light_uv(cx / self._root.width(), cy / self._root.height())
                # 0.30 del lado menor (el mandato original) se veía
                # deslucido — casi tapado por el propio texto de estado en
                # capturas reales a 1920x1080/1366x768 (esto se notó DESPUÉS
                # de corregir el bug real: un uniform escalar que dejaba
                # todo el pipeline congelado, ver `shader_loader.py`). 0.34
                # lo hace protagonista sin invadir la consola de abajo.
                radius_px = 0.30 * min(g.width(), g.height())
                self.gpu_stage.set_light_radius(radius_px / self._root.height())
                if self._status_manual_position:
                    self._position_status_below_rings(g, cy, radius_px)
        elif obj is self.orb and event.type() == QtCore.QEvent.Type.Enter:
            if self.gpu_stage is not None:
                self.gpu_stage.set_hover(True)
        elif obj is self.orb and event.type() == QtCore.QEvent.Type.Leave:
            if self.gpu_stage is not None:
                self.gpu_stage.set_hover(False)
        return super().eventFilter(obj, event)

    def _target_chat_height(self) -> int:
        if self._console_expanded:
            return int(max(self.CHAT_MIN_HEIGHT, min(self.CHAT_MAX_HEIGHT, self.height() * 0.36)))
        return self.CHAT_COMPACT_HEIGHT

    def _fit_chat_height(self) -> None:
        """Consola con altura según el modo (compacta/expandida); el orbe
        se queda con el resto. Ajuste directo (sin animar): lo dispara un
        resize normal de ventana, no un cambio de modo."""
        target = self._target_chat_height()
        if self.chat.height() != target or self.chat.minimumHeight() != target:
            self.chat.setFixedHeight(target)

    def _animate_chat_height(self) -> None:
        """Transición de ~250 ms (OutCubic) al cambiar de modo de consola.
        El orbe la acompaña solo: comparte el stretch=1 del mismo layout,
        así que cada frame de esta animación también le recalcula el alto."""
        target = self._target_chat_height()
        duration = 1 if self._reduced_motion else self.CONSOLE_ANIM_MS
        anim = QtCore.QPropertyAnimation(self.chat, b"panelHeight", self)
        anim.setDuration(duration)
        anim.setStartValue(self.chat.height())
        anim.setEndValue(target)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        anim.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._console_anim = anim  # referencia fuerte: si no, el GC la corta a medias

    def _update_mode_chevron(self) -> None:
        self.chat.mode_chevron.setText("▴" if self._console_expanded else "▾")

    def _fit_stage_height(self) -> None:
        """El orbe ocupa como mínimo el STAGE_MIN_FRACTION del alto de la
        ventana — un piso, no un tope: crece más si sobra sitio (tiene
        stretch=1 en el layout; `status` se queda con su alto natural)."""
        self.orb.setMinimumHeight(round(self.height() * self.STAGE_MIN_FRACTION))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_chat_height()
        self._fit_stage_height()
        self._sync_gpu_stage_geometry()
        if hasattr(self, "_toasts"):
            self._toasts.reposition(self._root.rect())

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self.gpu_stage is not None:
            QtCore.QTimer.singleShot(0, self._check_gpu_stage_after_first_paint)

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.WindowStateChange:
            self.orb.set_paused(self.isMinimized())
            if self.gpu_stage is not None:
                self.gpu_stage.set_paused(self.isMinimized())
        elif event.type() == QtCore.QEvent.Type.ActivationChange:
            self.orb.refresh_frame_rate()
        super().changeEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self.orb.set_paused(True)
        if self.gpu_stage is not None:
            self.gpu_stage.set_paused(True)
        self.closing.emit()
        super().closeEvent(event)
