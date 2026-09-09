"""JARVIS Local - Escritura del portapapeles (PLAN_EJECUCION FASE G).

Único trozo de la FASE G que se implementa: poner texto en el portapapeles.
Bajo riesgo — no ejecuta nada; el usuario pega con SU Ctrl+V (humano en el
bucle). El teclado sintético queda descartado (ver `docs/G0_ANALISIS_TECLADO.md`).

  - `escribir_portapapeles(texto)`: EXECUTE + VERIFY (se relee y se compara).
    Guarda el contenido anterior para poder restaurarlo ("deshaz").
  - Confirmación **solo** cuando el texto es largo o parece un comando / una
    URL / una credencial.
  - `restaurar_portapapeles`: devuelve el portapapeles a lo que había antes.
  - Interruptor `data/portapapeles_escritura.json` -> `{"activa": bool}`
    (por defecto activa).
  - Backend: `wl-copy`/`wl-paste` (Wayland nativo); si no están, `xclip`
    (X11 vía Xwayland — las apps Wayland puras pueden no verlo). Sin ninguno:
    ERROR claro.
  - Auditoría D2: el plan solo lleva un *preview* + longitud + motivo, nunca
    el texto entero (la auditoría no es un volcado del portapapeles).
"""
from __future__ import annotations

import contextlib
import json
import re
import secrets as _secrets
import shutil
import subprocess

from jarvis_local.config import BASE_DIR
from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy

_SWITCH = BASE_DIR / "data" / "portapapeles_escritura.json"
_LARGO = 280

# texto completo en espera de /confirmar (token efímero) y contenido previo
_PENDIENTE: dict[str, str] = {}
_PREVIO: dict = {"texto": None, "hubo": False}


# --- interruptor -------------------------------------------------------

def activa() -> bool:
    try:
        return bool(json.loads(_SWITCH.read_text(encoding="utf-8")).get("activa", True))
    except FileNotFoundError:
        return True
    except Exception:
        return True


def set_escritura(on: bool) -> ActionPlan:
    on = bool(on)
    with contextlib.suppress(Exception):
        _SWITCH.parent.mkdir(parents=True, exist_ok=True)
        _SWITCH.write_text(json.dumps({"activa": on}), encoding="utf-8")
    p = ActionPlan(action="escritura_portapapeles", params={"activa": on},
                   risk=RiskLevel.EXECUTE, status=ActionStatus.EXECUTED,
                   reason=("Activar" if on else "Desactivar") + " escritura de portapapeles")
    p.result = ("Ya puedo escribir en el portapapeles, senor." if on else
                "No escribiré en el portapapeles hasta que lo vuelvas a activar, senor.")
    return p


# --- backend ---------------------------------------------------------

def _backend() -> tuple[str, list[str], list[str]] | None:
    """(nombre, cmd_copiar, cmd_pegar) o None si no hay ninguno."""
    if shutil.which("wl-copy") and shutil.which("wl-paste"):
        return "wl-clipboard", ["wl-copy"], ["wl-paste", "--no-newline"]
    if shutil.which("xclip"):
        return ("xclip",
                ["xclip", "-selection", "clipboard"],
                ["xclip", "-selection", "clipboard", "-o"])
    return None


