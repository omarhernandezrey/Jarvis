"""JARVIS Local - VERIFY post-acción (PLAN_EJECUCION FASE D · D1).

Una herramienta de WRITE no puede reportar ÉXITO sin COMPROBAR su efecto en la
máquina. El catálogo de la FASE B ya declara, en texto, cómo se comprueba cada
herramienta (`ToolContract.verify`); aquí esa comprobación se vuelve ejecutable.

Contrato de una herramienta con VERIFY:

  1. Ejecuta su efecto.
  2. Lo COMPRUEBA (lee el estado real: nivel de volumen, proceso vivo, archivo
     en disco, pista sonando...).
  3. Si la comprobación sale NEGATIVA -> reintenta UNA vez con una estrategia
     DISTINTA (otro binario, otra vía) y vuelve a comprobar.
  4. Si el reintento también falla -> el ActionPlan queda en ERROR con el
     detalle de lo que se intentó. JARVIS nunca dice "hecho" sin verde.

Tres desenlaces, no dos (`VerifyOutcome.ok`):
  - True  -> comprobado: el efecto ocurrió.
  - False -> comprobado: el efecto NO ocurrió (o quedó mal).
  - None  -> no se pudo comprobar en esta máquina (falta el mecanismo de
             lectura). No es un fallo, pero TAMPOCO es un éxito que se pueda
             afirmar: se reporta con la salvedad explícita.

`finish()` centraliza cómo se pliega el desenlace en el ActionPlan para que
todas las herramientas lo cuenten igual.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from jarvis_local.safety.policy import ActionPlan, ActionStatus

# Margen para que el efecto "asiente" antes de leerlo (spawn de proceso,
# PipeWire aplicando el volumen). Corto: no queremos que VERIFY añada latencia
# perceptible. Se puede subir por herramienta si hace falta.
GRACE_SECONDS = 0.15


@dataclass(frozen=True)
class VerifyOutcome:
    """Resultado de comprobar el efecto de una acción.

    ok:      True comprobado-hecho / False comprobado-no-hecho / None no-medible.
    detail:  qué se leyó exactamente (para el log y el mensaje honesto).
    method:  cómo se comprobó ("wpctl get-volume", "psutil process_iter"...).
    """

    ok: bool | None
    detail: str = ""
    method: str = ""


def grace(seconds: float = GRACE_SECONDS) -> None:
    """Pequeña espera para que el efecto sea observable. Aislada para poder
    parchearla a 0 en los tests."""
    if seconds > 0:
        time.sleep(seconds)


def finish(
    plan: ActionPlan,
    outcome: VerifyOutcome,
    *,
    ok_msg: str,
    fail_msg: str,
    tried: list[str] | None = None,
) -> ActionPlan:
    """Pliega el desenlace de VERIFY en el ActionPlan, de forma uniforme.

    - ok is True  -> EXECUTED, `ok_msg`.
    - ok is None  -> EXECUTED, `ok_msg` + salvedad ("no pude confirmarlo").
    - ok is False -> ERROR, `fail_msg` + lo que se intentó. Nunca se presenta
      como éxito.

    `tried` son las estrategias probadas (la principal y el reintento), para
    que el mensaje de fallo diga QUÉ se intentó y no solo que no salió.
    """
    plan.params = {
        **(plan.params or {}),
        "verify": {"ok": outcome.ok, "method": outcome.method, "detail": outcome.detail},
    }
    if outcome.ok is True:
        plan.status = ActionStatus.EXECUTED
        plan.result = ok_msg
        return plan
    if outcome.ok is None:
        plan.status = ActionStatus.EXECUTED
        salvedad = outcome.detail or "no hay forma de leer el estado en esta máquina"
        plan.result = f"{ok_msg} (No pude confirmar el efecto: {salvedad}.)"
        return plan
    # ok is False: el efecto no ocurrió. Esto NO se reporta como hecho.
    plan.status = ActionStatus.ERROR
    intentos = ""
    if tried:
        intentos = " Intenté: " + "; ".join(tried) + "."
    detalle = f" ({outcome.detail})" if outcome.detail else ""
    plan.error = f"verificación negativa{detalle}"
    plan.result = f"{fail_msg}{intentos}"
    return plan


# =============================================================================
# Comprobadores concretos
# =============================================================================


def volume_settled(expected: int, *, tol: int = 4) -> VerifyOutcome:
    """Lee el volumen maestro real y lo compara con el pedido.

    `tol` absorbe el redondeo de PipeWire/WASAPI (0.65 -> 65, pasos no exactos).
    """
    from jarvis_local.tools.media_controls import get_volume

    actual = get_volume()
    if actual is None:
        return VerifyOutcome(None, "no pude leer el volumen (sin wpctl/WASAPI)", "get_volume")
    if abs(actual - expected) <= tol:
        return VerifyOutcome(True, f"volumen={actual}% (pedido {expected}%)", "get_volume")
    return VerifyOutcome(False, f"volumen={actual}%, se pidió {expected}%", "get_volume")


def volume_changed(before: int | None, *, direction: int) -> VerifyOutcome:
    """Comprueba que el volumen se movió en el sentido pedido (`direction` = +1
    para subir, -1 para bajar). Tolera el tope: si ya estaba en 100 y se pidió
    subir, quedarse en 100 es correcto."""
    from jarvis_local.tools.media_controls import get_volume

    after = get_volume()
    if before is None or after is None:
        return VerifyOutcome(None, "no pude leer el volumen (sin wpctl/WASAPI)", "get_volume")
    if direction > 0:
        if after > before or before >= 100:
            return VerifyOutcome(True, f"{before}% -> {after}%", "get_volume")
    elif after < before or before <= 0:
        return VerifyOutcome(True, f"{before}% -> {after}%", "get_volume")
    return VerifyOutcome(False, f"{before}% -> {after}% (no cambió en el sentido pedido)", "get_volume")


def mute_settled(expected: bool) -> VerifyOutcome:
    """Lee el estado real de silencio y lo compara con el pedido."""
    from jarvis_local.tools.media_controls import is_muted

    actual = is_muted()
    if actual is None:
        return VerifyOutcome(None, "no pude leer el estado de silencio", "is_muted")
    if actual is expected:
        return VerifyOutcome(True, f"muteado={actual}", "is_muted")
    return VerifyOutcome(False, f"muteado={actual}, se pidió {expected}", "is_muted")
