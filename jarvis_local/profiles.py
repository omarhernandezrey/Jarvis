"""
JARVIS Local - Sistema de Perfiles Multi-Usuario
Permite múltiples usuarios con sus propias configuraciones.
"""
from pathlib import Path

from jarvis_local.config import BASE_DIR
from jarvis_local.logging_config import get_logger

logger = get_logger("profiles")

PROFILES_DIR = BASE_DIR / "data" / "profiles"


def get_profiles_dir() -> Path:
    """Obtiene el directorio de perfiles."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def list_profiles() -> list[str]:
    """Lista los perfiles disponibles."""
    profiles_dir = get_profiles_dir()
    return [d.name for d in profiles_dir.iterdir() if d.is_dir()]


def create_profile(name: str) -> bool:
    """Crea un nuevo perfil."""
    profiles_dir = get_profiles_dir()
    profile_dir = profiles_dir / name
    if profile_dir.exists():
        return False
    profile_dir.mkdir(parents=True)
    # Crear estructura básica
    (profile_dir / "data").mkdir()
    (profile_dir / "logs").mkdir()
    logger.info(f"Perfil creado: {name}")
    return True


def get_profile_dir(name: str) -> Path | None:
    """Obtiene el directorio de un perfil."""
    profiles_dir = get_profiles_dir()
    profile_dir = profiles_dir / name
    return profile_dir if profile_dir.exists() else None


def delete_profile(name: str) -> bool:
    """Elimina un perfil."""
    import shutil
    profiles_dir = get_profiles_dir()
    profile_dir = profiles_dir / name
    if not profile_dir.exists():
        return False
    shutil.rmtree(profile_dir)
    logger.info(f"Perfil eliminado: {name}")
    return True
