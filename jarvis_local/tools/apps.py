"""
JARVIS Local - Herramientas de Aplicaciones (Fase 2)
Abrir aplicaciones de la whitelist con subprocess controlado.
Cerrar aplicaciones por nombre y las abiertas en la sesion.
"""
import contextlib
import difflib
import os
import subprocess
from pathlib import Path

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.permissions import get_app_path, list_allowed_apps
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy
from jarvis_local.tools._utils import normalize_text as _norm

ALLOWED_APP_NAMES = ["chrome", "vscode", "explorador", "powershell", "terminal",
                       "wsl", "notepad", "calculadora", "control", "configuracion",
                       "cmd", "taskmgr", "edge", "firefox"]

# Directorio inicial al abrir la terminal de WSL (usa el home del usuario actual)
WSL_START_DIR = str(Path.home())

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


def _running_procnames() -> set[str]:
    """Nombres (en minuscula, sin extension) de los procesos vivos ahora."""
    try:
        import psutil
    except ImportError:
        return set()
    out: set[str] = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info.get("name") or "").lower()
        if n:
            out.add(n)
            if n.endswith(".exe"):
                out.add(n[:-4])
    return out


def _ya_esta_abierta(candidatos: list[str]) -> bool:
    """True si algun proceso vivo coincide con un candidato (nombre de exe,
    stem del .desktop, primera palabra del nombre...)."""
    vivos = _running_procnames()
    if not vivos:
        return False
    for c in candidatos:
        c = (c or "").lower().removesuffix(".exe").removesuffix(".desktop")
        if not c:
            continue
        # "google-chrome" cubre "chrome"; "code" cubre "code"
        if any(c == v or c in v.split("-") or c in v.split("_") for v in vivos):
            return True
    return False


def _try_focus(nombre: str) -> bool:
    """Best-effort: traer la ventana al frente en Linux con wmctrl si esta.
    En Wayland puro no funciona (limitacion conocida); devuelve False y JARVIS
    lo dice con honestidad en vez de fingir."""
    if IS_WINDOWS:
        return False
    wmctrl = _shutil_which("wmctrl")
    if not wmctrl:
        return False
    try:
        r = subprocess.run([wmctrl, "-a", nombre], capture_output=True, timeout=3)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _shutil_which(cmd: str) -> str | None:
    import shutil
    return shutil.which(cmd)


# ── VERIFY de apertura (PLAN_EJECUCION FASE D · D1) ───────────────────────────
# Arrancar una app no es instantáneo (sondeo con tope, no sleep fijo). Y "el
# proceso existe" NO es "la ventana abrió": un proceso que arranca y muere a
# los 2 s pasa un chequeo por PID sin haber abierto nada. En Wayland todavía
# no se pueden listar ventanas (llega en la FASE F): si solo se puede
# comprobar el proceso, el desenlace es None (con salvedad), no True.

def _session_is_wayland() -> bool:
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY")) and not os.environ.get("DISPLAY")