def _leer() -> str | None:
    b = _backend()
    if b is None:
        return None
    try:
        out = subprocess.run(b[2], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    # xclip/wl-paste devuelven rc != 0 cuando el portapapeles está vacío
    return out.stdout if out.returncode == 0 else ""


def _escribir(texto: str) -> bool:
    b = _backend()
    if b is None:
        return False
    try:
        # `xclip`/`wl-copy` se DAEMONIZAN para servir el selection: si se
        # capturan stdout/stderr, `run` se queda esperando EOF de esas pipes
        # (que el hijo hereda y no cierra nunca) hasta el timeout. Con DEVNULL
        # `run` vuelve en cuanto el proceso padre termina.
        p = subprocess.run(b[1], input=texto.encode("utf-8"),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=5)
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _sin_backend(plan: ActionPlan) -> ActionPlan:
    plan.status = ActionStatus.ERROR
    plan.error = "sin backend de portapapeles"
    plan.result = ("No puedo escribir en el portapapeles, senor: instala "
                   "`wl-clipboard` (`sudo apt install wl-clipboard`) o, en su "
                   "defecto, `xclip`.")
    return plan


# --- sensibilidad --------------------------------------------------

_RE_URL = re.compile(r"https?://|\bwww\.", re.IGNORECASE)
_RE_CMD = re.compile(
    r"(?:^|\s|;|&&|\|)\s*(?:sudo|rm\s+-rf|curl|wget|chmod|chown|dd\s+if=|mkfs|"
    r"eval|systemctl|kill|pkill|apt(?:-get)?\s+(?:install|remove|purge))\b"
    r"|:\(\)\s*\{|>\s*/dev/|/etc/[a-z]|\|\s*(?:sudo\s+)?(?:sh|bash|zsh)\b",
    re.IGNORECASE)
_RE_SECRETO = re.compile(
    r"-----BEGIN |"
    r"\b(?:password|passwd|token|secret|api[_-]?key|bearer)\b\s*[:=]|"
    r"\bghp_[A-Za-z0-9]{20}|\bAKIA[0-9A-Z]{12}\b|\beyJ[A-Za-z0-9_-]{10,}\.",
    re.IGNORECASE)


def _motivo_confirmacion(texto: str) -> str | None:
    if len(texto) > _LARGO:
        return f"es largo ({len(texto)} caracteres)"
    if _RE_CMD.search(texto):
        return "parece un comando"
    if _RE_URL.search(texto):
        return "contiene una URL"
    if _RE_SECRETO.search(texto):
        return "parece contener una credencial"
    return None


def _preview(texto: str) -> str:
    t = texto.replace("\n", " ⏎ ")
    return (t[:60] + "…") if len(t) > 60 else t


# --- escribir: plan + (confirmación condicional) + ejecutar --------

def plan_write_clipboard(texto: str) -> ActionPlan:
    plan = ActionPlan(action="escribir_portapapeles", risk=RiskLevel.EXECUTE,
                      reason="Escribir en el portapapeles")
    if _backend() is None:
        return _sin_backend(plan)
    if not activa():
        plan.status = ActionStatus.BLOCKED
        plan.result = ("La escritura del portapapeles está desactivada, senor. "
                       "Actívala si quieres que copie cosas.")
        return plan
    texto = texto if texto is not None else ""
    if not texto.strip():
        plan.status = ActionStatus.EXECUTED
        plan.result = "¿Qué copio al portapapeles, senor?"
        return plan

    motivo = _motivo_confirmacion(texto)
    if motivo is None:
        return execute_write_clipboard(texto)          # directo, con VERIFY

    tok = _secrets.token_hex(4)
    _PENDIENTE[tok] = texto
    plan.params.update(token=tok, preview=_preview(texto), n=len(texto), motivo=motivo)
    plan.simulation_result = permisos.texto_confirmacion(
        "copiar al portapapeles", _preview(texto),
        {"longitud": f"{len(texto)} caracteres", "motivo": motivo,
         "aviso": "sobrescribe lo que tengas copiado; puedo restaurarlo con «deshaz»"})
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_write_clipboard(texto: str) -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="escribir_portapapeles", risk=RiskLevel.EXECUTE,
                      status=ActionStatus.CONFIRMED, reason="Escribir en el portapapeles")
    if _backend() is None:
        return _sin_backend(plan)
    if not activa():
        plan.status = ActionStatus.BLOCKED
        plan.result = "La escritura del portapapeles está desactivada, senor."
        return plan

    _PREVIO["texto"] = _leer()
    _PREVIO["hubo"] = True
    ok = _escribir(texto)
    # la propiedad del selection es asíncrona (sobre todo con xclip): se
    # sondea la relectura un poco antes de dar el efecto por no aplicado.
    _v.wait_until(lambda: _leer() == texto, timeout=1.5, interval=0.2)
    leido = _leer()
    plan.params.update(preview=_preview(texto), n=len(texto))
    metodo = f"{_backend()[0]} -o"

    if ok and leido == texto:
        return _v.finish(
            plan, _v.VerifyOutcome(True, f"{len(texto)} caracteres en el portapapeles", metodo),
            ok_msg=f"Copiado, senor ({len(texto)} caracteres). Di «deshaz el portapapeles» "
                   "para restaurar lo anterior.", fail_msg="")
    if ok and leido is None:
        return _v.finish(
            plan, _v.VerifyOutcome(None, "no pude releer el portapapeles para confirmarlo", metodo),
            ok_msg="Lo envié al portapapeles, senor, pero no he podido confirmarlo.", fail_msg="")
    return _v.finish(
        plan, _v.VerifyOutcome(False, "el portapapeles no quedó con ese texto", metodo),
        tried=[f"{_backend()[0]} copy"], ok_msg="",
        fail_msg="No pude copiar al portapapeles, senor.")


def restore_clipboard() -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="restaurar_portapapeles", risk=RiskLevel.EXECUTE,
                      reason="Restaurar el portapapeles anterior")
    if _backend() is None:
        return _sin_backend(plan)
    if not _PREVIO["hubo"]:
        plan.status = ActionStatus.EXECUTED
        plan.result = "No he tocado tu portapapeles en esta sesión, senor; no hay nada que restaurar."
        return plan
    previo = _PREVIO["texto"] or ""
    ok = _escribir(previo)
    _v.wait_until(lambda: _leer() == previo, timeout=1.5, interval=0.2)
    leido = _leer()
    if ok and leido == previo:
        _PREVIO["hubo"] = False
        return _v.finish(
            plan, _v.VerifyOutcome(True, f"{len(previo)} caracteres restaurados", f"{_backend()[0]} -o"),
            ok_msg="Restaurado el portapapeles a lo que tenías antes, senor.", fail_msg="")
    return _v.finish(
        plan, _v.VerifyOutcome(False, "no quedó con el contenido previo", f"{_backend()[0]} -o"),
        tried=[f"{_backend()[0]} copy"], ok_msg="",
        fail_msg="No pude restaurar el portapapeles, senor.")
