"""
JARVIS Local - Utilidades compartidas para herramientas.
Funciones de normalización, carga/guardado JSON y helpers comunes.
"""
import json
import unicodedata
from collections.abc import Callable
from functools import wraps
from pathlib import Path

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


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


def tool_action(action_name: str, risk: RiskLevel = RiskLevel.READ):
    """Decorador que envuelve el patrón ActionPlan + try/except.

    Uso:
        @tool_action("calcular", RiskLevel.READ)
        def calculate(expression: str) -> ActionPlan:
            # ... lógica que devuelve resultado o lanza excepción
            return resultado_como_string
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> ActionPlan:
            plan = ActionPlan(
                action=action_name,
                risk=risk,
                reason=f"Ejecutar {action_name}",
            )
            try:
                result = func(*args, **kwargs)
                if isinstance(result, ActionPlan):
                    return result
                plan.result = str(result) if result is not None else "Operacion completada."
                plan.status = ActionStatus.EXECUTED
            except Exception as e:
                plan.status = ActionStatus.ERROR
                plan.error = str(e)
                plan.result = f"Error en {action_name}: {e}"
            return plan
        return wrapper
    return decorator