def _active_window_title() -> str | None:
    """Título de la ventana activa en X11 (best-effort). None si no se puede."""
    xdotool = _shutil_which("xdotool")
    if not xdotool:
        return None
    try:
        r = subprocess.run([xdotool, "getactivewindow", "getwindowname"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _window_presente(cands: list[str]):
    """True si se ve una ventana que casa con la app; None si no se puede
    saber (Wayland puro, o sin wmctrl/X11). NUNCA devuelve False: que un
    título no aparezca no prueba que no haya ventana."""
    if IS_WINDOWS or _session_is_wayland():
        return None
    wmctrl = _shutil_which("wmctrl")
    if not wmctrl:
        return None
    try:
        r = subprocess.run([wmctrl, "-l"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    titulos = r.stdout.lower()
    for c in cands:
        c = (c or "").lower().removesuffix(".exe").removesuffix(".desktop")
        if len(c) >= 3 and c in titulos:
            return True
    return None


def _verify_lanzamiento(cands: list[str]):
    """Comprueba que una app RECIÉN lanzada de verdad arrancó.

    Devuelve un `verify.VerifyOutcome`:
      - False: el proceso no apareció en 3 s, o apareció y murió enseguida.
      - True:  proceso vivo Y ventana visible (solo comprobable en X11+wmctrl).
      - None:  proceso vivo pero la ventana no se puede confirmar (Wayland;
               llega en la FASE F). Se reporta con salvedad, no como éxito.
    """
    from jarvis_local.tools import verify as _v

    aparecio = _v.wait_until(lambda: _ya_esta_abierta(cands), timeout=3.0, interval=0.2)
    if not aparecio:
        return _v.VerifyOutcome(False, "el proceso no apareció tras 3 s", "psutil")
    # ¿sobrevivió? un spawn que muere en el acto no ha abierto nada
    _v.grace(0.4)
    if not _ya_esta_abierta(cands):
        return _v.VerifyOutcome(False, "el proceso arrancó y murió enseguida", "psutil")
    if _window_presente(cands) is True:
        return _v.VerifyOutcome(True, "proceso vivo y ventana visible", "wmctrl -l")
    return _v.VerifyOutcome(
        None,
        "el proceso está vivo, pero no puedo confirmar que la ventana abrió "
        "(introspección de ventanas en Wayland: FASE F)",
        "psutil")


def _verify_foco(cands: list[str]):
    """Para el caso "ya estaba abierta": lo que hay que comprobar NO es que el
    proceso exista (ya existía), sino que la app quedó ENFOCADA."""
    from jarvis_local.tools import verify as _v

    if IS_WINDOWS or _session_is_wayland() or not _shutil_which("wmctrl"):
        return _v.VerifyOutcome(
            None, "no puedo confirmar el foco en Wayland (gestión de ventanas: "
            "FASE F)", "-")
    titulo = _active_window_title()
    if titulo is None:
        return _v.VerifyOutcome(None, "no pude leer la ventana activa", "-")
    for c in cands:
        c = (c or "").lower().removesuffix(".exe").removesuffix(".desktop")
        if len(c) >= 3 and c in titulo.lower():
            return _v.VerifyOutcome(True, f"ventana activa: {titulo!r}", "xdotool")
    return _v.VerifyOutcome(None, f"ventana activa: {titulo!r} (no casa con la app)",
                            "xdotool")


def _finish_ya_abierta(plan: ActionPlan, display: str, cands: list[str]) -> ActionPlan:
    """La app ya estaba abierta: se pide enfocarla y se COMPRUEBA el foco."""
    from jarvis_local.tools import verify as _v

    _try_focus(display)
    return _v.finish(
        plan, _verify_foco(cands),
        ok_msg=f"{display} ya estaba abierta, la traje al frente.",
        fail_msg=f"{display} ya estaba abierta, pero no pude traerla al frente, senor.")


def _finish_lanzada(plan: ActionPlan, display: str, cands: list[str],
                    estrategias: list) -> ActionPlan:
    """Lanza la app con una o más estrategias y COMPRUEBA que arrancó. Cada
    `estrategia` es un callable que lanza y devuelve una etiqueta corta, o
    lanza excepción."""
    from jarvis_local.tools import verify as _v

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, lanzar in enumerate(estrategias):
        try:
            metodo = lanzar()
        except Exception as e:
            tried.append(f"{getattr(lanzar, '__name__', 'estrategia')}: {e}")
            outcome = _v.VerifyOutcome(False, str(e), "lanzar")
            continue
        outcome = _verify_lanzamiento(cands)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0 and len(estrategias) > 1:
            plan.reason += " (reintento con vía alterna)"
    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"{display} abierto correctamente.",
        fail_msg=f"No pude abrir {display}, senor.")


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

    # FOTO PREVIA (D1): sin saber qué había ANTES no se puede distinguir "lo
    # abrí yo" de "ya estaba". Ya abierta -> NO lanzar un duplicado (era el
    # bug: "abre VS Code" dos veces abría dos ventanas): enfocar la existente
    # y comprobar el FOCO, no el proceso (que ya existía).
    _cands = [Path(path).name, name_lower, *_CLOSE_PROC_MAP.get(name_lower, [])]
    if _ya_esta_abierta(_cands):
        _register_opened(name_lower, name, procnames=[Path(path).name])
        return _finish_ya_abierta(plan, name, _cands)

    def _exec_directo() -> str:
        if IS_WINDOWS and name_lower == "configuracion":
            subprocess.Popen(["start", "ms-settings:"], shell=True)
            _register_opened(name_lower, name, procnames=["SystemSettings.exe"])
            return "start ms-settings:"
        if IS_WINDOWS and name_lower == "wsl":
            proc = _launch_wsl(path)
            _register_opened(name_lower, name, pid=proc.pid,
                             procnames=[Path(path).name])
            return "lanzar WSL"
        proc = subprocess.Popen([path], shell=False)
        _register_opened(name_lower, name, pid=proc.pid,
                         procnames=[Path(path).name])
        return f"exec {Path(path).name}"

    def _exec_desktop() -> str:
        # Estrategia DISTINTA: activación por archivo .desktop (gtk-launch) en
        # vez de exec directo del binario.
        from jarvis_local.tools.app_index import find_app, launch_app
        matches = find_app(name)
        if not matches:
            raise RuntimeError("sin entrada .desktop para activar")
        launch_app(matches[0]["appid"])
        _register_opened(name_lower, name, procnames=[Path(path).name])
        return f"gtk-launch {matches[0]['appid']}"

    estrategias = [_exec_directo] if IS_WINDOWS else [_exec_directo, _exec_desktop]
    return _finish_lanzada(plan, name, _cands, estrategias)


def _open_installed_app(name: str) -> ActionPlan:
    """Abre una app instalada (menu inicio) por nombre con busqueda difusa.
    `find_app` ya aplica sinonimos ("word" -> LibreOffice Writer, etc.)."""
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

    # Ya abierta -> no duplicar; comprobar el FOCO (D1)
    _stem = str(best["appid"]).split("/")[-1]
    _cands = [_stem, best["norm"], best["norm"].split()[0],
              *_CLOSE_PROC_MAP.get(_norm(name), [])]
    if _ya_esta_abierta(_cands):
        _register_opened(best["norm"], best["name"])
        return _finish_ya_abierta(plan, best["name"], _cands)

    def _via_desktop() -> str:
        launch_app(best["appid"])
        _register_opened(best["norm"], best["name"])
        return f"gtk-launch {best['appid']}"

    def _via_binario() -> str:
        # Estrategia DISTINTA: ejecutar el binario directo si está en el PATH.
        exe = _shutil_which(_stem.removesuffix(".desktop")) or \
            _shutil_which(best["norm"].split()[0])
        if not exe:
            raise RuntimeError("sin binario en el PATH para exec directo")
        proc = subprocess.Popen([exe], shell=False)
        _register_opened(best["norm"], best["name"], pid=proc.pid)
        return f"exec {exe}"

    resultado = _finish_lanzada(plan, best["name"], _cands, [_via_desktop, _via_binario])
    if resultado.status == ActionStatus.EXECUTED and len(matches) > 1:
        otros = ", ".join(m["name"] for m in matches[1:4])
        resultado.result += f" (Tambien encontre: {otros})"
    return resultado


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
    _cands = [Path(path).name, name_lower, *_CLOSE_PROC_MAP.get(name_lower, [])]
    if _ya_esta_abierta(_cands):
        _register_opened(name_lower, name, procnames=[Path(path).name])
        return _finish_ya_abierta(plan, name, _cands)

    def _exec_directo() -> str:
        if IS_WINDOWS and name_lower == "wsl":
            proc = _launch_wsl(path)
        else:
            proc = subprocess.Popen([path], shell=False)
        _register_opened(name_lower, name, pid=proc.pid,
                         procnames=[Path(path).name])
        return f"exec {Path(path).name}"

    return _finish_lanzada(plan, name, _cands, [_exec_directo])


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
        procnames.append(Path(path).name)

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
