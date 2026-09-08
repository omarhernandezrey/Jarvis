"""JARVIS Local - Catálogo único de herramientas (PLAN_EJECUCION FASE B).

FUENTE ÚNICA DE VERDAD. Antes había dos catálogos que no se conocían:

  - `jarvis.py`: `_READ_TOOLS` / `_WRITE_TOOLS` / `_PLAN_TOOLS` (dicts
    `nombre_inglés -> lambda(args)`), que usa la RUTA DEL PARSER.
  - `agent/registry.py`: `TOOLS: list[Tool]` (nombres en español, esquema JSON,
    `needs_confirmation`), que usa la RUTA DEL AGENTE y el retriever.

Divergían en nombres (`open_app` vs `abrir_aplicacion`), en granularidad
(`volume_up` suelto vs `controlar_volumen(accion)`) y en nombres de argumentos
(`set_reminder{text,minutes,at}` vs `crear_recordatorio{texto,minutos,hora}`).
Dar de alta una herramienta obligaba a tocar los dos.

AHORA: un `ToolContract` por entrada. `agent/registry.py` y los tres dicts de
`jarvis.py` se DERIVAN de `CONTRACTS` en tiempo de import (adaptadores más
abajo). Dar de alta una herramienta = añadir un `ToolContract` a este archivo,
y nada más.

Decisiones (docs/FASE_B_DISENO.md):
  - Idioma canónico: español. Los nombres del parser (`open_app`...) son alias.
  - `RiskLevel` se reutiliza de `safety/policy.py`.
  - `verify` / `revert` son DECLARATIVOS en FASE B (texto). Se vuelven
    ejecutables en FASE D (VERIFY post-acción).
"""
from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis_local.config import user_dir
from jarvis_local.safety.policy import ActionStatus, RiskLevel

# =============================================================================
# Ejecutores (import perezoso: arrancar JARVIS no debe cargar todos los tools).
# Movidos aquí desde agent/registry.py — son la cola de pegamento, viven con el
# catálogo. `registry.py` los importa de aquí.
# =============================================================================

def _open_app(app: str):
    from jarvis_local.tools.apps import open_app
    return open_app(app)


def _close_app(app: str):
    from jarvis_local.tools.apps import close_app
    return close_app(app)


def _close_all_apps():
    from jarvis_local.tools.apps import close_all_apps
    return close_all_apps()


def _list_apps():
    from jarvis_local.tools.apps import list_apps
    return list_apps()


def _set_reminder(texto: str, minutos: int = 0, hora: str = ""):
    from jarvis_local.tools.reminders import set_reminder
    return set_reminder(texto, minutos, hora)


def _list_reminders():
    from jarvis_local.tools.reminders import list_reminders
    return list_reminders()


def _cancel_reminder(cual: str = "todos"):
    from jarvis_local.tools.reminders import cancel_reminder
    return cancel_reminder(cual)


def _send_whatsapp(para: str, mensaje: str):
    from jarvis_local.tools.whatsapp import send_whatsapp
    return send_whatsapp(para, mensaje)


def _add_contact(name: str, phone: str):
    from jarvis_local.tools.whatsapp import add_contact
    return add_contact(name, phone)


def _list_contacts():
    from jarvis_local.tools.whatsapp import list_contacts
    return list_contacts()


def _window_control(accion: str):
    from jarvis_local.tools.desktop_actions import minimize_all, snap_window
    accion = (accion or "").lower()
    if accion in ("minimizar_todo", "escritorio", "todo"):
        return minimize_all()
    return snap_window(accion)


def _daily_briefing():
    from jarvis_local.tools.briefing import daily_briefing
    return daily_briefing()


def _read_clipboard():
    from jarvis_local.tools.reader import read_clipboard
    return read_clipboard()


def _read_file(ruta: str):
    from jarvis_local.tools.reader import read_file_aloud
    return read_file_aloud(ruta)


def _power_control(accion: str):
    from jarvis_local.tools import power
    accion = (accion or "").lower()
    if accion in ("bloquear", "bloqueo"):
        return power.lock_pc()
    if accion == "apagar":
        return power.shutdown_pc()
    if accion == "reiniciar":
        return power.restart_pc()
    if accion in ("suspender", "dormir", "hibernar"):
        return power.suspend_pc()
    if accion in ("cancelar", "cancelar_apagado"):
        return power.cancel_shutdown()
    return f"No entiendo la accion de energia '{accion}'."


def _volume_control(accion: str, nivel: int = 50):
    from jarvis_local.tools import media_controls as mc
    accion = (accion or "").lower()
    if accion in ("subir", "sube", "aumentar"):
        return mc.volume_up()
    if accion in ("bajar", "baja", "reducir"):
        return mc.volume_down()
    if accion in ("silenciar", "mute", "silencio"):
        return mc.volume_mute(True)
    if accion in ("activar", "desmutear", "sonido"):
        return mc.volume_mute(False)
    if accion in ("nivel", "fijar", "poner"):
        return mc.set_volume(int(nivel))
    return f"No entiendo la accion de volumen '{accion}'."


def _volume_mute_bool(mute: bool = True):
    """Adaptador del intent fino `volume_mute` del parser ({mute: bool})."""
    return _volume_control("silenciar" if mute else "activar")


def _media_control(accion: str):
    from jarvis_local.tools import media_controls as mc
    accion = (accion or "").lower()
    if accion in ("pausar", "pausa", "reanudar", "reproducir"):
        return mc.media_play_pause()
    if accion in ("siguiente", "proxima"):
        return mc.media_next()
    if accion in ("anterior", "previa"):
        return mc.media_previous()
    return f"No entiendo la accion multimedia '{accion}'."


def _list_files(path: str = ""):
    from jarvis_local.tools.files import list_files
    return list_files(path or user_dir("documents"))


def _search_files(name: str, path: str = ""):
    from jarvis_local.tools.files import search_files
    return search_files(name, path or user_dir("documents"))


def _file_info(path: str):
    from jarvis_local.tools.files import read_metadata
    return read_metadata(path)


def _create_directory(path: str):
    from jarvis_local.tools.files import create_directory
    return create_directory(path)


def _create_file(path: str, content: str = ""):
    from jarvis_local.tools.files import create_file
    return create_file(path, content)


def _copy_file(src: str, dst: str):
    from jarvis_local.tools.files import copy_file
    return copy_file(src, dst)


def _move_file(src: str, dst: str):
    from jarvis_local.tools.files import move_file
    return move_file(src, dst)


def _rename_file(path: str, new_name: str):
    from jarvis_local.tools.files import rename_file
    return rename_file(path, new_name)


def _delete_file(path: str):
    from jarvis_local.safety.policy import policy
    from jarvis_local.tools.files import plan_delete
    plan = plan_delete(path)
    policy.pending_plan = plan
    return plan


def _run_command(command: str):
    # Un solo guardia: execute_command llama a validate_shell_command
    # (safety.permissions), el unico punto que valida todo comando de shell.
    from jarvis_local.tools.terminal import execute_command
    return execute_command(command)


def _plan_command(command: str):
    from jarvis_local.tools.terminal import plan_command
    return plan_command(command)


def _weather(city: str = ""):
    from jarvis_local.tools.location import my_location
    from jarvis_local.tools.weather import get_weather
    if not city:
        loc = my_location()
        city = loc["city"] if loc else ""
    if not city:
        return "De que ciudad desea saber el clima, senor?"
    return get_weather(city)


def _locate(place: str):
    from jarvis_local.tools.location import locate
    return locate(place)


def _system_status():
    from jarvis_local.tools.system_info import system_status
    return system_status()


def _list_processes(por: str = "cpu", top: int = 12):
    from jarvis_local.tools.processes import list_processes
    return list_processes(por, int(top or 12))


def _kill_process(objetivo: str):
    from jarvis_local.tools.processes import plan_kill
    return plan_kill(str(objetivo))


def _service_status(servicio: str, ambito: str = "user"):
    from jarvis_local.tools.services import service_status
    return service_status(servicio, ambito)


