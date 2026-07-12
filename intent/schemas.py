"""
JARVIS Local - Esquemas de intencion (Fase 4)
Tipos de datos para resultados del parser de intenciones.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntentResult:
    kind: str  # "chat" | "tool_read" | "tool_execute" | "tool_plan" | "ambiguous" | "unsupported"
    tool: Optional[str] = None
    arguments: dict = field(default_factory=dict)
    clarification: Optional[str] = None
    reason: Optional[str] = None
