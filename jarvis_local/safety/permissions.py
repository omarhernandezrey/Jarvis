"""
JARVIS Local - Permisos y Whitelists (Fase 2)
Define carpetas, apps y comandos permitidos. Valida rutas contra escapes.
"""
import os
import re
import shutil
from pathlib import Path

from jarvis_local.config import IS_WINDOWS, user_dir

ALLOWED_FOLDERS = [
    user_dir("documents"),
    user_dir("downloads"),
    user_dir("desktop"),
    user_dir("music"),
    user_dir("pictures"),
    user_dir("videos"),
]
if IS_WINDOWS:
    ALLOWED_FOLDERS.append(os.path.expandvars(r"%USERPROFILE%\OneDrive"))

# Cada app tiene "paths" (candidatos de ruta absoluta, Windows) y/o
# "linux_bins" (nombres de binario a resolver con PATH via shutil.which,
# porque en Linux no hay un "Program Files" que adivinar). get_app_path()
# usa la lista que corresponda al SO.
ALLOWED_APPS = {
    "chrome": {
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "linux_bins": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
        "description": "Google Chrome",
    },
    "vscode": {
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        "linux_bins": ["code", "code-insiders"],
        "description": "Visual Studio Code",
    },
    "explorador": {
        "paths": [r"C:\Windows\explorer.exe"],
        "linux_bins": ["nautilus", "nemo", "dolphin", "pcmanfm"],
        "description": "Explorador de archivos",
    },
    "powershell": {
        "paths": [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        ],
        "linux_bins": ["ptyxis", "gnome-terminal", "konsole", "xterm"],
        "description": "PowerShell",
    },
    "terminal": {
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
            r"C:\Program Files\WindowsApps\Microsoft.WindowsTerminal*\wt.exe",
        ],
        "linux_bins": ["ptyxis", "gnome-terminal", "konsole", "xterm"],
        "description": "Windows Terminal",
    },
    "wsl": {
        "paths": [
            r"C:\Windows\System32\wsl.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wsl.exe"),
        ],
        # No hay WSL en Linux: "abre wsl" cae a abrir una terminal cualquiera.
        "linux_bins": ["ptyxis", "gnome-terminal", "konsole", "xterm"],
        "description": "Terminal WSL (Ubuntu)",
    },
    "notepad": {
        "paths": [r"C:\Windows\System32\notepad.exe"],
        "linux_bins": ["gnome-text-editor", "gedit", "kate", "leafpad"],
        "description": "Bloc de notas",
    },
    "calculadora": {
        "paths": [r"C:\Windows\System32\calc.exe"],
        "linux_bins": ["gnome-calculator", "kcalc", "galculator"],
        "description": "Calculadora",
    },
    "control": {
        "paths": [r"C:\Windows\System32\control.exe"],
        "linux_bins": ["gnome-control-center"],
        "description": "Panel de control",
    },
    "configuracion": {
        "paths": [
            os.path.expandvars(r"%WINDIR%\explorer.exe"),
        ],
        "linux_bins": ["gnome-control-center"],
        "description": "Configuracion de Windows (abre con start ms-settings:)",
    },
    "cmd": {
        "paths": [r"C:\Windows\System32\cmd.exe"],
        "linux_bins": ["ptyxis", "gnome-terminal", "konsole", "xterm"],
        "description": "Simbolo del sistema (CMD)",
    },
    "taskmgr": {
        "paths": [r"C:\Windows\System32\Taskmgr.exe"],
        "linux_bins": ["gnome-system-monitor", "ksysguard"],
        "description": "Administrador de tareas",
    },
    "edge": {
        "paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "linux_bins": ["microsoft-edge", "microsoft-edge-stable"],
        "description": "Microsoft Edge",
    },
    "firefox": {
        "paths": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "linux_bins": ["firefox", "firefox-esr"],
        "description": "Mozilla Firefox",
    },
}