def _service_control(accion: str, servicio: str, ambito: str = "user"):
    from jarvis_local.tools.services import plan_service
    return plan_service(accion, servicio, ambito)


def _notify(mensaje: str, titulo: str = "JARVIS", urgencia: str = "normal"):
    from jarvis_local.tools.notify import send_notification
    return send_notification(mensaje, titulo, urgencia)


def _net_status():
    from jarvis_local.tools.network import net_status
    return net_status()


def _wifi_list():
    from jarvis_local.tools.network import wifi_list
    return wifi_list()


def _wifi_connect(red: str):
    from jarvis_local.tools.network import wifi_connect
    return wifi_connect(red)


def _wifi_radio(encender: bool = True):
    from jarvis_local.tools.network import plan_wifi_radio
    return plan_wifi_radio(bool(encender))


def _net_disconnect(objetivo: str = ""):
    from jarvis_local.tools.network import plan_disconnect
    return plan_disconnect(objetivo)


def _brightness(accion: str, nivel: int = 50):
    from jarvis_local.tools import brightness as b
    accion = (accion or "").lower()
    if accion in ("subir", "sube", "mas"):
        return b.brightness_up()
    if accion in ("bajar", "baja", "menos"):
        return b.brightness_down()
    return b.set_brightness(int(nivel))


def _untouchables_list():
    from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
    from jarvis_local.safety.untouchables import explicar
    p = ActionPlan(action="listar_intocables", risk=RiskLevel.READ,
                   reason="Operacion de solo lectura")
    p.result = explicar()
    p.status = ActionStatus.EXECUTED
    return p


def _wiki(topic: str):
    from jarvis_local.tools.wiki import wiki_summary
    return wiki_summary(topic)


def _news():
    from jarvis_local.tools.news import headlines
    return headlines()


def _calculate(expression: str):
    from jarvis_local.tools.calculator import calculate
    from jarvis_local.tools.wolfram import ask_wolfram, has_app_id
    plan = calculate(expression)
    if plan.status == ActionStatus.ERROR and has_app_id():
        wa = ask_wolfram(expression)
        if wa.status != ActionStatus.ERROR:
            return wa
    return plan


def _wolfram(question: str):
    from jarvis_local.tools.wolfram import ask_wolfram
    return ask_wolfram(question)


def _joke():
    from jarvis_local.tools.jokes import tell_joke
    return tell_joke()


def _get_ip():
    from jarvis_local.tools.ip_info import get_ip
    return get_ip()


def _calendar():
    from jarvis_local.tools.gcalendar import upcoming_events
    return upcoming_events()


def _open_website(site: str):
    from jarvis_local.tools.web import open_website
    return open_website(site)


def _google(query: str):
    from jarvis_local.tools.web import google_search
    return google_search(query)


def _youtube(query: str):
    from jarvis_local.tools.web import youtube_play
    return youtube_play(query)


def _spotify(song: str):
    from jarvis_local.tools.spotify import play_song
    return play_song(song)


def _play_music(song: str = ""):
    from jarvis_local.tools.desktop_actions import play_music
    return play_music(song)


def _take_note(text: str):
    from jarvis_local.tools.notes import take_note
    return take_note(text)


def _screenshot(name: str = ""):
    from jarvis_local.tools.desktop_actions import take_screenshot
    return take_screenshot(name)


def _switch_window():
    from jarvis_local.tools.desktop_actions import switch_window
    return switch_window()


def _send_email(to: str, subject: str, body: str):
    from jarvis_local.tools.email_sender import plan_email
    return plan_email(to, subject, body)


def _hide_files(path: str, hide: bool = True):
    from jarvis_local.tools.hidden_files import plan_hide
    return plan_hide(path, hide)


def _search_jobs(puesto: str, ciudad: str = ""):
    from jarvis_local.tools.jobs import search_jobs
    return search_jobs(puesto, ciudad)


def _open_job(number: int):
    from jarvis_local.tools.jobs import open_job
    return open_job(int(number))


def _show_jobs(puesto: str = "", ciudad: str = ""):
    from jarvis_local.tools.browser import show_jobs_in_browser
    return show_jobs_in_browser(puesto, ciudad)


def _browser_navigate(url: str):
    from jarvis_local.tools.browser import navigate
    return navigate(url)


def _close_browser():
    from jarvis_local.tools.browser import close_browser
    return close_browser()


def _audit_query(dia: str = "hoy"):
    from jarvis_local.tools.audit_query import query_audit
    return query_audit(dia)


def _remember(text: str):
    """Guarda un dato en la memoria permanente, COMPROBANDO que quedó escrito.

    D1 · VERIFY: no se confía en el retorno de `MemoryStore.add`; se abre un
    store nuevo (relee memory.json) y se comprueba que el dato está. El fallo
    de una memoria no se percibe hasta que JARVIS no la recuerda, días después.
    """
    from jarvis_local.config import BASE_DIR
    from jarvis_local.safety.policy import ActionPlan
    from jarvis_local.storage.memory import MAX_MEMORY_LENGTH, MemoryStore
    from jarvis_local.tools import verify as _v

    plan = ActionPlan(action="recordar", params={"texto": str(text)[:80]},
                      risk=RiskLevel.CREATE, reason="Guardar en memoria permanente")
    clean = str(text)[:MAX_MEMORY_LENGTH].strip()
    if not clean:
        plan.status = ActionStatus.ERROR
        plan.error = "texto vacío"
        plan.result = "No me dijo qué recordar, senor."
        return plan

    mem = MemoryStore(BASE_DIR / "data")
    item = mem.add(clean)
    if item is None:
        plan.status = ActionStatus.ERROR
        plan.error = "límite de memorias alcanzado"
        plan.result = "No pude guardar la memoria (limite alcanzado), senor."
        return plan

    outcome = _v.memory_saved(clean, base_dir=BASE_DIR)
    tried = [f"MemoryStore.add -> {outcome.detail}"]
    if outcome.ok is False:
        plan.reason += " (reintento sobre store nuevo)"
        try:
            mem2 = MemoryStore(BASE_DIR / "data")
            if not any(it.get("text") == clean for it in mem2.list()):
                mem2.add(clean)
        except Exception as e:  # noqa: BLE001
            tried.append(f"reintento falló ({e})")
        else:
            outcome = _v.memory_saved(clean, base_dir=BASE_DIR)
            tried.append(f"reintento -> {outcome.detail}")

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Lo recordare, senor: {clean}",
        fail_msg="Intenté guardarlo en memoria pero al releer no aparece, senor.")


# =============================================================================
# Helpers de JSON Schema (antes en registry.py; se re-exportan allí).
# =============================================================================

def _obj(props: dict, required: list[str] | None = None) -> dict:
    # `required=None` => todas obligatorias. `required=[]` => ninguna.
    if required is None:
        required = list(props.keys())
    return {"type": "object", "properties": props, "required": required}


def _str(desc: str, enum: list[str] | None = None) -> dict:
    schema: dict = {"type": "string", "description": desc}
    if enum:
        schema["enum"] = enum
    return schema


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


def _bool(desc: str) -> dict:
    return {"type": "boolean", "description": desc}


