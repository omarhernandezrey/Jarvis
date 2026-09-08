"""JARVIS Local - Bluetooth (PLAN_EJECUCION FASE F · F3).

`bluetoothctl`. Detección en runtime (D0). Solo dispositivos YA EMPAREJADOS:
emparejar uno nuevo pide un PIN / passkey que hay que teclear en el momento y
JARVIS no puede hacerlo — se deja fuera y se explica cómo hacerlo a mano.

  - Lectura sin preguntar: estado del controlador, emparejados, conectados.
  - Conectar / desconectar un emparejado: escritura + VERIFY real (`Connected:`
    de `bluetoothctl info`, no el código de salida). Tres desenlaces: sí / no /
    ilegible (salvedad).

Desconectar un dispositivo Bluetooth no deja a JARVIS sin red, así que no
exige confirmación (a diferencia del WiFi en F2).
"""
from __future__ import annotations

import re
import shutil
import subprocess

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

_MAC = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$", re.IGNORECASE)


def _hay_bluetoothctl() -> bool:
    return shutil.which("bluetoothctl") is not None


def _bt(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bluetoothctl", *args], capture_output=True,
                          text=True, timeout=20)


def _sin_bluetoothctl(plan: ActionPlan) -> ActionPlan:
    plan.status = ActionStatus.ERROR
    plan.error = "bluetoothctl no instalado"
    plan.result = ("No puedo gestionar el Bluetooth: falta `bluetoothctl`, senor. "
                   "Instálalo con `sudo apt install bluez`.")
    return plan


def _hay_controlador() -> bool:
    out = _bt("show")
    return out.returncode == 0 and "Controller" in (out.stdout or "")


def _sin_controlador(plan: ActionPlan) -> ActionPlan:
    plan.status = ActionStatus.ERROR
    plan.error = "sin controlador Bluetooth"
    plan.result = ("Este equipo no tiene un controlador Bluetooth disponible, "
                   "senor (¿está encendido el adaptador?).")
    return plan


def _dispositivos(cual: str) -> list[tuple[str, str]]:
    """[(MAC, nombre)] de `bluetoothctl devices <cual>` (Paired / Connected)."""
    out = _bt("devices", cual)
    res = []
    for ln in (out.stdout or "").splitlines():
        p = ln.split(" ", 2)
        if len(p) >= 2 and p[0] == "Device":
            res.append((p[1], p[2].strip() if len(p) > 2 else p[1]))
    return res


def _emparejados() -> list[tuple[str, str]]:
    return _dispositivos("Paired")


def _macs_conectadas() -> set[str]:
    return {mac for mac, _ in _dispositivos("Connected")}


def _esta_conectado(mac: str) -> bool | None:
    """`Connected:` de `bluetoothctl info` -> True / False / None si no se lee."""
    out = _bt("info", mac)
    mm = re.search(r"Connected:\s*(yes|no)", out.stdout or "")
    if mm is None:
        return None
    return mm.group(1) == "yes"


def _resolver(objetivo: str, entre: list[tuple[str, str]]
              ) -> tuple[str, str] | list[tuple[str, str]] | None:
    """(mac, nombre) si hay una coincidencia clara; la lista si hay varias;
    None si ninguna. `objetivo` puede ser una MAC o parte del nombre."""
    objetivo = (objetivo or "").strip()
    if _MAC.match(objetivo):
        for mac, nombre in entre:
            if mac.lower() == objetivo.lower():
                return (mac, nombre)
        return None
    low = objetivo.lower()
    cand = [(mac, nombre) for mac, nombre in entre if low in nombre.lower()]
    if len(cand) == 1:
        return cand[0]
    return cand or None


# --- LECTURA -----------------------------------------------------------

def bt_status() -> ActionPlan:
    plan = ActionPlan(action="estado_bluetooth", risk=RiskLevel.READ,
                      reason="Estado del Bluetooth (solo lectura)")
    if not _hay_bluetoothctl():
        return _sin_bluetoothctl(plan)
    out = _bt("show")
    if out.returncode != 0 or "Controller" not in (out.stdout or ""):
        return _sin_controlador(plan)
    pw = re.search(r"Powered:\s*(yes|no)", out.stdout)
    encendido = bool(pw and pw.group(1) == "yes")
    n_emp = len(_emparejados())
    n_con = len(_macs_conectadas())
    plan.result = (
        f"Bluetooth, senor: {'encendido' if encendido else 'apagado'}, "
        f"{n_emp} emparejado(s), {n_con} conectado(s)."
        + ("" if encendido else " Enciéndelo desde Configuración para conectar algo."))
    plan.status = ActionStatus.EXECUTED
    return plan


