"""JARVIS Local - Procesos (PLAN_EJECUCION FASE E · E3).

Listar por consumo, matar por nombre o PID. Reglas duras:

  - E1: nunca se mata un proceso de la lista de intocables, ni a petición
    explícita (`safety/untouchables`).
  - E2: un proceso de otro usuario necesita root -> BLOQUEADO con la regla de
    sudoers (`safety/permisos`). JARVIS no usa `sudo`.
  - Confirmación (D-fase / E2): antes de matar se muestra PID, nombre, comando
    y usuario, con /cancelar.
  - SIGTERM primero, con espera. SIGKILL solo si sigue vivo y SOLO tras un
    segundo aviso. `kill -9` nunca es la primera opción.
  - Varios procesos con ese nombre -> se listan y se pregunta; JARVIS no elige.
  - VERIFY: se comprueba que el proceso murió de verdad. Un kill que devuelve
    0 y deja el proceso vivo es justo el fallo que la FASE D existe para cazar.
"""
from __future__ import annotations

import contextlib
import os

from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy
from jarvis_local.safety.untouchables import alternativa, is_untouchable_process

_TERM_ESPERA_S = 3.0
_KILL_ESPERA_S = 2.0


def _psutil():
    import psutil
    return psutil


def _safe(fn, defecto: str = ""):
    try:
        return fn() or defecto
    except Exception:
        return defecto


def _info(p) -> dict:
    """PID, nombre, comando, usuario — lo que se muestra antes de matar."""
    nombre = _safe(p.name, "?")
    comando = _safe(lambda: " ".join(p.cmdline()), "") or nombre
    return {
        "pid": p.pid,
        "nombre": nombre,
        "comando": comando[:160],
        "usuario": _safe(p.username, "?"),
    }


# --- listar --------------------------------------------------------------------

def list_processes(por: str = "cpu", top: int = 12) -> ActionPlan:
    plan = ActionPlan(action="listar_procesos", params={"por": por, "top": top},
                      risk=RiskLevel.READ, reason="Listar procesos (solo lectura)")
    por = (por or "cpu").lower()
    clave = "memoria" if por in ("ram", "memoria", "mem") else "cpu"
    try:
        psutil = _psutil()
    except ImportError:
        plan.status = ActionStatus.ERROR
        plan.error = "psutil no disponible"
        plan.result = "No puedo leer los procesos: falta psutil, senor."
        return plan

    import time

    # cpu_percent() necesita DOS lecturas con tiempo entre medias: se ceba en
    # la primera pasada y se lee en la segunda. (Con una sola pasada todo sale
    # a 0% y el "top por CPU" no ordena nada.)
    procs = list(psutil.process_iter(["pid", "name", "username"]))
    if clave == "cpu":
        for p in procs:
            with contextlib.suppress(Exception):
                p.cpu_percent(None)
        time.sleep(0.3)

    filas = []
    for p in procs:
        with contextlib.suppress(Exception):
            filas.append((
                p.info["pid"], p.info.get("name") or "?",
                p.cpu_percent(None) if clave == "cpu" else 0.0,
                p.memory_info().rss / 1024 / 1024,
                p.info.get("username") or "?",
            ))
    filas.sort(key=lambda f: f[2] if clave == "cpu" else f[3], reverse=True)

    unidad = "% CPU" if clave == "cpu" else "MB RAM"
    lineas = [f"Procesos por {unidad}, senor:"]
    for pid, nombre, cpu, mb, user in filas[:max(1, top)]:
        val = f"{cpu:.0f}%" if clave == "cpu" else f"{mb:.0f} MB"
        lineas.append(f"  {pid:>7}  {val:>7}  {nombre[:28]:<28}  {user}")
    plan.result = "\n".join(lineas)
    plan.status = ActionStatus.EXECUTED
    return plan


# --- resolver el objetivo ---------------------------------------------------

def _resolver(objetivo: str) -> tuple[list, str]:
    """Devuelve (procesos, error). `objetivo` es un PID o un nombre."""
    psutil = _psutil()
    obj = (objetivo or "").strip()
    if obj.isdigit():
        try:
            return [psutil.Process(int(obj))], ""
        except psutil.NoSuchProcess:
            return [], f"No hay ningún proceso con PID {obj}, senor."
    if not obj:
        return [], "¿Qué proceso quieres cerrar, senor? Dime el nombre o el PID."

    q = obj.lower().removesuffix(".exe")
    propios = {os.getpid()}
    encontrados = []
    for p in psutil.process_iter(["pid", "name"]):
        if p.info["pid"] in propios:
            continue
        n = (p.info.get("name") or "").lower()
        base = n.removesuffix(".exe")
        if base == q or (len(q) >= 3 and q in base):
            encontrados.append(p)
    if not encontrados:
        return [], f"No encontré ningún proceso que se llame '{obj}', senor."
    return encontrados, ""


