"""Widgets de soporte del HUD: iconos vectoriales, fondo, barra superior y bloque de estado."""

from __future__ import annotations

import math
import time
from typing import Optional

from . import theme
from .qt_compat import Qt, QtCore, QtGui, QtWidgets
from .state import OrbState, StateLike, parse_state

QPointF = QtCore.QPointF
QRectF = QtCore.QRectF

try:  # métricas opcionales
    import psutil  # type: ignore
except Exception:  # pragma: no cover - dependencia opcional
    psutil = None


# ── Iconos vectoriales (sin assets externos) ───────────────────────────────
def make_icon(kind: str, color: str = theme.TEXT, size: int = 20) -> QtGui.QIcon:
    dpr = 3.0
    pm = QtGui.QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(dpr)
    qp = QtGui.QPainter(pm)
    qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    qp.setPen(pen)
    qp.setBrush(Qt.BrushStyle.NoBrush)
    s = float(size)
    if kind == "mic":
        qp.drawRoundedRect(QRectF(s * 0.36, s * 0.14, s * 0.28, s * 0.44), s * 0.14, s * 0.14)
        path = QtGui.QPainterPath()
        path.moveTo(s * 0.24, s * 0.44)
        path.cubicTo(s * 0.24, s * 0.80, s * 0.76, s * 0.80, s * 0.76, s * 0.44)
        qp.drawPath(path)
        qp.drawLine(QPointF(s * 0.5, s * 0.72), QPointF(s * 0.5, s * 0.86))
        qp.drawLine(QPointF(s * 0.38, s * 0.86), QPointF(s * 0.62, s * 0.86))
    elif kind == "send":
        pen.setWidthF(2.0)
        qp.setPen(pen)
        qp.drawLine(QPointF(s * 0.5, s * 0.80), QPointF(s * 0.5, s * 0.22))
        qp.drawLine(QPointF(s * 0.28, s * 0.44), QPointF(s * 0.5, s * 0.22))
        qp.drawLine(QPointF(s * 0.72, s * 0.44), QPointF(s * 0.5, s * 0.22))
    elif kind == "trash":
        qp.drawLine(QPointF(s * 0.22, s * 0.28), QPointF(s * 0.78, s * 0.28))
        qp.drawLine(QPointF(s * 0.40, s * 0.28), QPointF(s * 0.42, s * 0.18))
        qp.drawLine(QPointF(s * 0.42, s * 0.18), QPointF(s * 0.58, s * 0.18))
        qp.drawLine(QPointF(s * 0.58, s * 0.18), QPointF(s * 0.60, s * 0.28))
        path = QtGui.QPainterPath()
        path.moveTo(s * 0.28, s * 0.28)
        path.lineTo(s * 0.32, s * 0.84)
        path.lineTo(s * 0.68, s * 0.84)
        path.lineTo(s * 0.72, s * 0.28)
        qp.drawPath(path)
        qp.drawLine(QPointF(s * 0.44, s * 0.42), QPointF(s * 0.45, s * 0.70))
        qp.drawLine(QPointF(s * 0.56, s * 0.42), QPointF(s * 0.55, s * 0.70))
    elif kind == "console":
        qp.drawLine(QPointF(s * 0.22, s * 0.32), QPointF(s * 0.40, s * 0.50))
        qp.drawLine(QPointF(s * 0.40, s * 0.50), QPointF(s * 0.22, s * 0.68))
        qp.drawLine(QPointF(s * 0.48, s * 0.70), QPointF(s * 0.78, s * 0.70))
    qp.end()
    return QtGui.QIcon(pm)