def bt_list() -> ActionPlan:
    plan = ActionPlan(action="listar_bluetooth", risk=RiskLevel.READ,
                      reason="Listar dispositivos Bluetooth emparejados")
    if not _hay_bluetoothctl():
        return _sin_bluetoothctl(plan)
    if not _hay_controlador():
        return _sin_controlador(plan)
    emp = _emparejados()
    if not emp:
        plan.result = ("No hay ningún dispositivo Bluetooth emparejado, senor. "
                       "Empareja uno desde Configuración > Bluetooth (pide un PIN "
                       "que yo no puedo teclear); luego ya puedo conectarlo.")
        plan.status = ActionStatus.EXECUTED
        return plan
    con = _macs_conectadas()
    filas = [f"  {'* ' if mac in con else '  '}{nombre}  [{mac}]"
             for mac, nombre in emp]
    plan.result = ("Dispositivos Bluetooth emparejados, senor (* = conectado):\n"
                   + "\n".join(filas))
    plan.status = ActionStatus.EXECUTED
    return plan


# --- ESCRITURA: conectar / desconectar (con VERIFY, sin confirmación) --

def _elige(objetivo: str, entre: list[tuple[str, str]], plan: ActionPlan,
           vacio_msg: str) -> tuple[str, str] | None:
    """Resuelve `objetivo` contra `entre`; si no puede, deja `plan` BLOCKED."""
    if not (objetivo or "").strip():
        if len(entre) == 1:
            return entre[0]
        plan.status = ActionStatus.BLOCKED
        plan.result = vacio_msg + (
            " ".join(f"{n} [{m}]" for m, n in entre) if entre else "no hay ninguno.")
        return None
    r = _resolver(objetivo, entre)
    if r is None:
        plan.status = ActionStatus.BLOCKED
        plan.result = (
            f"No encuentro ningún dispositivo emparejado que case con "
            f"'{objetivo}', senor. Emparejados: "
            + (", ".join(n for _, n in entre) or "ninguno") + ".")
        return None
    if isinstance(r, list):
        plan.status = ActionStatus.BLOCKED
        plan.result = (f"Hay varios que casan con '{objetivo}': "
                       + ", ".join(f"{n} [{m}]" for m, n in r)
                       + ". Dime el nombre exacto o la MAC, senor.")
        return None
    return r


def bt_connect(objetivo: str = "") -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="conectar_bluetooth", params={"objetivo": objetivo},
                      risk=RiskLevel.EXECUTE,
                      reason=f"Conectar {objetivo or 'un dispositivo'} por Bluetooth")
    if not _hay_bluetoothctl():
        return _sin_bluetoothctl(plan)
    if not _hay_controlador():
        return _sin_controlador(plan)
    r = _elige(objetivo, _emparejados(), plan,
               "Dime a qué dispositivo Bluetooth me conecto, senor: ")
    if r is None:
        return plan
    mac, nombre = r
    plan.params["objetivo"] = nombre
    out = _bt("connect", mac)
    _v.grace(0.6)
    estado = _esta_conectado(mac)
    if estado is True:
        return _v.finish(
            plan, _v.VerifyOutcome(True, f"'{nombre}' conectado", "bluetoothctl info"),
            ok_msg=f"Conectado a {nombre}, senor.", fail_msg="")
    if estado is None:
        return _v.finish(
            plan, _v.VerifyOutcome(None, "no pude releer el estado de conexión",
                                   "bluetoothctl info"),
            ok_msg=f"Lancé la conexión con {nombre}, senor.", fail_msg="")
    err = ((out.stdout or "").strip().splitlines() or [""])[-1] \
        or (out.stderr or "").strip() or f"código {out.returncode}"
    return _v.finish(
        plan, _v.VerifyOutcome(False, err, "bluetoothctl info"),
        tried=[f"bluetoothctl connect {mac} -> {err}"], ok_msg="",
        fail_msg=f"No pude conectar a {nombre}, senor: {err}.")


def bt_disconnect(objetivo: str = "") -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="desconectar_bluetooth", params={"objetivo": objetivo},
                      risk=RiskLevel.EXECUTE,
                      reason=f"Desconectar {objetivo or 'el dispositivo Bluetooth'}")
    if not _hay_bluetoothctl():
        return _sin_bluetoothctl(plan)
    if not _hay_controlador():
        return _sin_controlador(plan)
    conectados = [(m, n) for m, n in _emparejados() if m in _macs_conectadas()]
    r = _elige(objetivo, conectados, plan,
               "Dime qué dispositivo Bluetooth desconecto, senor: ")
    if r is None:
        return plan
    mac, nombre = r
    plan.params["objetivo"] = nombre
    out = _bt("disconnect", mac)
    _v.grace(0.6)
    estado = _esta_conectado(mac)
    if estado is False:
        return _v.finish(
            plan, _v.VerifyOutcome(True, f"'{nombre}' desconectado", "bluetoothctl info"),
            ok_msg=f"Desconectado de {nombre}, senor.", fail_msg="")
    if estado is None:
        return _v.finish(
            plan, _v.VerifyOutcome(None, "no pude releer el estado de conexión",
                                   "bluetoothctl info"),
            ok_msg=f"Lancé la desconexión de {nombre}, senor.", fail_msg="")
    err = (out.stderr or "").strip() or f"código {out.returncode}"
    return _v.finish(
        plan, _v.VerifyOutcome(False, f"'{nombre}' sigue conectado; {err}",
                               "bluetoothctl info"),
        tried=[f"bluetoothctl disconnect {mac}"], ok_msg="",
        fail_msg=f"No pude desconectar {nombre}, senor.")