BLOCKED_COMMAND_PATTERNS = [
    r"\.ps1",
    r"\.bat",
    r"\.cmd",
    r"Invoke-Expression",
    r"\biex\b",
    r"\bdel\b\s+/",
    r"\brmdir\b",
    r"\brd\b\s+/",
    r"\bformat\b",
    r"\bdiskpart\b",
    r"\breg\b\s+(add|delete|import)",
    r"\bschtasks\b.*\/create",
    r"\btaskkill\b\s+\/f",
    r"\bshutdown\b",
    r"\brm\s+-rf\b",
    r"\brm\s+-r\b",
    r"Set-ExecutionPolicy",
    r"\bicacls\b",
    r"\btakeown\b",
    # --- bash/Linux: mismo nivel de rigor que la lista de arriba ---
    r":\(\)\s*\{\s*:\|:&\s*\};:",       # bomba fork
    r"(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(ba)?sh\b",  # pipe a un shell
    r"\bsystemctl\b\s+(poweroff|reboot|suspend|halt)",  # solo via tools/power.py
    r">\s*/dev/sd[a-z]",
    r"\bchmod\b\s+-R\s+777\s+/",
]

# Palabras/cmdlets bloqueados como token completo (\b<kw>\b), sin importar
# en que orden aparezcan sus argumentos. Esto es deliberado: el bloqueo
# anterior exigia que -Force/-Recurse aparecieran INMEDIATAMENTE despues
# de "Remove-Item", lo que la sintaxis natural de PowerShell
# ("Remove-Item -Recurse -Force C:\ruta" o "Remove-Item C:\ruta -Force")
# evade con facilidad. Bloquear el cmdlet completo cierra ese bypass:
# el borrado real de archivos debe pasar por la herramienta dedicada
# (borrar_archivo), que si exige /confirmar.
BLOCKED_CMD_KEYWORDS = [
    "del", "rmdir", "rd", "format", "diskpart", "reg",
    "schtasks", "taskkill", "shutdown", "rm",
    "remove-item", "ri", "erase",
    "restart-computer", "stop-computer",
    "stop-process", "set-itemproperty", "new-itemproperty",
    "remove-itemproperty", "set-acl",
    # cmdlets de almacenamiento de PowerShell: "formatea el disco" hacia que
    # el agente emitiera `Get-Disk | ... | Clear-Disk` y no lo frenaba nada.
    "get-disk", "set-disk", "clear-disk", "initialize-disk", "update-disk",
    "format-volume", "new-partition", "remove-partition", "resize-partition",
    "get-partition", "set-partition",
    # bash/Linux: solo matchean si el token aparece de verdad, asi que
    # convivir en la misma lista con las palabras de Windows no causa falsos
    # positivos de un lado ni del otro.
    "sudo", "dd", "mkfs", "passwd", "userdel", "visudo",
    "iptables", "ufw", "crontab",
    "wipefs", "parted", "fdisk", "cfdisk", "sgdisk", "mkswap", "shred",
    "chpasswd", "usermod", "groupdel", "chattr",
]

# Operadores que encadenan o inyectan comandos. El pipe simple `|` NO esta:
# es legitimo para filtrar salidas ("ps aux | grep foo").
_SHELL_CHAINING = re.compile(r'[;`]|&&|\|\||\$\(|\$\{|>\s*/dev/|<\(')


def _sanitize_shell(command: str) -> str:
    """Colapsa saltos de linea/tabs/espacios. Comun a plan y ejecucion."""
    limpio = command.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", limpio).strip()


def validate_shell_command(command: str) -> tuple[bool, str, str]:
    """GUARDIA UNICO de todo comando de shell (parser, agente, terminal…).

    Todo camino que acabe en `subprocess` con un shell pasa por aqui. Si hay
    mas de una puerta con reglas distintas, hay un agujero: por eso esta es la
    unica.

    Returns:
        (permitido, motivo, comando_saneado)
    """
    saneado = _sanitize_shell(command)
    if not saneado:
        return False, "Comando vacio", saneado
    if _SHELL_CHAINING.search(saneado):
        return (False,
                "Comando bloqueado: operadores de encadenamiento/inyeccion no "
                "permitidos ( ; ` && || $() ${} >/dev/ )", saneado)
    bloqueado, motivo = is_command_blocked(saneado)
    if bloqueado:
        return False, motivo, saneado
    return True, "", saneado


