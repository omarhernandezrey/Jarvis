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
    elif kind == "tool":
        pen.setWidthF(1.9)
        qp.setPen(pen)
        qp.drawLine(QPointF(s * 0.30, s * 0.70), QPointF(s * 0.62, s * 0.38))
        path = QtGui.QPainterPath()
        path.addEllipse(QRectF(s * 0.56, s * 0.14, s * 0.30, s * 0.30))
        qp.drawPath(path)
        qp.drawLine(QPointF(s * 0.18, s * 0.82), QPointF(s * 0.30, s * 0.70))
    elif kind == "check":
        pen.setWidthF(2.0)
        qp.setPen(pen)
        qp.drawLine(QPointF(s * 0.20, s * 0.52), QPointF(s * 0.42, s * 0.74))
        qp.drawLine(QPointF(s * 0.42, s * 0.74), QPointF(s * 0.82, s * 0.26))
    elif kind == "error":
        pen.setWidthF(2.0)
        qp.setPen(pen)
        qp.drawLine(QPointF(s * 0.24, s * 0.24), QPointF(s * 0.76, s * 0.76))
        qp.drawLine(QPointF(s * 0.76, s * 0.24), QPointF(s * 0.24, s * 0.76))
    elif kind == "memory":
        qp.drawRoundedRect(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64), s * 0.10, s * 0.10)
        qp.drawLine(QPointF(s * 0.32, s * 0.40), QPointF(s * 0.68, s * 0.40))
        qp.drawLine(QPointF(s * 0.32, s * 0.58), QPointF(s * 0.68, s * 0.58))
    elif kind == "new":
        pen.setWidthF(2.0)
        qp.setPen(pen)
        qp.drawLine(QPointF(s * 0.5, s * 0.18), QPointF(s * 0.5, s * 0.82))
        qp.drawLine(QPointF(s * 0.18, s * 0.5), QPointF(s * 0.82, s * 0.5))
    elif kind == "mute":
        qp.drawRoundedRect(QRectF(s * 0.20, s * 0.36, s * 0.22, s * 0.28), s * 0.04, s * 0.04)
        path = QtGui.QPainterPath()
        path.moveTo(s * 0.42, s * 0.36)
        path.lineTo(s * 0.64, s * 0.20)
        path.lineTo(s * 0.64, s * 0.80)
        path.lineTo(s * 0.42, s * 0.64)
        path.closeSubpath()
        qp.drawPath(path)
        pen.setWidthF(1.8)
        qp.setPen(pen)
        qp.drawLine(QPointF(s * 0.72, s * 0.36), QPointF(s * 0.88, s * 0.64))
        qp.drawLine(QPointF(s * 0.88, s * 0.36), QPointF(s * 0.72, s * 0.64))
    elif kind == "wake":
        pen.setWidthF(1.6)
        qp.setPen(pen)
        bars = (0.30, 0.55, 0.75, 0.55, 0.30)
        for i, hfrac in enumerate(bars):
            x = s * (0.20 + i * 0.15)
            h = s * hfrac
            qp.drawLine(QPointF(x, s * 0.5 - h / 2), QPointF(x, s * 0.5 + h / 2))
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
        self._paint_enabled = True

    def set_paint_enabled(self, enabled: bool) -> None:
        """Cuando `HoloStage` (fondo GPU) está activo, ESTE widget no debe
        pintar nada: su propio repintado (disparado por cualquier cosa que
        llame `update()` aquí, no sólo por `set_focus_point`) corre encima
        del último frame ya compuesto del hijo GL y lo tapa — confirmado
        empíricamente como una carrera real (fondo GPU en negro o partido
        a la mitad según qué región se repintara). Al desactivarlo también
        se quita `WA_OpaquePaintEvent`: si no, Qt asume que este widget
        rellenó cada píxel y el contenido de `HoloStage` por debajo queda
        indefinido en vez de mostrarse."""
        if self._paint_enabled == enabled:
            return
        self._paint_enabled = enabled
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, enabled)
        # sin esto, la región que este widget deja sin pintar no se trata
        # como "veo lo de detrás" sino como negro sólido — Qt necesita
        # saber que puede ALPHA-BLENDEAR el contenido GL de `HoloStage`
        # con lo que este widget (no) dibuja encima, no basta con omitir
        # el paintEvent.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, not enabled)
        self.update()

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
        if not self._paint_enabled:
            return
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
def _set_label_text(label: QtWidgets.QLabel, text: str) -> None:
    """`setText` sólo si el texto cambió de verdad — con un QOpenGLWidget
    en la ventana, cada repaint de un widget obliga a recomponerla TODA,
    así que «actualizar» con el mismo dato es CPU tirada (tarea A)."""
    if label.text() != text:
        label.setText(text)