def _param_names(fn: Callable) -> set[str] | None:
    """Nombres de parámetros del ejecutor. `None` si acepta **kwargs (sin límite)."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    names: set[str] = set()
    for prm in sig.parameters.values():
        if prm.kind == inspect.Parameter.VAR_KEYWORD:
            return None
        if prm.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY):
            names.add(prm.name)
    return names


# =============================================================================
# El contrato
# =============================================================================

@dataclass(frozen=True)
class ToolContract:
    name: str                              # canónico, español, snake_case
    description: str                       # para el LLM (obligatoria si llm_visible)
    parameters: dict                       # JSON Schema de los argumentos
    run: Callable[..., Any]                # ejecutor estilo **kwargs (props del schema)
    risk: RiskLevel
    verify: str                            # cómo se comprueba el efecto (declarativo FASE B)
    revert: str                            # cómo se revierte, o "irreversible" / "n/a"
    needs_confirmation: bool = False       # default se fuerza en __post_init__ si risk>=DELETE
    llm_visible: bool = True               # el agente lo ofrece al LLM
    plan_capable: bool = False             # aparece en el dict _PLAN_TOOLS de la ruta parser
    plan_run: Callable[..., Any] | None = None  # ejecutor de la variante plan (si difiere de run)
    in_legacy_write: bool = False          # además, clave en _WRITE_TOOLS (histórico: delete_file estaba en ambos dicts)
    parser_intents: tuple[str, ...] = ()   # nombres que emite intent/parser.py -> caen aquí
    parser_argmap: dict[str, str] = field(default_factory=dict)   # {clave_parser: clave_schema}
    parser_fixed: dict[str, Any] = field(default_factory=dict)    # args fijos al venir del parser
    aliases: tuple[str, ...] = ()          # otros nombres que resuelven a este contrato

    def __post_init__(self):
        # Regla dura: DELETE (destructivo) siempre confirma con /confirmar.
        # CRITICAL (sistema: apagar, shell) NO se fuerza aquí: su guardia es otra
        # (60 s cancelables, blocklist de shell) y endurecerlo con /confirmar es
        # trabajo de FASE E (modelo de permisos), no de FASE B. Debe declararlo
        # explícito quien lo defina.
        if self.risk == RiskLevel.DELETE and not self.needs_confirmation:
            object.__setattr__(self, "needs_confirmation", True)

    # --- vistas derivadas ---
    def schema(self) -> dict:
        """Formato de tool calling de Ollama/OpenAI (idéntico al de registry.Tool)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases, *self.parser_intents)

    def parser_executor(self, plan: bool = False) -> Callable[[dict], Any]:
        """Lambda al estilo viejo (`fn(args: dict)`) para los dicts de jarvis.py.
        Traduce las claves del parser (`parser_argmap`), inyecta `parser_fixed`
        y llama al ejecutor canónico con **kwargs."""
        fn = (self.plan_run or self.run) if plan else self.run
        allowed = _param_names(fn)  # None => el ejecutor acepta **kwargs

        def _call(args: dict) -> Any:
            args = args or {}
            kw: dict[str, Any] = dict(self.parser_fixed)
            for k, v in args.items():
                k2 = self.parser_argmap.get(k, k)
                if allowed is None or k2 in allowed:
                    kw[k2] = v
            return fn(**kw)

        return _call


# =============================================================================
# Validación de completitud — un contrato a medias rompe el import (y el test).
# =============================================================================

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_contract(c: ToolContract, *, others: list[ToolContract] | None = None) -> list[str]:
    """Devuelve la lista de problemas del contrato. Vacía == OK."""
    p: list[str] = []
    if not c.name or not _SNAKE.match(c.name):
        p.append(f"name inválido: {c.name!r}")
    if c.llm_visible and len(c.description.strip()) < 30:
        p.append(f"{c.name}: descripción demasiado corta para el LLM ({len(c.description)} chars)")
    if not isinstance(c.risk, RiskLevel):
        p.append(f"{c.name}: risk no es RiskLevel")
    if not callable(c.run):
        p.append(f"{c.name}: run no es callable")
    if not c.verify.strip():
        p.append(f"{c.name}: falta 'verify' (cómo se comprueba el efecto)")
    if not c.revert.strip():
        p.append(f"{c.name}: falta 'revert' (cómo se revierte)")
    if c.risk == RiskLevel.DELETE and not c.needs_confirmation:
        p.append(f"{c.name}: risk DELETE (destructivo) exige needs_confirmation")
    # JSON Schema mínimo
    params = c.parameters
    props: dict = {}
    if not isinstance(params, dict) or params.get("type") != "object":
        p.append(f"{c.name}: parameters no es un objeto JSON Schema")
    else:
        props = params.get("properties", {})
        if not isinstance(props, dict):
            p.append(f"{c.name}: properties no es dict")
            props = {}
        for r in params.get("required", []):
            if r not in props:
                p.append(f"{c.name}: required '{r}' no está en properties")
    # Para el LLM: cada propiedad del schema debe existir como parámetro del ejecutor.
    run_params = _param_names(c.run)
    if c.llm_visible and run_params is not None:
        for prop in props:
            if prop not in run_params:
                p.append(f"{c.name}: la propiedad '{prop}' del schema no es parámetro de run{sorted(run_params)}")
    # argmap/fixed traducen claves del parser -> parámetros del ejecutor.
    if run_params is not None:
        for k in c.parser_argmap.values():
            if k not in run_params:
                p.append(f"{c.name}: parser_argmap apunta a '{k}', no es parámetro de run")
        for k in c.parser_fixed:
            if k not in run_params:
                p.append(f"{c.name}: parser_fixed fija '{k}', no es parámetro de run")
    # Colisiones de nombre entre contratos
    if others:
        mine = set(c.all_names())
        for o in others:
            if o is c:
                continue
            clash = mine & set(o.all_names())
            if clash:
                p.append(f"{c.name}: nombres en colisión con {o.name}: {sorted(clash)}")
    return p


# =============================================================================
# CONTRACTS — la tabla. Una fila = una entrada. Ver docs/FASE_B_DISENO.md.
# =============================================================================

_V_LECTURA = "n/a (lectura: no cambia estado)"

