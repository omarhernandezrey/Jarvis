"""JARVIS Local - Red y WiFi (PLAN_EJECUCION FASE F · F2).

`nmcli`. Detección en runtime (D0). Contraseñas de WiFi: JARVIS NUNCA las
maneja — solo activa conexiones YA GUARDADAS (`nmcli connection up <nombre>`),
que usan las credenciales que NetworkManager tiene. No hay ninguna contraseña
en los parámetros, ni en la auditoría, ni en el prompt del modelo. (La capa 0
además redacta `psk`/`wireless-security` por si algo se colara.)

  - Lectura sin preguntar: estado, red actual, redes disponibles, IP.
  - Conectar a una red CONOCIDA: escritura + VERIFY (conectado de verdad).
  - Desconectar / apagar el WiFi / cambiar de red: confirmación explícita —
    si me deja sin conexión no puedo pedir que lo deshaga.
  - Bloqueado si hay una transacción de paquetes en curso (guardia E1·c): un
    `apt` a medias sin red deja el sistema peor.
"""
from __future__ import annotations

import shutil
import subprocess

from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy


def _hay_nmcli() -> bool:
    return shutil.which("nmcli") is not None


def _nmcli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=25)


def _sin_nmcli(plan: ActionPlan) -> ActionPlan:
    plan.status = ActionStatus.ERROR
    plan.error = "nmcli no instalado"
    plan.result = ("No puedo gestionar la red: falta `nmcli` (NetworkManager), "
                   "senor. Instálalo con `sudo apt install network-manager`.")
    return plan


def _wifi_hw_presente() -> bool:
    out = _nmcli("-t", "-f", "WIFI-HW", "radio")
    return "missing" not in (out.stdout or "").lower()


def _conexiones_guardadas() -> dict[str, str]:
    """{nombre: tipo} de las conexiones que NetworkManager tiene guardadas."""
    out = _nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
    d = {}
    for ln in (out.stdout or "").splitlines():
        nombre, _, tipo = ln.rpartition(":")
        if nombre:
            d[nombre] = tipo
    return d


# --- LECTURA -------------------------------------------------------------

def net_status() -> ActionPlan:
    plan = ActionPlan(action="estado_red", risk=RiskLevel.READ,
                      reason="Estado de la red (solo lectura)")
    if not _hay_nmcli():
        return _sin_nmcli(plan)
    dev = _nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device")
    lineas = ["Estado de la red, senor:"]
    for ln in (dev.stdout or "").splitlines():
        p = ln.split(":")
        if len(p) < 4 or p[1] in ("loopback",):
            continue
        estado = p[2]
        conn = p[3] or "—"
        ip = ""
        if estado == "connected":
            ipo = _nmcli("-t", "-f", "IP4.ADDRESS", "device", "show", p[0])
            m = [x.split(":", 1)[1] for x in (ipo.stdout or "").splitlines()
                 if x.startswith("IP4.ADDRESS")]
            ip = f", IP {m[0]}" if m else ""
        lineas.append(f"  {p[0]} ({p[1]}): {estado} — {conn}{ip}")
    radio = _nmcli("-t", "-f", "WIFI", "radio").stdout.strip()
    lineas.append(f"  WiFi: {'encendido' if radio == 'enabled' else radio or 'sin datos'}"
                  + ("" if _wifi_hw_presente() else " (no hay hardware WiFi en este equipo)"))
    plan.result = "\n".join(lineas)
    plan.status = ActionStatus.EXECUTED
    return plan


def wifi_list() -> ActionPlan:
    plan = ActionPlan(action="listar_wifi", risk=RiskLevel.READ,
                      reason="Listar redes WiFi (solo lectura)")
    if not _hay_nmcli():
        return _sin_nmcli(plan)
    if not _wifi_hw_presente():
        plan.status = ActionStatus.EXECUTED
        plan.result = "Este equipo no tiene WiFi, senor."
        return plan
    out = _nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list")
    if out.returncode != 0:
        plan.status = ActionStatus.ERROR
        plan.error = (out.stderr or "").strip()
        plan.result = f"No pude listar las redes WiFi, senor: {plan.error}"
        return plan
    filas = []
    for ln in (out.stdout or "").splitlines():
        p = ln.split(":")
        if len(p) < 4 or not p[1]:
            continue
        marca = "* " if p[0] == "*" else "  "
        filas.append(f"  {marca}{p[1][:32]:<32} {p[2]:>3}%  {p[3] or 'abierta'}")
    plan.result = ("Redes WiFi visibles, senor:\n" + "\n".join(filas)
                   if filas else "No veo ninguna red WiFi, senor.")
    plan.status = ActionStatus.EXECUTED
    return plan


# --- ESCRITURA: conectar (sin confirmación, con VERIFY) ----------------

def _conexion_activa(nombre: str) -> bool:
    out = _nmcli("-t", "-f", "NAME,STATE", "connection", "show", "--active")
    for ln in (out.stdout or "").splitlines():
        n, _, st = ln.rpartition(":")
        if n == nombre and st == "activated":
            return True
    return False


