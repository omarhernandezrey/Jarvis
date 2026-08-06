"""
JARVIS Local - Energia del equipo: bloquear, apagar, reiniciar, suspender.

Apagar y reiniciar NO son inmediatos: se programan con una cuenta regresiva
(60 s por defecto) que el sistema anuncia y que se aborta con "cancela el
apagado". Esa ventana ES la confirmacion, y funciona igual por texto y por
voz, en Windows y en Linux. Bloquear y suspender si son inmediatos: no
destruyen nada.
"""
import math
import subprocess

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

if IS_WINDOWS:
    import ctypes

DEFAULT_DELAY_SECONDS = 60


def _run_shutdown(args: list[str]) -> subprocess.CompletedProcess:
    """Unico punto que toca shutdown.exe en Windows (los tests lo reemplazan)."""
    return subprocess.run(["shutdown", *args], capture_output=True, text=True)


def _run_shutdown_linux(args: list[str]) -> subprocess.CompletedProcess:
    """Unico punto que toca `shutdown` en Linux (los tests lo reemplazan).
    Via sudo no interactivo (-n): si esta maquina no tiene sudo sin
    contrasena configurado, falla con un error legible en vez de colgarse
    esperando un password que nunca vendra."""
    return subprocess.run(["sudo", "-n", "shutdown", *args],
                          capture_output=True, text=True)


def _lock_workstation() -> bool:
    return bool(ctypes.windll.user32.LockWorkStation())


def _lock_session_linux() -> bool:
    out = subprocess.run(["loginctl", "lock-session"],
                         capture_output=True, text=True)
    return out.returncode == 0


def lock_pc() -> ActionPlan:
    """Bloquea la sesion (pantalla de bloqueo)."""
    plan = ActionPlan(action="bloquear_pc", risk=RiskLevel.EXECUTE,
                      reason="Bloquear la sesion")
    try:
        ok = _lock_workstation() if IS_WINDOWS else _lock_session_linux()
        if ok:
            plan.result = "Sesion bloqueada, senor."
            plan.status = ActionStatus.EXECUTED
        else:
            plan.status = ActionStatus.ERROR
            plan.error = "El sistema rechazo el bloqueo de sesion"
            plan.result = "No pude bloquear la sesion, senor."
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude bloquear la sesion: {e}"
    return plan


def _delayed(action: str, win_flag: str, linux_flag: str, verbo: str,
             seconds: int = DEFAULT_DELAY_SECONDS) -> ActionPlan:
    seconds = max(10, min(int(seconds), 3600))  # nunca menor a 10 s
    plan = ActionPlan(action=action, params={"segundos": seconds},
                      risk=RiskLevel.EXECUTE,
                      reason=f"{verbo} el equipo con cuenta regresiva cancelable")
    try:
        if IS_WINDOWS:
            out = _run_shutdown([win_flag, "/t", str(seconds)])
            ok = out.returncode == 0
        else:
            # `shutdown` en Linux solo acepta minutos, no segundos.
            minutos = max(1, math.ceil(seconds / 60))
            out = _run_shutdown_linux([linux_flag, f"+{minutos}"])
            ok = out.returncode == 0
        if not ok:
            raise OSError(out.stderr.strip() or f"shutdown {win_flag} fallo")
        plan.result = (f"{verbo}re el equipo en {seconds} segundos, senor. "
                       "Diga 'cancela el apagado' si desea abortarlo.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude programar la operacion: {e}"
    return plan


def shutdown_pc(seconds: int = DEFAULT_DELAY_SECONDS) -> ActionPlan:
    return _delayed("apagar_pc", "/s", "-h", "Apaga", seconds)


def restart_pc(seconds: int = DEFAULT_DELAY_SECONDS) -> ActionPlan:
    return _delayed("reiniciar_pc", "/r", "-r", "Reinicia", seconds)


def cancel_shutdown() -> ActionPlan:
    plan = ActionPlan(action="cancelar_apagado", risk=RiskLevel.EXECUTE,
                      reason="Abortar el apagado o reinicio programado")
    try:
        if IS_WINDOWS:
            out = _run_shutdown(["/a"])
            sin_pendiente = out.returncode == 1116
        else:
            out = _run_shutdown_linux(["-c"])
            sin_pendiente = out.returncode != 0 and "no scheduled" in (out.stderr or "").lower()
        if out.returncode == 0:
            plan.result = "Apagado cancelado, senor."
        elif sin_pendiente:
            plan.result = "No hay ningun apagado programado, senor."
        else:
            raise OSError(out.stderr.strip() or "no se pudo cancelar el apagado")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cancelar el apagado: {e}"
    return plan


def suspend_pc() -> ActionPlan:
    """Suspende el equipo (dormir). Inmediato pero reversible: se despierta."""
    plan = ActionPlan(action="suspender_pc", risk=RiskLevel.EXECUTE,
                      reason="Suspender el equipo")
    try:
        if IS_WINDOWS:
            # SetSuspendState(hibernate=0, force=0, wakeupEventsDisabled=0)
            ok = bool(ctypes.windll.powrprof.SetSuspendState(0, 0, 0))
            if not ok:
                raise OSError("SetSuspendState devolvio 0")
        else:
            out = subprocess.run(["systemctl", "suspend"],
                                 capture_output=True, text=True)
            if out.returncode != 0:
                raise OSError(out.stderr.strip() or "systemctl suspend fallo")
        plan.result = "Suspendiendo el equipo, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude suspender el equipo: {e}"
    return plan