CONTRACTS: list[ToolContract] = [
    # ---- Aplicaciones ----
    ToolContract(
        "abrir_aplicacion",
        "Abre cualquier aplicacion instalada en el computador por su nombre "
        "(Chrome, WhatsApp, Word, VS Code, Spotify, WSL/Ubuntu, calculadora...). "
        "Usar cuando el usuario pida abrir, lanzar o iniciar un programa.",
        _obj({"app": _str("Nombre de la aplicacion, ej: 'whatsapp', 'chrome', 'word'")}),
        _open_app, RiskLevel.EXECUTE,
        verify="EJECUTABLE (D1): sondeo con tope tras lanzar. Proceso que no "
               "aparece o muere -> ERROR. Proceso vivo pero sin poder listar "
               "ventanas (Wayland) -> EXECUTED con salvedad, no un 'hecho' liso. "
               "Reintento por gtk-launch (.desktop) vs exec directo.",
        revert="Cerrar la app (cerrar_aplicacion).",
        plan_capable=True, parser_intents=("open_app",)),

    ToolContract(
        "cerrar_aplicacion",
        "Cierra una aplicacion o programa abierto por su nombre (Word, Chrome, "
        "WhatsApp, Spotify, calculadora...). Usar cuando el usuario pida cerrar, "
        "terminar o salir de un programa.",
        _obj({"app": _str("Nombre de la aplicacion a cerrar, ej: 'word', 'chrome'")}),
        _close_app, RiskLevel.EXECUTE,
        verify="El proceso de la app ya no aparece en la lista de procesos.",
        revert="Volver a abrirla (abrir_aplicacion); el estado no guardado se pierde.",
        parser_intents=("close_app",)),

    ToolContract(
        "cerrar_todas_aplicaciones",
        "Cierra de una sola vez todos los programas que JARVIS abrio en esta "
        "sesion. Usar cuando el usuario pida cerrar todo o todos los programas.",
        _obj({}, []), _close_all_apps, RiskLevel.EXECUTE,
        verify="Ninguno de los procesos registrados por JARVIS sigue vivo.",
        revert="No reversible en bloque; reabrir cada app manualmente.",
        parser_intents=("close_all_apps",)),

    ToolContract("listar_aplicaciones",
                 "Lista las aplicaciones instaladas que JARVIS sabe abrir.",
                 _obj({}, []), _list_apps, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("list_apps",)),

    # ---- Volumen y multimedia ----
    ToolContract(
        "controlar_volumen",
        "Controla el volumen del computador: subir, bajar, silenciar, activar el "
        "sonido o fijarlo a un nivel exacto (0-100).",
        _obj({"accion": _str("Una de: subir, bajar, silenciar, activar, nivel",
                             ["subir", "bajar", "silenciar", "activar", "nivel"]),
              "nivel": _int("Nivel 0-100, solo si accion=nivel")}, ["accion"]),
        _volume_control, RiskLevel.EXECUTE,
        verify="EJECUTABLE (D1): tras aplicar se lee el volumen/estado real; si no "
               "cuadra se reintenta por vía alterna (pactl) y, sin verde, ERROR.",
        revert="Fijar el volumen anterior (controlar_volumen accion=nivel)."),

    ToolContract(
        "controlar_musica",
        "Controla la reproduccion multimedia en curso (Spotify, YouTube, etc.): "
        "pausar/reanudar, siguiente cancion o cancion anterior.",
        _obj({"accion": _str("Una de: pausar, siguiente, anterior",
                             ["pausar", "siguiente", "anterior"])}),
        _media_control, RiskLevel.EXECUTE,
        verify="EJECUTABLE (D1): sin reproductor MPRIS -> ERROR (no un 'hecho' "
               "vacío). Con reproductor, se comprueba que el estado (pausa) o la "
               "pista (siguiente/anterior) cambió; reintento con --all-players.",
        revert="Acción inversa (anterior/pausar); no siempre exacta."),

    ToolContract("volume_up", "Sube el volumen un paso.", _obj({}, []),
                 _volume_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): se comprueba que el volumen subió; si no, "
                        "reintento por pactl y, sin verde, ERROR.",
                 revert="volume_down.",
                 parser_intents=("volume_up",), parser_fixed={"accion": "subir"}),
    ToolContract("volume_down", "Baja el volumen un paso.", _obj({}, []),
                 _volume_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): se comprueba que el volumen bajó; si no, "
                        "reintento por pactl y, sin verde, ERROR.",
                 revert="volume_up.",
                 parser_intents=("volume_down",), parser_fixed={"accion": "bajar"}),
    ToolContract("volume_set", "Fija el volumen a un nivel exacto (0-100).",
                 _obj({"level": _int("Nivel 0-100")}),
                 _volume_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): se lee el volumen real y se compara con el "
                        "pedido (tol. redondeo); si no, reintento por pactl y, sin "
                        "verde, ERROR.",
                 revert="Fijar el nivel anterior.",
                 parser_intents=("volume_set",), parser_fixed={"accion": "nivel"},
                 parser_argmap={"level": "nivel"}),
    ToolContract("volume_mute", "Silencia o reactiva el sonido.",
                 _obj({"mute": _bool("true=silenciar, false=activar")}, []),
                 _volume_mute_bool, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): se lee el estado real de silencio y se "
                        "compara con el pedido; si no, reintento por pactl y, sin "
                        "verde, ERROR.",
                 revert="volume_mute con el valor inverso.",
                 parser_intents=("volume_mute",)),
    ToolContract("media_play_pause", "Pausa o reanuda la reproduccion.", _obj({}, []),
                 _media_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): sin reproductor -> ERROR; con él, el "
                        "`playerctl status` tiene que haber cambiado.",
                 revert="Volver a pulsar.",
                 parser_intents=("media_play_pause",), parser_fixed={"accion": "pausar"}),
    ToolContract("media_next", "Salta a la siguiente pista.", _obj({}, []),
                 _media_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): sin reproductor -> ERROR; con él, la "
                        "huella de la pista (`playerctl metadata`) tiene que cambiar.",
                 revert="media_previous.",
                 parser_intents=("media_next",), parser_fixed={"accion": "siguiente"}),
    ToolContract("media_previous", "Vuelve a la pista anterior.", _obj({}, []),
                 _media_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): sin reproductor -> ERROR; con él, la "
                        "huella de la pista (`playerctl metadata`) tiene que cambiar.",
                 revert="media_next.",
                 parser_intents=("media_previous",), parser_fixed={"accion": "anterior"}),

    # ---- Recordatorios ----
    ToolContract(
        "crear_recordatorio",
        "Programa un recordatorio con alarma que sonara y hablara a la hora "
        "indicada. Usar cuando el usuario diga 'recuerdame en X minutos...' o "
        "'avisame a las 3...'.",
        _obj({"texto": _str("Que hay que recordar"),
              "minutos": _int("Dentro de cuantos minutos avisar (0 si se usa hora)"),
              "hora": _str("Hora exacta en formato 24h HH:MM, ej '15:30'. Vacio si se usan minutos")},
             ["texto"]),
        _set_reminder, RiskLevel.CREATE,
        verify="EJECUTABLE (D1): se RELEE reminders.json de disco y se comprueba "
               "id + texto + hora (tol. 60 s); reintento con escritura atómica. "
               "Sin verde -> ERROR.",
        revert="cancelar_recordatorio.",
        parser_intents=("set_reminder",),
        parser_argmap={"text": "texto", "minutes": "minutos", "at": "hora"}),

    ToolContract("listar_recordatorios",
                 "Lista los recordatorios y alarmas pendientes del usuario.",
                 _obj({}, []), _list_reminders, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("list_reminders",)),

    ToolContract("cancelar_recordatorio",
                 "Cancela recordatorios pendientes: por numero, por texto o todos.",
                 _obj({"cual": _str("Numero del recordatorio, parte del texto, o 'todos'")}, []),
                 _cancel_reminder, RiskLevel.EXECUTE,
                 verify="listar_recordatorios ya no incluye el/los cancelado(s).",
                 revert="No reversible; volver a crearlo (crear_recordatorio).",
                 parser_intents=("cancel_reminder",),
                 parser_argmap={"which": "cual"}),

    # ---- WhatsApp / contactos ----
    ToolContract(
        "enviar_whatsapp",
        "Abre WhatsApp con un mensaje ya escrito para un contacto o numero. NO lo "
        "envia: el usuario solo pulsa enviar. Usar cuando pidan mandar un whatsapp "
        "o mensaje a alguien.",
        _obj({"para": _str("Nombre del contacto o numero de telefono"),
              "mensaje": _str("El texto del mensaje")}),
        _send_whatsapp, RiskLevel.EXECUTE,
        verify="WhatsApp abre el chat del destinatario con el texto en la caja.",
        revert="n/a (no se envía; el usuario decide).",
        parser_intents=("send_whatsapp",),
        parser_argmap={"to": "para", "message": "mensaje"}),

    ToolContract("add_contact", "Guarda un contacto (nombre + telefono) para WhatsApp.",
                 _obj({"name": _str("Nombre del contacto"),
                       "phone": _str("Numero de telefono")}),
                 _add_contact, RiskLevel.CREATE, llm_visible=False,
                 verify="list_contacts incluye el nombre nuevo.",
                 revert="Editar el archivo de contactos a mano.",
                 parser_intents=("add_contact",)),

    ToolContract("list_contacts", "Lista los contactos guardados para WhatsApp.",
                 _obj({}, []), _list_contacts, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("list_contacts",)),

    # ---- Ventanas / escritorio ----
    ToolContract(
        "organizar_ventanas",
        "Organiza las ventanas del escritorio: minimizar todas, o poner la ventana "
        "activa a la izquierda, derecha, maximizarla o minimizarla.",
        _obj({"accion": _str("Una de: minimizar_todo, izquierda, derecha, maximizar, minimizar",
                             ["minimizar_todo", "izquierda", "derecha", "maximizar", "minimizar"])}),
        _window_control, RiskLevel.EXECUTE,
        verify="El gestor de ventanas refleja la nueva geometría/estado.",
        revert="Restaurar la ventana manualmente (no hay undo)."),

    ToolContract("minimize_all", "Minimiza todas las ventanas (mostrar escritorio).",
                 _obj({}, []), _window_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="No hay ventanas visibles.", revert="Restaurar a mano.",
                 parser_intents=("minimize_all",),
                 parser_fixed={"accion": "minimizar_todo"}),
    ToolContract("snap_window", "Coloca la ventana activa (izquierda/derecha/maximizar/minimizar).",
                 _obj({"direction": _str("izquierda, derecha, maximizar o minimizar")}),
                 _window_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="La ventana activa tomó la geometría pedida.",
                 revert="Restaurar a mano.",
                 parser_intents=("snap_window",),
                 parser_argmap={"direction": "accion"}),
    # (cambiar_ventana va más abajo, junto a captura_de_pantalla, para que el
    #  orden de los esquemas que ve el LLM sea idéntico al de antes)

    ToolContract("resumen_del_dia",
                 "Da un resumen completo del dia: fecha, clima actual, agenda del "
                 "calendario y titulares de noticias, todo en una sola respuesta.",
                 _obj({}, []), _daily_briefing, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("daily_briefing",)),

    ToolContract("leer_portapapeles",
                 "Lee en voz alta el texto que el usuario tiene copiado en el "
                 "portapapeles.",
                 _obj({}, []), _read_clipboard, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("read_clipboard",)),

    ToolContract("consultar_auditoria",
                 "Dice qué acciones de escritura/sistema hizo JARVIS hoy o ayer, "
                 "con su resultado, si se verificaron y si el usuario las "
                 "confirmó. Solo lectura de la auditoría append-only (D2).",
                 _obj({"dia": _str("'hoy' o 'ayer'", ["hoy", "ayer"])}, []),
                 _audit_query, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("audit_query",)),

    ToolContract("leer_archivo",
                 "Lee en voz alta el contenido de un archivo de texto (txt, md, "
                 "csv, json) de las carpetas permitidas.",
                 _obj({"ruta": _str("Ruta o nombre del archivo, ej 'notas.txt'")}),
                 _read_file, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("read_file",), parser_argmap={"path": "ruta"}),

    # ---- Energía ----
    ToolContract(
        "energia_del_equipo",
        "Bloquear la sesion, apagar, reiniciar o suspender el computador, o "
        "cancelar un apagado programado. Apagar y reiniciar dan 60 segundos "
        "cancelables. NO usar para cerrar programas ni para apagar el sonido.",
        _obj({"accion": _str("Una de: bloquear, apagar, reiniciar, suspender, cancelar",
                             ["bloquear", "apagar", "reiniciar", "suspender", "cancelar"])}),
        _power_control, RiskLevel.CRITICAL, needs_confirmation=False,
        verify="Para 'cancelar': `shutdown -c` sin error. Para apagar/reiniciar: "
               "el trabajo programado existe (`shutdown` devuelve hora).",
        revert="apagar/reiniciar: 'cancelar' dentro de los 60 s. bloquear/suspender: "
               "no reversible por software."),

    ToolContract("lock_pc", "Bloquea la sesion.", _obj({}, []), _power_control,
                 RiskLevel.CRITICAL, needs_confirmation=False, llm_visible=False,
                 verify="La sesión queda bloqueada.", revert="Desbloquear con contraseña.",
                 parser_intents=("lock_pc",), parser_fixed={"accion": "bloquear"}),
    ToolContract("shutdown_pc", "Apaga el equipo con 60 s cancelables.", _obj({}, []),
                 _power_control, RiskLevel.CRITICAL, needs_confirmation=False, llm_visible=False,
                 verify="`shutdown` programó el apagado.", revert="cancel_shutdown (< 60 s).",
                 parser_intents=("shutdown_pc",), parser_fixed={"accion": "apagar"}),
    ToolContract("restart_pc", "Reinicia el equipo con 60 s cancelables.", _obj({}, []),
                 _power_control, RiskLevel.CRITICAL, needs_confirmation=False, llm_visible=False,
                 verify="`shutdown -r` programó el reinicio.", revert="cancel_shutdown (< 60 s).",
                 parser_intents=("restart_pc",), parser_fixed={"accion": "reiniciar"}),
    ToolContract("suspend_pc", "Suspende el equipo.", _obj({}, []), _power_control,
                 RiskLevel.CRITICAL, needs_confirmation=False, llm_visible=False,
                 verify="El equipo entra en suspensión.", revert="Encender de nuevo.",
                 parser_intents=("suspend_pc",), parser_fixed={"accion": "suspender"}),
    ToolContract("cancel_shutdown", "Cancela un apagado o reinicio programado.", _obj({}, []),
                 _power_control, RiskLevel.EXECUTE, llm_visible=False,
                 verify="`shutdown -c`; no queda trabajo programado.", revert="n/a",
                 parser_intents=("cancel_shutdown",), parser_fixed={"accion": "cancelar"}),

    # ---- Sistema / lectura ----
    ToolContract("estado_del_sistema",
                 "Informa el uso de CPU, memoria RAM, disco y el estado de la "
                 "bateria de este computador.",
                 _obj({}, []), _system_status, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("system_status",)),

    # ---- Procesos (FASE E · E3). Solo por la ruta del parser: matar procesos
    #      es demasiado delicado para dejarlo al criterio del 3B. ----
    ToolContract("listar_procesos",
                 "Lista los procesos que más CPU o RAM consumen, con PID y usuario.",
                 _obj({"por": _str("'cpu' o 'ram'", ["cpu", "ram"]),
                       "top": _int("Cuántos mostrar (por defecto 12)")}, []),
                 _list_processes, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("list_processes",)),
    ToolContract("matar_proceso",
                 "Cierra un proceso por nombre o PID, con confirmación.",
                 _obj({"objetivo": _str("Nombre del proceso o PID a cerrar")}),
                 _kill_process, RiskLevel.DELETE, llm_visible=False,
                 verify="EJECUTABLE (E3/D1): tras SIGTERM/SIGKILL se comprueba "
                        "que el PID ya no existe (o es zombie). Un kill que "
                        "devuelve 0 y deja el proceso vivo -> ERROR. E1: no "
                        "toca intocables. E2: proceso de otro usuario -> sudo.",
                 revert="Irreversible; volver a lanzar la app manualmente.",
                 plan_capable=True, plan_run=_kill_process,
                 parser_intents=("kill_process",)),

    # ---- Servicios systemd (FASE E · E4). Solo ruta parser. ----
    ToolContract("estado_servicio",
                 "Dice el estado de un servicio de systemd (activo/parado, "
                 "habilitado al arranque).",
                 _obj({"servicio": _str("Nombre del servicio, ej 'cups'"),
                       "ambito": _str("'user' (por defecto) o 'system'",
                                      ["user", "system"])}, ["servicio"]),
                 _service_status, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("service_status",)),
    ToolContract("controlar_servicio",
                 "Inicia, para o reinicia un servicio de systemd, con "
                 "confirmación. Solo servicios de usuario; los de sistema "
                 "exigen una regla de sudoers que se te muestra.",
                 _obj({"accion": _str("iniciar | parar | reiniciar",
                                      ["iniciar", "parar", "reiniciar"]),
                       "servicio": _str("Nombre del servicio"),
                       "ambito": _str("'user' (por defecto) o 'system'",
                                      ["user", "system"])}, ["accion", "servicio"]),
                 _service_control, RiskLevel.DELETE, llm_visible=False,
                 verify="EJECUTABLE (E4/D1): se RELEE `systemctl show` tras la "
                        "acción; si el ActiveState no es el esperado -> ERROR. "
                        "E1: no toca unidades intocables. E2: ámbito system -> "
                        "sudo con la regla concreta.",
                 revert="La acción inversa (parar<->iniciar); reiniciar no revierte.",
                 plan_capable=True, plan_run=_service_control,
                 parser_intents=("service_control",)),

    ToolContract("listar_intocables",
                 "Dice qué procesos y servicios NO puede tocar JARVIS y por qué.",
                 _obj({}, []), _untouchables_list, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("untouchables",)),

    # ---- Brillo de pantalla (FASE F · F1) ----
    ToolContract("controlar_brillo",
                 "Sube, baja o fija el brillo de la pantalla (0-100).",
                 _obj({"accion": _str("subir | bajar | nivel", ["subir", "bajar", "nivel"]),
                       "nivel": _int("Nivel 0-100, solo si accion=nivel")}, ["accion"]),
                 _brightness, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (F1/D1): se relee `brightnessctl get`; si no "
                        "cuadra, reintento y luego ERROR. Nunca por debajo del "
                        "mínimo utilizable. Sin brightnessctl -> ERROR claro.",
                 revert="Fijar el brillo anterior.",
                 parser_intents=("brightness_ctl",)),
    ToolContract("brightness_up", "Sube el brillo un paso.", _obj({}, []),
                 _brightness, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (F1): se comprueba que el brillo subió.",
                 revert="brightness_down.",
                 parser_intents=("brightness_up",), parser_fixed={"accion": "subir"}),
    ToolContract("brightness_down", "Baja el brillo un paso.", _obj({}, []),
                 _brightness, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (F1): se comprueba que el brillo bajó.",
                 revert="brightness_up.",
                 parser_intents=("brightness_down",), parser_fixed={"accion": "bajar"}),
    ToolContract("brightness_set", "Fija el brillo a un nivel exacto (0-100).",
                 _obj({"level": _int("Nivel 0-100")}),
                 _brightness, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (F1): se relee el brillo real y se compara.",
                 revert="Fijar el nivel anterior.",
                 parser_intents=("brightness_set",), parser_fixed={"accion": "nivel"},
                 parser_argmap={"level": "nivel"}),

    # ---- Red y WiFi (FASE F · F2) ----
    ToolContract("estado_red",
                 "Dice el estado de la red: interfaces, conexión activa, IP y "
                 "si el WiFi está encendido.",
                 _obj({}, []), _net_status, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("net_status",)),
    ToolContract("listar_wifi",
                 "Lista las redes WiFi visibles con su señal y seguridad.",
                 _obj({}, []), _wifi_list, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("wifi_list",)),
    ToolContract("conectar_wifi",
                 "Conecta a una red WiFi YA GUARDADA (usa la contraseña que "
                 "NetworkManager tiene; JARVIS no maneja contraseñas).",
                 _obj({"red": _str("Nombre de la red guardada")}),
                 _wifi_connect, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (F2/D1): tras `nmcli connection up` se "
                        "comprueba que la conexión está 'activated', no el rc. "
                        "Red no guardada -> BLOQUEADO. Transacción de paquetes "
                        "en curso -> BLOQUEADO.",
                 revert="desconectar_red.",
                 parser_intents=("wifi_connect",)),
    ToolContract("wifi_encender", "Enciende la radio WiFi (con confirmación).",
                 _obj({}, []), _wifi_radio, RiskLevel.DELETE, llm_visible=False,
                 verify="EJECUTABLE (F2/D1): se relee `nmcli radio wifi`.",
                 revert="wifi_apagar.",
                 plan_capable=True, plan_run=_wifi_radio,
                 parser_intents=("wifi_on",), parser_fixed={"encender": True}),
    ToolContract("wifi_apagar",
                 "Apaga la radio WiFi. Confirmación: puede dejarte sin conexión.",
                 _obj({}, []), _wifi_radio, RiskLevel.DELETE, llm_visible=False,
                 verify="EJECUTABLE (F2/D1): se relee `nmcli radio wifi`.",
                 revert="wifi_encender.",
                 plan_capable=True, plan_run=_wifi_radio,
                 parser_intents=("wifi_off",), parser_fixed={"encender": False}),
    ToolContract("desconectar_red",
                 "Desconecta una conexión de red. Confirmación: si es la única, "
                 "JARVIS pierde acceso a todo lo que no sea local.",
                 _obj({"objetivo": _str("Nombre de la conexión. Vacío = la de WiFi")}, []),
                 _net_disconnect, RiskLevel.DELETE, llm_visible=False,
                 verify="EJECUTABLE (F2/D1): se comprueba que la conexión ya no "
                        "está activa.",
                 revert="Volver a conectar (conectar_wifi / nmcli connection up).",
                 plan_capable=True, plan_run=_net_disconnect,
                 parser_intents=("net_disconnect",)),

    # ---- Notificaciones (FASE E · E5) ----
    ToolContract("enviar_notificacion",
                 "Muestra una notificación de escritorio con notify-send.",
                 _obj({"mensaje": _str("El texto de la notificación"),
                       "titulo": _str("Título (por defecto 'JARVIS')"),
                       "urgencia": _str("baja | normal | alta",
                                        ["baja", "normal", "alta"])}, ["mensaje"]),
                 _notify, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (E5/D1): notify-send rc 0 -> EXECUTED con "
                        "salvedad (que se muestre en pantalla no es comprobable "
                        "-> verify None). Sin notify-send -> ERROR claro.",
                 revert="n/a (la notificación se descarta sola).",
                 parser_intents=("notify",)),

    ToolContract(
        "ejecutar_comando",
        "Ejecuta un comando de PowerShell en el computador. Solo para comandos "
        "de consulta seguros (dir, ipconfig, git status). Los comandos "
        "destructivos estan bloqueados.",
        _obj({"command": _str("El comando de PowerShell a ejecutar")}),
        _run_command, RiskLevel.CRITICAL, needs_confirmation=False,
        verify="El comando devolvió salida y código 0; validate_shell_command lo permitió.",
        revert="Depende del comando; los que mutan estado están bloqueados.",
        plan_capable=True, plan_run=_plan_command, parser_intents=("run_command",)),

    # ---- Archivos ----
    ToolContract("listar_archivos",
                 "Lista los archivos y carpetas de un directorio permitido "
                 "(Documentos, Descargas, Escritorio, Musica, Imagenes, Videos).",
                 _obj({"path": _str("Ruta de la carpeta. Vacio = Documentos")}, []),
                 _list_files, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("list_files",)),

    ToolContract("buscar_archivo",
                 "Busca archivos por nombre dentro de una carpeta permitida.",
                 _obj({"name": _str("Nombre o parte del nombre del archivo"),
                       "path": _str("Carpeta donde buscar. Vacio = Documentos")}, ["name"]),
                 _search_files, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("search_files",)),

    ToolContract("file_info", "Da metadatos de un archivo (tamaño, fechas, tipo).",
                 _obj({"path": _str("Ruta del archivo")}),
                 _file_info, RiskLevel.READ, llm_visible=False,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("file_info",)),

    ToolContract("crear_carpeta", "Crea una carpeta nueva en una ruta permitida.",
                 _obj({"path": _str("Ruta completa de la carpeta a crear")}),
                 _create_directory, RiskLevel.CREATE,
                 verify="EJECUTABLE (D1): os.path.isdir tras crear; reintento con "
                        "os.makedirs. Sin verde -> ERROR.",
                 revert="Borrar la carpeta creada.",
                 plan_capable=True, parser_intents=("create_directory",)),

    ToolContract("crear_archivo", "Crea un archivo de texto con contenido en una ruta permitida.",
                 _obj({"path": _str("Ruta completa del archivo"),
                       "content": _str("Contenido del archivo")}, ["path"]),
                 _create_file, RiskLevel.CREATE,
                 verify="EJECUTABLE (D1): existe + TAMAÑO + CONTENIDO byte a byte "
                        "(un fichero vacío no pasa); reintento con escritura cruda "
                        "+ fsync. Sin verde -> ERROR.",
                 revert="Borrar el archivo creado.",
                 plan_capable=True, parser_intents=("create_file",)),

    ToolContract("copiar_archivo", "Copia un archivo de una ruta permitida a otra.",
                 _obj({"src": _str("Ruta origen"), "dst": _str("Ruta destino")}),
                 _copy_file, RiskLevel.CREATE, llm_visible=False,
                 verify="EJECUTABLE (D1): destino existe y tamaño == origen; "
                        "reintento con copyfileobj + fsync. Sin verde -> ERROR.",
                 revert="Borrar la copia.",
                 plan_capable=True, parser_intents=("copy_file",)),

    ToolContract("mover_archivo", "Mueve o renombra un archivo entre rutas permitidas.",
                 _obj({"src": _str("Ruta origen"), "dst": _str("Ruta destino")}),
                 _move_file, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): destino existe Y origen ya no (si el "
                        "origen sigue, fue copia, no move -> ERROR); reintento "
                        "copy2 + remove.",
                 revert="Mover de vuelta (mover_archivo con src/dst invertidos).",
                 plan_capable=True, parser_intents=("move_file",)),

    ToolContract("renombrar_archivo", "Cambia el nombre de un archivo en su carpeta.",
                 _obj({"path": _str("Ruta del archivo"),
                       "new_name": _str("Nuevo nombre (sin carpeta)")}),
                 _rename_file, RiskLevel.EXECUTE, llm_visible=False,
                 verify="EJECUTABLE (D1): existe el nombre nuevo y no el viejo; "
                        "reintento con shutil.move. Sin verde -> ERROR.",
                 revert="Renombrar de vuelta al nombre anterior.",
                 plan_capable=True, parser_intents=("rename_file",)),

    ToolContract("borrar_archivo",
                 "Prepara el borrado de un archivo. NO borra de inmediato: crea un "
                 "plan que el usuario debe confirmar con /confirmar.",
                 _obj({"path": _str("Ruta del archivo a borrar")}),
                 _delete_file, RiskLevel.DELETE,
                 verify="Tras /confirmar: `os.path.exists(path)` es False.",
                 revert="Irreversible (o restaurar desde papelera/backup si existe).",
                 plan_capable=True, plan_run=_delete_file, in_legacy_write=True,
                 parser_intents=("delete_file",)),

    ToolContract("ocultar_archivos",
                 "Oculta (o vuelve visibles) todos los archivos de una carpeta. "
                 "Requiere confirmacion del usuario.",
                 _obj({"path": _str("Ruta de la carpeta"),
                       "hide": _bool("true para ocultar, false para mostrar")}, ["path"]),
                 _hide_files, RiskLevel.DELETE,
                 verify="Tras /confirmar: los archivos empiezan (o no) por '.'.",
                 revert="ocultar_archivos con hide invertido.",
                 plan_capable=True, plan_run=_hide_files, parser_intents=("hide_files",)),

    # ---- Información ----
    ToolContract("clima",
                 "Dice el clima actual de cualquier ciudad del mundo: temperatura, "
                 "humedad, viento y pronostico del dia.",
                 _obj({"city": _str("Ciudad. Vacio = ciudad actual del usuario")}, []),
                 _weather, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("weather",)),

    ToolContract("ubicar_lugar",
                 "Abre un lugar en Google Maps e informa la distancia desde la "
                 "ubicacion actual del usuario.",
                 _obj({"place": _str("Ciudad, pais o lugar a ubicar")}),
                 _locate, RiskLevel.EXECUTE,
                 verify="El navegador abrió la URL de Maps para el lugar.",
                 revert="Cerrar la pestaña.",
                 parser_intents=("locate",)),

    ToolContract("wikipedia",
                 "Cuenta informacion sobre una persona, lugar, empresa o tema, "
                 "consultando Wikipedia. Usar cuando pregunten quien es alguien o "
                 "que es algo del mundo real.",
                 _obj({"topic": _str("Persona o tema a consultar")}),
                 _wiki, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("wiki",)),

    ToolContract("noticias", "Lee los titulares principales de las noticias de hoy.",
                 _obj({}, []), _news, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("news_headlines",)),

    ToolContract("calcular",
                 "Resuelve una operacion o ecuacion matematica. Acepta lenguaje "
                 "natural ('5 mas 3 por 2') y ecuaciones ('x + 135 - 234 = 345').",
                 _obj({"expression": _str("La expresion o ecuacion a resolver")}),
                 _calculate, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("calculate",)),

    ToolContract("preguntar_wolframalpha",
                 "Responde preguntas de datos y ciencia (distancias, poblaciones, "
                 "conversiones, formulas) via WolframAlpha. Funciona mejor en ingles.",
                 _obj({"question": _str("La pregunta factual")}),
                 _wolfram, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("wolfram",)),

    ToolContract("mi_direccion_ip",
                 "Informa la direccion IP local y publica de este computador.",
                 _obj({}, []), _get_ip, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("get_ip",)),

    ToolContract("proximos_eventos",
                 "Lista los proximos eventos del calendario de Google del usuario.",
                 _obj({}, []), _calendar, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("calendar_events",)),

    ToolContract("contar_chiste", "Cuenta un chiste para entretener al usuario.",
                 _obj({}, []), _joke, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("tell_joke",)),

    # ---- Web ----
    ToolContract("abrir_sitio_web", "Abre una pagina web en el navegador del usuario.",
                 _obj({"site": _str("Dominio o URL, ej: 'github.com', 'youtube.com'")}),
                 _open_website, RiskLevel.EXECUTE,
                 verify="El navegador abrió la URL.", revert="Cerrar la pestaña.",
                 parser_intents=("open_website",)),

    ToolContract("buscar_en_google",
                 "Busca cualquier cosa en Google y abre los resultados en el navegador.",
                 _obj({"query": _str("Lo que se quiere buscar")}),
                 _google, RiskLevel.EXECUTE,
                 verify="El navegador abrió la búsqueda.", revert="Cerrar la pestaña.",
                 parser_intents=("google_search",)),

    ToolContract("reproducir_en_spotify",
                 "Busca y reproduce cualquier cancion o artista en Spotify, usando "
                 "la cuenta del usuario. Es la forma preferida de poner musica "
                 "cuando el usuario pide una cancion o artista especifico, salvo "
                 "que pida explicitamente YouTube o musica local.",
                 _obj({"song": _str("Cancion o artista a reproducir, ej: 'bohemian rhapsody'")}),
                 _spotify, RiskLevel.EXECUTE,
                 verify="La API de Spotify reporta reproducción activa de la pista.",
                 revert="Pausar (controlar_musica accion=pausar).",
                 parser_intents=("spotify_play",)),

    ToolContract("reproducir_en_youtube",
                 "Busca y reproduce un video en YouTube. Usar solo cuando el "
                 "usuario pida YouTube explicitamente, no para pedidos genericos "
                 "de musica.",
                 _obj({"query": _str("Cancion, artista o video a reproducir")}),
                 _youtube, RiskLevel.EXECUTE,
                 verify="El navegador abrió el video de YouTube.",
                 revert="Cerrar la pestaña.",
                 parser_intents=("youtube_play",)),

    ToolContract("reproducir_musica_local",
                 "Reproduce musica guardada en la carpeta Musica del computador.",
                 _obj({"song": _str("Nombre de la cancion. Vacio = aleatoria")}, []),
                 _play_music, RiskLevel.EXECUTE,
                 verify="El reproductor local está sonando.",
                 revert="Pausar/parar el reproductor.",
                 parser_intents=("play_music",)),

    ToolContract("navegar_con_selenium",
                 "Abre una pagina en el navegador Chrome que JARVIS controla "
                 "(automatizado). Usar solo si piden control del navegador.",
                 _obj({"url": _str("URL a la que navegar")}),
                 _browser_navigate, RiskLevel.EXECUTE,
                 verify="El driver de Selenium reporta la URL cargada.",
                 revert="cerrar_navegador o navegar a otra URL.",
                 parser_intents=("browser_navigate",)),

    ToolContract("cerrar_navegador",
                 "Cierra el navegador Chrome controlado por JARVIS.",
                 _obj({}, []), _close_browser, RiskLevel.EXECUTE,
                 verify="El proceso del driver ya no está vivo.",
                 revert="Volver a abrirlo (navegar_con_selenium).",
                 parser_intents=("close_browser",)),

    # ---- Empleo ----
    ToolContract("buscar_empleo",
                 "Busca ofertas de trabajo en Computrabajo y LinkedIn, ordenadas "
                 "de la mas reciente a la mas antigua, con empresa, salario y "
                 "ubicacion.",
                 _obj({"puesto": _str("Cargo buscado, ej: 'desarrollador', 'contador'"),
                       "ciudad": _str("Ciudad. Vacio = toda Colombia")}, ["puesto"]),
                 _search_jobs, RiskLevel.READ,
                 verify=_V_LECTURA, revert="n/a",
                 parser_intents=("search_jobs",)),

    ToolContract("abrir_oferta_empleo",
                 "Abre en el navegador una de las ofertas de la ultima busqueda "
                 "de empleo.",
                 _obj({"number": _int("Numero de la oferta en la lista (1, 2, 3...)")}),
                 _open_job, RiskLevel.EXECUTE,
                 verify="El navegador abrió la URL de la oferta n.",
                 revert="Cerrar la pestaña.",
                 parser_intents=("open_job",)),

    ToolContract("mostrar_ofertas_empleo",
                 "Abre los portales de empleo (Computrabajo, El Empleo, LinkedIn) "
                 "en el navegador, cada uno en su pestana, con la busqueda "
                 "aplicada.",
                 _obj({"puesto": _str("Cargo. Vacio = ultima busqueda"),
                       "ciudad": _str("Ciudad")}, []),
                 _show_jobs, RiskLevel.EXECUTE,
                 verify="Se abrieron las pestañas de los portales.",
                 revert="Cerrar las pestañas.",
                 parser_intents=("show_jobs",)),

    # ---- Escritorio y productividad ----
    ToolContract("tomar_nota",
                 "Guarda una nota de texto con la fecha y hora, y la abre en el "
                 "Bloc de notas.",
                 _obj({"text": _str("El texto de la nota")}),
                 _take_note, RiskLevel.CREATE,
                 verify="EJECUTABLE (D1): se RELEE el archivo de notas y se "
                        "comprueba que la línea escrita está; reintento con "
                        "append + fsync. Sin verde -> ERROR.",
                 revert="Editar/borrar la línea en el archivo de notas.",
                 parser_intents=("take_note",)),

    ToolContract("captura_de_pantalla",
                 "Toma una captura de la pantalla y la guarda como imagen PNG.",
                 _obj({"name": _str("Nombre del archivo. Vacio = fecha y hora")}, []),
                 _screenshot, RiskLevel.CREATE,
                 verify="Existe el PNG en la carpeta de capturas.",
                 revert="Borrar la imagen.",
                 parser_intents=("screenshot",)),

    ToolContract("cambiar_ventana",
                 "Cambia a la ventana anterior del escritorio (Alt+Tab).",
                 _obj({}, []), _switch_window, RiskLevel.EXECUTE,
                 verify="El foco pasó a otra ventana.", revert="Volver a cambiar_ventana.",
                 parser_intents=("switch_window",)),

    ToolContract("enviar_correo",
                 "Prepara el envio de un correo electronico. NO lo envia de "
                 "inmediato: el usuario debe confirmar con /confirmar.",
                 _obj({"to": _str("Destinatario: direccion de correo o nombre de contacto"),
                       "subject": _str("Asunto del correo"),
                       "body": _str("Cuerpo del mensaje")}),
                 _send_email, RiskLevel.DELETE,
                 verify="Tras /confirmar: el servidor SMTP acepta el mensaje (250 OK).",
                 revert="Irreversible una vez enviado.",
                 plan_capable=True, plan_run=_send_email, parser_intents=("send_email",)),

    ToolContract("recordar",
                 "Guarda en la memoria permanente un dato que el usuario quiere "
                 "que JARVIS recuerde para siempre (preferencias, datos "
                 "personales, gustos).",
                 _obj({"text": _str("El dato a recordar")}),
                 _remember, RiskLevel.CREATE,
                 verify="EJECUTABLE (D1): se abre un MemoryStore NUEVO (relee "
                        "memory.json) y se comprueba que el dato está; reintento "
                        "sobre store nuevo. Sin verde -> ERROR.",
                 revert="Borrar la entrada del store de memoria.",
                 # FASE C · C6: antes era la única de las 5 herramientas
                 # solo-agente sin NINGÚN intent de parser (a diferencia de
                 # volumen/música/energía/ventanas, que ya llegaban por sus
                 # intents finos). "recuerda/recuérdame/acuérdate/acordate/
                 # no olvides/ten en cuenta que <dato>" -> _parse_recordar().
                 parser_intents=("recordar",)),
]

