"""Motor GPU del HUD (FASE A): detección de capacidades + `HoloStage`, el
fondo renderizado en OpenGL con pipeline multipasada (bloom, destello
anamórfico, aberración cromática, tone mapping ACES + grano + viñeta).

Import perezoso a propósito: nada aquí toca OpenGL hasta que alguien pide
`detect()` o construye un `HoloStage` — así el resto de hud_pro (orbe
raster, consola, chips) sigue funcionando igual en máquinas sin GPU
utilizable, y los tests que no necesitan GL no pagan el costo de import.
"""

from __future__ import annotations

from .capabilities import GLCapabilities, detect

__all__ = ["GLCapabilities", "detect"]
