"""JARVIS Local - Brillo de pantalla (PLAN_EJECUCION FASE F · F1).

`brightnessctl`. Detección en runtime: si no está, se dice claramente (D0).

Límite inferior duro: NUNCA por debajo de `MIN_BRILLO_PCT`. Que la pantalla
quede a 0 y no se vea nada para corregirlo es un fallo del que no se sale
hablándole a JARVIS.

VERIFY: se relee el valor real tras aplicar (tres desenlaces D1).
"""
from __future__ import annotations

import shutil
import subprocess

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

MIN_BRILLO_PCT = 5          # nunca menos: hay que poder volver a subirlo
_PASO_PCT = 10


def _hay_brightnessctl() -> bool:
    return shutil.which("brightnessctl") is not None


def _bctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["brightnessctl", *args], capture_output=True,
                          text=True, timeout=10)


def get_brightness() -> int | None:
    """Brillo actual en % (0-100), o None si no se pudo leer."""
    if not _hay_brightnessctl():
        return None
    try:
        out = _bctl("-m", "get")           # -m: valor crudo (no %)
        maxi = _bctl("-m", "max")
        cur = int(out.stdout.strip())
        mx = int(maxi.stdout.strip())
        return round(cur * 100 / mx) if mx else None
    except (OSError, ValueError, ZeroDivisionError):
        return None


def _aplicar(pct: int) -> tuple[bool, str]:
    out = _bctl("set", f"{pct}%")
    if out.returncode != 0:
        return False, (out.stderr or "").strip() or f"código {out.returncode}"
    return True, ""


def set_brightness(nivel: int) -> ActionPlan:
    plan = ActionPlan(action="brillo_pantalla", params={"nivel": nivel},
                      risk=RiskLevel.EXECUTE, reason=f"Fijar el brillo al {nivel}%")
    if not _hay_brightnessctl():
        plan.status = ActionStatus.ERROR
        plan.error = "brightnessctl no instalado"
        plan.result = ("No puedo controlar el brillo: falta `brightnessctl`, "
                       "senor. Instálalo con `sudo apt install brightnessctl`.")
        return plan

    pedido = int(nivel)
    pct = max(MIN_BRILLO_PCT, min(pedido, 100))
    recorte = (f" (no bajo del {MIN_BRILLO_PCT}% para que no te quedes a "
               "oscuras sin poder corregirlo)") if pedido < MIN_BRILLO_PCT else ""
    plan.params["aplicado"] = pct

    from jarvis_local.tools import verify as _v
    tried: list[str] = []
    for i in range(2):
        ok, err = _aplicar(pct)
        if not ok:
            tried.append(f"brightnessctl set {pct}% -> {err}")
            if i == 0:
                continue
            return _v.finish(
                plan, _v.VerifyOutcome(False, err, "brightnessctl"),
                tried=tried, ok_msg="",
                fail_msg=f"No pude cambiar el brillo, senor: {err}.")
        _v.grace(0.2)
        real = get_brightness()
        if real is None:
            return _v.finish(
                plan, _v.VerifyOutcome(None, "no pude releer el brillo", "brightnessctl get"),
                ok_msg=f"Brillo al {pct} por ciento, senor.{recorte}", fail_msg="")
        if abs(real - pct) <= 4:
            return _v.finish(
                plan, _v.VerifyOutcome(True, f"brillo={real}%", "brightnessctl get"),
                ok_msg=f"Brillo al {real} por ciento, senor.{recorte}", fail_msg="")
        tried.append(f"leído {real}%, pedido {pct}%")
        if i == 0:
            plan.reason += " (reintento)"
    return _v.finish(
        plan, _v.VerifyOutcome(False, f"brillo={get_brightness()}%, pedido {pct}%",
                               "brightnessctl get"),
        tried=tried, ok_msg="",
        fail_msg=f"Pedí el brillo al {pct}% pero no se quedó ahí, senor.")


def brightness_up() -> ActionPlan:
    cur = get_brightness()
    return set_brightness((cur if cur is not None else 50) + _PASO_PCT)


def brightness_down() -> ActionPlan:
    cur = get_brightness()
    return set_brightness((cur if cur is not None else 50) - _PASO_PCT)
