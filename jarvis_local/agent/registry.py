"""
JARVIS Local - Registro de herramientas del AGENTE (adaptador del catálogo único).

Desde FASE B (PLAN_EJECUCION) la fuente de verdad es
`jarvis_local/tools/catalog.py`. Este módulo sólo ADAPTA los contratos
`llm_visible` a la forma `Tool` que consumen el bucle del agente
(`agent/loop.py`), el retriever y el selector, y mantiene la API histórica
(`TOOLS`, `get_tool`, `all_schemas`, `tool_names`, `execute`).

Dar de alta una herramienta = añadir un `ToolContract` en catalog.py. Aquí no
se toca nada.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from jarvis_local.safety.policy import ActionPlan, ActionStatus
from jarvis_local.tools import catalog as _catalog


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict           # JSON Schema de los argumentos
    run: Callable[..., object]  # devuelve ActionPlan o str
    needs_confirmation: bool = False
    aliases: list[str] = field(default_factory=list)

    def schema(self) -> dict:
        """Formato de tool calling de Ollama/OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _from_contract(c: _catalog.ToolContract) -> Tool:
    return Tool(
        name=c.name,
        description=c.description,
        parameters=c.parameters,
        run=c.run,
        needs_confirmation=c.needs_confirmation,
        aliases=list(c.aliases),
    )


# Los contratos que el agente ofrece al LLM, en el orden del catálogo.
TOOLS: list[Tool] = [_from_contract(c) for c in _catalog.agent_contracts()]

_BY_NAME = {t.name: t for t in TOOLS}


def get_tool(name: str) -> Tool | None:
    return _BY_NAME.get(name)


def all_schemas() -> list[dict]:
    """Esquemas JSON de todas las herramientas, para enviar al LLM."""
    return [t.schema() for t in TOOLS]


def tool_names() -> list[str]:
    return list(_BY_NAME)


def _validate_arg_type(value, expected_type: str) -> bool:
    """Valida que un valor coincida con el tipo esperado del schema."""
    if expected_type == "string":
        return isinstance(value, str)
    elif expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    elif expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected_type == "boolean":
        return isinstance(value, bool)
    elif expected_type == "array":
        return isinstance(value, list)
    elif expected_type == "object":
        return isinstance(value, dict)
    return True  # Tipo desconocido, no validar


def _coerce_arg_type(value, expected_type: str):
    """Intenta convertir un valor al tipo esperado."""
    if expected_type == "integer":
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    elif expected_type == "number":
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    elif expected_type == "boolean":
        if isinstance(value, str):
            return value.lower() in ("true", "1", "si", "yes")
        return bool(value)
    return value


def execute(name: str, arguments: dict) -> tuple[str, bool]:
    """
    Ejecuta una herramienta por nombre.

    Returns:
        (texto_resultado, requiere_confirmacion)
    """
    tool = get_tool(name)
    if tool is None:
        return f"No existe la herramienta '{name}'.", False

    # Filtrar argumentos que la herramienta no conoce (el LLM a veces inventa)
    validos = set(tool.parameters.get("properties", {}))
    args = {k: v for k, v in (arguments or {}).items() if k in validos}

    # Validar y convertir tipos de argumentos
    properties = tool.parameters.get("properties", {})
    for key, value in list(args.items()):
        if key in properties:
            expected_type = properties[key].get("type", "string")
            if not _validate_arg_type(value, expected_type):
                # Intentar convertir al tipo correcto
                coerced = _coerce_arg_type(value, expected_type)
                if _validate_arg_type(coerced, expected_type):
                    args[key] = coerced
                else:
                    return (f"El argumento '{key}' debe ser de tipo {expected_type}, "
                            f"pero recibi '{value}'. Puede corregirlo, senor?"), False

    faltantes = [r for r in tool.parameters.get("required", []) if r not in args]
    if faltantes:
        return (f"Me falta un dato para {name}: {', '.join(faltantes)}. "
                "Puede indicarmelo, senor?"), False

    try:
        result = tool.run(**args)
    except Exception as e:
        from jarvis_local.safety.logger import logger
        logger.log_error(f"tool:{name}", str(e))
        return f"No pude ejecutar '{name}': {e}", False

    # Verificación centralizada de needs_confirmation
    if tool.needs_confirmation:
        if not isinstance(result, ActionPlan):
            # La herramienta debería haber devuelto un ActionPlan para confirmación
            from jarvis_local.safety.logger import logger
            logger.log_error(f"tool:{name}",
                             f"Herramienta con needs_confirmation=True no devolvió ActionPlan: {type(result)}")
            return (f"Error interno: la herramienta '{name}' requiere confirmación "
                    "pero no generó un plan."), False
        if result.status not in (ActionStatus.PLANNED, ActionStatus.CONFIRMED):
            # El plan debería estar pendiente de confirmación
            from jarvis_local.safety.logger import logger
            logger.log_error(f"tool:{name}",
                             f"Herramienta con needs_confirmation=True devolvió status: {result.status}")

    if isinstance(result, ActionPlan):
        pendiente = result.status in (ActionStatus.PLANNED, ActionStatus.CONFIRMED)
        texto = result.result or (str(result) if pendiente else "Operacion completada.")
        if pendiente:
            texto = str(result)
        return texto, pendiente
    return str(result), False
