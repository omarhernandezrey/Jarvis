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


# Mensaje honesto por estado cuando la herramienta NO dejó `.result` ni
# `.error`. Antes, cualquiera de estos caía en "Operacion completada." — una
# acción no hecha (BLOCKED / ERROR / PLANNED) reportada como hecha. El defecto
# se invierte: lo desconocido se dice, no se asume éxito.
_ESTADO_SIN_MENSAJE = {
    "executed": ("'{tool}' dice que terminó, pero no informó de qué hizo ni "
                 "dejó nada que verificar. No puedo confirmar que saliera "
                 "bien, senor."),
    "error": "'{tool}' falló y no dio detalles, senor.",
    "blocked": "'{tool}' quedó bloqueada por seguridad, senor.",
    "planned": "'{tool}' quedó pendiente de que usted la confirme, senor.",
    "confirmed": "'{tool}' está confirmada pero todavía no se ejecutó, senor.",
    "rejected": "'{tool}' se canceló, senor.",
}


def describe_outcome(plan, *, tool: str = "la herramienta") -> str:
    """Traduce el resultado de una herramienta a texto para el usuario SIN
    inventar éxito.

    Regla: si esta capa no sabe qué pasó, lo dice; nunca rellena el hueco con
    "Operacion completada." / "Hecho, senor.". Un `.result` real (lo pone la
    herramienta) o un `.error` mandan; en su ausencia se reporta el ESTADO tal
    cual, y un estado desconocido se marca como desconocido.
    """
    if plan is None:
        return f"'{tool}' no devolvió ningún resultado; no sé si funcionó, senor."
    if isinstance(plan, str):
        return plan or f"'{tool}' no devolvió ningún mensaje, senor."

    result = getattr(plan, "result", "") or ""
    if result:
        return result

    error = getattr(plan, "error", "") or ""
    if error:
        from jarvis_local.safety.secrets import redact_secrets
        safe, _ = redact_secrets(str(error))
        return f"Error en '{tool}': {safe}"

    status = getattr(getattr(plan, "status", None), "value", None)
    if status in _ESTADO_SIN_MENSAJE:
        return _ESTADO_SIN_MENSAJE[status].format(tool=tool)
    return (f"'{tool}' terminó en un estado que no sé interpretar ({status!r}); "
            "no puedo confirmar qué pasó, senor.")


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
                if result is None:
                    # La función debía devolver un resultado y no lo hizo: no
                    # se asume éxito (era "Operacion completada." + EXECUTED).
                    plan.status = ActionStatus.ERROR
                    plan.error = "la herramienta no devolvió ningún resultado"
                    plan.result = (f"'{action_name}' no devolvió nada; no puedo "
                                   "confirmar que funcionara, senor.")
                else:
                    plan.result = str(result)
                    plan.status = ActionStatus.EXECUTED
            except Exception as e:
                plan.status = ActionStatus.ERROR
                plan.error = str(e)
                plan.result = f"Error en {action_name}: {e}"
            return plan
        return wrapper
    return decorator
