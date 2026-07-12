"""
JARVIS Local - Configuracion
Carga configuraciones desde config.yaml.
"""
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"

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
