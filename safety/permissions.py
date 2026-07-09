"""
JARVIS Local - Permisos y Whitelists (Fase 2)
Define carpetas, apps y comandos permitidos. Valida rutas contra escapes.
"""
import os
from pathlib import Path
from typing import Optional, Tuple

ALLOWED_FOLDERS = [
    os.path.expandvars(r"%USERPROFILE%\Documents"),
    os.path.expandvars(r"%USERPROFILE%\Downloads"),
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
]

ALLOWED_APPS = {
    "chrome": {
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "description": "Google Chrome",
    },
    "vscode": {
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ],
        "description": "Visual Studio Code",
    },
    "explorador": {
        "paths": [r"C:\Windows\explorer.exe"],
        "description": "Explorador de archivos",
    },
    "powershell": {
        "paths": [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        ],
        "description": "PowerShell",
    },
    "terminal": {
        "paths": [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"),
            r"C:\Program Files\WindowsApps\Microsoft.WindowsTerminal*\wt.exe",
        ],
        "description": "Windows Terminal",
    },
}

BLOCKED_COMMAND_PATTERNS = [
    r"\.ps1",
    r"\.bat",
    r"\.cmd",
    r"\.exe\b",
    r"Invoke-Expression",
    r"iex\b",
    r"curl\b",
    r"irm\b",
    r"iwr\b",
    r"Start-Process",
    r"Remove-Item\s+-Force",
    r"Remove-Item\s+-Recurse",
    r"\bdel\b\s+/",
    r"\bdel\b\s+.",
    r"\brmdir\b",
    r"\brd\b\s+/",
    r"\bformat\b",
    r"\bdiskpart\b",
    r"\breg\b\s+(add|delete|import|export)",
    r"\bschtasks\b",
    r"\btaskkill\b",
    r"\bshutdown\b",
    r">\s*\S",
    r"\|\s*\S",
    r"\brm\s+-rf\b",
    r"\brm\s+-r\b",
]

BLOCKED_CMD_KEYWORDS = [
    "del", "rmdir", "rd", "format", "diskpart", "reg",
    "schtasks", "taskkill", "shutdown", "rm",
]


def is_within_allowed(path_str: str) -> Tuple[bool, Optional[Path]]:
    """
    Verifica que una ruta este dentro de las carpetas permitidas.
    Resuelve rutas reales y bloquea escapes con ../, symlinks, etc.

    Returns:
        (True, resolved_path) si esta permitido.
        (False, None) si esta fuera.
    """
    try:
        raw = Path(path_str)
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


def get_app_path(name: str) -> Optional[str]:
    """Busca el ejecutable de una app permitida. Devuelve None si no existe."""
    info = ALLOWED_APPS.get(name.lower())
    if not info:
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


def is_command_blocked(command: str) -> Tuple[bool, str]:
    """
    Verifica si un comando esta bloqueado.
    Returns:
        (True, razon) si esta bloqueado.
        (False, "") si esta permitido.
    """
    import re
    cmd_lower = command.lower()
    for kw in BLOCKED_CMD_KEYWORDS:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, cmd_lower):
            return True, f"Comando bloqueado: '{kw}' no esta permitido"
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, f"El comando contiene un patron bloqueado"
    return False, ""
