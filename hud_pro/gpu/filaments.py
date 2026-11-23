"""Generador de la red de filamentos del orbe (textura 2D cacheada).

La red se dibuja una sola vez (con supersampling 2x) y se guarda en
``_cache/filament_<size>.rgba``: canal R y G = dos redes independientes (para
parallax en el shader), canal B = halo suave de ambas, canal A = opaco
(reservado; el shader usa su propia máscara esférica).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CACHE_DIR = Path(__file__).resolve().parent / "_cache"
DEFAULT_SIZE = 1024
_TAU = math.tau


def _grow_network(size: int, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    ss = 2
    render = size * ss
    cx = cy = render * 0.5
    radius = render * 0.355
    scale = render / 1024.0
    n_att = 760
    rr = np.where(
        rng.random(n_att) < 0.55,
        radius * np.sqrt(rng.random(n_att)),
        radius * rng.random(n_att) ** 1.7,
    )
    aa = rng.random(n_att) * _TAU
    att = np.stack([cx + np.cos(aa) * rr, cy + np.sin(aa) * rr], axis=1)

    nodes = [np.array([cx, cy], dtype=float)]
    depths = [0]
    for _ in range(8):
        a = rng.random() * _TAU
        r = rng.random() ** 0.7 * radius * 0.48
        nodes.append(np.array([cx + math.cos(a) * r, cy + math.sin(a) * r]))
        depths.append(0)
    nodes_arr = np.array(nodes)
    edges: list[tuple[float, float, float, float, float]] = []

    for _ in range(420):
        if len(att) == 0:
            break
        diff = att[:, None, :] - nodes_arr[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        nearest = dist.argmin(axis=1)
        min_dist = dist[np.arange(len(att)), nearest]
        alive = min_dist >= 8.0 * scale
        candidates: list[tuple[np.ndarray, int]] = []

        for ni in np.unique(nearest[alive]):
            idx = np.where((nearest == ni) & alive)[0]
            if idx.size == 0:
                continue
            vecs = att[idx] - nodes_arr[ni]
            lens = np.linalg.norm(vecs, axis=1)
            keep = lens < radius * 0.30
            if not keep.any():
                continue
            vecs = vecs[keep]
            lens = lens[keep]
            dirs = vecs / lens[:, None]
            mean = dirs.mean(axis=0)
            n = np.linalg.norm(mean)
            if n < 1e-6:
                continue
            mean /= n
            curl = 0.24 * math.sin(nodes_arr[ni][0] * 0.014 + seed * 0.5) + 0.19 * math.cos(nodes_arr[ni][1] * 0.018 - seed * 0.3)
            mean = np.array([mean[0] * math.cos(curl) - mean[1] * math.sin(curl), mean[0] * math.sin(curl) + mean[1] * math.cos(curl)])
            angles = np.arctan2(dirs[:, 1], dirs[:, 0])
            mean_angle = math.atan2(mean[1], mean[0])
            delta = (angles - mean_angle + math.pi) % _TAU - math.pi

            if idx.size > 4 and np.abs(delta).max() > 0.62:
                left = delta > 0.0
                if left.sum() >= 2 and (~left).sum() >= 2:
                    for mask in (left, ~left):
                        v = dirs[mask].mean(axis=0)
                        v /= max(np.linalg.norm(v), 1e-6)
                        candidates.append((nodes_arr[ni] + v * 5.0 * scale, depths[ni] + 1))
                    continue

            candidates.append((nodes_arr[ni] + mean * 5.0 * scale, depths[ni] + 1))

        for pos, depth in candidates:
            if np.linalg.norm(pos - np.array([cx, cy])) > radius * 0.99:
                continue
            if np.min(np.linalg.norm(nodes_arr - pos, axis=1)) < 4.0 * scale:
                continue
            parent = int(np.argmin(np.linalg.norm(nodes_arr - pos, axis=1)))
            nodes_arr = np.vstack([nodes_arr, pos])
            nodes.append(pos)
            depths.append(depth)
            edges.append((nodes_arr[parent][0], nodes_arr[parent][1], pos[0], pos[1], depth))
        att = att[alive]

    xy = nodes_arr
    for i in range(len(xy)):
        for j in range(i + 1, min(len(xy), i + 18)):
            if np.linalg.norm(xy[i] - xy[j]) < 24.0 * scale and rng.random() < 0.030:
                edges.append((xy[i][0], xy[i][1], xy[j][0], xy[j][1], 5.0))

    img = Image.new("L", (render, render), 0)
    draw = ImageDraw.Draw(img)

    def wavy(x0: float, y0: float, x1: float, y1: float, width: int) -> None:
        mx = (x0 + x1) * 0.5
        my = (y0 + y1) * 0.5
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        off = rng.normal(0.0, 1.4 * scale)
        mx += -dy / ln * off
        my += dx / ln * off
        draw.line((x0, y0, mx, my, x1, y1), fill=255, width=width)

    for x0, y0, x1, y1, depth in edges:
        width = max(1, int(round((6.5 - float(depth) * 0.45) * scale)))
        wavy(x0, y0, x1, y1, width)

    for _ in range(200):
        a = rng.random() * _TAU
        r = rng.random() ** 0.8 * radius * 0.86
        x = cx + math.cos(a) * r
        y = cy + math.sin(a) * r
        theta = rng.random() * _TAU
        length = rng.uniform(14, 64) * scale
        x0, y0 = x, y
        for _seg in range(4):
            theta += rng.normal(0.0, 0.35)
            x += math.cos(theta) * length / 4.0
            y += math.sin(theta) * length / 4.0
            wavy(x0, y0, x, y, max(1, int(round(2 * scale))))
            x0, y0 = x, y

    for _ in range(28):
        a = rng.random() * _TAU
        r = rng.random() ** 0.7 * radius * 0.72
        lx = cx + math.cos(a) * r
        ly = cy + math.sin(a) * r
        rw = rng.uniform(10, 65) * scale
        rh = rng.uniform(6, 35) * scale
        start = rng.uniform(0, 360)
        draw.arc((lx - rw, ly - rh, lx + rw, ly + rh), start, start + rng.uniform(50, 260), fill=150, width=max(1, int(round(2 * scale))))

    img = img.resize((size, size), Image.LANCZOS)
    return img.filter(ImageFilter.GaussianBlur(0.5))


def _generate(size: int) -> bytes:
    net_a = _grow_network(size, 7311)
    net_b = _grow_network(size, 9917)
    halo = Image.blend(net_a, net_b, 0.5).filter(ImageFilter.GaussianBlur(size * 0.016))
    halo = halo.point(lambda v: int(min(255, v * 1.6)))

    rgba = Image.merge("RGBA", (net_a, net_b, halo, Image.new("L", (size, size), 255)))
    return rgba.tobytes()


def generate_or_load(size: int = DEFAULT_SIZE) -> bytes:
    path = CACHE_DIR / f"filament_{size}.rgba"
    expected = size * size * 4
    if path.exists() and path.stat().st_size == expected:
        return path.read_bytes()
    data = _generate(size)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


if __name__ == "__main__":
    out = CACHE_DIR / "filament_preview.png"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGBA", (DEFAULT_SIZE, DEFAULT_SIZE), generate_or_load()).save(out)
    print(out)
