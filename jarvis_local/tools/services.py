"""JARVIS Local - Servicios systemd (PLAN_EJECUCION FASE E · E4).

Estado, iniciar, parar, reiniciar. Reglas:

  - Por defecto, unidades de USUARIO (`systemctl --user`). Las de SISTEMA
    exigen root -> BLOQUEADO con la regla de sudoers concreta (`safety/
    permisos`); JARVIS no usa `sudo`.
  - La lista de intocables de E1 manda igual aquí: no se para `gdm`,
    `NetworkManager`, `systemd-logind`, `dbus`, `ollama`... ni con la regla
    de sudoers puesta.
  - Cambiar el estado de un servicio pide CONFIRMACIÓN (mostrando la unidad,
    la acción y el estado actual), con /cancelar.
  - VERIFY: se RELEE el estado del servicio tras la acción. Un `systemctl`
    que devuelve 0 y deja el servicio como estaba -> ERROR.
  - Si no hay `systemctl`, se dice; no se falla en silencio (D0).
"""
from __future__ import annotations

import shutil
import subprocess

from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy
from jarvis_local.safety.untouchables import alternativa, is_untouchable_unit

_ACCIONES = {
    "iniciar": "start", "arrancar": "start", "start": "start", "levantar": "start",
    "parar": "stop", "detener": "stop", "stop": "stop", "apagar": "stop",
    "reiniciar": "restart", "restart": "restart", "reinicia": "restart",
}
_ESPERADO = {"start": ("active", "activating"), "restart": ("active", "activating"),
             "stop": ("inactive", "failed", "dead")}


def _hay_systemctl() -> bool:
    return shutil.which("systemctl") is not None


def _norm_unit(servicio: str) -> str:
    s = (servicio or "").strip()
    if not s:
        return s
    if not s.endswith((".service", ".socket", ".timer", ".target", ".path", ".slice")):
        s += ".service"
    return s


def _systemctl(scope: str, *args: str) -> subprocess.CompletedProcess:
    base = ["systemctl"]
    if (scope or "user").lower() == "user":
        base.append("--user")
    return subprocess.run([*base, "--no-pager", *args],
                          capture_output=True, text=True, timeout=20)


def _show(scope: str, unit: str) -> dict:
    out = _systemctl(scope, "show", unit,
                     "-p", "LoadState", "-p", "ActiveState", "-p", "SubState",
                     "-p", "UnitFileState")
    d = {}
    for ln in (out.stdout or "").splitlines():
        k, _, v = ln.partition("=")
        d[k.strip()] = v.strip()
    return d


def _resumen(d: dict) -> str:
    return f"{d.get('ActiveState', '?')}/{d.get('SubState', '?')}"


# --- lectura ---------------------------------------------------------------

def service_status(servicio: str, scope: str = "user") -> ActionPlan:
    plan = ActionPlan(action="estado_servicio",
                      params={"servicio": servicio, "scope": scope},
                      risk=RiskLevel.READ, reason="Estado de servicio (solo lectura)")
    if not _hay_systemctl():
        plan.status = ActionStatus.ERROR
        plan.error = "systemctl no está"
        plan.result = "No puedo consultar servicios: este sistema no tiene systemctl, senor."
        return plan
    unit = _norm_unit(servicio)
    d = _show(scope, unit)
    if d.get("LoadState") == "not-found":
        otro = "system" if scope == "user" else "user"
        d2 = _show(otro, unit)
        if d2.get("LoadState") != "not-found":
            plan.result = (f"'{unit}' no es un servicio de {scope}, pero sí de "
                           f"{otro}: {_resumen(d2)} (habilitado: "
                           f"{d2.get('UnitFileState') or '?'}).")
            plan.status = ActionStatus.EXECUTED
            return plan
        plan.result = f"No encontré el servicio '{unit}', senor."
        plan.status = ActionStatus.EXECUTED
        return plan
    plan.result = (f"{unit} ({scope}): {_resumen(d)}. "
                   f"Habilitado al arranque: {d.get('UnitFileState') or '?'}.")
    plan.status = ActionStatus.EXECUTED
    return plan


# --- cambio de estado ----------------------------------------------------

