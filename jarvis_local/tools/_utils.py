"""
JARVIS Local - Utilidades compartidas para herramientas.
Funciones de normalización, carga/guardado JSON y helpers comunes.
"""
import json
import unicodedata
from pathlib import Path


def normalize_text(text: str) -> str:
    """Normaliza texto: minúsculas y sin acentos, para comparar nombres."""
    t = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def load_json(path: Path, default=None):
    """Carga un archivo JSON, devolviendo default si no existe o es inválido."""
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return default


def save_json(path: Path, data) -> bool:
    """Guarda datos en un archivo JSON de forma atómica."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return True
    except OSError:
        return False
