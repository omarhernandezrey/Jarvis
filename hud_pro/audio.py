"""Conversión de audio a nivel 0..1 para el orbe (escala perceptual en dBFS).

Sin dependencias obligatorias: usa numpy si está disponible, si no, Python puro.
"""

from __future__ import annotations

import array
import math
import sys
from typing import Any

DEFAULT_FLOOR_DB = -55.0  # por debajo = silencio visual


def rms_to_level(rms: float, floor_db: float = DEFAULT_FLOOR_DB) -> float:
    """RMS lineal (0..1, relativo a escala completa) → nivel perceptual 0..1."""
    try:
        rms = float(rms)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(rms) or rms <= 0.0:
        return 0.0
    if floor_db >= 0:
        raise ValueError("floor_db debe ser negativo (p. ej. -55.0)")
    db = 20.0 * math.log10(min(rms, 1.0))
    return max(0.0, min(1.0, (db - floor_db) / -floor_db))


def level_from_pcm16(data: bytes, floor_db: float = DEFAULT_FLOOR_DB) -> float:
    """Bloque PCM int16 little-endian (PyAudio, Vosk, webrtcvad…) → nivel 0..1."""
    if not data:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data[: len(data) - (len(data) % 2)])
    if not samples:
        return 0.0
    if sys.byteorder == "big":
        samples.byteswap()
    acc = sum(s * s for s in samples)
    return rms_to_level(math.sqrt(acc / len(samples)) / 32768.0, floor_db)


def level_from_float(samples: Any, floor_db: float = DEFAULT_FLOOR_DB) -> float:
    """Muestras float en -1..1 (sounddevice, numpy, listas) → nivel 0..1."""
    try:
        import numpy as np  # type: ignore

        arr = np.asarray(samples, dtype=np.float64).ravel()
        if arr.size == 0:
            return 0.0
        return rms_to_level(float(np.sqrt(np.mean(arr * arr))), floor_db)
    except ImportError:  # pragma: no cover - sin numpy
        vals = [float(x) for x in samples]
        if not vals:
            return 0.0
        return rms_to_level(math.sqrt(sum(v * v for v in vals) / len(vals)), floor_db)
