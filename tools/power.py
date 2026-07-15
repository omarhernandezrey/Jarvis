"""
JARVIS Local - Energia del equipo: bloquear, apagar, reiniciar, suspender.

Apagar y reiniciar NO son inmediatos: se programan con una cuenta regresiva
(60 s por defecto) que Windows anuncia en pantalla y que se aborta con
"cancela el apagado". Esa ventana ES la confirmacion, y funciona igual por
texto y por voz. Bloquear y suspender si son inmediatos: no destruyen nada.
"""
import ctypes
import subprocess

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

DEFAULT_DELAY_SECONDS = 60


def _run_shutdown(args: list[str]) -> subprocess.CompletedProcess:
    """Unico punto que toca shutdown.exe (los tests lo reemplazan)."""
    return subprocess.run(["shutdown", *args], capture_output=True, text=True)


def _lock_workstation() -> bool:
    return bool(ctypes.windll.user32.LockWorkStation())


def lock_pc() -> ActionPlan:
    """Bloquea la sesion de Windows (pantalla de bloqueo)."""
    plan = ActionPlan(action="bloquear_pc", risk=RiskLevel.EXECUTE,
                      reason="Bloquear la sesion de Windows")
    try:
        if _lock_workstation():
            plan.result = "Sesion bloqueada, senor."
            plan.status = ActionStatus.EXECUTED
        else:
            plan.status = ActionStatus.ERROR
            plan.error = "LockWorkStation devolvio 0"
            plan.result = "Windows rechazo el bloqueo de sesion, senor."
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude bloquear la sesion: {e}"
    return plan


def _delayed(action: str, flag: str, verbo: str,
             seconds: int = DEFAULT_DELAY_SECONDS) -> ActionPlan:
    seconds = max(10, min(int(seconds), 3600))  # nunca menor a 10 s
    plan = ActionPlan(action=action, params={"segundos": seconds},
                      risk=RiskLevel.EXECUTE,
                      reason=f"{verbo} el equipo con cuenta regresiva cancelable")
    try:
        out = _run_shutdown([flag, "/t", str(seconds)])
        if out.returncode != 0:
            raise OSError(out.stderr.strip() or f"shutdown {flag} fallo")
        plan.result = (f"{verbo}re el equipo en {seconds} segundos, senor. "
                       "Diga 'cancela el apagado' si desea abortarlo.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude programar la operacion: {e}"
    return plan


def shutdown_pc(seconds: int = DEFAULT_DELAY_SECONDS) -> ActionPlan:
    return _delayed("apagar_pc", "/s", "Apaga", seconds)


def restart_pc(seconds: int = DEFAULT_DELAY_SECONDS) -> ActionPlan:
    return _delayed("reiniciar_pc", "/r", "Reinicia", seconds)


def cancel_shutdown() -> ActionPlan:
    plan = ActionPlan(action="cancelar_apagado", risk=RiskLevel.EXECUTE,
                      reason="Abortar el apagado o reinicio programado")
    try:
        out = _run_shutdown(["/a"])
        if out.returncode == 0:
            plan.result = "Apagado cancelado, senor."
        elif out.returncode == 1116:  # no habia apagado en curso
            plan.result = "No hay ningun apagado programado, senor."
        else:
            raise OSError(out.stderr.strip() or "shutdown /a fallo")
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
        # SetSuspendState(hibernate=0, force=0, wakeupEventsDisabled=0)
        ok = ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
        if not ok:
            raise OSError("SetSuspendState devolvio 0")
        plan.result = "Suspendiendo el equipo, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude suspender el equipo: {e}"
    return plan
