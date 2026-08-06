"""
JARVIS Local - Esquemas de intencion (Fase 4)
Tipos de datos para resultados del parser de intenciones.
"""
from dataclasses import dataclass, field


@dataclass
class IntentResult:
    kind: str  # "chat" | "tool_read" | "tool_execute" | "tool_plan" | "ambiguous" | "unsupported"
    tool: str | None = None
    arguments: dict = field(default_factory=dict)
    clarification: str | None = None
    reason: str | None = None