class _Dot(QtWidgets.QWidget):
    def __init__(self, color: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QtGui.QColor(color)
        self.setFixedSize(14, 14)

    def set_color(self, color: str) -> None:
        new = QtGui.QColor(color)
        if new == self._color:
            return  # mismo color: un update() aquí recompone TODA la ventana
        self._color = new
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


class _PulseDot(_Dot):
    """Punto que late (opacidad oscilante) mientras el servicio trabaja de
    verdad — no decorativo: lo enciende/apaga `HudBridge.set_service_active`."""

    def __init__(self, color: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(color, parent)
        self._active = False
        self._phase = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active: bool) -> None:
        active = bool(active)
        if active == self._active:
            return
        self._active = active
        if active:
            self._timer.start(40)
        else:
            self._timer.stop()
            self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.12) % (2 * math.pi)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._active:
            super().paintEvent(event)
            return
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        qp.setPen(Qt.PenStyle.NoPen)
        c = QPointF(self.width() / 2, self.height() / 2)
        k = 0.5 + 0.5 * math.sin(self._phase)
        glow = QtGui.QColor(self._color)
        glow.setAlpha(int(40 + 60 * k))
        qp.setBrush(glow)
        qp.drawEllipse(c, 6.5 + 2.0 * k, 6.5 + 2.0 * k)
        qp.setBrush(self._color)
        qp.drawEllipse(c, 3.2, 3.2)
        qp.end()