def _guardas(unit: str, scope: str) -> ActionPlan | None:
    prot, motivo = is_untouchable_unit(unit)
    if prot:
        p = ActionPlan(action="controlar_servicio", risk=RiskLevel.DELETE,
                       status=ActionStatus.BLOCKED)
        p.result = (f"No voy a tocar {unit}: {motivo}, senor.\n{alternativa(unit)}")
        return p
    if permisos.unidad_es_de_sistema(scope):
        regla = permisos.SUDOERS_RULES["systemctl_sistema"].replace("<UNIDAD>", unit)
        pl = permisos.bloqueo_por_sudo(
            "systemctl_sistema", f"controlar el servicio de sistema {unit}",
            hazlo_tu=f"sudo systemctl <accion> {unit}")
        pl.result = pl.result.replace(
            permisos.SUDOERS_RULES["systemctl_sistema"], regla)
        return pl
    return None


def plan_service(accion: str, servicio: str, scope: str = "user") -> ActionPlan:
    a = _ACCIONES.get((accion or "").strip().lower())
    plan = ActionPlan(action="controlar_servicio",
                      params={"accion": a, "servicio": servicio, "scope": scope},
                      risk=RiskLevel.DELETE, reason=f"{accion} servicio {servicio}")
    if not _hay_systemctl():
        plan.status = ActionStatus.ERROR
        plan.error = "systemctl no está"
        plan.result = "Este sistema no tiene systemctl, senor."
        return plan
    if a is None:
        plan.status = ActionStatus.BLOCKED
        plan.result = (f"No sé qué es '{accion}' para un servicio, senor. "
                       "Puedo iniciar, parar o reiniciar.")
        return plan

    unit = _norm_unit(servicio)
    bloqueo = _guardas(unit, scope)
    if bloqueo is not None:
        return bloqueo

    d = _show(scope, unit)
    if d.get("LoadState") == "not-found":
        plan.status = ActionStatus.EXECUTED
        plan.result = f"No encontré el servicio '{unit}' (de {scope}), senor."
        return plan

    plan.params["unit"] = unit
    plan.simulation_result = permisos.texto_confirmacion(
        {"start": "iniciar", "stop": "parar", "restart": "reiniciar"}[a] + " el servicio",
        unit, {"estado ahora": _resumen(d), "ámbito": scope})
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_service(accion: str, servicio: str, scope: str = "user") -> ActionPlan:
    """Ejecuta la acción CONFIRMADA y RELEE el estado (VERIFY)."""
    from jarvis_local.tools import verify as _v

    a = _ACCIONES.get((accion or "").strip().lower(), accion)
    unit = _norm_unit(servicio)
    plan = ActionPlan(action="controlar_servicio",
                      params={"accion": a, "servicio": unit, "scope": scope},
                      risk=RiskLevel.DELETE, status=ActionStatus.CONFIRMED,
                      reason=f"{a} {unit}")

    bloqueo = _guardas(unit, scope)
    if bloqueo is not None:
        return bloqueo

    out = _systemctl(scope, a, unit)
    _v.grace(0.3)
    d = _show(scope, unit)
    estado = _resumen(d)
    esperado = _ESPERADO.get(a, ())

    if out.returncode != 0 and d.get("ActiveState") not in esperado:
        err = (out.stderr or "").strip() or f"código {out.returncode}"
        return _v.finish(
            plan, _v.VerifyOutcome(False, f"systemctl {a}: {err}; estado={estado}",
                                   "systemctl show"),
            tried=[f"systemctl {'--user ' if scope == 'user' else ''}{a} {unit}"],
            ok_msg="",
            fail_msg=f"No pude {a} {unit}, senor: {err}. Sigue en {estado}.")

    ok = d.get("ActiveState") in esperado
    return _v.finish(
        plan,
        _v.VerifyOutcome(bool(ok), f"estado tras {a}: {estado}", "systemctl show"),
        tried=[f"systemctl {a} {unit}"],
        ok_msg=f"Hecho, senor: {unit} quedó en {estado}.",
        fail_msg=f"Ejecuté '{a} {unit}' sin error pero el servicio quedó en "
                 f"{estado}, no en {'/'.join(esperado)}.")
