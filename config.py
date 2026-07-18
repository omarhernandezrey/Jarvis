"""
JARVIS Local - Configuracion
Carga configuraciones desde config.yaml.
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"

IS_WINDOWS = sys.platform == "win32"

# Nombre de la carpeta en Windows (%USERPROFILE%\<nombre>), clave que le pasa
# xdg-user-dir en Linux, y nombre de respaldo si xdg-user-dir no responde
# (ej. maquina sin entorno grafico). En Linux estas carpetas suelen estar en
# el idioma del sistema (~/Documentos, no ~/Documents), por eso no se puede
# hardcodear un solo nombre para los dos SO.
_USER_DIRS = {
    "documents": ("Documents", "DOCUMENTS", "Documentos"),
    "downloads": ("Downloads", "DOWNLOAD", "Descargas"),
    "desktop": ("Desktop", "DESKTOP", "Escritorio"),
    "music": ("Music", "MUSIC", "Musica"),
    "pictures": ("Pictures", "PICTURES", "Imagenes"),
    "videos": ("Videos", "VIDEOS", "Videos"),
}


def user_dir(kind: str) -> str:
    """Ruta a Documentos/Descargas/Escritorio/Musica/Imagenes/Videos del
    usuario, resuelta para el SO y el idioma real de esta maquina."""
    win_name, xdg_key, fallback = _USER_DIRS[kind]
    if IS_WINDOWS:
        return os.path.expandvars(f"%USERPROFILE%\\{win_name}")
    try:
        out = subprocess.run(["xdg-user-dir", xdg_key], capture_output=True,
                             text=True, timeout=5)
        resolved = out.stdout.strip()
        if resolved:
            return resolved
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.expanduser(f"~/{fallback}")

DEFAULT_CONFIG = {
    "ollama": {
        "host": "http://localhost:11434",
        "model": "qwen2.5:3b",
        "timeout": 600,
        "num_ctx": 4096,
    },
    "jarvis": {
        "name": "JARVIS",
        "language": "es",
        "max_history": 20,
    },
    "logging": {
        "dir": str(BASE_DIR / "logs"),
        "actions_log": "actions.log",
        "errors_log": "errors.log",
    },
}

_config_cache = None


def _load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
            _deep_merge(cfg, user_cfg)
    return cfg


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def get_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = _load_config()
    return _config_cache


def reload_config() -> dict:
    global _config_cache
    _config_cache = None
    return get_config()


# --- Secretos (API keys, credenciales) ---
# Viven en secrets.yaml, que esta en .gitignore y NUNCA se sube al repo.
SECRETS_FILE = BASE_DIR / "secrets.yaml"
_secrets_cache = None


def get_secrets() -> dict:
    """Carga secrets.yaml (API keys, correo). Devuelve {} si no existe."""
    global _secrets_cache
    if _secrets_cache is None:
        if SECRETS_FILE.exists():
            with open(SECRETS_FILE, encoding="utf-8") as f:
                _secrets_cache = yaml.safe_load(f) or {}
        else:
            _secrets_cache = {}
    return _secrets_cache


def reload_secrets() -> dict:
    global _secrets_cache
    _secrets_cache = None
    return get_secrets()
