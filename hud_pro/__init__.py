"""HUD de escritorio pro para JARVIS Local (Qt: PySide6 / PyQt6 / PyQt5).

Uso mínimo::

    from hud_pro import create_app, HudWindow, HudBridge
    app = create_app()
    win = HudWindow()
    bridge = HudBridge(win)          # thread-safe para STT/LLM/TTS
    win.show()
    app.exec()
"""

from .app import create_app
from .bridge import HudBridge
from .orb import OrbRenderer, OrbWidget
from .qt_compat import QT_API
from .state import OrbState, parse_state
from .window import HudWindow

__all__ = [
    "QT_API",
    "create_app",
    "HudWindow",
    "HudBridge",
    "OrbWidget",
    "OrbRenderer",
    "OrbState",
    "parse_state",
]
__version__ = "2.0.0"
