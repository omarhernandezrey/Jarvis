"""Orbe JARVIS: renderer QPainter por capas + widget animado.

Separación de responsabilidades:
- ``OrbRenderer``: simulación (``advance``) y dibujo (``paint``). Sin QWidget → testeable
  y renderizable a QImage (capturas, GIFs, tests offscreen).
- ``OrbWidget``: ciclo de animación, eventos Qt y API pública.

Rendimiento (raster puro, sin GPU):
- Geometría de anillos → contornos pre-calculados a radio de referencia; por frame solo
  se rota/escala y rellena (sin stroker).
- Halo/bloom y capa HUD estática → sprites cacheados por (radio, color cuantizado).
- Interior del núcleo → textura a baja resolución + relleno del contorno a resolución
  completa (bordes nítidos, gradientes ~6× más baratos).
- Partículas → sprite único escalado con opacidad.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Iterable, Optional

from .qt_compat import Qt, QtCore, QtGui, QtWidgets, Signal
from .state import OrbState, StateLike, parse_state
from .theme import FONT_MONO, STATE_STYLES, StateStyle

TAU = math.tau
QPointF = QtCore.QPointF
QRectF = QtCore.QRectF
QColor = QtGui.QColor
QImage = QtGui.QImage
Plus = QtGui.QPainter.CompositionMode.CompositionMode_Plus
SourceOver = QtGui.QPainter.CompositionMode.CompositionMode_SourceOver
ARGB32P = QtGui.QImage.Format.Format_ARGB32_Premultiplied
AA = QtGui.QPainter.RenderHint.Antialiasing
SMOOTH = QtGui.QPainter.RenderHint.SmoothPixmapTransform

R_REF = 200.0  # radio de referencia para la geometría cacheada
_GLOW_BAKE = 1.45  # intensidad horneada en el sprite de halo; se modula con opacidad
_MICROTEXT = (
    (90.0, "NEURAL CORE  ·  v2"),
    (-30.0, "LOCAL  ·  OLLAMA"),
    (210.0, "VOICE  ·  MEMORY  ·  TOOLS"),
)
_SEGMENTS: tuple[tuple[float, float], ...] = (
    (0, 64),
    (78, 36),
    (126, 92),
    (232, 18),
    (262, 70),
    (344, 8),
)
_ANIM_KEYS = (
    "glow",
    "deform",
    "ring_speed",
    "particle_speed",
    "spectrum",
    "scanner",
    "ripple",
    "pulse_rate",
    "pulse_depth",
    "core",
)
_SPECTRUM_BARS = 120
_SPEC_TRIG = [
    (math.cos(TAU * i / _SPECTRUM_BARS - math.pi / 2), math.sin(TAU * i / _SPECTRUM_BARS - math.pi / 2))
    for i in range(_SPECTRUM_BARS)
]
_BLOB_POINTS = 160
_BLOB_TRIG = [
    (TAU * k / _BLOB_POINTS, math.cos(TAU * k / _BLOB_POINTS), math.sin(TAU * k / _BLOB_POINTS))
    for k in range(_BLOB_POINTS)
]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def _approach(cur: float, target: float, rate: float, dt: float) -> float:
    """Suavizado exponencial independiente del framerate."""
    return target + (cur - target) * math.exp(-rate * dt)


def _style_values(style: StateStyle) -> dict[str, float]:
    values = {k: float(getattr(style, k)) for k in _ANIM_KEYS}
    for prefix, rgb in (("p", style.primary), ("s", style.secondary), ("a", style.accent)):
        for ch, v in zip("rgb", rgb):
            values[prefix + ch] = float(v)
    return values


def _col(rgb: Iterable[float], a: float) -> QColor:
    r, g, b = rgb
    return QColor(int(r), int(g), int(b), int(_clamp(a) * 255))


def _quant(rgb: Iterable[float], step: int = 6) -> tuple[int, ...]:
    return tuple(int(round(v / step)) * step for v in rgb)


def _new_image(w: int, h: int) -> QImage:
    img = QImage(max(1, w), max(1, h), ARGB32P)
    img.fill(0)
    return img


def _hairline(color: QColor) -> QtGui.QPen:
    """Pen cosmético de 1 px físico: usa la ruta rápida del motor raster (5-10× más barato
    que un pen ancho) y queda nítido en HiDPI. El grosor se logra con trazos concéntricos."""
    pen = QtGui.QPen(color)
    pen.setWidthF(1.0)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


def _hairline_brush(brush: QtGui.QBrush) -> QtGui.QPen:
    pen = QtGui.QPen(brush, 1.0)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


def _draw_arcs(
    qp,
    c,
    radius: float,
    arcs: Iterable[tuple[float, float]],
    rotation: float,
    thickness: int = 1,
    step: float = 0.9,
) -> None:
    """Arcos (grados Qt) con grosor simulado mediante ``thickness`` trazos concéntricos."""
    offsets = [(i - (thickness - 1) / 2) * step for i in range(thickness)]
    for off in offsets:
        r = radius + off
        rect = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        for start, span in arcs:
            qp.drawArc(rect, int((start + rotation) * 16), int(span * 16))


@dataclass
class _Particle:
    radius: float  # múltiplo de R
    tilt: float
    orient: float
    speed: float
    phase: float
    size: float


class _RingGeometry:
    """Geometría de anillos a ``R_REF``. Se construye una sola vez por proceso."""

    _instance: Optional[_RingGeometry] = None

    @classmethod
    def get(cls) -> _RingGeometry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        R = R_REF
        r0 = R * 1.62
        self.ticks: list[QtCore.QLineF] = []
        for i in range(180):
            a = TAU * i / 180
            ln = R * (0.075 if i % 15 == 0 else 0.042 if i % 5 == 0 else 0.022)
            ca, sa = math.cos(a), math.sin(a)
            self.ticks.append(QtCore.QLineF(ca * r0, sa * r0, ca * (r0 + ln), sa * (r0 + ln)))

        dots = QtGui.QPainterPath()
        r2 = R * 1.52
        d = R * 0.0085
        for i in range(96):
            a = math.radians(300.0 * i / 96)
            dots.addRect(QRectF(math.cos(a) * r2 - d / 2, -math.sin(a) * r2 - d / 2, d, d))
        self.dots = dots

        self.brackets = [(90.0 * k - 6.0, 12.0) for k in range(4)]
        self.inner_outer = [(s * 120.0, 78.0) for s in range(3)]
        self.inner_inner = [(s * 120.0 + 40.0, 78.0) for s in range(3)]


class OrbRenderer:
    """Estado animado + dibujo del orbe. No depende de QWidget."""

    TRANSITION_RATE = 5.5  # 1/s → ~0.5 s por transición
    RIPPLE_LIFE = 1.9  # s
    MAX_RIPPLES = 7
    LEVEL_TIMEOUT = 0.35  # s sin nivel externo → nivel sintético al hablar
    TEXTURE_SCALE = 0.4  # resolución del interior del núcleo
    MICROTEXT_MIN_R = 95  # px

    def __init__(self, seed: int = 7, particles: int = 72) -> None:
        self.state = OrbState.IDLE
        self.reduced_motion = False
        self.scale = 1.0
        self._p = _style_values(STATE_STYLES[self.state])
        self._target = dict(self._p)
        self._t = 0.0
        # fases integradas (sin saltos al cambiar velocidades)
        self._ring = 0.0
        self._def_t = 0.0
        self._pt = 0.0
        self._pulse = 0.0
        self._scan = 90.0
        # audio
        self._level = 0.0
        self._level_target = 0.0
        self._level_ts = -1e9
        # ondas
        self._ripples: list[float] = []
        self._ripple_acc = 0.0
        # cachés
        self._glow_key: Optional[tuple] = None
        self._glow_img: Optional[QImage] = None
        self._static_key: Optional[tuple] = None
        self._static_img: Optional[QImage] = None
        self._spark_key: Optional[tuple] = None
        self._spark_img: Optional[QImage] = None
        self._tex: Optional[QImage] = None
        rnd = random.Random(seed)
        self._particles = [
            _Particle(
                radius=rnd.uniform(1.18, 1.78),
                tilt=math.radians(rnd.uniform(58, 80)),
                orient=rnd.uniform(0, TAU),
                speed=rnd.uniform(0.16, 0.48) * rnd.choice((-1, 1)),
                phase=rnd.uniform(0, TAU),
                size=rnd.uniform(0.7, 2.0),
            )
            for _ in range(particles)
        ]

    # ── API ───────────────────────────────────────────────────────────────
    def set_state(self, state: OrbState) -> None:
        self.state = state
        self._target = _style_values(STATE_STYLES[state])

    def set_level(self, level: float) -> None:
        try:
            value = float(level)
        except (TypeError, ValueError):
            value = 0.0
        if math.isnan(value) or math.isinf(value):
            value = 0.0
        self._level_target = _clamp(value)
        self._level_ts = self._t

    @property
    def level(self) -> float:
        return self._level

    def param(self, key: str) -> float:
        return self._p[key]

    def snap(self) -> None:
        """Salta directo al estado objetivo (tests/capturas)."""
        self._p = dict(self._target)

    # ── Simulación ────────────────────────────────────────────────────────
    def advance(self, dt: float) -> None:
        dt = _clamp(dt, 0.0, 0.1)
        self._t += dt
        p, tgt = self._p, self._target
        for k, v in tgt.items():
            p[k] = _approach(p[k], v, self.TRANSITION_RATE, dt)

        motion = 0.15 if self.reduced_motion else 1.0

        target = self._level_target
        if self._t - self._level_ts > self.LEVEL_TIMEOUT:
            target = self._synthetic_level() if self.state is OrbState.SPEAKING else 0.0
        rate = 28.0 if target > self._level else 7.0
        self._level = _approach(self._level, target, rate, dt)

        self._ring += dt * p["ring_speed"] * motion
        self._def_t += dt * (0.6 + 0.5 * p["ring_speed"]) * motion
        self._pt += dt * p["particle_speed"] * motion
        self._pulse += dt * TAU * p["pulse_rate"] * (0.35 if self.reduced_motion else 1.0)
        self._scan = (self._scan + dt * (40 + 150 * p["scanner"]) * p["ring_speed"] * motion) % 360

        if self.reduced_motion:
            self._ripples.clear()
            return
        self._ripple_acc += dt * p["ripple"] * (0.55 + 1.6 * self._level)
        while self._ripple_acc >= 1.0:
            self._ripple_acc -= 1.0
            self._ripples.append(self._t)
        self._ripples = [b for b in self._ripples if self._t - b < self.RIPPLE_LIFE][-self.MAX_RIPPLES :]

    def _synthetic_level(self) -> float:
        t = self._t
        v = 0.5 + 0.5 * math.sin(t * 7.3) * math.sin(t * 2.9 + 1.1)
        v *= 0.55 + 0.45 * math.sin(t * 1.3 + 0.4) ** 2
        return _clamp(0.12 + 0.6 * v)

    # ── Geometría ─────────────────────────────────────────────────────────
    @staticmethod
    def base_radius(w: float, h: float, scale: float = 1.0) -> float:
        return min(w, h) * 0.235 * scale

    # ── Dibujo ────────────────────────────────────────────────────────────
    def paint(self, painter: QtGui.QPainter, w: float, h: float) -> None:
        R = self.base_radius(w, h, self.scale)
        if R < 6:
            return
        p = self._p
        c = QPointF(w / 2.0, h / 2.0)
        P = (p["pr"], p["pg"], p["pb"])
        S = (p["sr"], p["sg"], p["sb"])
        A = (p["ar"], p["ag"], p["ab"])
        lvl = self._level
        pulse = 1.0 + p["pulse_depth"] * math.sin(self._pulse) + 0.07 * lvl
        Rr = R * pulse
        geo = _RingGeometry.get()

        painter.save()
        painter.setRenderHint(AA, True)
        painter.setRenderHint(SMOOTH, True)
        painter.setPen(Qt.PenStyle.NoPen)

        self._blit_centered(
            painter,
            c,
            self._glow_sprite(R, P, S),
            opacity=_clamp(p["glow"] * (1.0 + 0.3 * lvl) / _GLOW_BAKE),
            plus=True,
        )
        self._blit_centered(painter, c, self._static_sprite(R, P, A))
        self._paint_ripples(painter, c, R, P, geo)
        self._paint_rings(painter, c, R, P, A, geo)
        self._paint_scanner(painter, c, R, P, A, p["scanner"])
        self._paint_particles(painter, c, R, A, front=False)
        self._paint_spectrum(painter, c, R * (1.10 + 0.02 * lvl), R, P, A, p["spectrum"], lvl)
        self._paint_body(painter, c, Rr, P, S, A, p, lvl, geo)
        self._paint_particles(painter, c, R, A, front=True)
        self._paint_scanner_heads(painter, c, R, A, p["scanner"])

        painter.restore()

    # sprites cacheados -------------------------------------------------------
    @staticmethod
    def _blit_centered(qp, c, img: QImage, opacity: float = 1.0, plus: bool = False) -> None:
        if opacity <= 0.003:
            return
        qp.save()
        if plus:
            qp.setCompositionMode(Plus)
        if opacity < 1.0:
            qp.setOpacity(opacity)
        qp.drawImage(QPointF(round(c.x() - img.width() / 2), round(c.y() - img.height() / 2)), img)
        qp.restore()

    def _glow_sprite(self, R: float, P, S) -> QImage:
        key = (int(R), _quant(P), _quant(S))
        if key == self._glow_key and self._glow_img is not None:
            return self._glow_img
        rad = int(R) * 2.25
        size = int(math.ceil(2 * rad)) + 4
        img = _new_image(size, size)
        qp = QtGui.QPainter(img)
        qp.setRenderHint(AA, True)
        qp.setPen(Qt.PenStyle.NoPen)
        qp.setCompositionMode(Plus)
        cc = QPointF(size / 2.0, size / 2.0)
        k = _GLOW_BAKE
        g = QtGui.QRadialGradient(cc, rad)
        g.setColorAt(0.00, _col(P, 0.30 * k))
        g.setColorAt(0.28, _col(P, 0.15 * k))
        g.setColorAt(0.55, _col(S, 0.055 * k))
        g.setColorAt(1.00, _col(S, 0.0))
        qp.setBrush(g)
        qp.drawEllipse(cc, rad, rad)
        hr = int(R) * 1.44
        h = QtGui.QRadialGradient(cc, hr)
        h.setColorAt(0.00, _col(P, 0.0))
        h.setColorAt(0.57, _col(P, 0.44 * k))
        h.setColorAt(0.71, _col(P, 0.17 * k))
        h.setColorAt(0.86, _col(S, 0.05 * k))
        h.setColorAt(1.00, _col(S, 0.0))
        qp.setBrush(h)
        qp.drawEllipse(cc, hr, hr)
        qp.end()
        self._glow_key, self._glow_img = key, img
        return img

    def _static_sprite(self, R: float, P, A) -> QImage:
        """Capa HUD estática: microtexto y círculos finos."""
        key = (int(R), _quant(P, 10), _quant(A, 10))
        if key == self._static_key and self._static_img is not None:
            return self._static_img
        Ri = float(int(R))
        size = int(math.ceil(Ri * 4.2)) + 4
        img = _new_image(size, size)
        qp = QtGui.QPainter(img)
        qp.setRenderHint(AA, True)
        cc = QPointF(size / 2.0, size / 2.0)
        qp.setBrush(Qt.BrushStyle.NoBrush)
        for radius, colr, alpha in ((1.745, A, 0.10), (1.30, P, 0.13), (1.97, A, 0.05)):
            pen = QtGui.QPen(_col(colr, alpha))
            pen.setWidthF(1.0)
            qp.setPen(pen)
            qp.drawEllipse(cc, Ri * radius, Ri * radius)
        qp.setPen(Qt.PenStyle.NoPen)

        if Ri >= self.MICROTEXT_MIN_R:  # en orbes pequeños el microtexto satura
            self._paint_microtext(qp, cc, Ri, A)
        qp.end()
        self._static_key, self._static_img = key, img
        return img

    @staticmethod
    def _paint_microtext(qp, cc, Ri: float, A) -> None:
        px = max(8.0, Ri * 0.042)
        f = QtGui.QFont(FONT_MONO)
        f.setPixelSize(int(px))
        fm = QtGui.QFontMetricsF(f)
        radius = Ri * 1.90
        spacing = px * 0.30
        text_path = QtGui.QPainterPath()
        for center_deg, label in _MICROTEXT:
            advs = [fm.horizontalAdvance(ch) + spacing for ch in label]
            acc = -sum(advs) / 2
            bottom = math.sin(math.radians(center_deg)) < 0  # mitad inferior → texto derecho
            for ch, adv in zip(label, advs):
                if not ch.isspace():
                    glyph = QtGui.QPainterPath()
                    w = fm.horizontalAdvance(ch)
                    delta = math.degrees((acc + adv / 2) / radius)
                    tr = QtGui.QTransform()
                    if bottom:
                        glyph.addText(QPointF(-w / 2, radius + fm.capHeight()), f, ch)
                        tr.rotate(-90.0 - center_deg - delta)
                    else:
                        glyph.addText(QPointF(-w / 2, -radius), f, ch)
                        tr.rotate(90.0 - center_deg + delta)
                    text_path.addPath(tr.map(glyph))
                acc += adv
        qp.translate(cc)
        qp.fillPath(text_path, QColor(130, 180, 235, 70))
        # marcas de separación del microtexto
        for center_deg, label in _MICROTEXT:
            half = (sum(fm.horizontalAdvance(ch) + spacing for ch in label) / 2) / radius
            for sign in (-1, 1):
                a = math.radians(center_deg) + sign * (half + 0.05)
                rm = radius + fm.capHeight() / 2
                x, y = math.cos(a) * rm, -math.sin(a) * rm
                qp.setBrush(_col(A, 0.35))
                qp.drawEllipse(QPointF(x, y), 1.4, 1.4)

    def _spark_sprite(self, A) -> QImage:
        key = _quant(A, 12)
        if key == self._spark_key and self._spark_img is not None:
            return self._spark_img
        n = 24
        img = _new_image(n, n)
        qp = QtGui.QPainter(img)
        qp.setRenderHint(AA, True)
        qp.setPen(Qt.PenStyle.NoPen)
        cc = QPointF(n / 2, n / 2)
        g = QtGui.QRadialGradient(cc, n / 2)
        g.setColorAt(0.00, _col((245, 252, 255), 1.0))
        g.setColorAt(0.14, _col(A, 1.0))
        g.setColorAt(0.26, _col(A, 0.35))
        g.setColorAt(1.00, _col(A, 0.0))
        qp.setBrush(g)
        qp.drawEllipse(cc, n / 2, n / 2)
        qp.end()
        self._spark_key, self._spark_img = key, img
        return img

    # capas dinámicas -----------------------------------------------------------
    @staticmethod
    def _fill_ref(qp, c, path, scale: float, angle: float, color: QColor) -> None:
        qp.save()
        qp.translate(c)
        if angle:
            qp.rotate(angle)
        qp.scale(scale, scale)
        qp.fillPath(path, color)
        qp.restore()

    def _paint_ripples(self, qp, c, R, P, geo: _RingGeometry) -> None:
        if not self._ripples:
            return
        qp.setBrush(Qt.BrushStyle.NoBrush)
        for born in self._ripples:
            k = _clamp((self._t - born) / self.RIPPLE_LIFE)
            ease = 1 - (1 - k) ** 3
            r = R * (1.06 + 0.95 * ease)
            fade = (1 - k) ** 2
            qp.setPen(_hairline(_col(P, 0.55 * fade)))
            qp.drawEllipse(c, r, r)
            if k < 0.45:  # más grueso al nacer
                qp.setPen(_hairline(_col(P, 0.35 * fade)))
                qp.drawEllipse(c, r + 0.9, r + 0.9)
        qp.setPen(Qt.PenStyle.NoPen)

    def _paint_rings(self, qp, c, R, P, A, geo: _RingGeometry) -> None:
        s = R / R_REF
        ring = self._ring
        # ticks (líneas finas cacheadas, rotadas/escaladas por transform)
        qp.save()
        qp.translate(c)
        qp.rotate(ring * 6.0)
        qp.scale(s, s)
        qp.setPen(_hairline(_col(A, 0.30)))
        qp.drawLines(geo.ticks)
        qp.restore()
        self._fill_ref(qp, c, geo.dots, s, -ring * 9.0, _col(A, 0.30))

        qp.setBrush(Qt.BrushStyle.NoBrush)
        qp.setPen(_hairline(_col(P, 0.62)))
        _draw_arcs(qp, c, R * 1.80, geo.brackets, -ring * 2.5, thickness=2)
        qp.setPen(_hairline(_col(P, 0.55)))
        _draw_arcs(qp, c, R * 1.44, _SEGMENTS, -ring * 14.0, thickness=3)
        qp.setPen(Qt.PenStyle.NoPen)

    def _scan_heads(self, scanner: float) -> list[tuple[float, float]]:
        heads = [(self._scan, _clamp(scanner))]
        second = _clamp((scanner - 0.5) * 2.0)
        if second > 0.01:
            heads.append(((self._scan + 180.0) % 360, second))
        return heads

    def _paint_scanner(self, qp, c, R, P, A, scanner) -> None:
        if scanner < 0.02:
            return
        span = 110.0
        edge = span / 360.0
        qp.setBrush(Qt.BrushStyle.NoBrush)
        for head, alpha in self._scan_heads(scanner):
            g = QtGui.QConicalGradient(c, (head - span) % 360)
            g.setColorAt(0.0, _col(P, 0.0))
            g.setColorAt(edge * 0.7, _col(P, 0.35 * alpha))
            g.setColorAt(edge, _col(A, 0.95 * alpha))
            g.setColorAt(min(1.0, edge + 0.002), _col(P, 0.0))
            g.setColorAt(1.0, _col(P, 0.0))
            qp.setPen(_hairline_brush(QtGui.QBrush(g)))
            _draw_arcs(qp, c, R * 1.30, ((head - span, span),), 0.0, thickness=3)
        qp.setPen(Qt.PenStyle.NoPen)

    def _paint_scanner_heads(self, qp, c, R, A, scanner) -> None:
        if scanner < 0.02:
            return
        r = R * 1.30
        spark = self._spark_sprite(A)
        qp.save()
        qp.setCompositionMode(Plus)
        for head, alpha in self._scan_heads(scanner):
            a = math.radians(head)
            x, y = c.x() + math.cos(a) * r, c.y() - math.sin(a) * r
            side = R * 0.16
            qp.setOpacity(_clamp(alpha))
            qp.drawImage(QRectF(x - side / 2, y - side / 2, side, side), spark)
        qp.restore()

    def _paint_particles(self, qp, c, R, A, front: bool) -> None:
        cx, cy = c.x(), c.y()
        unit = max(0.8, R / 190.0)
        spark = self._spark_sprite(A)
        pt_time = self._pt * 2.2
        qp.save()
        for pt in self._particles:
            phi = pt.phase + pt.speed * pt_time
            sphi = math.sin(phi)
            z = sphi * math.sin(pt.tilt)
            if (z >= 0) != front:
                continue
            ro = pt.radius * R
            x0 = math.cos(phi) * ro
            y0 = sphi * ro * math.cos(pt.tilt)
            co, so = math.cos(pt.orient), math.sin(pt.orient)
            depth = (z + 1) / 2
            side = pt.size * unit * (0.65 + 0.6 * depth) * 7.0
            qp.setOpacity(0.20 + 0.70 * depth)
            x = cx + x0 * co - y0 * so
            y = cy + x0 * so + y0 * co
            qp.drawImage(QRectF(x - side / 2, y - side / 2, side, side), spark)
        qp.restore()

    def _paint_spectrum(self, qp, c, rb, R, P, A, vis, lvl) -> None:
        if vis < 0.02:
            return
        n = _SPECTRUM_BARS
        t = self._t
        cx, cy = c.x(), c.y()
        hw = 0.55 if R < 150 else 0.8  # separación de los 2 trazos que forman cada barra
        QLineF = QtCore.QLineF
        sin = math.sin
        lines: list = []
        append = lines.append
        for i, (ca, sa) in enumerate(_SPEC_TRIG):
            j = min(i, n - i)  # simetría espejo
            shape = 0.5 + 0.5 * sin(j * 0.55 + t * 5.2) * sin(j * 0.21 - t * 3.1 + 1.3)
            jitter = 0.5 + 0.5 * sin(t * (9.0 + (j % 7)) + j)
            ln = R * (
                0.012
                + vis * (0.018 + 0.30 * lvl * (0.35 + 0.65 * shape) * (0.6 + 0.4 * jitter) + 0.022 * shape)
            )
            x0, y0 = cx + ca * rb, cy + sa * rb
            x1, y1 = x0 + ca * ln, y0 + sa * ln
            ox, oy = -sa * hw, ca * hw
            append(QLineF(x0 + ox, y0 + oy, x1 + ox, y1 + oy))
            append(QLineF(x0 - ox, y0 - oy, x1 - ox, y1 - oy))
        g = QtGui.QRadialGradient(c, rb + R * 0.34)
        edge = rb / (rb + R * 0.34)
        g.setColorAt(0.0, _col(P, 0.0))
        g.setColorAt(edge, _col(P, 0.35 * vis + 0.1))
        g.setColorAt(min(1.0, edge + 0.12), _col(A, 0.85 * vis))
        g.setColorAt(1.0, _col(A, 0.95 * vis))
        qp.setPen(_hairline_brush(QtGui.QBrush(g)))
        qp.drawLines(lines)
        qp.setPen(Qt.PenStyle.NoPen)

    def _blob_path(self, c, Rr, deform, lvl) -> QtGui.QPainterPath:
        """Contorno orgánico del núcleo (suma de senos + reacción al audio)."""
        td = self._def_t
        t = self._t
        cx, cy = c.x(), c.y()
        body = QtGui.QPainterPath()
        a1, a2, a3 = 1.1 * td, -1.7 * td + 1.0, 2.3 * td + 2.0
        audio = lvl * 0.028
        sin = math.sin
        for k, (th, ct, st) in enumerate(_BLOB_TRIG):
            d = deform * (0.55 * sin(3 * th + a1) + 0.30 * sin(5 * th + a2) + 0.15 * sin(8 * th + a3))
            if audio:
                d += audio * sin(4 * th + 4.2 * t) * sin(2 * th - 1.3 * t)
            r = Rr * (1.0 + d)
            if k == 0:
                body.moveTo(cx + ct * r, cy + st * r)
            else:
                body.lineTo(cx + ct * r, cy + st * r)
        body.closeSubpath()
        return body

    def _body_texture(self, Rr, P, S, A, p, lvl) -> tuple[QImage, float]:
        """Interior del núcleo a baja resolución. Devuelve (imagen, semilado en px lógicos)."""
        k = self.TEXTURE_SCALE
        half = Rr * (1.0 + p["deform"] * 1.3 + 0.06) + 3
        n = int(math.ceil(2 * half * k)) + 2
        if self._tex is None or self._tex.width() != n:
            self._tex = QImage(n, n, ARGB32P)
        img = self._tex
        half = n / (2 * k)
        img.fill(0)
        qp = QtGui.QPainter(img)
        qp.setRenderHint(AA, True)
        qp.setPen(Qt.PenStyle.NoPen)
        qp.scale(k, k)
        cx = cy = half
        c = QPointF(cx, cy)
        core = p["core"] * (1.0 + 0.25 * lvl)

        base = QtGui.QRadialGradient(QPointF(cx - Rr * 0.16, cy - Rr * 0.2), Rr * 1.2)
        base.setColorAt(0.0, _col((S[0] * 0.75, S[1] * 0.75, S[2] * 0.85), 1.0))
        base.setColorAt(0.55, QColor(9, 24, 60))
        base.setColorAt(1.0, QColor(3, 8, 22))
        qp.fillRect(QRectF(0, 0, 2 * half, 2 * half), QtGui.QBrush(base))

        qp.setCompositionMode(Plus)
        t = self._def_t
        for wx, wy, ph, rr, colr, a in (
            (0.9, 1.3, 0.0, 0.62, P, 0.42),
            (1.2, 0.7, 2.1, 0.55, S, 0.55),
            (0.6, 1.1, 4.0, 0.50, A, 0.22),
            (1.5, 0.9, 5.2, 0.44, P, 0.30),
        ):
            gp = QPointF(cx + Rr * 0.40 * math.cos(wx * t + ph), cy + Rr * 0.36 * math.sin(wy * t + ph * 0.7))
            rad = Rr * rr
            g = QtGui.QRadialGradient(gp, rad)
            g.setColorAt(0.0, _col(colr, a * core))
            g.setColorAt(0.5, _col(colr, a * 0.35 * core))
            g.setColorAt(1.0, _col(colr, 0.0))
            qp.setBrush(g)
            qp.drawEllipse(gp, rad, rad)

        sw = QtGui.QConicalGradient(c, (self._ring * 22.0) % 360)
        stripes = 18
        for i in range(stripes + 1):
            sw.setColorAt(i / stripes, _col(P, 0.09 if i % 2 else 0.0))
        qp.setBrush(sw)
        qp.drawEllipse(c, Rr, Rr)

        cr = Rr * 0.64 * (1.0 + 0.10 * lvl)
        g = QtGui.QRadialGradient(c, cr)
        g.setColorAt(0.00, _col((235, 250, 255), 0.95 * core))
        g.setColorAt(0.10, _col(A, 0.80 * core))
        g.setColorAt(0.32, _col(P, 0.42 * core))
        g.setColorAt(0.68, _col(S, 0.10 * core))
        g.setColorAt(1.00, _col(S, 0.0))
        qp.setBrush(g)
        qp.drawEllipse(c, cr, cr)

        rim_r = Rr * (1.0 + p["deform"] * 1.1)
        g = QtGui.QRadialGradient(c, rim_r)
        g.setColorAt(0.70, _col(P, 0.0))
        g.setColorAt(0.92, _col(P, 0.32))
        g.setColorAt(1.00, _col(A, 0.62))
        qp.setBrush(g)
        qp.drawEllipse(c, rim_r * 1.06, rim_r * 1.06)
        qp.setCompositionMode(SourceOver)

        qp.translate(cx - Rr * 0.34, cy - Rr * 0.46)
        qp.rotate(-28)
        qp.scale(1.0, 0.46)
        sr = Rr * 0.44
        g = QtGui.QRadialGradient(QPointF(0, 0), sr)
        g.setColorAt(0.0, QColor(255, 255, 255, 58))
        g.setColorAt(1.0, QColor(255, 255, 255, 0))
        qp.setBrush(g)
        qp.drawEllipse(QPointF(0, 0), sr, sr)
        qp.end()
        return img, half

    def _paint_body(self, qp, c, Rr, P, S, A, p, lvl, geo: _RingGeometry) -> None:
        body = self._blob_path(c, Rr, p["deform"], lvl)
        tex, half = self._body_texture(Rr, P, S, A, p, lvl)

        brush = QtGui.QBrush(tex)
        tr = QtGui.QTransform()
        tr.translate(c.x() - half, c.y() - half)
        tr.scale(1.0 / self.TEXTURE_SCALE, 1.0 / self.TEXTURE_SCALE)
        brush.setTransform(tr)
        qp.setPen(Qt.PenStyle.NoPen)
        qp.fillPath(body, brush)

        qp.setBrush(Qt.BrushStyle.NoBrush)
        qp.setPen(_hairline(_col(A, 0.62)))  # filo nítido tipo cristal
        qp.drawPath(body)
        qp.setPen(_hairline(_col(A, 0.24)))
        _draw_arcs(qp, c, Rr * 0.80, geo.inner_outer, -self._ring * 18.0)
        qp.setPen(_hairline(_col(A, 0.16)))
        _draw_arcs(qp, c, Rr * 0.60, geo.inner_inner, self._ring * 26.0)
        qp.setPen(Qt.PenStyle.NoPen)


class OrbWidget(QtWidgets.QWidget):
    """Widget animado del orbe. Transparente: se dibuja sobre el fondo del padre."""

    stateChanged = Signal(str)

    IDLE_FPS = 30  # reposo: movimiento lento, 30 fps se ven fluidos y cuestan la mitad
    BACKGROUND_FPS = 20  # reposo + ventana sin foco

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, fps: Optional[int] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Orb")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 240)
        self.setAccessibleName("Orbe de estado de JARVIS")

        self._renderer = OrbRenderer()
        self._renderer.reduced_motion = os.environ.get("JARVIS_REDUCED_MOTION", "") == "1"

        env_fps = os.environ.get("JARVIS_HUD_FPS", "")
        self._fps = max(10, min(144, int(fps or (int(env_fps) if env_fps.isdigit() else 60))))
        self._timer = QtCore.QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._clock = QtCore.QElapsedTimer()
        self._paused = False

    # ── API pública ───────────────────────────────────────────────────────
    @property
    def state(self) -> OrbState:
        return self._renderer.state

    @property
    def renderer(self) -> OrbRenderer:
        return self._renderer

    def set_state(self, state: StateLike) -> None:
        new = parse_state(state)
        if new is self._renderer.state:
            return
        self._renderer.set_state(new)
        self._apply_interval()
        self.stateChanged.emit(new.value)
        self.update()

    def set_level(self, level: float) -> None:
        """Nivel de audio 0..1 (RMS normalizado). Seguro a alta frecuencia."""
        self._renderer.set_level(level)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._renderer.reduced_motion = bool(enabled)

    def set_fps(self, fps: int) -> None:
        self._fps = max(10, min(144, int(fps)))
        self._apply_interval()

    def set_paused(self, paused: bool) -> None:
        self._paused = bool(paused)
        self._sync_timer()

    def is_animating(self) -> bool:
        return self._timer.isActive()

    def orb_center(self) -> QtCore.QPointF:
        return QtCore.QPointF(self.width() / 2.0, self.height() / 2.0)

    def orb_radius(self) -> float:
        return OrbRenderer.base_radius(self.width(), self.height(), self._renderer.scale)

    # ── Ciclo ─────────────────────────────────────────────────────────────
    def _current_fps(self) -> int:
        if self._renderer.state is OrbState.IDLE:
            win = self.window()
            focused = win is None or win.isActiveWindow()
            return min(self._fps, self.IDLE_FPS if focused else self.BACKGROUND_FPS)
        return self._fps

    def refresh_frame_rate(self) -> None:
        """Recalcula el intervalo (p. ej. al ganar/perder foco la ventana)."""
        self._apply_interval()

    def _apply_interval(self) -> None:
        if self._timer.isActive():
            self._timer.setInterval(max(1, round(1000 / self._current_fps())))

    def _sync_timer(self) -> None:
        should_run = self.isVisible() and not self._paused
        if should_run and not self._timer.isActive():
            self._clock.restart()
            self._timer.start(max(1, round(1000 / self._current_fps())))
        elif not should_run and self._timer.isActive():
            self._timer.stop()

    def _tick(self) -> None:
        dt = self._clock.restart() / 1000.0
        self._renderer.advance(dt)
        self.update(self._dirty_rect())

    def _dirty_rect(self) -> QtCore.QRect:
        """Solo se repinta el cuadrado que ocupa el orbe (no todo el ancho del escenario)."""
        half = int(self.orb_radius() * 2.35) + 6
        c = self.rect().center()
        return QtCore.QRect(c.x() - half, c.y() - half, 2 * half, 2 * half).intersected(self.rect())

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        self._sync_timer()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        try:
            self._renderer.paint(painter, self.width(), self.height())
        finally:
            painter.end()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(520, 520)