# Validación al importar: un contrato a medias rompe el arranque.
_PROBLEMS: list[str] = []
for _c in CONTRACTS:
    _PROBLEMS += validate_contract(_c, others=CONTRACTS)
assert not _PROBLEMS, "Contratos inválidos en catalog.CONTRACTS:\n- " + "\n- ".join(_PROBLEMS)


# =============================================================================
# Adaptadores — las vistas que consumen jarvis.py y agent/registry.py
# =============================================================================

def _contracts(contracts: list[ToolContract] | None) -> list[ToolContract]:
    return CONTRACTS if contracts is None else contracts


def by_name(name: str, contracts: list[ToolContract] | None = None) -> ToolContract | None:
    """Resuelve por nombre canónico, alias o intent del parser."""
    for c in _contracts(contracts):
        if name in c.all_names():
            return c
    return None


def agent_contracts(contracts: list[ToolContract] | None = None) -> list[ToolContract]:
    """Los contratos que el agente ofrece al LLM (los `llm_visible`)."""
    return [c for c in _contracts(contracts) if c.llm_visible]


def _keys(c: ToolContract) -> tuple[str, ...]:
    """Claves con las que se registra en los dicts de la ruta parser: el nombre
    canónico y cada intent que emite intent/parser.py."""
    seen: list[str] = []
    for n in (c.name, *c.parser_intents):
        if n not in seen:
            seen.append(n)
    return tuple(seen)


