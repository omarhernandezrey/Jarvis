"""Estados del asistente y su normalización (acepta español e inglés)."""

from __future__ import annotations

from enum import Enum
from typing import Union


class OrbState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def hint(self) -> str:
        return _HINTS[self]


_LABELS: dict[OrbState, str] = {
    OrbState.IDLE: "LISTO",
    OrbState.LISTENING: "ESCUCHANDO",
    OrbState.THINKING: "PROCESANDO",
    OrbState.SPEAKING: "HABLANDO",
    OrbState.ERROR: "ERROR",
}

_HINTS: dict[OrbState, str] = {
    OrbState.IDLE: "Di «Jarvis» o escribe en la consola",
    OrbState.LISTENING: "Te escucho…",
    OrbState.THINKING: "Analizando tu solicitud…",
    OrbState.SPEAKING: "Respondiendo…",
    OrbState.ERROR: "Algo salió mal. Revisa los registros.",
}

_ALIASES: dict[str, OrbState] = {
    # español
    "listo": OrbState.IDLE,
    "inactivo": OrbState.IDLE,
    "reposo": OrbState.IDLE,
    "escuchando": OrbState.LISTENING,
    "procesando": OrbState.THINKING,
    "pensando": OrbState.THINKING,
    "hablando": OrbState.SPEAKING,
    "respondiendo": OrbState.SPEAKING,
    # inglés
    "idle": OrbState.IDLE,
    "ready": OrbState.IDLE,
    "listening": OrbState.LISTENING,
    "thinking": OrbState.THINKING,
    "processing": OrbState.THINKING,
    "speaking": OrbState.SPEAKING,
    "talking": OrbState.SPEAKING,
    "error": OrbState.ERROR,
}

StateLike = Union[OrbState, str]


def parse_state(value: StateLike) -> OrbState:
    """Convierte str/OrbState a OrbState. Lanza ValueError si no es válido."""
    if isinstance(value, OrbState):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Estado inválido: {value!r}")
    key = value.strip().lower()
    try:
        return _ALIASES[key]
    except KeyError:
        raise ValueError(f"Estado desconocido: {value!r}. Válidos: {sorted(_ALIASES)}") from None
