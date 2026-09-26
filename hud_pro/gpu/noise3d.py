"""Ruido 3D tileable, precalculado — para el plasma del orbe (FASE C) y la
niebla del fondo (FASE B). Presupuesto de GPU en esta máquina (Intel HD 520)
prohíbe fbm procedural por píxel (varias octavas de ruido evaluadas en
cada fragmento, cada frame): en su lugar el shader hace 2-3 muestras de
ESTA textura con distinto offset/escala — el costo real es una lectura de
textura, no una cascada de `noise()` en GLSL.

Generación: dos campos de ruido de banda limitada (FFT de ruido blanco con
un filtro paso-bajo gaussiano) — tileables por construcción, ya que la DFT
es periódica: el borde de la textura envuelve exacto, sin costura. Canal R
= forma gruesa (cutoff bajo), canal G = detalle fino (cutoff alto). Se
cachea en disco (``_cache/noise3d_<size>.bin``) — sólo se regenera si no
existe o cambia el tamaño pedido.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).resolve().parent / "_cache"
DEFAULT_SIZE = 64
_SEED = 20260925  # fijo: reproducible entre corridas, no aleatorio por sesión


def _tileable_field(size: int, seed: int, cutoff: float) -> np.ndarray:
    """Campo real en [0, 1], `size`³, periódico en las 3 dimensiones."""
    rng = np.random.default_rng(seed)
    white = rng.normal(size=(size, size, size))
    spectrum = np.fft.fftn(white)
    freqs = np.fft.fftfreq(size)
    kx, ky, kz = np.meshgrid(freqs, freqs, freqs, indexing="ij")
    k = np.sqrt(kx**2 + ky**2 + kz**2)
    spectrum *= np.exp(-((k / cutoff) ** 2))
    field = np.fft.ifftn(spectrum).real
    lo, hi = field.min(), field.max()
    return (field - lo) / (hi - lo + 1e-12)


def _generate(size: int) -> bytes:
    r = _tileable_field(size, _SEED, cutoff=0.09)  # forma gruesa (niebla, cuerpo del plasma)
    g = _tileable_field(size, _SEED + 1, cutoff=0.24)  # detalle fino (filamentos, grano)
    packed = np.empty((size, size, size, 2), dtype=np.uint8)
    packed[..., 0] = np.clip(r * 255.0, 0, 255).astype(np.uint8)
    packed[..., 1] = np.clip(g * 255.0, 0, 255).astype(np.uint8)
    return packed.tobytes()


def generate_or_load(size: int = DEFAULT_SIZE) -> bytes:
    """`size`³ × 2 bytes (RG8), listos para `QOpenGLTexture(Target3D)`."""
    path = CACHE_DIR / f"noise3d_{size}.bin"
    expected = size * size * size * 2
    if path.exists() and path.stat().st_size == expected:
        return path.read_bytes()
    data = _generate(size)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data