# ── Fondo ─────────────────────────────────────────────────────────────────
class BackgroundWidget(QtWidgets.QWidget):
    """Fondo del HUD: viñeta, resplandor que sigue al orbe, retícula y esquinas.
    Se cachea en un QPixmap y solo se regenera al cambiar tamaño o foco."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HudRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._cache: Optional[QtGui.QPixmap] = None
        self._cache_size = QtCore.QSize()
        self._focus = QPointF(0.5, 0.38)  # relativo (0..1)

    def set_focus_point(self, point: QPointF) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return
        rel = QPointF(point.x() / self.width(), point.y() / self.height())
        if abs(rel.x() - self._focus.x()) > 0.002 or abs(rel.y() - self._focus.y()) > 0.002:
            self._focus = rel
            self._cache = None
            self.update()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        self._cache = None
        super().resizeEvent(event)

    def _render(self) -> QtGui.QPixmap:
        dpr = self.devicePixelRatioF()
        w, h = self.width(), self.height()
        pm = QtGui.QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QtGui.QColor(theme.BG_0))
        qp = QtGui.QPainter(pm)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        qp.setPen(Qt.PenStyle.NoPen)

        fx, fy = self._focus.x() * w, self._focus.y() * h
        big = max(w, h)
        g = QtGui.QRadialGradient(QPointF(fx, fy), big * 0.55)
        g.setColorAt(0.0, QtGui.QColor(16, 44, 96, 150))
        g.setColorAt(0.35, QtGui.QColor(10, 26, 60, 90))
        g.setColorAt(1.0, QtGui.QColor(4, 8, 18, 0))
        qp.fillRect(QRectF(0, 0, w, h), QtGui.QBrush(g))

        g2 = QtGui.QRadialGradient(QPointF(w * 0.5, h * 1.05), big * 0.5)
        g2.setColorAt(0.0, QtGui.QColor(10, 34, 70, 70))
        g2.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        qp.fillRect(QRectF(0, 0, w, h), QtGui.QBrush(g2))

        # retícula de puntos muy sutil
        pen = QtGui.QPen(QtGui.QColor(120, 170, 255, 16))
        pen.setCosmetic(True)
        pen.setWidthF(1.0)
        qp.setPen(pen)
        step = 28
        pts = [
            QPointF(x + 0.5, y + 0.5) for y in range(step // 2, h, step) for x in range(step // 2, w, step)
        ]
        if pts:
            qp.drawPoints(QtGui.QPolygonF(pts))

        # viñeta
        v = QtGui.QRadialGradient(QPointF(w / 2, h / 2), math.hypot(w, h) * 0.62)
        v.setColorAt(0.55, QtGui.QColor(0, 0, 0, 0))
        v.setColorAt(1.0, QtGui.QColor(0, 0, 0, 150))
        qp.setPen(Qt.PenStyle.NoPen)
        qp.fillRect(QRectF(0, 0, w, h), QtGui.QBrush(v))

        # esquinas HUD
        pen = QtGui.QPen(QtGui.QColor(110, 190, 255, 70))
        pen.setCosmetic(True)
        qp.setPen(pen)
        m, ln = 10.5, 18
        for x, y, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            qp.drawLine(QPointF(x, y), QPointF(x + dx * ln, y))
            qp.drawLine(QPointF(x, y), QPointF(x, y + dy * ln))
        qp.end()
        return pm

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._cache is None or self._cache_size != self.size():
            self._cache = self._render()
            self._cache_size = self.size()
        qp = QtGui.QPainter(self)
        try:
            rect = event.rect()
            qp.drawPixmap(QRectF(rect), self._cache, self._source_rect(rect))
        finally:
            qp.end()

    def _source_rect(self, rect: QtCore.QRect) -> QtCore.QRectF:
        dpr = self._cache.devicePixelRatio() if self._cache else 1.0
        return QRectF(rect.x() * dpr, rect.y() * dpr, rect.width() * dpr, rect.height() * dpr)


# ── Indicadores ───────────────────────────────────────────────────────────
class _Dot(QtWidgets.QWidget):
    def __init__(self, color: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self.setFixedSize(14, 14)

    def set_color(self, color: str) -> None:
        self._color = QtGui.QColor(color)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        qp.setPen(Qt.PenStyle.NoPen)
        c = QPointF(self.width() / 2, self.height() / 2)
        glow = QtGui.QColor(self._color)
        glow.setAlpha(60)
        qp.setBrush(glow)
        qp.drawEllipse(c, 6, 6)
        qp.setBrush(self._color)
        qp.drawEllipse(c, 3.2, 3.2)
        qp.end()


class StatusChip(QtWidgets.QFrame):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusChip")
        self.setFixedHeight(28)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 12, 0)
        lay.setSpacing(6)
        self._dot = _Dot(theme.ACCENT, self)
        self._label = QtWidgets.QLabel("", self)
        self._label.setFont(theme.font(theme.FONT_DISPLAY, 10, QtGui.QFont.Weight.Medium, 2.0))
        lay.addWidget(self._dot)
        lay.addWidget(self._label)
        self.set_state(OrbState.IDLE)

    def set_state(self, state: OrbState) -> None:
        color = theme.STATE_STYLES[state].ui
        self._dot.set_color(color)
        self._label.setText(state.label)
        self._label.setStyleSheet(f"color: {color};")
        self.setAccessibleName(f"Estado: {state.label}")

    def text(self) -> str:
        return self._label.text()


class _MiniOrb(QtWidgets.QWidget):
    """Logotipo: mini orbe estático."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(24, 24)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        c = QPointF(12, 12)
        g = QtGui.QRadialGradient(c, 11)
        g.setColorAt(0.0, QtGui.QColor(230, 250, 255))
        g.setColorAt(0.35, QtGui.QColor(56, 189, 248))
        g.setColorAt(0.75, QtGui.QColor(30, 80, 200, 160))
        g.setColorAt(1.0, QtGui.QColor(30, 80, 200, 0))
        qp.setPen(Qt.PenStyle.NoPen)
        qp.setBrush(g)
        qp.drawEllipse(c, 11, 11)
        pen = QtGui.QPen(QtGui.QColor(120, 210, 255, 150))
        pen.setWidthF(1.0)
        qp.setPen(pen)
        qp.setBrush(Qt.BrushStyle.NoBrush)
        qp.drawArc(QRectF(1.5, 1.5, 21, 21), 20 * 16, 120 * 16)
        qp.drawArc(QRectF(1.5, 1.5, 21, 21), 200 * 16, 120 * 16)
        qp.end()


