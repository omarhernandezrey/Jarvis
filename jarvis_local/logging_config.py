"""
JARVIS Local - Configuración centralizada de logging.
Proporciona loggers consistentes para todo el proyecto.
"""
import logging
import logging.handlers
from pathlib import Path

from jarvis_local.config import BASE_DIR, get_config

# Niveles de log disponibles
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# Formato para consola (más简洁)
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S"

# Formato para archivo (más详细)
FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(force: bool = False):
    """Configura el sistema de logging global."""
    global _configured
    if _configured and not force:
        return

    cfg = get_config().get("logging", {})
    log_dir = BASE_DIR / cfg.get("dir", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Nivel global
    level_name = cfg.get("level", "info").lower()
    level = LOG_LEVELS.get(level_name, logging.INFO)

    # Logger raíz
    root_logger = logging.getLogger("jarvis")
    root_logger.setLevel(logging.DEBUG)

    # Limpiar handlers existentes
    root_logger.handlers.clear()

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, CONSOLE_DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # Handler de archivo con rotación
    actions_log = log_dir / cfg.get("actions_log", "actions.log")
    file_handler = logging.handlers.RotatingFileHandler(
        actions_log,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, FILE_DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # Handler de errores separado
    errors_log = log_dir / cfg.get("errors_log", "errors.log")
    error_handler = logging.handlers.RotatingFileHandler(
        errors_log,
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=2,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(FILE_FORMAT, FILE_DATE_FORMAT))
    root_logger.addHandler(error_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger para un módulo específico."""
    if not _configured:
        setup_logging()
    return logging.getLogger(f"jarvis.{name}")


# Inicializar logging al importar el módulo
setup_logging()
