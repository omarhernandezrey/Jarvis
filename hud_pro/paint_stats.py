"""JARVIS_HUD_PAINT_STATS=1 — contador de ``QEvent.Paint`` por widget.

Herramienta de diagnóstico (tarea A de CPU): con un ``QOpenGLWidget`` en
la ventana, CUALQUIER ``update()`` de un widget encima obliga a Qt a
recomponer TODA la ventana — un reloj o un chip que repinta "por si
acaso" cuesta lo mismo que repintar el HUD entero. Este filtro se
instala en la ``QApplication`` (sólo si la variable de entorno está a 1)
y cuenta los eventos ``Paint`` que recibe cada widget, con un volcado
periódico a stderr de los que superan un ritmo mínimo (por defecto 2
repintados/segundo, medido en la ventana real del HUD).

Variables de entorno:
    JARVIS_HUD_PAINT_STATS=1        activa el contador (ausente = apagado, coste cero)
    JARVIS_HUD_PAINT_STATS_INTERVAL segundos entre volcados (por defecto 10; 0 = sólo manual)
    JARVIS_HUD_PAINT_STATS_MIN      paints/s mínimos para listar un widget (por defecto 2)

En tests no hace falta la variable: se puede instanciar
:class:`PaintStatsFilter` a mano (intervalo 0) y leer :meth:`rates`.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from typing import IO, Optional

from .qt_compat import QtCore, QtWidgets


class PaintStatsFilter(QtCore.QObject):
    """Event filter de sólo observación (devuelve siempre False) que
    cuenta ``QEvent.Paint`` por widget destino. ``interval_s=0`` deja el
    volcado automático apagado (uso desde tests / volcado manual)."""

    def __init__(
        self,
        app: QtWidgets.QApplication,
        interval_s: float = 10.0,
        min_rate: float = 2.0,
        out: Optional[IO[str]] = None,
    ) -> None:
        super().__init__(app)
        self._interval_s = float(interval_s)
        self._min_rate = float(min_rate)
        self._out = out if out is not None else sys.stderr
        self._counts: Counter[int] = Counter()
        self._names: dict[int, str] = {}
        self._t0 = time.monotonic()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.dump)
        if self._interval_s > 0:
            self._timer.start(round(self._interval_s * 1000))

    # ── API ─────────────────────────────────────────────────────────────
    def reset(self) -> None:
        """Pone a cero contadores y el reloj (empezar una medición nueva)."""
        self._counts.clear()
        self._t0 = time.monotonic()

    def rates(self) -> dict[str, float]:
        """{etiqueta de widget: paints/segundo} desde el último ``reset``,
        ordenado de mayor a menor ritmo."""
        dt = max(1e-3, time.monotonic() - self._t0)
        rows = {self._names.get(k, str(k)): c / dt for k, c in self._counts.items()}
        return dict(sorted(rows.items(), key=lambda kv: kv[1], reverse=True))

    def top(self, min_rate: Optional[float] = None) -> dict[str, float]:
        """Sólo los widgets por encima del ritmo mínimo (``min_rate`` o el
        configurado)."""
        threshold = self._min_rate if min_rate is None else float(min_rate)
        return {k: v for k, v in self.rates().items() if v >= threshold}

    def dump(self) -> None:
        """Volcado a stderr (o al stream configurado) y ``reset`` — lo
        llama el timer interno cada ``interval_s`` segundos."""
        rates = self.rates()
        above = {k: v for k, v in rates.items() if v >= self._min_rate}
        dt = time.monotonic() - self._t0
        print(f"[paint-stats] últimos {dt:.0f}s — widgets a ≥{self._min_rate:.0f} paints/s:", file=self._out)
        if not above:
            print("[paint-stats]   (ninguno — la ventana está quieta)", file=self._out)
        for label, rate in above.items():
            print(f"[paint-stats]   {rate:6.1f}/s  {label}", file=self._out)
        total = sum(rates.values())
        print(f"[paint-stats]   total: {total:.1f} paints/s en {len(rates)} widgets", file=self._out)
        self.reset()

    # ── Filtro ──────────────────────────────────────────────────────────
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.Paint and isinstance(obj, QtWidgets.QWidget):
            key = id(obj)
            self._counts[key] += 1
            if key not in self._names:
                self._names[key] = self._label_for(obj)
        return False  # sólo observar: el evento sigue su camino normal

    @staticmethod
    def _label_for(widget: QtWidgets.QWidget) -> str:
        """Etiqueta legible: clase#objectName, más el texto (truncado) si
        es un QLabel — sin él, «QLabel#Metric» no dice CUÁL métrica es."""
        label = widget.metaObject().className()
        obj_name = widget.objectName()
        if obj_name:
            label += f"#{obj_name}"
        text = getattr(widget, "text", None)
        if callable(text):
            try:
                value = str(text()).strip()
            except Exception:  # pragma: no cover - defensivo
                value = ""
            if value:
                label += f"({value[:24]})"
        return label


def install_paint_stats(app: QtWidgets.QApplication, out: Optional[IO[str]] = None) -> PaintStatsFilter:
    """Instala el filtro en ``app`` leyendo los ajustes del entorno. Lo
    llama ``hud_pro.app.create_app`` cuando JARVIS_HUD_PAINT_STATS=1."""
    try:
        interval = float(os.environ.get("JARVIS_HUD_PAINT_STATS_INTERVAL", "10") or 10)
    except ValueError:
        interval = 10.0
    try:
        min_rate = float(os.environ.get("JARVIS_HUD_PAINT_STATS_MIN", "2") or 2)
    except ValueError:
        min_rate = 2.0
    stats = PaintStatsFilter(app, interval_s=interval, min_rate=min_rate, out=out)
    app.installEventFilter(stats)
    # referencia fuerte desde la propia app: con parent=app shiboken ya la
    # mantiene viva, pero esto la deja además accesible para tests/bench.
    app._paint_stats = stats  # type: ignore[attr-defined]  # noqa: SLF001
    print(
        f"[paint-stats] activo — volcado cada {interval:.0f}s, umbral {min_rate:.0f} paints/s",
        file=out if out is not None else sys.stderr,
    )
    return stats