def is_within_allowed(path_str: str) -> tuple[bool, Path | None]:
    """
    Verifica que una ruta este dentro de las carpetas permitidas.
    Resuelve rutas reales y bloquea escapes con ../, symlinks, etc.

    Returns:
        (True, resolved_path) si esta permitido.
        (False, None) si esta fuera.
    """
    try:
        raw = Path(path_str)
        if not raw.is_absolute():
            # Path.resolve() de una ruta relativa la resuelve contra el
            # directorio de trabajo actual del proceso, que no es fijo ni
            # confiable (depende de desde donde se arranco JARVIS). Sin este
            # anclaje, una ruta relativa "inocente" puede terminar cayendo
            # dentro de una carpeta permitida por pura coincidencia de cwd
            # en vez de por la intencion real de la ruta.
            raw = Path(user_dir("documents")) / raw
        resolved = raw.resolve()
        for allowed_str in ALLOWED_FOLDERS:
            allowed = Path(allowed_str).resolve()
            try:
                resolved.relative_to(allowed)
                return True, resolved
            except ValueError:
                pass
        return False, None
    except (OSError, ValueError):
        return False, None


def get_app_path(name: str) -> str | None:
    """Busca el ejecutable de una app permitida. Devuelve None si no existe."""
    info = ALLOWED_APPS.get(name.lower())
    if not info:
        return None
    if not IS_WINDOWS:
        for binname in info.get("linux_bins", []):
            found = shutil.which(binname)
            if found:
                return found
        return None
    for p in info["paths"]:
        expanded = os.path.expandvars(p)
        candidates = [Path(expanded)]
        if "*" in expanded:
            import glob as _glob
            candidates = [Path(g) for g in _glob.glob(expanded)]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    return None


def list_allowed_apps() -> dict:
    """Lista las apps permitidas con estado de instalacion."""
    result = {}
    for name, info in ALLOWED_APPS.items():
        found = get_app_path(name)
        result[name] = {
            "description": info["description"],
            "installed": found is not None,
            "path": found,
        }
    return result


def is_command_blocked(command: str) -> tuple[bool, str]:
    """
    Verifica si un comando esta bloqueado.
    Returns:
        (True, razon) si esta bloqueado.
        (False, "") si esta permitido.
    """
    import re

    # Normalizar: minúsculas y sin espacios extra para evitar ofuscaciones
    cmd_lower = command.lower().strip()
    # Colapsar espacios múltiples (evita "rm  -rf" o "rm\t-rf")
    cmd_normalized = re.sub(r'\s+', ' ', cmd_lower)

    # Verificar keywords bloqueadas como token completo
    for kw in BLOCKED_CMD_KEYWORDS:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, cmd_normalized):
            return True, f"Comando bloqueado: '{kw}' no esta permitido"

    # Verificar patrones bloqueados
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, cmd_normalized, re.IGNORECASE):
            return True, "El comando contiene un patron bloqueado"

    # Verificar ofuscaciones comunes
    # 1. Caracteres de control y null bytes
    if re.search(r'[\x00-\x08\x0e-\x1f\x7f]', command):
        return True, "Comando contiene caracteres de control no permitidos"

    # 2. Secuencias de escape que podrían ocultar comandos
    if re.search(r'\\x[0-9a-f]{2}', cmd_lower):
        return True, "Comando contiene secuencias de escape hexadecimales"

    # 3. Encoding sospechoso (base64 en bash)
    if re.search(r'base64\s+(-d|--decode)', cmd_lower):
        return True, "Decodificacion base64 no permitida en comandos"

    # 4. Subshells y command substitution
    if re.search(r'\$\(|`[^`]*`', command):
        return True, "Subshells y command substitution no permitidos"

    return False, ""