def _divider(parent: QtWidgets.QWidget) -> QtWidgets.QFrame:
    d = QtWidgets.QFrame(parent)
    d.setObjectName("Divider")
    d.setFixedSize(1, 18)
    return d


class TopBar(QtWidgets.QWidget):
    """Marca, modelo activo, métricas del sistema, estado y reloj."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(12)

        lay.addWidget(_MiniOrb(self))
        mark = QtWidgets.QLabel("J.A.R.V.I.S", self)
        mark.setObjectName("Wordmark")
        mark.setFont(theme.font(theme.FONT_DISPLAY, 15, QtGui.QFont.Weight.Bold, 4.0))
        lay.addWidget(mark)
        lay.addWidget(_divider(self))
        sub = QtWidgets.QLabel("Asistente local", self)
        sub.setObjectName("WordmarkSub")
        sub.setFont(theme.font(theme.FONT_UI, 12))
        lay.addWidget(sub)
        lay.addStretch(1)

        self.model_label = QtWidgets.QLabel("", self)
        self.model_label.setObjectName("Metric")
        self.model_label.setVisible(False)
        lay.addWidget(self.model_label)

        self.metrics_label = QtWidgets.QLabel("", self)
        self.metrics_label.setObjectName("Metric")
        self.metrics_label.setVisible(psutil is not None)
        lay.addWidget(self.metrics_label)
        lay.addWidget(_divider(self))

        self.chip = StatusChip(self)
        lay.addWidget(self.chip)

        self.clock = QtWidgets.QLabel("", self)
        self.clock.setObjectName("Clock")
        self.clock.setMinimumWidth(44)
        lay.addWidget(self.clock)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        if psutil is not None:
            psutil.cpu_percent(interval=None)  # cebar la medición
        self._refresh()

    def set_model(self, name: str) -> None:
        name = (name or "").strip()
        self.model_label.setText(f"MODELO  {name}" if name else "")
        self.model_label.setVisible(bool(name))

    def _refresh(self) -> None:
        self.clock.setText(time.strftime("%H:%M"))
        if psutil is not None:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                self.metrics_label.setText(f"CPU {cpu:.0f}%  ·  RAM {ram:.0f}%")
            except Exception:  # pragma: no cover
                self.metrics_label.setVisible(False)


class StatusBlock(QtWidgets.QWidget):
    """Estado actual, pista contextual y transcripción en vivo (altura fija: sin saltos)."""

    MAX_TRANSCRIPT = 180

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.title = QtWidgets.QLabel("", self)
        self.title.setObjectName("StateTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setFont(theme.font(theme.FONT_DISPLAY, 17, QtGui.QFont.Weight.DemiBold, 7.0))

        self.hint = QtWidgets.QLabel("", self)
        self.hint.setObjectName("StateHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setFont(theme.font(theme.FONT_UI, 13))

        self.transcript = QtWidgets.QLabel("", self)
        self.transcript.setObjectName("Transcript")
        self.transcript.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript.setWordWrap(True)
        self.transcript.setTextFormat(Qt.TextFormat.PlainText)
        f = theme.font(theme.FONT_UI, 14)
        f.setItalic(True)
        self.transcript.setFont(f)
        self.transcript.setMaximumWidth(720)
        self.transcript.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.transcript.setFixedHeight(QtGui.QFontMetrics(f).lineSpacing() * 2 + 4)

        lay.addWidget(self.title)
        lay.addWidget(self.hint)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.transcript, 100)
        row.addStretch(1)
        lay.addLayout(row)
        self.set_state(OrbState.IDLE)

    def set_state(self, state: StateLike, detail: Optional[str] = None) -> None:
        st = parse_state(state)
        self.title.setText(st.label)
        self.title.setStyleSheet(f"color: {theme.STATE_STYLES[st].ui};")
        self.hint.setText((detail or "").strip()[:200] or st.hint)

    def set_transcript(self, text: str) -> None:
        text = " ".join((text or "").split())
        if len(text) > self.MAX_TRANSCRIPT:
            text = "…" + text[-self.MAX_TRANSCRIPT :]
        self.transcript.setText(f"“{text}”" if text else "")
