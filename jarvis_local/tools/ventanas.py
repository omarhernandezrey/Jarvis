"""JARVIS Local - Ventanas en Wayland (PLAN_EJECUCION FASE F · F4.2).

Habla por D-Bus con la extensión de GNOME Shell `ventanas-jarvis@local`
(interfaz `org.gnome.Shell.Extensions.VentanasJarvis`: List / Details /
Activate / Close). En Wayland no hay otra vía soportada — ver
`docs/F4_INVESTIGACION_VENTANAS.md`.

  - `listar_ventanas`: lectura.
  - `enfocar_ventana`: escritura + VERIFY (que `has_focus` se movió de verdad).
  - `cerrar_ventana`: DESTRUCTIVO (modelo de permisos E2). Confirmación
    mostrando título y aplicación de la ventana exacta. Guardia de intocables
    (E1) por `wm_class` y por `pid`: nunca la ventana de `gnome-shell` ni la
    del propio JARVIS. VERIFY: la ventana ya no está en `List()`.
  - Varias coincidencias -> se listan y se pregunta (como E3 con procesos).
  - Detección en runtime: sin `gdbus` o sin la extensión -> ERROR claro con
    cómo instalarla. Nunca fallo en silencio.
  - Interruptor: `data/ventanas_integracion.json` -> `{"activa": bool}`.
    Desactiva la integración sin tocar el compositor.
"""
from __future__ import annotations

import ast
import contextlib
import json
import shutil
import subprocess

from jarvis_local.config import BASE_DIR
from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy
from jarvis_local.safety.untouchables import (
    alternativa,
    is_untouchable_process,
    own_pids,
)

_DEST = "org.gnome.Shell"
_PATH = "/org/gnome/Shell/Extensions/VentanasJarvis"
_IFACE = "org.gnome.Shell.Extensions.VentanasJarvis"
_UUID = "ventanas-jarvis@local"
_SWITCH = BASE_DIR / "data" / "ventanas_integracion.json"

_COMO_INSTALAR = (
    "La extensión de ventanas no está instalada o no responde, senor. "
    "Instálala con: `cp -r gnome-extension/ventanas-jarvis@local "
    "~/.local/share/gnome-shell/extensions/ && gnome-extensions enable "
    "ventanas-jarvis@local`, y reinicia la sesión (cierra sesión y vuelve a "
    "entrar; en Wayland no se recarga en caliente). Detalle y recuperación en "
    "docs/RECUPERACION_GNOME.md."
)


# --- interruptor de integración -------------------------------------------

def integracion_activa() -> bool:
    try:
        return bool(json.loads(_SWITCH.read_text(encoding="utf-8")).get("activa", True))
    except FileNotFoundError:
        return True
    except Exception:
        return True


def set_integracion(activa: bool) -> ActionPlan:
    activa = bool(activa)
    with contextlib.suppress(Exception):
        _SWITCH.parent.mkdir(parents=True, exist_ok=True)
        _SWITCH.write_text(json.dumps({"activa": activa}), encoding="utf-8")
    p = ActionPlan(action="integracion_ventanas", params={"activa": activa},
                   risk=RiskLevel.EXECUTE, status=ActionStatus.EXECUTED,
                   reason=("Activar" if activa else "Desactivar") + " integración de ventanas")
    p.result = (
        "Integración de ventanas ACTIVADA, senor." if activa else
        "Integración de ventanas DESACTIVADA, senor: no tocaré ninguna ventana "
        "hasta que la vuelvas a activar. La extensión de GNOME sigue instalada; "
        "esto no toca el compositor.")
    return p


# --- fontanería D-Bus ----------------------------------------------------

def _hay_gdbus() -> bool:
    return shutil.which("gdbus") is not None


