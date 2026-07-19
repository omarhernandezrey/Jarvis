"""
JARVIS Local - Recordatorios con alarma

"recuerdame en 20 minutos sacar la comida" arma un temporizador que, al
vencer, suena (winsound), habla (TTS) y se imprime en la consola. Los
recordatorios se guardan en data/reminders.json: si JARVIS se cierra y se
vuelve a abrir, los pendientes se rearman y los vencidos se avisan tarde
(mejor tarde que nunca).
"""
import contextlib
import json
import os
import re
import threading
from datetime import datetime, timedelta

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

REMINDERS_PATH = os.path.join(os.path.dirname(__file__), "..", "data",
                              "reminders.json")

_LOCK = threading.Lock()
_TIMERS: dict[int, threading.Timer] = {}
_loaded = False

# Para poder probar sin sonar ni hablar (los tests lo reemplazan)
_notify_hook = None


def _load_store() -> list[dict]:
    if not os.path.exists(REMINDERS_PATH):
        return []
    try:
        with open(REMINDERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_store(items: list[dict]) -> None:
    os.makedirs(os.path.dirname(REMINDERS_PATH), exist_ok=True)
    with open(REMINDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def _notify(message: str) -> None:
    """Suena, habla e imprime. El orden importa: el sonido es inmediato,
    la voz puede tardar un par de segundos en generarse."""
    if _notify_hook is not None:
        _notify_hook(message)
        return
    with contextlib.suppress(Exception):
        import winsound
        for _ in range(3):
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    print(f"\n  [RECORDATORIO] {message}\n")
    with contextlib.suppress(Exception):
        from jarvis_local.voice.tts import speak
        speak(message)


def _fire(rid: int) -> None:
    with _LOCK:
        items = _load_store()
        actual = next((i for i in items if i["id"] == rid), None)
        items = [i for i in items if i["id"] != rid]
        _save_store(items)
        _TIMERS.pop(rid, None)
    if actual:
        _notify(f"Recordatorio, senor: {actual['text']}")


def _arm(rid: int, when: datetime, atrasado: bool = False) -> None:
    seconds = max(1.0, (when - datetime.now()).total_seconds())
    if atrasado:
        seconds = 2.0
    t = threading.Timer(seconds, _fire, args=(rid,))
    t.daemon = True
    t.start()
    _TIMERS[rid] = t


def ensure_loaded() -> None:
    """Rearma los recordatorios guardados (una vez por sesion)."""
    global _loaded
    with _LOCK:
        if _loaded:
            return
        _loaded = True
        items = _load_store()
    for item in items:
        when = datetime.fromisoformat(item["when"])
        if item["id"] in _TIMERS:
            continue
        _arm(item["id"], when, atrasado=when <= datetime.now())


def _next_id(items: list[dict]) -> int:
    return max((i["id"] for i in items), default=0) + 1


def _parse_hora(hora: str) -> datetime | None:
    """'15:30' o '3' -> el proximo momento en que sean esas horas."""
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?$', hora.strip())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2) or 0)
    if hh > 23 or mm > 59:
        return None
    when = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    if when <= datetime.now():
        # ya paso hoy: si era formato 12h ambiguo intentar +12h, si no manana
        if hh < 12 and datetime.now().hour >= hh:
            pm = when + timedelta(hours=12)
            if pm > datetime.now():
                return pm
        when += timedelta(days=1)
    return when


def set_reminder(text: str, minutes: float = 0, at: str = "") -> ActionPlan:
    """Crea un recordatorio: en N minutos (minutes) o a una hora (at HH:MM)."""
    ensure_loaded()
    plan = ActionPlan(action="crear_recordatorio",
                      params={"texto": text, "minutos": minutes, "hora": at},
                      risk=RiskLevel.CREATE,
                      reason="Crear recordatorio con alarma")
    text = (text or "").strip() or "alarma"
    when = None
    if minutes and float(minutes) > 0:
        when = datetime.now() + timedelta(minutes=float(minutes))
    elif at:
        when = _parse_hora(at)
    if when is None:
        plan.status = ActionStatus.ERROR
        plan.error = "sin tiempo valido"
        plan.result = ("Para cuando lo programo, senor? Diga por ejemplo "
                       "'en 20 minutos' o 'a las 3:30'.")
        return plan
    try:
        with _LOCK:
            items = _load_store()
            rid = _next_id(items)
            items.append({"id": rid, "text": text, "when": when.isoformat()})
            _save_store(items)
        _arm(rid, when)
        hora_txt = when.strftime("%I:%M %p").lstrip("0").lower()
        plan.params["id"] = rid
        plan.result = (f"Entendido, senor. Le recordare '{text}' "
                       f"a las {hora_txt}.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude crear el recordatorio: {e}"
    return plan


def list_reminders() -> ActionPlan:
    ensure_loaded()
    plan = ActionPlan(action="listar_recordatorios", risk=RiskLevel.READ,
                      reason="Operacion de solo lectura")
    items = sorted(_load_store(), key=lambda i: i["when"])
    if not items:
        plan.result = "No tiene recordatorios pendientes, senor."
    else:
        lineas = []
        for i in items:
            when = datetime.fromisoformat(i["when"])
            hora = when.strftime("%d/%m %I:%M %p").lower()
            lineas.append(f"  {i['id']}. {i['text']} - {hora}")
        plan.result = "Sus recordatorios, senor:\n" + "\n".join(lineas)
    plan.status = ActionStatus.EXECUTED
    return plan


def cancel_reminder(which: str = "todos") -> ActionPlan:
    """Cancela un recordatorio por numero, o todos."""
    ensure_loaded()
    plan = ActionPlan(action="cancelar_recordatorio", params={"cual": which},
                      risk=RiskLevel.EXECUTE, reason="Cancelar recordatorio")
    try:
        with _LOCK:
            items = _load_store()
            which_str = str(which).strip().lower()
            if which_str in ("todos", "todas", "all", ""):
                borrar = [i["id"] for i in items]
            elif which_str.isdigit():
                # Solo cuenta si ese ID existe de verdad -- antes
                # `borrar = [int(which_str)]` sin verificar dejaba pasar el
                # chequeo de "no encontre" (borrar no vacio) aunque el ID no
                # existiera, y el resultado quedaba en "Cancelados 0
                # recordatorios" en vez de avisar que no lo encontro.
                rid_pedido = int(which_str)
                borrar = [i["id"] for i in items if i["id"] == rid_pedido]
            else:
                # por texto: "cancela el del arroz"
                borrar = [i["id"] for i in items
                          if which_str in i["text"].lower()]
            if not borrar or not items:
                plan.result = "No encontre ese recordatorio, senor."
                plan.status = ActionStatus.EXECUTED
                return plan
            restantes = [i for i in items if i["id"] not in borrar]
            _save_store(restantes)
        for rid in borrar:
            t = _TIMERS.pop(rid, None)
            if t:
                t.cancel()
        n = len(items) - len(restantes)
        plan.result = ("Cancelado, senor." if n == 1
                       else f"Cancelados {n} recordatorios, senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cancelar: {e}"
    return plan
