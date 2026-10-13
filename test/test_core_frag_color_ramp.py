"""PLAN_EJECUCION FASE J · J6 (deuda nombrada): el "residuo verde del
satelite companero" (core.frag, anotado en I6.1/I2, nunca localizado con
certeza) resulto NO ser el satelite -- es el bloque de dispersion cromatica
del fresnel (BORDE, ~linea 159-163): `col.g` nunca se toca ahi, pero
`col.r`/`col.b` si, de forma asimetrica (derivada de un bump, positiva a un
lado del anillo, negativa al otro). Ninguno de los dos canales se vuelve
negativo nunca (demostrable analiticamente: la contribucion neta de ese
bloque es `rimCol * rimK * (0.6*rim + 0.4*shifted_bump)`, suma de dos
terminos no-negativos) -- la hipotesis de "canal negativo recortado a 0"
era incorrecta. El bug real: en el lado donde el desplazamiento RESTA,
R y/o B pueden quedar por DEBAJO de G sin volverse negativos, rompiendo
la invariante "todo lo que emite este shader sale de la rampa azul/cian"
(core.frag, comentario de cabecera). Justo tras una transicion de estado
(`transPhase=1`, dispara en CADA cambio listo/escuchando/hablando) con
emission/energy moderados (nada extremo) el color final tonemapeado sale
RGB=(0.65, 1.00, 0.67) -- verde puro.

Este test replica la formula EXACTA de `core.frag` (frecuencia 1 -- cuerpo,
y frecuencia 2 -- fresnel + dispersion cromatica) en Python puro, barre un
espacio de parametros realista (emission/energy/transPhase/escala de
pixel), y verifica que el canal G nunca supera a R ni a B tras el tonemap.
Si `core.frag` cambia esa formula, este test se desincroniza -- mantenerlo
en paso con el shader es responsabilidad de quien lo edite."""
from __future__ import annotations

import itertools


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _bump(absx: float, rw: float) -> float:
    return _smoothstep(rw, 0.0, absx)


def _hexcol(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _scale(a, s):
    return tuple(c * s for c in a)


# Design.cyan / Design.coreHot / Design.coreDeep (jarvis_local/ui/hud/qml/Design.qml)
_TINT = _hexcol("37D2FF")
_TINT_HOT = _hexcol("DCF6FF")
_TINT_DEEP = _hexcol("0A2A6E")
_LIMB_R = 0.86
_CA_OFF = 0.0035


def _warm_tint(energy: float) -> tuple[float, float, float]:
    rest = max(0.0, 1.0 - min(1.0, energy * 1.6))
    a = _mix(_mix(_TINT, _TINT_DEEP, 0.35 * (1 - energy)), _TINT_HOT, 0.22 * energy)
    dream = 0.5  # caso medio del seno de deriva onirica; no afecta el resultado cualitativo
    return _mix(a, _mix(_TINT_DEEP, _TINT, 0.65), 0.14 * dream * rest)


def _body_term(rad: float, emission: float, energy: float) -> tuple[float, float, float]:
    absorb = _smoothstep(0.0, 0.85, rad)
    body_mask = _smoothstep(0.98, 0.0, rad)
    wt = _warm_tint(energy)
    body = _mix(_scale(_TINT_DEEP, 0.5), wt, absorb)
    body = _mix(body, wt, 0.18 * energy)
    return _scale(body, body_mask * (0.34 + 0.5 * emission) * (0.6 + 0.5 * energy))


def _rim_ca_term(rad: float, rw: float, rim_k: float, fixed: bool) -> tuple[float, float, float]:
    rim_col = _mix(_TINT, _TINT_HOT, 0.55)
    rim = _bump(abs(rad - _LIMB_R), rw)
    shift_r = _bump(abs((rad + _CA_OFF) - _LIMB_R), rw) - rim
    shift_b = _bump(abs((rad - _CA_OFF) - _LIMB_R), rw) - rim
    r = rim_col[0] * rim * rim_k + rim_col[0] * shift_r * rim_k * 0.4
    g = rim_col[1] * rim * rim_k
    b = rim_col[2] * rim * rim_k + rim_col[2] * shift_b * rim_k * 0.4
    if fixed:
        r = max(r, g)
        b = max(b, g)
    return (r, g, b)


def _tonemap_clamp(col: tuple[float, float, float]) -> tuple[float, float, float]:
    denom = 1.0 + max(col) * 0.22
    return tuple(max(0.0, min(1.0, c / denom)) for c in col)


def _sweep_worst_greenness(fixed: bool) -> tuple[float, tuple]:
    """Mayor (g - max(r,b)) tras tonemap+clamp sobre un barrido realista de
    emission/energy/transPhase/escala de pixel alrededor del anillo del
    fresnel (limbR +/- unos pocos anchos de banda)."""
    worst = (-1.0, None)
    for emission, energy, trans_phase, aa in itertools.product(
        (0.2, 0.4, 0.6, 0.8, 1.0),
        (0.2, 0.4, 0.6, 0.8, 1.0),
        (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0),
        (0.002, 0.0035, 0.006),
    ):
        rim_k = (0.55 + 0.9 * emission) * (0.7 + 0.6 * energy) * (1.0 + 2.2 * (trans_phase ** 1.6))
        rw = max(aa, 0.0035) * 1.6
        n = 240
        for i in range(n):
            rad = _LIMB_R - 3 * rw + (6 * rw) * i / (n - 1)
            total = _add(_body_term(rad, emission, energy), _rim_ca_term(rad, rw, rim_k, fixed))
            r, g, b = _tonemap_clamp(total)
            greenness = g - max(r, b)
            if greenness > worst[0]:
                worst = (greenness, (r, g, b, rad, rim_k, emission, energy, trans_phase))
    return worst


def test_rim_dispersion_pre_fix_produces_visible_green():
    """Documenta el bug tal como existia: sin el piso `max(col.r/b, col.g)`,
    el bloque de dispersion cromatica SI produce un verde claramente
    dominante en una condicion realista (transicion de estado, emission/
    energy moderados) -- no un caso extremo inventado."""
    greenness, detail = _sweep_worst_greenness(fixed=False)
    assert greenness > 0.25, (
        f"se esperaba reproducir el verde pre-fix (>0.25), salio {greenness:.4f} -- "
        f"detalle={detail}"
    )


def test_rim_dispersion_never_breaks_cyan_ramp_after_fix():
    """Con el piso aplicado (core.frag actual: `col.r=max(col.r,col.g);
    col.b=max(col.b,col.g)`), G nunca debe superar a R ni a B tras el
    tonemap, en ningun punto del barrido -- la invariante que el propio
    comentario de core.frag declara ("todo... sale de la rampa azul/cian")
    vuelve a cumplirse de verdad."""
    greenness, detail = _sweep_worst_greenness(fixed=True)
    assert greenness <= 1e-9, f"queda verdor residual tras el fix: {greenness:.6f} -- detalle={detail}"
