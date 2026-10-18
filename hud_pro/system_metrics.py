"""Fuente única de `psutil.cpu_percent()`/`virtual_memory()` para todo el HUD.

`psutil.cpu_percent(interval=None)` es no bloqueante, pero guarda un único
timestamp GLOBAL de "última llamada" (no uno por caller). Antes, tres
widgets independientes (`widgets.py::TopBar`, `panels.py::CompactSystemWidget`,
`panels.py::SystemPanel`) lo llamaban cada uno por su cuenta con cadencias
distintas (2 s, 1 s, 1 s) — se robaban la ventana de muestreo entre sí y
terminaban mostrando números de CPU DISTINTOS al mismo tiempo en la misma
pantalla (la barra superior se quedaba pegada cerca de 0 % mientras el
anillo de la esquina mostraba 40-50 %). Bug real, visto en captura.

Este módulo hace la ÚNICA llamada real a `psutil.cpu_percent` de todo
`hud_pro`. Cualquier widget que necesite CPU/RAM se suscribe a `sampler`
(`acquire()`/`release()` + señal `sampled`) en vez de llamar a psutil
directamente.
"""

from __future__ import annotations

from .qt_compat import QtCore, Signal

try:  # métricas opcionales, misma convención que widgets.py/panels.py
    import psutil  # type: ignore
except Exception:  # pragma: no cover - dependencia opcional
    psutil = None

AVAILABLE = psutil is not None

UPDATE_MS = 1000


class SystemMetricsSampler(QtCore.QObject):
    """Un solo `QTimer` por proceso. Arranca con el primer suscriptor
    (`acquire`) y para cuando se va el último (`release`) — mismo criterio
    de costo-cero que ya tenían los widgets individuales."""

    sampled = Signal(float, float)  # cpu_percent, ram_percent

    def __init__(self) -> None:
        super().__init__()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._sample)
        self._refcount = 0
        self._primed = False
        self._cpu = 0.0
        self._ram = 0.0

    def acquire(self) -> None:
        """Un suscriptor pide que el muestreo corra (idempotente por caller:
        cada `acquire()` debe tener su `release()` correspondiente)."""
        if not AVAILABLE:
            return
        if not self._primed:
            psutil.cpu_percent(interval=None)  # cebar la medición
            self._primed = True
        self._refcount += 1
        if self._refcount == 1:
            self._timer.start(UPDATE_MS)
            self._sample()

    def release(self) -> None:
        """El suscriptor ya no necesita el dato; para el timer si nadie más
        lo pidió."""
        if not AVAILABLE:
            return
        self._refcount = max(0, self._refcount - 1)
        if self._refcount == 0:
            self._timer.stop()

    def last(self) -> tuple[float, float]:
        """Último valor cacheado, sin volver a llamar a psutil."""
        return self._cpu, self._ram

    def _sample(self) -> None:
        if not AVAILABLE:
            return
        self._cpu = psutil.cpu_percent(interval=None)
        self._ram = psutil.virtual_memory().percent
        self.sampled.emit(self._cpu, self._ram)


sampler = SystemMetricsSampler()
