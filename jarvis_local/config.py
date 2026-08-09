"""
JARVIS Local - Configuracion
Carga configuraciones desde config.yaml.
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Raiz del proyecto (la carpeta que contiene el paquete jarvis_local/).
# Ahi viven config.yaml, secrets.yaml, data/ y logs/.
BASE_DIR = Path(__file__).resolve().parent.parent
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
        return str(Path(os.environ.get("USERPROFILE", "~")) / win_name)
    try:
        out = subprocess.run(["xdg-user-dir", xdg_key], capture_output=True,
                             text=True, timeout=5)
        resolved = out.stdout.strip()
        if resolved:
            return resolved
    except (OSError, subprocess.SubprocessError):
        pass
    return str(Path.home() / fallback)

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


class ConfigManager:
    """Gestiona la configuración y secretos de forma segura."""

    _instance = None
    _config_cache = None
    _secrets_cache = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> dict:
        if ConfigManager._config_cache is None:
            ConfigManager._config_cache = self._load_config()
        return ConfigManager._config_cache

    def reload_config(self) -> dict:
        ConfigManager._config_cache = None
        return self.get_config()

    def get_secrets(self) -> dict:
        """Carga secrets.yaml (API keys, correo). Devuelve {} si no existe."""
        if ConfigManager._secrets_cache is None:
            secrets_file = BASE_DIR / "secrets.yaml"
            if secrets_file.exists():
                with open(secrets_file, encoding="utf-8") as f:
                    ConfigManager._secrets_cache = yaml.safe_load(f) or {}
            else:
                ConfigManager._secrets_cache = {}
        return ConfigManager._secrets_cache

    def reload_secrets(self) -> dict:
        ConfigManager._secrets_cache = None
        return self.get_secrets()

    @staticmethod
    def _load_config() -> dict:
        cfg = DEFAULT_CONFIG.copy()
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
                ConfigManager._deep_merge(cfg, user_cfg)
        return cfg

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value


# Funciones de compatibilidad con código existente
def get_config() -> dict:
    return ConfigManager.get_instance().get_config()


def reload_config() -> dict:
    return ConfigManager.get_instance().reload_config()


def get_secrets() -> dict:
    return ConfigManager.get_instance().get_secrets()


def reload_secrets() -> dict:
    return ConfigManager.get_instance().reload_secrets()