def _linea_proc(p) -> str:
    i = _info(p)
    prot, _ = is_untouchable_process(name=i["nombre"], pid=i["pid"],
                                    cmdline=i["comando"])
    marca = "  [protegido, no lo mato]" if prot else ""
    return f"  PID {i['pid']:>7}  {i['nombre'][:24]:<24}  {i['usuario']:<10}  {i['comando'][:70]}{marca}"


def plan_kill(objetivo: str) -> ActionPlan:
    """Prepara el cierre de un proceso (pendiente de /confirmar). Nunca mata
    aquí."""
    try:
        _psutil()
    except ImportError:
        p = ActionPlan(action="matar_proceso", risk=RiskLevel.DELETE,
                       status=ActionStatus.ERROR)
        p.error = "psutil no disponible"
        p.result = "No puedo gestionar procesos: falta psutil, senor."
        return p

    procs, err = _resolver(objetivo)
    plan = ActionPlan(action="matar_proceso", params={"objetivo": objetivo},
                      risk=RiskLevel.DELETE, reason=f"Cerrar proceso: {objetivo}")
    if err:
        plan.status = ActionStatus.EXECUTED if "No encontré" in err or "No hay" in err \
            else ActionStatus.BLOCKED
        plan.result = err
        return plan

    if len(procs) > 1:
        # E3: no elige JARVIS. Se listan y se pide el PID exacto.
        plan.status = ActionStatus.BLOCKED
        plan.result = (
            f"Hay {len(procs)} procesos que casan con '{objetivo}', senor. "
            "Dime el PID exacto:\n" + "\n".join(_linea_proc(p) for p in procs))
        return plan

    p = procs[0]
    i = _info(p)

    prot, motivo = is_untouchable_process(name=i["nombre"], pid=i["pid"],
                                          cmdline=i["comando"])
    if prot:
        plan.status = ActionStatus.BLOCKED
        plan.result = (f"No voy a matar el PID {i['pid']} ({i['nombre']}): "
                       f"{motivo}, senor.\n{alternativa(i['nombre'])}")
        return plan

    mio = permisos.proceso_es_del_usuario(i["pid"])
    if mio is False:
        # E1·c: un proceso del sistema mientras se instalan paquetes puede ser
        # un script de mantenimiento; no se toca hasta que la transacción acabe.
        if permisos.transaccion_de_paquetes_en_curso():
            return permisos.bloqueo_por_transaccion(
                f"matar el PID {i['pid']} ({i['nombre']})")
        return permisos.bloqueo_por_sudo(
            "kill_otro_usuario",
            f"matar el PID {i['pid']} ({i['nombre']}, de {i['usuario']})",
            hazlo_tu=f"sudo kill {i['pid']}")

    plan.params["pid"] = i["pid"]
    plan.simulation_result = permisos.texto_confirmacion(
        "matar el proceso", i["nombre"],
        {"PID": i["pid"], "usuario": i["usuario"], "comando": i["comando"]})
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


# --- ejecutar (tras /confirmar) --------------------------------------------

def _murio(pid: int) -> bool:
    psutil = _psutil()
    if not psutil.pid_exists(pid):
        return True
    with contextlib.suppress(Exception):
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    return False


def _re_guardas(pid: int) -> ActionPlan | None:
    """Defensa en profundidad: E1 y E2 se re-comprueban antes de ejecutar."""
    psutil = _psutil()
    try:
        p = psutil.Process(pid)
        i = _info(p)
    except psutil.NoSuchProcess:
        pl = ActionPlan(action="matar_proceso", risk=RiskLevel.DELETE,
                        status=ActionStatus.EXECUTED)
        pl.params = {"pid": pid, "verify": {"ok": True, "method": "pid_exists",
                                            "detail": "ya no existía"}}
        pl.result = f"El proceso {pid} ya no estaba, senor."
        return pl
    prot, motivo = is_untouchable_process(name=i["nombre"], pid=pid,
                                          cmdline=i["comando"])
    if prot:
        pl = ActionPlan(action="matar_proceso", risk=RiskLevel.DELETE,
                        status=ActionStatus.BLOCKED)
        pl.result = f"No mato el PID {pid} ({i['nombre']}): {motivo}, senor."
        return pl
    if permisos.proceso_es_del_usuario(pid) is False:
        if permisos.transaccion_de_paquetes_en_curso():
            return permisos.bloqueo_por_transaccion(
                f"matar el PID {pid} ({i['nombre']})")
        return permisos.bloqueo_por_sudo(
            "kill_otro_usuario", f"matar el PID {pid} ({i['nombre']})",
            hazlo_tu=f"sudo kill {pid}")
    return None