class ServiceChip(QtWidgets.QFrame):
    """Chip de un servicio real (mic/wake/tts/memoria): ícono + etiqueta +
    punto que late si está trabajando. Sólo se muestra si el dato existe."""

    def __init__(self, icon_kind: str, label: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ServiceChip")
        self.setFixedHeight(24)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(7, 0, 9, 0)
        lay.setSpacing(5)
        self._icon = QtWidgets.QLabel(self)
        self._icon.setPixmap(make_icon(icon_kind, theme.TEXT_DIM, 13).pixmap(13, 13))
        self._label = QtWidgets.QLabel(label, self)
        self._label.setObjectName("ServiceChipLabel")
        self._dot = _PulseDot(theme.TEXT_MUTED, self)
        lay.addWidget(self._icon)
        lay.addWidget(self._label)
        lay.addWidget(self._dot)
        self._last_state: Optional[tuple] = None
        self.setVisible(False)

    def set_state(self, *, on: Optional[bool] = None, active: bool = False, tip: str = "") -> None:
        """`on=None` → dato desconocido (chip oculto: no se inventa). `on`
        real → color según disponibilidad; `active` → el punto late.
        Llega en cada muestreo de métricas (~2s) casi siempre con el MISMO
        estado: si nada cambió, no se toca nada (cada repaint recompone
        TODA la ventana, hay un QOpenGLWidget debajo)."""
        state = (on, bool(active), tip)
        if state == self._last_state:
            return
        self._last_state = state
        if on is None:
            self.setVisible(False)
            return
        self.setVisible(True)
        self._dot.set_color(theme.ACCENT if on else theme.TEXT_MUTED)
        self._dot.set_active(active and on)
        if tip:
            self.setToolTip(tip)

    def is_active(self) -> bool:
        return self._dot._active

    def set_active(self, active: bool) -> None:
        if self.isVisible():
            self._dot.set_active(active)


class Toast(QtWidgets.QFrame):
    """Aviso no intrusivo (error/recordatorio/info) que se apaga solo a los
    5 s. `kind='error'` es lo único que sale del azul/cian (rojo)."""

    LIFETIME_MS = 5000

    def __init__(self, message: str, kind: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", kind)
        self.setMaximumWidth(360)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        label = QtWidgets.QLabel(message, self)
        label.setObjectName("ToastText")
        label.setWordWrap(True)
        lay.addWidget(label)

        effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._in = QtCore.QPropertyAnimation(effect, b"opacity", self)
        self._in.setDuration(180)
        self._in.setStartValue(0.0)
        self._in.setEndValue(1.0)
        self._in.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._in.start()
        self._effect = effect

        QtCore.QTimer.singleShot(self.LIFETIME_MS, self._dismiss)

    def _dismiss(self) -> None:
        out = QtCore.QPropertyAnimation(self._effect, b"opacity", self)
        out.setDuration(220)
        out.setStartValue(1.0)
        out.setEndValue(0.0)
        out.finished.connect(self.deleteLater)
        out.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._out = out


class ToastOverlay(QtWidgets.QWidget):
    """Contenedor flotante (esquina superior derecha) que no participa del
    layout: se posiciona a mano sobre el resto de la ventana."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addStretch(1)  # los toasts se apilan desde abajo del contenedor
        self._layout = lay

    def add(self, message: str, kind: str) -> None:
        toast = Toast(message, kind, self)
        toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._layout.addWidget(toast)
        toast.destroyed.connect(lambda: None)

    def reposition(self, parent_rect: QtCore.QRect) -> None:
        w = 360
        margin = 16
        self.setGeometry(parent_rect.width() - w - margin, margin, w, parent_rect.height() - 2 * margin)
        self.raise_()


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

        # Ollama: único punto verde/rojo del HUD (pedido así explícitamente
        # para este indicador — el resto de la paleta se queda en azul/cian).
        self.ollama_dot = _Dot(theme.TEXT_MUTED, self)
        self.ollama_label = QtWidgets.QLabel("", self)
        self.ollama_label.setObjectName("Metric")
        self.ollama_label.setVisible(False)
        self.ollama_dot.setVisible(False)
        lay.addWidget(self.ollama_dot)
        lay.addWidget(self.ollama_label)

        # tokens/s + tiempo al primer token: sólo tienen sentido durante una
        # respuesta en curso — se ocultan en cuanto no hay dato reciente.
        self.speed_label = QtWidgets.QLabel("", self)
        self.speed_label.setObjectName("Metric")
        self.speed_label.setVisible(False)
        lay.addWidget(self.speed_label)

        self.metrics_label = QtWidgets.QLabel("", self)
        self.metrics_label.setObjectName("Metric")
        self.metrics_label.setVisible(psutil is not None)
        lay.addWidget(self.metrics_label)

        # VRAM (nvidia-smi): sólo aparece si la máquina de verdad lo tiene.
        self.vram_label = QtWidgets.QLabel("", self)
        self.vram_label.setObjectName("Metric")
        self.vram_label.setVisible(False)
        lay.addWidget(self.vram_label)
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

    def update_metrics(self, data: dict) -> None:
        """Datos reales del backend (Ollama, tokens/s, ttft, VRAM). Una
        clave ausente no toca lo que ya se mostraba; `None` explícito oculta
        ese campo — nunca se rellena con un valor inventado. Llega cada ~2s
        casi siempre con el MISMO dato: textos y stylesheet sólo se aplican
        si cambian (cada repaint recompone TODA la ventana, tarea A)."""
        if "online" in data:
            online = data["online"]
            if online is None:
                self.ollama_dot.setVisible(False)
                self.ollama_label.setVisible(False)
            else:
                self.ollama_dot.set_color("#22C55E" if online else theme.DANGER)
                self.ollama_dot.setVisible(True)
                ping = data.get("pingMs")
                _set_label_text(self.ollama_label, "OLLAMA" + (f"  {ping} ms" if online and ping is not None else ""))
                color = f"color: {'#22C55E' if online else theme.DANGER};"
                if self.ollama_label.styleSheet() != color:
                    self.ollama_label.setStyleSheet(color)
                self.ollama_label.setVisible(True)
        if "tokensPerSecond" in data or "ttftMs" in data:
            tps = data.get("tokensPerSecond")
            ttft = data.get("ttftMs")
            bits = []
            if tps:
                bits.append(f"{tps:.0f} tok/s")
            if ttft:
                bits.append(f"{ttft:.0f} ms al primer token")
            _set_label_text(self.speed_label, "  ·  ".join(bits))
            self.speed_label.setVisible(bool(bits))
        if "vramUsedMb" in data:
            vram = data.get("vramUsedMb")
            total = data.get("vramTotalMb")
            if vram is None:
                self.vram_label.setVisible(False)
            else:
                text = f"VRAM {vram:.0f}"
                if total:
                    text += f"/{total:.0f} MB"
                else:
                    text += " MB"
                _set_label_text(self.vram_label, text)
                self.vram_label.setVisible(True)

    def _refresh(self) -> None:
        # el reloj muestra HH:MM: fuera de un cambio de minuto, setText con
        # la misma hora es un repaint de la ventana entera tirado a la basura
        _set_label_text(self.clock, time.strftime("%H:%M"))
        if psutil is not None:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                _set_label_text(self.metrics_label, f"CPU {cpu:.0f}%  ·  RAM {ram:.0f}%")
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
        self.transcript.setVisible(False)  # vacía al arrancar: no reserva alto

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
        # Vacía = no reserva alto (capa bajo el orbe, no una franja fija
        # esperando texto): un widget oculto no ocupa espacio en el layout.
        self.transcript.setVisible(bool(text))