def _gdbus(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gdbus", *args], capture_output=True, text=True, timeout=15)


def _extension_responde() -> bool:
    out = _gdbus("introspect", "--session", "--dest", _DEST, "--object-path", _PATH)
    return out.returncode == 0 and _IFACE in (out.stdout or "")


def _call(metodo: str, *cargs: str) -> tuple[bool, str, str]:
    out = _gdbus("call", "--session", "--dest", _DEST, "--object-path", _PATH,
                 "--method", f"{_IFACE}.{metodo}", *cargs)
    return out.returncode == 0, (out.stdout or "").strip(), (out.stderr or "").strip()


def _unwrap(s: str) -> str:
    """gdbus imprime la salida como `('<json>',)`; `ast.literal_eval` deshace
    el tuple y el quoting/escapado de GVariant sin sorpresas."""
    with contextlib.suppress(Exception):
        v = ast.literal_eval(s.strip())
        if isinstance(v, tuple) and v:
            return str(v[0])
    return s.strip()


def _ventanas() -> tuple[list[dict], str]:
    ok, out, err = _call("List")
    if not ok:
        return [], err or "la extensión no respondió a List"
    try:
        data = json.loads(_unwrap(out))
        return (data if isinstance(data, list) else []), ""
    except Exception as e:  # noqa: BLE001 - se reporta al usuario
        return [], f"no pude interpretar la respuesta de la extensión ({e})"


# --- puerta común de disponibilidad ------------------------------------

def _gate(accion: str, riesgo: RiskLevel) -> ActionPlan | None:
    """ERROR/BLOCKED si no se puede operar ventanas ahora mismo."""
    if not _hay_gdbus():
        p = ActionPlan(action=accion, risk=riesgo, status=ActionStatus.ERROR)
        p.error = "gdbus no disponible"
        p.result = ("No puedo hablar con GNOME: falta `gdbus`, senor "
                    "(`sudo apt install libglib2.0-bin`).")
        return p
    if not integracion_activa():
        p = ActionPlan(action=accion, risk=riesgo, status=ActionStatus.BLOCKED)
        p.result = ("La integración de ventanas está DESACTIVADA, senor. "
                    "Actívala si quieres que opere ventanas.")
        return p
    if not _extension_responde():
        p = ActionPlan(action=accion, risk=riesgo, status=ActionStatus.ERROR)
        p.error = "extensión ventanas-jarvis@local no responde"
        p.result = _COMO_INSTALAR
        return p
    return None


# --- resolver / intocables -------------------------------------------

def _normales(wins: list[dict]) -> list[dict]:
    # window_type 0 = NORMAL. Descarta docks, notificaciones, etc.
    return [w for w in wins if w.get("window_type", 0) == 0]


def _resolver(objetivo: str) -> tuple[list[dict], str]:
    wins, err = _ventanas()
    if err:
        return [], err
    normales = _normales(wins)
    obj = (objetivo or "").strip()
    if not obj:
        return [], "¿Qué ventana, senor? Dime parte del título o de la aplicación."
    if obj.isdigit():
        wid = int(obj)
        hit = [w for w in normales if w.get("id") == wid]
        return (hit, "") if hit else ([], f"No hay ninguna ventana con id {wid}, senor.")
    q = obj.lower()
    hit = [w for w in normales
           if q in (w.get("title") or "").lower()
           or q in (w.get("wm_class") or "").lower()
           or q in (w.get("wm_class_instance") or "").lower()]
    if not hit:
        return [], f"No encuentro ninguna ventana que case con '{obj}', senor."
    return hit, ""


def _protegida(w: dict) -> tuple[bool, str]:
    """(True, motivo) si la ventana NO se puede tocar (E1), por pid o wm_class."""
    pid = w.get("pid")
    wm = w.get("wm_class") or ""
    if pid in own_pids():
        return True, "es una ventana del propio JARVIS"
    prot, motivo = is_untouchable_process(name=wm, pid=pid, cmdline="")
    if prot:
        return True, motivo
    # nombre real del proceso a partir del pid (una app puede declarar un
    # wm_class distinto de su binario)
    with contextlib.suppress(Exception):
        import psutil
        p = psutil.Process(pid)
        prot, motivo = is_untouchable_process(
            name=p.name(), pid=pid, cmdline=" ".join(p.cmdline()))
        if prot:
            return True, motivo
    return False, ""


def _linea(w: dict, con_marca: bool = True) -> str:
    prot, _m = _protegida(w) if con_marca else (False, "")
    marca = "  [protegida, no la toco]" if prot else ""
    foco = " *" if w.get("has_focus") else "  "
    return (f"  id {w.get('id'):<12}{foco} {(w.get('title') or '(sin título)')[:52]:<52} "
            f"[{w.get('wm_class') or '?'} · pid {w.get('pid')}]{marca}")


def _varias(hits: list[dict], objetivo: str, verbo: str) -> str:
    return (f"Hay {len(hits)} ventanas que casan con '{objetivo}', senor. "
            f"Dime el id exacto para {verbo}:\n"
            + "\n".join(_linea(w) for w in hits))


# --- listar ---------------------------------------------------------

def list_windows() -> ActionPlan:
    gate = _gate("listar_ventanas", RiskLevel.READ)
    if gate is not None:
        return gate
    plan = ActionPlan(action="listar_ventanas", risk=RiskLevel.READ,
                      reason="Listar ventanas (solo lectura)")
    wins, err = _ventanas()
    if err:
        plan.status = ActionStatus.ERROR
        plan.error = err
        plan.result = f"No pude listar las ventanas, senor: {err}."
        return plan
    normales = _normales(wins)
    if not normales:
        plan.status = ActionStatus.EXECUTED
        plan.result = "No hay ventanas de aplicación abiertas, senor."
        return plan
    plan.status = ActionStatus.EXECUTED
    plan.result = ("Ventanas abiertas, senor (* = enfocada):\n"
                   + "\n".join(_linea(w, con_marca=False) for w in normales))
    return plan


# --- enfocar (EXECUTE + VERIFY) ------------------------------------

def focus_window(objetivo: str) -> ActionPlan:
    from jarvis_local.tools import verify as _v
    gate = _gate("enfocar_ventana", RiskLevel.EXECUTE)
    if gate is not None:
        return gate
    plan = ActionPlan(action="enfocar_ventana", params={"objetivo": objetivo},
                      risk=RiskLevel.EXECUTE, reason=f"Enfocar ventana: {objetivo}")
    hits, err = _resolver(objetivo)
    if err:
        plan.status = ActionStatus.EXECUTED if "No encuentro" in err else ActionStatus.BLOCKED
        plan.result = err
        return plan
    if len(hits) > 1:
        plan.status = ActionStatus.BLOCKED
        plan.result = _varias(hits, objetivo, "enfocar")
        return plan
    w = hits[0]
    ok, _out, cerr = _call("Activate", str(w["id"]))
    if not ok:
        return _v.finish(
            plan, _v.VerifyOutcome(False, cerr or "Activate falló", "gdbus"),
            tried=[f"Activate {w['id']}"], ok_msg="",
            fail_msg=f"No pude enfocar «{w.get('title')}», senor: {cerr}.")
    _v.grace(0.4)
    wins, _e = _ventanas()
    ahora = next((x for x in wins if x.get("id") == w["id"]), None)
    if ahora is None:
        return _v.finish(
            plan, _v.VerifyOutcome(None, "la ventana ya no está en List()", "List()"),
            ok_msg=f"Pedí enfocar «{w.get('title')}» pero ya no está, senor.", fail_msg="")
    if ahora.get("has_focus"):
        return _v.finish(
            plan, _v.VerifyOutcome(True, "has_focus=true", "List()"),
            ok_msg=f"Enfocada «{ahora.get('title')}», senor.", fail_msg="")
    return _v.finish(
        plan, _v.VerifyOutcome(False, "has_focus sigue en false", "List()"),
        tried=[f"Activate {w['id']}"], ok_msg="",
        fail_msg=f"Pedí enfocar «{w.get('title')}» pero el foco no se movió, senor.")


# --- cerrar (DELETE: plan + confirmación + execute + VERIFY) ---------

def plan_close_window(objetivo: str) -> ActionPlan:
    plan = ActionPlan(action="cerrar_ventana", params={"objetivo": objetivo},
                      risk=RiskLevel.DELETE, reason=f"Cerrar ventana: {objetivo}")
    gate = _gate("cerrar_ventana", RiskLevel.DELETE)
    if gate is not None:
        return gate
    hits, err = _resolver(objetivo)
    if err:
        plan.status = ActionStatus.EXECUTED if "No encuentro" in err else ActionStatus.BLOCKED
        plan.result = err
        return plan
    if len(hits) > 1:
        plan.status = ActionStatus.BLOCKED
        plan.result = _varias(hits, objetivo, "cerrar")
        return plan
    w = hits[0]
    prot, motivo = _protegida(w)
    if prot:
        plan.status = ActionStatus.BLOCKED
        plan.result = (f"No voy a cerrar «{w.get('title')}» ({w.get('wm_class')}): "
                       f"{motivo}, senor.\n{alternativa(w.get('wm_class') or '')}")
        return plan
    plan.params.update(id=w["id"], title=w.get("title") or "(sin título)",
                       wm_class=w.get("wm_class") or "?", pid=w.get("pid"))
    plan.simulation_result = permisos.texto_confirmacion(
        "cerrar la ventana", plan.params["title"],
        {"aplicación": plan.params["wm_class"], "pid": plan.params["pid"],
         "aviso": "si hay cambios sin guardar, la aplicación debería preguntarte; "
                  "si no, se pierden"})
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_close_window(wid: int) -> ActionPlan:
    from jarvis_local.tools import verify as _v
    plan = ActionPlan(action="cerrar_ventana", params={"id": wid},
                      risk=RiskLevel.DELETE, status=ActionStatus.CONFIRMED,
                      reason=f"Cerrar ventana {wid}")
    gate = _gate("cerrar_ventana", RiskLevel.DELETE)
    if gate is not None:
        return gate
    wins, err = _ventanas()
    if err:
        plan.status = ActionStatus.ERROR
        plan.error = err
        plan.result = f"No pude comprobar la ventana antes de cerrar, senor: {err}."
        return plan
    w = next((x for x in wins if x.get("id") == wid), None)
    if w is None:
        return _v.finish(
            plan, _v.VerifyOutcome(True, "ya no estaba en List()", "List()"),
            ok_msg="Esa ventana ya no estaba abierta, senor.", fail_msg="")
    # re-guarda E1 antes de ejecutar
    prot, motivo = _protegida(w)
    if prot:
        plan.status = ActionStatus.BLOCKED
        plan.result = f"No cierro «{w.get('title')}»: {motivo}, senor."
        return plan
    titulo = w.get("title") or "(sin título)"
    ok, _out, cerr = _call("Close", str(wid))
    if not ok:
        return _v.finish(
            plan, _v.VerifyOutcome(False, cerr or "Close falló", "gdbus"),
            tried=[f"Close {wid}"], ok_msg="",
            fail_msg=f"No pude cerrar «{titulo}», senor: {cerr}.")
    _v.grace(1.5)
    wins2, _e = _ventanas()
    if not any(x.get("id") == wid for x in wins2):
        return _v.finish(
            plan, _v.VerifyOutcome(True, "ya no está en List()", "List()"),
            ok_msg=f"Cerrada «{titulo}», senor.", fail_msg="")
    # sigue abierta: casi siempre un diálogo "¿guardar?" -> None con salvedad,
    # nunca un ERROR ni un éxito inventado.
    plan.status = ActionStatus.EXECUTED
    plan.params["verify"] = {"ok": None, "method": "List()",
                             "detail": "sigue abierta tras Close"}
    plan.result = (f"Pedí cerrar «{titulo}», senor, pero sigue abierta: seguramente "
                   "la aplicación está preguntando si guardar los cambios. "
                   "Responde en la ventana.")
    return plan
