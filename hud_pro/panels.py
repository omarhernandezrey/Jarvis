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

from . import theme
from .qt_compat import Qt, QtCore, QtGui, QtWidgets

try:  # métricas opcionales, igual convención que widgets.py
    import psutil  # type: ignore
except Exception:  # pragma: no cover - dependencia opcional
    psutil = None


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


class SystemPanel(QtWidgets.QFrame):
    """Panel SISTEMA: CPU/RAM/ping/red reales (nunca sintetizados) a 1Hz,
    más el uptime del sistema. Sólo corre su timer mientras es visible."""

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
        if psutil is not None:
            psutil.cpu_percent(interval=None)  # cebar la medición

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start(self.UPDATE_MS)
            self._sample()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()

    def _sample(self) -> None:
        if psutil is not None:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self._cpu_spark.push(cpu, vmax=100.0)
            self._cpu_val.setText(f"{cpu:.0f}%")
            self._ram_spark.push(ram, vmax=100.0)
            self._ram_val.setText(f"{ram:.0f}%")

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
            self._tps_label.setText(f"{tokens_per_second:.0f} tok/s")
            self._bar.push(tokens_per_second, vmax=max(20.0, tokens_per_second * 1.2))
        if ttft_ms is not None:
            self._ttft_label.setText(f"TTFT {ttft_ms:.0f} ms")