def wifi_connect(red: str) -> ActionPlan:
    plan = ActionPlan(action="conectar_wifi", params={"red": red},
                      risk=RiskLevel.EXECUTE, reason=f"Conectar a la red {red}")
    if not _hay_nmcli():
        return _sin_nmcli(plan)
    if permisos.transaccion_de_paquetes_en_curso():
        return permisos.bloqueo_por_transaccion(f"conectar a la red {red}")

    guardadas = _conexiones_guardadas()
    if red not in guardadas:
        # coincidencia laxa por si el usuario dice el SSID sin el prefijo
        cand = [n for n in guardadas if red.lower() in n.lower()]
        if len(cand) == 1:
            red = cand[0]
        elif not cand:
            plan.status = ActionStatus.BLOCKED
            plan.result = (
                f"No tengo guardada ninguna red que se llame '{red}', senor. "
                "Conéctate a ella una vez a mano (con su contraseña) y luego yo "
                "puedo reconectar. Guardadas: "
                + (", ".join(sorted(guardadas)) or "ninguna") + ".")
            return plan
        else:
            plan.status = ActionStatus.BLOCKED
            plan.result = (f"Hay varias redes guardadas que casan con '{red}': "
                           + ", ".join(cand) + ". Dime el nombre exacto, senor.")
            return plan

    from jarvis_local.tools import verify as _v
    out = _nmcli("connection", "up", red)          # usa las credenciales guardadas
    _v.grace(0.5)
    if _conexion_activa(red):
        return _v.finish(
            plan, _v.VerifyOutcome(True, f"'{red}' activada", "nmcli connection show --active"),
            ok_msg=f"Conectado a {red}, senor.", fail_msg="")
    err = (out.stderr or "").strip() or f"código {out.returncode}"
    return _v.finish(
        plan, _v.VerifyOutcome(False, err, "nmcli connection show --active"),
        tried=[f"nmcli connection up {red} -> {err}"], ok_msg="",
        fail_msg=f"No pude conectar a {red}, senor: {err}.")


# --- ESCRITURA con confirmación: desconectar / apagar WiFi -------------

def _guard_cambio(objetivo: str) -> ActionPlan | None:
    if not _hay_nmcli():
        return _sin_nmcli(ActionPlan(action="red", risk=RiskLevel.DELETE))
    if permisos.transaccion_de_paquetes_en_curso():
        return permisos.bloqueo_por_transaccion(objetivo)
    return None


def plan_wifi_radio(encender: bool) -> ActionPlan:
    verbo = "encender" if encender else "apagar"
    plan = ActionPlan(action="wifi_radio", params={"encender": encender},
                      risk=RiskLevel.DELETE, reason=f"{verbo} el WiFi")
    g = _guard_cambio(f"{verbo} el WiFi")
    if g is not None:
        return g
    estado = _nmcli("-t", "-f", "WIFI", "radio").stdout.strip()
    plan.simulation_result = permisos.texto_confirmacion(
        f"{verbo} el WiFi", "radio WiFi", {"estado ahora": estado})
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def plan_disconnect(objetivo: str = "") -> ActionPlan:
    plan = ActionPlan(action="desconectar_red", params={"objetivo": objetivo},
                      risk=RiskLevel.DELETE, reason=f"Desconectar {objetivo or 'la red actual'}")
    g = _guard_cambio(f"desconectar {objetivo or 'la red'}")
    if g is not None:
        return g
    act = _nmcli("-t", "-f", "NAME,DEVICE,TYPE", "connection", "show", "--active")
    activas = [ln.split(":") for ln in (act.stdout or "").splitlines()
               if ln and not ln.startswith("lo:")]
    activas = [a for a in activas if len(a) >= 3 and a[2] != "loopback"]
    if not objetivo:
        wifi = [a for a in activas if "wireless" in a[2]]
        elegidas = wifi or activas
        if len(elegidas) != 1:
            plan.status = ActionStatus.BLOCKED
            plan.result = ("Dime qué desconecto, senor: "
                           + ", ".join(a[0] for a in elegidas) + ".")
            return plan
        objetivo = elegidas[0][0]
    plan.params["objetivo"] = objetivo
    plan.simulation_result = permisos.texto_confirmacion(
        "desconectar", objetivo,
        {"aviso": "te quedarás sin esa conexión; si es la única, pierdo el acceso "
                  "a todo lo que no sea local"})
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_wifi_radio(encender: bool) -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="wifi_radio", params={"encender": encender},
                      risk=RiskLevel.DELETE, status=ActionStatus.CONFIRMED,
                      reason=f"{'encender' if encender else 'apagar'} el WiFi")
    g = _guard_cambio("cambiar el WiFi")
    if g is not None:
        return g
    _nmcli("radio", "wifi", "on" if encender else "off")
    _v.grace(0.4)
    estado = _nmcli("-t", "-f", "WIFI", "radio").stdout.strip()
    ok = (estado == "enabled") is encender
    return _v.finish(
        plan, _v.VerifyOutcome(bool(ok), f"radio WiFi = {estado}", "nmcli radio"),
        ok_msg=f"WiFi {'encendido' if encender else 'apagado'}, senor.",
        fail_msg=f"Pedí {'encender' if encender else 'apagar'} el WiFi pero quedó '{estado}'.")


def execute_disconnect(objetivo: str) -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="desconectar_red", params={"objetivo": objetivo},
                      risk=RiskLevel.DELETE, status=ActionStatus.CONFIRMED,
                      reason=f"Desconectar {objetivo}")
    g = _guard_cambio(f"desconectar {objetivo}")
    if g is not None:
        return g
    out = _nmcli("connection", "down", objetivo)
    _v.grace(0.4)
    if not _conexion_activa(objetivo):
        return _v.finish(
            plan, _v.VerifyOutcome(True, f"'{objetivo}' ya no está activa", "nmcli --active"),
            ok_msg=f"Desconectado de {objetivo}, senor.", fail_msg="")
    err = (out.stderr or "").strip() or f"código {out.returncode}"
    return _v.finish(
        plan, _v.VerifyOutcome(False, f"'{objetivo}' sigue activa; {err}", "nmcli --active"),
        tried=[f"nmcli connection down {objetivo}"], ok_msg="",
        fail_msg=f"No pude desconectar {objetivo}, senor: {err}.")
