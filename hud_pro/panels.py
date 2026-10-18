"""FASE D — paneles SISTEMA/ACTIVIDAD, gauges de tokens/s y sparklines.

Presupuesto de CPU (máquina de 2 núcleos, gobernador de render en
`hud_pro/gpu/stage.py`): estos paneles se actualizan a 1-2 Hz, NUNCA por
frame — `Sparkline` cachea su dibujo en un `QPixmap` propio y sólo lo
recalcula cuando llega un dato nuevo (`push`), nunca en `paintEvent`
(que sólo hace `drawPixmap` del cache). `SystemPanel` para su propio
timer en `hideEvent`/lo arranca en `showEvent` — cero coste mientras el
panel no es visible (cajón cerrado, modo enfoque, etc.).
"""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

from . import system_metrics, theme
from .qt_compat import Qt, QtCore, QtGui, QtWidgets

try:  # métricas opcionales, igual convención que widgets.py
    import psutil  # type: ignore
except Exception:  # pragma: no cover - dependencia opcional
    psutil = None

from .widgets import _set_label_text  # noqa: E402 — setText sólo si cambia (tarea A)


class Sparkline(QtWidgets.QWidget):
    """Serie temporal chiquita dibujada con `QPainter`, cacheada en un
    `QPixmap` — el coste de dibujar (líneas + relleno) sólo se paga
    cuando llega un dato nuevo (`push`), nunca en cada repintado de Qt."""

    def __init__(self, color: str = theme.ACCENT, maxlen: int = 60, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self._values: deque[float] = deque(maxlen=maxlen)
        self._vmax = 1.0
        self._pixmap: Optional[QtGui.QPixmap] = None
        self.setFixedHeight(28)
        self.setMinimumWidth(60)

    def push(self, value: float, vmax: Optional[float] = None) -> None:
        self._values.append(max(0.0, float(value)))
        if vmax is not None:
            self._vmax = max(1e-6, float(vmax))
        else:
            self._vmax = max(1e-6, max(self._values))
        self._redraw_cache()
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._redraw_cache()

    def _redraw_cache(self) -> None:
        w, h = max(1, self.width()), max(1, self.height())
        dpr = self.devicePixelRatioF()
        pm = QtGui.QPixmap(max(1, round(w * dpr)), max(1, round(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        qp = QtGui.QPainter(pm)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        n = len(self._values)
        if n >= 2:
            step = w / max(1, (self._values.maxlen or n) - 1)
            offset = w - (n - 1) * step
            pts = [
                QtCore.QPointF(offset + i * step, h - (v / self._vmax) * (h - 2) - 1)
                for i, v in enumerate(self._values)
            ]
            fill = QtGui.QPolygonF([*pts, QtCore.QPointF(pts[-1].x(), h), QtCore.QPointF(pts[0].x(), h)])
            fill_color = QtGui.QColor(self._color)
            fill_color.setAlphaF(0.16)
            qp.setPen(Qt.PenStyle.NoPen)
            qp.setBrush(fill_color)
            qp.drawPolygon(fill)
            pen = QtGui.QPen(self._color)
            pen.setWidthF(1.6)
            qp.setPen(pen)
            qp.setBrush(Qt.BrushStyle.NoBrush)
            qp.drawPolyline(QtGui.QPolygonF(pts))
        qp.end()
        self._pixmap = pm

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        qp = QtGui.QPainter(self)
        qp.drawPixmap(0, 0, self._pixmap)


def _metric_row(label_text: str, color: str, parent: QtWidgets.QWidget) -> tuple[QtWidgets.QWidget, QtWidgets.QLabel, Sparkline]:
    row = QtWidgets.QWidget(parent)
    lay = QtWidgets.QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    label = QtWidgets.QLabel(label_text, row)
    label.setObjectName("PanelMeta")
    label.setMinimumWidth(76)
    spark = Sparkline(color, parent=row)
    value = QtWidgets.QLabel("—", row)
    value.setObjectName("PanelMeta")
    value.setMinimumWidth(52)
    value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(label)
    lay.addWidget(spark, 1)
    lay.addWidget(value)
    return row, value, spark


class MiniRing(QtWidgets.QWidget):
    """Anillo de progreso chiquito (CPU/RAM) — mismo patrón de cache que
    `Sparkline`: el arco se recalcula sólo en `push`, `paintEvent` sólo
    hace `drawPixmap`. Y `push` con el mismo valor visible (entero) no
    redibuja NADA: un repaint aquí obliga a recomponer toda la ventana
    (hay un QOpenGLWidget debajo)."""

    def __init__(self, color: str = theme.ACCENT, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self._value = 0.0
        self._shown: Optional[int] = None  # último entero dibujado (None = nunca)
        self._pixmap: Optional[QtGui.QPixmap] = None
        self.setFixedSize(34, 34)

    def push(self, value: float) -> None:
        self._value = max(0.0, min(100.0, float(value)))
        shown = round(self._value)
        if shown == self._shown:
            return  # el dato no cambió de verdad: cero trabajo de pintado
        self._shown = shown
        self._redraw_cache()
        self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._redraw_cache()

    def _redraw_cache(self) -> None:
        w, h = max(1, self.width()), max(1, self.height())
        dpr = self.devicePixelRatioF()
        pm = QtGui.QPixmap(max(1, round(w * dpr)), max(1, round(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        qp = QtGui.QPainter(pm)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen_bg = QtGui.QPen(QtGui.QColor(theme.LINE))
        pen_bg.setWidthF(3.0)
        qp.setPen(pen_bg)
        rect = QtCore.QRectF(3, 3, w - 6, h - 6)
        qp.drawArc(rect, 0, 360 * 16)
        pen = QtGui.QPen(self._color)
        pen.setWidthF(3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        qp.setPen(pen)
        span = int(-360 * 16 * (self._value / 100.0))
        qp.drawArc(rect, 90 * 16, span)
        qp.setPen(QtGui.QColor(theme.TEXT))
        qp.setFont(QtGui.QFont(theme.FONT_MONO, 8))
        qp.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), f"{self._value:.0f}")
        qp.end()
        self._pixmap = pm

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        qp = QtGui.QPainter(self)
        qp.drawPixmap(0, 0, self._pixmap)


class CornerBadge(QtWidgets.QFrame):
    """Base compartida de los 4 widgets HUD de esquina: vidrio semi-
    transparente (QSS) + esquinas tipo corchete pintadas a mano — el
    mismo lenguaje que los corchetes HUD del fondo (`BackgroundWidget`),
    no un rectángulo redondeado genérico. Nunca tapa el orbe (se
    posiciona en las esquinas del escenario — ver
    `HudWindow._position_corner_widgets`)."""

    BRACKET_LEN = 7  # px de cada brazo del corchete

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CornerBadge")

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        # el fondo/borde lo pinta el QSS (#CornerBadge) vía el estilo —
        # sin este drawPrimitive un paintEvent propio se lo saltaría.
        opt = QtWidgets.QStyleOption()
        opt.initFrom(self)
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.style().drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_Widget, opt, qp, self)
        # corchetes en las 4 esquinas (encima del borde QSS, en acento)
        pen = QtGui.QPen(QtGui.QColor(theme.LINE_STRONG))
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        qp.setPen(pen)
        w, h, ln, m = self.width(), self.height(), float(self.BRACKET_LEN), 2.5
        for x, y, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            qp.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x + dx * ln, y))
            qp.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x, y + dy * ln))
        qp.end()


class CompactSystemWidget(CornerBadge):
    """Esquina arriba-izquierda: CPU/RAM en mini anillos. Mismo dato real
    que `SystemPanel` (el cajón de detalle) y la barra superior — los
    tres leen de `system_metrics.sampler`, la única fuente real de
    `psutil.cpu_percent` (ver `hud_pro/system_metrics.py`: llamarlo por
    separado desde varios widgets hacía que mostraran números de CPU
    distintos al mismo tiempo). Se suscribe mientras es visible, nada
    más."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self._cpu_ring = MiniRing(theme.ACCENT, self)
        self._ram_ring = MiniRing(theme.ACCENT_2, self)
        for ring, tip in ((self._cpu_ring, "CPU"), (self._ram_ring, "RAM")):
            ring.setToolTip(tip)
            lay.addWidget(ring)
        self._subscribed = False

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._subscribed:
            self._subscribed = True
            system_metrics.sampler.sampled.connect(self._on_sampled)
            system_metrics.sampler.acquire()
            self._on_sampled(*system_metrics.sampler.last())

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        if self._subscribed:
            self._subscribed = False
            system_metrics.sampler.sampled.disconnect(self._on_sampled)
            system_metrics.sampler.release()

    def _on_sampled(self, cpu: float, ram: float) -> None:
        self._cpu_ring.push(cpu)
        self._ram_ring.push(ram)


class CompactServicesWidget(CornerBadge):
    """Esquina abajo-izquierda: estado real de los servicios (Ollama +
    ping, mic, TTS, memoria) — mismos datos que ya llegan por
    `HudWindow.update_metrics`/`set_service_active`, nunca inventados.
    Punto lleno = disponible, hueco = no disponible, «—» = sin dato."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)
        self._ollama_label = QtWidgets.QLabel("Ollama —", self)
        self._ollama_label.setObjectName("PanelMeta")
        self._mic_label = QtWidgets.QLabel("Mic —", self)
        self._mic_label.setObjectName("PanelMeta")
        self._tts_label = QtWidgets.QLabel("TTS —", self)
        self._tts_label.setObjectName("PanelMeta")
        self._memory_label = QtWidgets.QLabel("Memoria —", self)
        self._memory_label.setObjectName("PanelMeta")
        for lbl in (self._ollama_label, self._mic_label, self._tts_label, self._memory_label):
            lay.addWidget(lbl)

    def set_ollama(self, online: Optional[bool], ping_ms: Optional[float]) -> None:
        if online is None:
            _set_label_text(self._ollama_label, "Ollama —")
        elif online:
            _set_label_text(
                self._ollama_label,
                f"Ollama ●  {ping_ms:.0f} ms" if ping_ms is not None else "Ollama ●",
            )
        else:
            _set_label_text(self._ollama_label, "Ollama ○")

    def set_mic(self, on: bool) -> None:
        _set_label_text(self._mic_label, f"Mic {'●' if on else '○'}")

    def set_tts(self, on: bool) -> None:
        _set_label_text(self._tts_label, f"TTS {'●' if on else '○'}")

    def set_memory(self, count: Optional[int]) -> None:
        _set_label_text(self._memory_label, f"Memoria {count}" if count is not None else "Memoria —")


class _Spinner(QtWidgets.QWidget):
    """Arco que rota mientras una herramienta corre DE VERDAD — el timer
    sólo vive durante la tool (se para al terminar), nunca es decorativo:
    cada tick repinta este cuadrito de 14px y obliga a recomponer la
    ventana, así que fuera de una tool real no existe."""

    def __init__(self, color: str = theme.ACCENT, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self._angle = 0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(14, 14)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start(50)

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.update()  # deja el arco quieto (lo tapa la marca ✓/✗)

    def is_spinning(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(self._color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        qp.setPen(pen)
        rect = QtCore.QRectF(2, 2, self.width() - 4, self.height() - 4)
        qp.drawArc(rect, self._angle * 16, 100 * 16)  # arco de 100°
        qp.end()


class CompactToolWidget(CornerBadge):
    """Esquina arriba-derecha: última herramienta real — en curso con
    spinner, o terminada con ✓ (cian) / ✗ (rojo, único uso del rojo fuera
    de errores en el HUD) y su duración real. Vacío hasta el primer
    `tool_start`: nunca una entrada inventada."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self._spinner = _Spinner(theme.ACCENT, self)
        self._spinner.setVisible(False)
        lay.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignTop)
        col = QtWidgets.QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        title = QtWidgets.QLabel("HERRAMIENTA", self)
        title.setObjectName("PanelMeta")
        col.addWidget(title)
        self._label = QtWidgets.QLabel("Sin actividad", self)
        self._label.setObjectName("PanelMeta")
        col.addWidget(self._label)
        lay.addLayout(col, 1)

    def set_running(self, name: str) -> None:
        self._spinner.setVisible(True)
        self._spinner.start()
        self._label.setStyleSheet("")  # vuelve al PanelMeta normal
        _set_label_text(self._label, f"{name}…")

    def set_done(self, name: str, ok: bool, ms: float) -> None:
        self._spinner.stop()
        self._spinner.setVisible(False)
        mark = "✓" if ok else "✗"
        self._label.setStyleSheet("" if ok else f"color: {theme.DANGER};")
        _set_label_text(self._label, f"{mark} {name} ({ms:.0f} ms)")


class SystemPanel(QtWidgets.QFrame):
    """Panel SISTEMA: CPU/RAM/ping/red reales (nunca sintetizados) a 1Hz,
    más el uptime del sistema. Sólo corre su timer mientras es visible.
    CPU/RAM vienen de `system_metrics.sampler` (misma fuente que la barra
    superior y el anillo de la esquina — ver `hud_pro/system_metrics.py`);
    ping/red/uptime no tienen ese problema de estado compartido y se
    siguen midiendo aquí directamente."""

    UPDATE_MS = 1000

    def __init__(self, ollama_ping_fn=None, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatPanel")  # mismo vidrio/estilo que la consola
        self._ping_fn = ollama_ping_fn
        self._last_net = psutil.net_io_counters() if psutil is not None else None
        self._last_net_t = time.monotonic()

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        title = QtWidgets.QLabel("SISTEMA", self)
        title.setObjectName("PanelTitle")
        lay.addWidget(title)

        _, self._cpu_val, self._cpu_spark = _metric_row("CPU", theme.ACCENT, self)
        _, self._ram_val, self._ram_spark = _metric_row("RAM", theme.ACCENT_2, self)
        _, self._ping_val, self._ping_spark = _metric_row("PING", theme.ACCENT, self)
        _, self._net_val, self._net_spark = _metric_row("RED", theme.ACCENT_2, self)
        for row_widget in (self._cpu_spark.parent(), self._ram_spark.parent(), self._ping_spark.parent(), self._net_spark.parent()):
            lay.addWidget(row_widget)

        self._uptime_label = QtWidgets.QLabel("", self)
        self._uptime_label.setObjectName("PanelMeta")
        lay.addWidget(self._uptime_label)
        lay.addStretch(1)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._sample)
        self._subscribed = False

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._subscribed:
            self._subscribed = True
            system_metrics.sampler.sampled.connect(self._on_sampled)
            system_metrics.sampler.acquire()
            self._on_sampled(*system_metrics.sampler.last())
        if not self._timer.isActive():
            self._timer.start(self.UPDATE_MS)
            self._sample()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()
        if self._subscribed:
            self._subscribed = False
            system_metrics.sampler.sampled.disconnect(self._on_sampled)
            system_metrics.sampler.release()

    def _on_sampled(self, cpu: float, ram: float) -> None:
        self._cpu_spark.push(cpu, vmax=100.0)
        self._cpu_val.setText(f"{cpu:.0f}%")
        self._ram_spark.push(ram, vmax=100.0)
        self._ram_val.setText(f"{ram:.0f}%")

    def _sample(self) -> None:
        if psutil is not None:
            now = psutil.net_io_counters()
            t1 = time.monotonic()
            dt = max(1e-3, t1 - self._last_net_t)
            if self._last_net is not None:
                kbs = ((now.bytes_sent + now.bytes_recv) - (self._last_net.bytes_sent + self._last_net.bytes_recv)) / dt / 1024.0
                self._net_spark.push(max(0.0, kbs))
                self._net_val.setText(f"{kbs:.0f} KB/s")
            self._last_net, self._last_net_t = now, t1

            boot = psutil.boot_time()
            up_s = int(time.time() - boot)
            h, rem = divmod(up_s, 3600)
            m, _s = divmod(rem, 60)
            self._uptime_label.setText(f"uptime {h}h {m}m")

        if self._ping_fn is not None:
            ms = self._ping_fn()
            if ms is not None:
                self._ping_spark.push(ms, vmax=200.0)
                self._ping_val.setText(f"{ms:.0f} ms")
            else:
                self._ping_val.setText("—")


class ActivityPanel(QtWidgets.QFrame):
    """Panel ACTIVIDAD: timeline de herramientas reales, recordatorios y
    memoria — cada uno con datos reales del backend; sin datos, muestra
    el estado vacío explícito en vez de inventar contenido."""

    MAX_EVENTS = 12

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatPanel")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        title = QtWidgets.QLabel("ACTIVIDAD", self)
        title.setObjectName("PanelTitle")
        lay.addWidget(title)

        sub1 = QtWidgets.QLabel("HERRAMIENTAS", self)
        sub1.setObjectName("PanelMeta")
        lay.addWidget(sub1)
        self._tools_list = QtWidgets.QListWidget(self)
        self._tools_list.setObjectName("ActivityList")
        self._tools_list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._tools_list.setFixedHeight(120)
        self._tools_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        lay.addWidget(self._tools_list)
        self._set_placeholder(self._tools_list, "Sin herramientas usadas todavía.")

        sub2 = QtWidgets.QLabel("RECORDATORIOS", self)
        sub2.setObjectName("PanelMeta")
        lay.addWidget(sub2)
        self._reminders_list = QtWidgets.QListWidget(self)
        self._reminders_list.setObjectName("ActivityList")
        self._reminders_list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._reminders_list.setFixedHeight(70)
        lay.addWidget(self._reminders_list)
        self._set_placeholder(self._reminders_list, "Sin recordatorios.")

        self._memory_label = QtWidgets.QLabel("Memoria: —", self)
        self._memory_label.setObjectName("PanelMeta")
        lay.addWidget(self._memory_label)
        lay.addStretch(1)

    @staticmethod
    def _set_placeholder(widget: QtWidgets.QListWidget, text: str) -> None:
        widget.clear()
        item = QtWidgets.QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        widget.addItem(item)

    def add_tool_event(self, name: str, ok: bool, ms: float) -> None:
        """Un evento REAL de herramienta (`HudWindow.tool_start/tool_end`
        ya llaman aquí) — nunca una entrada sintética."""
        if self._tools_list.count() == 1 and not (self._tools_list.item(0).flags() & Qt.ItemFlag.ItemIsSelectable):
            self._tools_list.clear()
        stamp = time.strftime("%H:%M:%S")
        status = "✓" if ok else "✗"
        item = QtWidgets.QListWidgetItem(f"{stamp}  {status}  {name}  ({ms:.0f} ms)")
        self._tools_list.insertItem(0, item)
        while self._tools_list.count() > self.MAX_EVENTS:
            self._tools_list.takeItem(self._tools_list.count() - 1)

    def update_reminders(self, reminders: list[str]) -> None:
        """Lista real de recordatorios activos — `None`/vacía muestra el
        estado vacío, nunca deja contenido inventado puesto por defecto."""
        if not reminders:
            self._set_placeholder(self._reminders_list, "Sin recordatorios.")
            return
        self._reminders_list.clear()
        for text in reminders:
            self._reminders_list.addItem(QtWidgets.QListWidgetItem(str(text)))

    def set_memory_count(self, count: Optional[int]) -> None:
        self._memory_label.setText(f"Memoria: {count} recuerdos" if count is not None else "Memoria: —")


class TokenGauge(QtWidgets.QFrame):
    """Gauge de tokens/s + tiempo al primer token — sólo visible mientras
    el LLM está generando/hablando de verdad (lo decide `HudWindow`, no
    este widget); nunca un valor sintetizado cuando no hay respuesta."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusChip")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)
        self._tps_label = QtWidgets.QLabel("— tok/s", self)
        self._tps_label.setObjectName("Metric")
        self._ttft_label = QtWidgets.QLabel("TTFT —", self)
        self._ttft_label.setObjectName("Metric")
        self._bar = Sparkline(theme.ACCENT, maxlen=30, parent=self)
        self._bar.setFixedWidth(70)
        lay.addWidget(self._tps_label)
        lay.addWidget(self._bar)
        lay.addWidget(self._ttft_label)
        self.setVisible(False)

    def update_tokens(self, tokens_per_second: Optional[float], ttft_ms: Optional[float]) -> None:
        if tokens_per_second is not None:
            _set_label_text(self._tps_label, f"{tokens_per_second:.0f} tok/s")
            self._bar.push(tokens_per_second, vmax=max(20.0, tokens_per_second * 1.2))
        if ttft_ms is not None:
            _set_label_text(self._ttft_label, f"TTFT {ttft_ms:.0f} ms")
