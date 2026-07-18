"""
JARVIS Local - Herramientas de Aplicaciones (Fase 2)
Abrir aplicaciones de la whitelist con subprocess controlado.
Cerrar aplicaciones por nombre y las abiertas en la sesion.
"""
import contextlib
import difflib
import os
import subprocess
import unicodedata

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.permissions import get_app_path, list_allowed_apps
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy

ALLOWED_APP_NAMES = ["chrome", "vscode", "explorador", "powershell", "terminal",
                       "wsl", "notepad", "calculadora", "control", "configuracion",
                       "cmd", "taskmgr", "edge", "firefox"]

# Directorio inicial (ruta Linux) al abrir la terminal de WSL
WSL_START_DIR = "/home/omarhernandez/personalProjects"

# Programas abiertos por JARVIS en esta sesion, para poder cerrarlos despues.
# clave normalizada -> {"display": nombre, "pids": set, "procnames": [exe...]}
_OPENED: dict[str, dict] = {}

# Nombre hablado -> ejecutable(s) del proceso. Cubre las apps mas comunes cuyo
# proceso no se llama como la app (word -> WINWORD.EXE). Los nombres de
# Windows y Linux conviven en la misma lista sin problema: cada uno solo
# matchea procesos reales de su propio SO.
_CLOSE_PROC_MAP: dict[str, list[str]] = {
    "chrome": ["chrome.exe", "chrome"],
    "vscode": ["Code.exe", "code"],
    "powershell": ["powershell.exe", "pwsh.exe", "ptyxis"],
    "terminal": ["WindowsTerminal.exe", "ptyxis", "gnome-terminal-server"],
    "wsl": ["wsl.exe", "WindowsTerminal.exe", "ptyxis"],
    "notepad": ["notepad.exe", "Notepad.exe", "gnome-text-editor", "gedit"],
    "calculadora": ["CalculatorApp.exe", "Calculator.exe", "calc.exe", "gnome-calculator"],
    "cmd": ["cmd.exe", "ptyxis"],
    "taskmgr": ["Taskmgr.exe", "gnome-system-monitor"],
    "edge": ["msedge.exe", "microsoft-edge"],
    "firefox": ["firefox.exe", "firefox"],
    "configuracion": ["SystemSettings.exe", "gnome-control-center"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "outlook": ["OUTLOOK.EXE"],
    "whatsapp": ["WhatsApp.exe"],
    "spotify": ["Spotify.exe", "spotify"],
    "telegram": ["Telegram.exe", "telegram-desktop"],
    "notion": ["Notion.exe", "notion-app"],
    "discord": ["Discord.exe", "discord"],
    "slack": ["slack.exe", "slack"],
    "teams": ["ms-teams.exe", "Teams.exe", "teams-for-linux"],
    "vlc": ["vlc.exe", "vlc"],
    "paint": ["mspaint.exe"],
}

# Procesos del sistema que JAMAS se cierran, ni por coincidencia de nombre.
_PROTECTED_PROCS = {
    "explorer.exe", "svchost.exe", "csrss.exe", "winlogon.exe", "wininit.exe",
    "services.exe", "lsass.exe", "smss.exe", "dwm.exe", "system", "registry",
    "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "conhost.exe",
}

# Palabras de relleno en nombres de apps: no sirven para identificar el proceso
_FILLER_WORDS = {"microsoft", "google", "mozilla", "apple", "windows", "app",
                 "de", "la", "el", "corporation", "inc"}


def _norm(text: str) -> str:
    """minusculas y sin acentos, para comparar nombres hablados."""
    t = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _register_opened(name: str, display: str, pid: int | None = None,
                     procnames: list[str] | None = None) -> None:
    """Anota un programa abierto por JARVIS para poder cerrarlo despues."""
    key = _norm(name)
    entry = _OPENED.setdefault(key, {"display": display, "pids": set(),
                                     "procnames": []})
    entry["display"] = display
    if pid:
        entry["pids"].add(pid)
    existentes = {p.lower() for p in entry["procnames"]}
    for pn in procnames or []:
        if pn and pn.lower() not in existentes:
            entry["procnames"].append(pn)
            existentes.add(pn.lower())


def _launch_wsl(wsl_path: str) -> subprocess.Popen:
    """Abre WSL en WSL_START_DIR, en Windows Terminal si esta disponible."""
    wt_path = get_app_path("terminal")
    args = [wsl_path, "--cd", WSL_START_DIR]
    if wt_path:
        return subprocess.Popen([wt_path] + args, shell=False)
    return subprocess.Popen(args, shell=False,
                            creationflags=subprocess.CREATE_NEW_CONSOLE)


def open_app(name: str) -> ActionPlan:
    name_lower = name.lower()
    if name_lower not in ALLOWED_APP_NAMES:
        return _open_installed_app(name)

    path = get_app_path(name_lower)
    if not path:
        all_apps = list_allowed_apps()
        info = all_apps.get(name_lower, {})
        installed = info.get("installed", False)
        if installed:
            return policy.block(f"No se encontro el ejecutable de {name} aunque parece instalada")
        else:
            return policy.block(f"{name} no esta instalada en este sistema")

    plan = ActionPlan(
        action="abrir_app",
        params={"app": name_lower, "path": path},
        paths_affected=[path],
        risk=RiskLevel.EXECUTE,
        reason=f"Abrir {name}",
    )
    try:
        if IS_WINDOWS and name_lower == "configuracion":
            subprocess.Popen(["start", "ms-settings:"], shell=True)
            _register_opened(name_lower, name, procnames=["SystemSettings.exe"])
        elif IS_WINDOWS and name_lower == "wsl":
            proc = _launch_wsl(path)
            _register_opened(name_lower, name, pid=proc.pid,
                             procnames=[os.path.basename(path)])
        else:
            proc = subprocess.Popen([path], shell=False)
            _register_opened(name_lower, name, pid=proc.pid,
                             procnames=[os.path.basename(path)])
        plan.result = f"{name} abierto correctamente."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No se pudo abrir {name}: {e}"
    return plan


def _open_installed_app(name: str) -> ActionPlan:
    """Abre una app instalada (menu inicio) por nombre con busqueda difusa."""
    from jarvis_local.tools.app_index import find_app, launch_app
    try:
        matches = find_app(name)
    except Exception as e:
        return policy.block(f"No pude consultar las apps instaladas: {e}")
    if not matches:
        return policy.block(
            f"No encontre ninguna aplicacion parecida a '{name}' en este equipo. "
            f"Tambien puedo abrir: {', '.join(ALLOWED_APP_NAMES)}")

    best = matches[0]
    plan = ActionPlan(
        action="abrir_app",
        params={"app": best["name"], "appid": best["appid"]},
        paths_affected=[best["appid"]],
        risk=RiskLevel.EXECUTE,
        reason=f"Abrir {best['name']} (app instalada)",
    )
    try:
        launch_app(best["appid"])
        _register_opened(best["norm"], best["name"])
        plan.result = f"{best['name']} abierto correctamente."
        if len(matches) > 1:
            otros = ", ".join(m["name"] for m in matches[1:4])
            plan.result += f" (Tambien encontre: {otros})"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No se pudo abrir {best['name']}: {e}"
    return plan


def list_apps() -> ActionPlan:
    apps = list_allowed_apps()
    lines = []
    for name, info in apps.items():
        status = "INSTALADA" if info["installed"] else "NO INSTALADA"
        lines.append(f"  {name}: {info['description']} [{status}]")
    plan = ActionPlan(
        action="listar_apps",
        risk=RiskLevel.READ,
        reason="Operacion de solo lectura",
    )
    plan.result = "\n".join(lines)
    plan.status = ActionStatus.EXECUTED
    return plan


def execute_open_app(name: str) -> ActionPlan:
    """Ejecuta la apertura de una app CONFIRMADA."""
    name_lower = name.lower()
    path = get_app_path(name_lower)
    if not path:
        return _open_installed_app(name)
    plan = ActionPlan(
        action="abrir_app_ejecutando",
        params={"app": name_lower, "path": path},
        paths_affected=[path],
        risk=RiskLevel.EXECUTE,
        status=ActionStatus.CONFIRMED,
    )
    try:
        if IS_WINDOWS and name_lower == "wsl":
            proc = _launch_wsl(path)
        else:
            proc = subprocess.Popen([path], shell=False)
        _register_opened(name_lower, name, pid=proc.pid,
                         procnames=[os.path.basename(path)])
        plan.result = f"{name} abierto correctamente"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
    return plan


def _find_target_procs(candidates: set[str], procnames: list[str],
                       pids: set[int]) -> tuple[list, list]:
    """Procesos en ejecucion que corresponden a la app buscada.

    Coincide por PID registrado, por nombre de ejecutable conocido o por
    parecido del nombre del proceso con lo que dijo el usuario. Nunca incluye
    procesos del sistema ni el propio JARVIS.

    Devuelve (confiables, ambiguos): los primeros vienen de un PID rastreado
    por JARVIS o de una coincidencia exacta de nombre de proceso, y se pueden
    cerrar sin mas; los segundos solo coinciden por subcadena (p.ej. "team"
    dentro de "teamviewer") y NO deben cerrarse sin que el usuario confirme
    explicitamente cual queria decir, para no matar procesos ajenos con
    trabajo sin guardar.
    """
    import psutil

    propios = {os.getpid()}
    with contextlib.suppress(psutil.Error):
        propios.update(p.pid for p in psutil.Process().parents())

    wanted = {p.lower() for p in procnames}
    utiles = {c for c in candidates if c and c not in _FILLER_WORDS}
    confiables, ambiguos = [], []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            nm = (proc.info["name"] or "").lower()
            if not nm or proc.info["pid"] in propios or nm in _PROTECTED_PROCS:
                continue
            base = nm[:-4] if nm.endswith(".exe") else nm
            exacto = base in utiles
            subcadena = any(len(c) >= 4 and c in base for c in utiles)
            if proc.info["pid"] in pids or nm in wanted or exacto:
                confiables.append(proc)
            elif subcadena:
                ambiguos.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return confiables, ambiguos


def _terminate_procs(procs: list) -> int:
    """Cierre educado (terminate) y, si un proceso se resiste, kill."""
    import psutil

    todos = []
    for p in procs:
        with contextlib.suppress(psutil.Error):
            todos.extend(p.children(recursive=True))
        todos.append(p)
    unicos = list({p.pid: p for p in todos}.values())
    for p in unicos:
        with contextlib.suppress(psutil.Error):
            p.terminate()
    _, vivos = psutil.wait_procs(unicos, timeout=3)
    for p in vivos:
        with contextlib.suppress(psutil.Error):
            p.kill()
    return len(unicos)


def close_app(name: str) -> ActionPlan:
    """Cierra una aplicacion abierta por su nombre hablado."""
    query = _norm(name)
    if not query:
        plan = policy.block("No se indico que aplicacion cerrar")
        plan.result = "Que aplicacion desea cerrar, senor?"
        return plan
    if "explorador" in query or "explorer" in query:
        plan = policy.block(
            "Cerrar el Explorador de archivos cerraria el escritorio de Windows")
        plan.result = ("No puedo cerrar el Explorador de archivos: cerraria "
                       "el escritorio de Windows, senor.")
        return plan

    procnames = list(_CLOSE_PROC_MAP.get(query, []))
    if not procnames:
        # tolerar errores al hablar/dictar: "world" -> "word"
        parecidos = difflib.get_close_matches(query, _CLOSE_PROC_MAP, n=1,
                                              cutoff=0.8)
        if parecidos:
            query = parecidos[0]
            procnames = list(_CLOSE_PROC_MAP[query])

    path = get_app_path(query)
    if path:
        procnames.append(os.path.basename(path))

    tracked = _OPENED.get(query)
    pids = set(tracked["pids"]) if tracked else set()
    if tracked:
        procnames.extend(tracked["procnames"])
    display = tracked["display"] if tracked else name

    candidates = {query}
    if not procnames and not pids:
        # app fuera del mapa: buscar su nombre real en el indice de instaladas
        try:
            from jarvis_local.tools.app_index import find_app
            matches = find_app(name)
            if matches:
                display = matches[0]["name"]
                candidates.add(matches[0]["norm"])
                candidates.update(matches[0]["norm"].split())
        except Exception:
            pass
    candidates.update(query.split())

    plan = ActionPlan(
        action="cerrar_app",
        params={"app": display},
        risk=RiskLevel.EXECUTE,
        reason=f"Cerrar {display}",
    )
    try:
        procs, ambiguos = _find_target_procs(candidates, procnames, pids)
        if not procs and not ambiguos:
            _OPENED.pop(query, None)
            plan.params["closed_count"] = 0
            plan.result = f"{display} no parece estar abierto, senor."
            plan.status = ActionStatus.EXECUTED
            return plan
        if not procs and ambiguos:
            # Solo hay coincidencias por parecido de nombre (p.ej. "team"
            # dentro de "teamviewer.exe"): no es la app que el usuario dijo
            # con certeza, asi que no se cierra nada sin confirmacion.
            nombres = ", ".join(sorted({p.info["name"] for p in ambiguos}))
            plan.status = ActionStatus.BLOCKED
            plan.result = (
                f"No encontre exactamente '{display}' abierto, pero si "
                f"proceso(s) parecidos ({nombres}). No los voy a cerrar por "
                "si acaso: diga el nombre completo si quiere cerrarlos."
            )
            return plan
        cerrados = _terminate_procs(procs)
        _OPENED.pop(query, None)
        plan.params["closed_count"] = cerrados
        detalle = f" ({cerrados} procesos)" if cerrados > 1 else ""
        plan.result = f"{display} cerrado correctamente{detalle}."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cerrar {display}: {e}"
    return plan


def close_all_apps() -> ActionPlan:
    """Cierra todos los programas que JARVIS abrio en esta sesion."""
    plan = ActionPlan(
        action="cerrar_todas_apps",
        risk=RiskLevel.EXECUTE,
        reason="Cerrar todos los programas abiertos en la sesion",
    )
    if not _OPENED:
        plan.result = "No he abierto ningun programa en esta sesion, senor."
        plan.status = ActionStatus.EXECUTED
        return plan

    cerrados, ya_cerrados, errores = [], [], []
    for key in list(_OPENED):
        display = _OPENED[key]["display"]
        sub = close_app(key)
        if sub.status == ActionStatus.EXECUTED:
            if sub.params.get("closed_count", 0) > 0:
                cerrados.append(display)
            else:
                ya_cerrados.append(display)
        else:
            errores.append(display)

    partes = []
    if cerrados:
        partes.append(f"Cerre {', '.join(cerrados)}.")
    if ya_cerrados:
        partes.append(f"Ya estaban cerrados: {', '.join(ya_cerrados)}.")
    if errores:
        partes.append(f"No pude cerrar: {', '.join(errores)}.")
    plan.result = " ".join(partes) or "No habia nada que cerrar, senor."
    plan.status = ActionStatus.ERROR if errores and not cerrados \
        else ActionStatus.EXECUTED
    if errores and not cerrados:
        plan.error = f"Fallo el cierre de: {', '.join(errores)}"
    return plan
