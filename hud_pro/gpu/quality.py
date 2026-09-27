"""Niveles de calidad del pipeline GPU + modo AUTO adaptivo por ms/frame real.

`JARVIS_HUD_QUALITY=low|medium|high|ultra|auto` (por defecto ``auto``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Quality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


@dataclass(frozen=True)
class QualitySettings:
    bloom_scale: float     # fracción de la resolución de pantalla para el FBO de bloom (1/4 en HIGH)
    kawase_levels: int      # niveles del pirámide dual-Kawase (downs + ups)
    streak_enabled: bool
    grain: float
    aberration: float       # px máximos de desplazamiento cromático en la esquina
    vignette: float
    godray_samples: int = 32     # 32..48 — nunca menos, mandato de presupuesto de GPU
    raymarch_steps: int = 24     # FASE C: pasos del raymarch del orbe (24 high / 40 ultra)
    bg_dynamic_scale: float = 0.6  # resolución de la capa DINÁMICA del fondo (niebla/reflejo/radar)


QUALITY_PRESETS: dict[Quality, QualitySettings] = {
    Quality.LOW: QualitySettings(
        bloom_scale=0.125, kawase_levels=2, streak_enabled=False,
        grain=0.018, aberration=0.6, vignette=0.22,
        godray_samples=32, raymarch_steps=16, bg_dynamic_scale=0.35,
    ),
    Quality.MEDIUM: QualitySettings(
        bloom_scale=0.20, kawase_levels=3, streak_enabled=True,
        grain=0.024, aberration=1.0, vignette=0.28,
        godray_samples=32, raymarch_steps=20, bg_dynamic_scale=0.5,
    ),
    Quality.HIGH: QualitySettings(
        bloom_scale=0.25, kawase_levels=4, streak_enabled=True,
        grain=0.030, aberration=1.4, vignette=0.32,
        # 32, no 40: medido en la Intel HD 520 real — los rayos de dios
        # son el pase más caro del pipeline: 40 muestras dejaba HIGH en
        # ~6-7ms GPU/1080p, por encima del presupuesto de FASE B (≤5ms).
        # 32 es el PISO del mandato (32-48), nunca menos.
        godray_samples=32, raymarch_steps=24, bg_dynamic_scale=0.6,
    ),
    Quality.ULTRA: QualitySettings(
        # kawase_levels=4, no 5: mandato "máximo 4 iteraciones" — un 5º
        # nivel no se nota en un bloom ya difuminado y cuesta 2 pases más
        # (down+up) de fill-rate.
        bloom_scale=0.333, kawase_levels=4, streak_enabled=True,
        grain=0.034, aberration=1.8, vignette=0.34,
        godray_samples=48, raymarch_steps=40, bg_dynamic_scale=0.75,
    ),
}


def parse_quality(value: str) -> Quality | None:
    """`None` -> modo AUTO (el valor no es un nivel fijo, o vino vacío)."""
    v = (value or "").strip().lower()
    if v in ("", "auto"):
        return None
    try:
        return Quality(v)
    except ValueError:
        return None


class AutoQualityController:
    """AUTO: parte de MEDIUM (medido en esta máquina: HIGH nunca sostiene
    el presupuesto de frame ni con el escalado máximo de AUTO — arrancar
    ahí sólo garantiza varios frames caros hasta que la histéresis baje el
    nivel) y escala `bloom_scale`/`kawase_levels` hacia abajo si el frame
    sostiene más de `TARGET_MS`, recuperándolos cuando sobra margen — con
    histéresis para no oscilar cada frame."""

    TARGET_MS = 14.0
    RECOVER_MS = 10.0  # sólo sube si hay este margen por debajo del objetivo
    MIN_SCALE = 0.4    # nunca baja de esta fracción del preset base
    STEP = 0.06
    WINDOW = 20        # frames que promedia antes de decidir

    def __init__(self, base: QualitySettings = QUALITY_PRESETS[Quality.MEDIUM]) -> None:
        self._base = base
        self._scale = 1.0
        self._samples: list[float] = []

    def update(self, frame_ms: float) -> QualitySettings:
        self._samples.append(max(0.0, frame_ms))
        if len(self._samples) < self.WINDOW:
            return self.current
        avg = sum(self._samples) / len(self._samples)
        self._samples.clear()
        if avg > self.TARGET_MS:
            self._scale = max(self.MIN_SCALE, self._scale - self.STEP)
        elif avg < self.RECOVER_MS:
            self._scale = min(1.0, self._scale + self.STEP)
        return self.current

    @property
    def current(self) -> QualitySettings:
        s = self._scale
        levels = min(4, max(1, round(self._base.kawase_levels * (0.5 + 0.5 * s))))
        return QualitySettings(
            bloom_scale=max(0.06, self._base.bloom_scale * s),
            kawase_levels=levels,
            streak_enabled=self._base.streak_enabled and s > 0.55,
            grain=self._base.grain,
            aberration=self._base.aberration,
            vignette=self._base.vignette,
            # el mandato de 32-48 muestras para los rayos de dios es un
            # PISO, no un objetivo — AUTO nunca lo cruza aunque degrade
            # todo lo demás.
            godray_samples=max(32, round(self._base.godray_samples * (0.5 + 0.5 * s))),
            raymarch_steps=max(12, round(self._base.raymarch_steps * (0.4 + 0.6 * s))),
            bg_dynamic_scale=max(0.3, self._base.bg_dynamic_scale * (0.5 + 0.5 * s)),
        )

    @property
    def scale(self) -> float:
        return self._scale
