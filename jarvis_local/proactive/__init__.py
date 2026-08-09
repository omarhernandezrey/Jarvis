"""
JARVIS Local - Sistema de Proactividad
Sugerencias automáticas basadas en contexto.
"""
from datetime import datetime

from jarvis_local.logging_config import get_logger

logger = get_logger("proactive")


class ProactiveEngine:
    """Motor de sugerencias proactivas."""

    def __init__(self):
        self.enabled = True
        self._last_suggestions = []

    def get_suggestions(self, context: dict = None) -> list[str]:
        """Genera sugerencias basadas en el contexto actual."""
        if not self.enabled:
            return []

        suggestions = []
        now = datetime.now()
        hour = now.hour

        # Sugerencias basadas en hora
        if 7 <= hour <= 9:
            suggestions.append("Buenos días. ¿Desea saber el clima antes de salir?")
        elif 12 <= hour <= 14:
            suggestions.append("Es hora del almuerzo. ¿Desea ver restaurantes cercanos?")
        elif 18 <= hour <= 20:
            suggestions.append("Buenas tardes. ¿Desea un resumen del día?")

        # Sugerencias basadas en día de la semana
        if now.weekday() == 0:  # Lunes
            suggestions.append("Feliz lunes. ¿Desea ver sus pendientes de la semana?")
        elif now.weekday() == 4:  # Viernes
            suggestions.append("Viernes. ¿Desea planificar el fin de semana?")

        self._last_suggestions = suggestions
        return suggestions

    def enable(self):
        """Activa las sugerencias proactivas."""
        self.enabled = True

    def disable(self):
        """Desactiva las sugerencias proactivas."""
        self.enabled = False


# Instancia global
_proactive_engine = None


def get_proactive_engine() -> ProactiveEngine:
    """Obtiene la instancia del motor de proactividad."""
    global _proactive_engine
    if _proactive_engine is None:
        _proactive_engine = ProactiveEngine()
    return _proactive_engine