def execute_kill(pid: int) -> ActionPlan:
    """SIGTERM + espera + VERIFY. Si sigue vivo, NO fuerza: devuelve un plan
    que pide un SEGUNDO /confirmar para SIGKILL."""
    from jarvis_local.tools import verify as _v

    bloqueo = _re_guardas(pid)
    if bloqueo is not None:
        return bloqueo

    psutil = _psutil()
    p = psutil.Process(pid)
    nombre = _safe(p.name) or str(pid)
    plan = ActionPlan(action="matar_proceso", params={"pid": pid, "nombre": nombre},
                      risk=RiskLevel.DELETE, status=ActionStatus.CONFIRMED,
                      reason=f"SIGTERM a {nombre} ({pid})")
    try:
        p.terminate()                       # SIGTERM, educado
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        return permisos.bloqueo_por_sudo(
            "kill_otro_usuario", f"matar el PID {pid} ({nombre})",
            hazlo_tu=f"sudo kill {pid}")
    _v.grace(0)
    with contextlib.suppress(Exception):
        psutil.wait_procs([p], timeout=_TERM_ESPERA_S)

    if _murio(pid):
        return _v.finish(plan, _v.VerifyOutcome(True, f"PID {pid} terminado (SIGTERM)",
                                                "psutil.pid_exists"),
                         ok_msg=f"Listo, senor: cerré {nombre} (PID {pid}) con SIGTERM.",
                         fail_msg="")

    # sigue vivo -> SEGUNDO aviso, no se fuerza sin él
    forzar = ActionPlan(action="forzar_matar_proceso", params={"pid": pid, "nombre": nombre},
                        risk=RiskLevel.DELETE, reason=f"SIGKILL a {nombre} ({pid})")
    forzar.simulation_result = (
        f"{nombre} (PID {pid}) sigue vivo tras SIGTERM y {int(_TERM_ESPERA_S)} s "
        f"de espera, senor. ¿Lo fuerzo con SIGKILL (kill -9)? Es más brusco: la "
        f"app no guarda nada.\nEscribe /confirmar para forzar o /cancelar.")
    forzar.status = ActionStatus.PLANNED
    policy.pending_plan = forzar
    # SIGTERM enviado pero el proceso NO murió: no es un éxito. Se deja el
    # verify en None (no confirmado) y el texto es el segundo aviso.
    plan.status = ActionStatus.EXECUTED
    plan.params["verify"] = {"ok": None, "method": "psutil.pid_exists",
                             "detail": "sigue vivo tras SIGTERM; pendiente SIGKILL"}
    plan.result = forzar.simulation_result
    return plan


def execute_kill_force(pid: int) -> ActionPlan:
    """SIGKILL + espera + VERIFY. Último recurso."""
    from jarvis_local.tools import verify as _v

    bloqueo = _re_guardas(pid)
    if bloqueo is not None:
        return bloqueo

    psutil = _psutil()
    nombre = str(pid)
    plan = ActionPlan(action="forzar_matar_proceso", params={"pid": pid},
                      risk=RiskLevel.DELETE, status=ActionStatus.CONFIRMED,
                      reason=f"SIGKILL a {pid}")
    try:
        p = psutil.Process(pid)
        nombre = _safe(p.name) or str(pid)
        plan.params["nombre"] = nombre
        p.kill()                            # SIGKILL
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        return permisos.bloqueo_por_sudo(
            "kill_otro_usuario", f"forzar el PID {pid}", hazlo_tu=f"sudo kill -9 {pid}")
    _v.grace(0)
    with contextlib.suppress(Exception):
        psutil.wait_procs([psutil.Process(pid)], timeout=_KILL_ESPERA_S)

    if _murio(pid):
        return _v.finish(plan, _v.VerifyOutcome(True, f"PID {pid} terminado (SIGKILL)",
                                                "psutil.pid_exists"),
                         ok_msg=f"Forzado, senor: {nombre} (PID {pid}) muerto con SIGKILL.",
                         fail_msg="")
    return _v.finish(
        plan,
        _v.VerifyOutcome(False, f"PID {pid} sigue vivo tras SIGKILL", "psutil.pid_exists"),
        tried=["SIGTERM + espera", "SIGKILL + espera"],
        ok_msg="",
        fail_msg=(f"No pude matar el PID {pid} ni con SIGKILL, senor. Suele ser "
                  "un proceso del kernel, un zombie irrecuperable, o necesita "
                  "root. Compruébalo tú con `ps -o stat= -p " + str(pid) + "`."))