def read_tools(contracts: list[ToolContract] | None = None) -> dict[str, Callable[[dict], Any]]:
    """Réplica de `jarvis._READ_TOOLS`: intents que el parser emite como
    `kind='tool_read'` (equivale a `risk == READ`)."""
    out: dict[str, Callable[[dict], Any]] = {}
    for c in _contracts(contracts):
        if c.risk != RiskLevel.READ:
            continue
        ex = c.parser_executor(plan=False)
        for n in _keys(c):
            out[n] = ex
    return out


def write_tools(contracts: list[ToolContract] | None = None) -> dict[str, Callable[[dict], Any]]:
    """Réplica de `jarvis._WRITE_TOOLS`: intents que el parser emite como
    `kind='tool_execute'` (tiene intent de parser y no es lectura ni plan-only
    destructivo: borrar/ocultar/correo van solo por plan_tools)."""
    out: dict[str, Callable[[dict], Any]] = {}
    for c in _contracts(contracts):
        if not c.parser_intents:
            continue
        if c.risk == RiskLevel.READ:
            continue
        if c.risk == RiskLevel.DELETE and not c.in_legacy_write:
            continue
        ex = c.parser_executor(plan=False)
        for n in _keys(c):
            out[n] = ex
    return out


def plan_tools(contracts: list[ToolContract] | None = None) -> dict[str, Callable[[dict], Any]]:
    """Réplica de `jarvis._PLAN_TOOLS`: los contratos `plan_capable` (usan
    `plan_run` si lo declaran, si no el `run` normal)."""
    out: dict[str, Callable[[dict], Any]] = {}
    for c in _contracts(contracts):
        if not c.plan_capable:
            continue
        ex = c.parser_executor(plan=True)
        for n in _keys(c):
            out[n] = ex
    return out


def slow_path_only(contracts: list[ToolContract] | None = None) -> list[str]:
    """Herramientas que el LLM ve pero que NINGUNA regla del parser alcanza:
    solo llegan por el camino lento (agente). Insumo del plan (FASE B)."""
    return sorted(c.name for c in _contracts(contracts)
                  if c.llm_visible and not c.parser_intents)


def parser_only(contracts: list[ToolContract] | None = None) -> list[str]:
    """Lo inverso: entradas que el parser resuelve pero que el agente NO ofrece
    al LLM (más capacidad por el camino rápido que por el lento)."""
    return sorted(c.name for c in _contracts(contracts)
                  if not c.llm_visible and c.parser_intents)
