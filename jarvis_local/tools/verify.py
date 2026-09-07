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


def wait_until(pred, *, timeout: float = 3.0, interval: float = 0.2) -> bool:
    """Sondea `pred()` hasta que sea verdadero o se agote `timeout`.

    Arrancar una app (o cualquier efecto asíncrono) NO es instantáneo:
    comprobar justo después da un falso negativo. Esto sondea cada `interval`
    segundos hasta `timeout` y devuelve en cuanto `pred` se cumple. Si se
    agota sin cumplirse, devuelve False — eso es un fallo real, no un
    "no medible".
    """
    import time as _t

    if pred():
        return True
    deadline = _t.monotonic() + max(0.0, timeout)
    while _t.monotonic() < deadline:
        _t.sleep(interval)
        if pred():
            return True
    return False


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


# --- archivos ----------------------------------------------------------------
# Que el fichero EXISTA no basta: un fichero creado y vacío pasa una
# comprobación de existencia. Se comprueba también el TAMAÑO y, cuando es
# razonable leerlo, el CONTENIDO byte a byte.

_MAX_READBACK = 2_000_000  # por encima de esto solo se compara el tamaño


def file_written(path, expected_content: str = "") -> VerifyOutcome:
    """Comprueba que `path` es un fichero, con el tamaño y (si es abarcable) el
    contenido que se pidió escribir."""
    from pathlib import Path as _P

    p = _P(path)
    if not p.is_file():
        return VerifyOutcome(False, f"{p} no existe como fichero tras escribir", "os.path")
    esperado = (expected_content or "").encode("utf-8")
    try:
        real_size = p.stat().st_size
    except OSError as e:
        return VerifyOutcome(False, f"no pude leer el tamaño de {p}: {e}", "os.stat")
    if real_size != len(esperado):
        return VerifyOutcome(
            False, f"tamaño={real_size} B, se esperaban {len(esperado)} B", "os.stat")
    if len(esperado) > _MAX_READBACK:
        return VerifyOutcome(
            None, f"tamaño OK ({real_size} B); contenido no comparado (fichero grande)",
            "os.stat")
    try:
        real = p.read_bytes()
    except OSError as e:
        return VerifyOutcome(None, f"tamaño OK; no pude releer el contenido: {e}", "read")
    if real != esperado:
        return VerifyOutcome(False, "el contenido en disco no es el que se pidió", "read")
    return VerifyOutcome(True, f"{real_size} B, contenido verificado", "read")


def dir_created(path) -> VerifyOutcome:
    from pathlib import Path as _P

    p = _P(path)
    if p.is_dir():
        return VerifyOutcome(True, f"{p} existe como carpeta", "os.path")
    return VerifyOutcome(False, f"{p} no existe como carpeta tras crearla", "os.path")


def copied(src, dst) -> VerifyOutcome:
    """El destino existe y su tamaño (fichero) o su condición de carpeta casa
    con el origen."""
    from pathlib import Path as _P

    s, d = _P(src), _P(dst)
    if s.is_dir():
        return (VerifyOutcome(True, f"{d} existe como carpeta", "os.path")
                if d.is_dir()
                else VerifyOutcome(False, f"{d} no existe tras copiar la carpeta", "os.path"))
    if not d.is_file():
        return VerifyOutcome(False, f"{d} no existe como fichero tras copiar", "os.path")
    try:
        if d.stat().st_size != s.stat().st_size:
            return VerifyOutcome(
                False, f"tamaño destino {d.stat().st_size} != origen {s.stat().st_size}",
                "os.stat")
    except OSError as e:
        return VerifyOutcome(None, f"destino existe; no pude comparar tamaños: {e}", "os.stat")
    return VerifyOutcome(True, f"{d} copiado ({d.stat().st_size} B)", "os.stat")


def moved(src, dst) -> VerifyOutcome:
    """El destino existe y el origen ya NO."""
    from pathlib import Path as _P

    s, d = _P(src), _P(dst)
    if not d.exists():
        return VerifyOutcome(False, f"{d} no existe tras mover", "os.path")
    if s.exists():
        return VerifyOutcome(False, f"{d} existe pero {s} sigue ahí (copia, no movimiento)",
                             "os.path")
    return VerifyOutcome(True, f"{s.name} -> {d}", "os.path")

