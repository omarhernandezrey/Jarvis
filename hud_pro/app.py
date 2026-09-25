"""Arranque de la aplicación Qt con tema oscuro, fuentes y HiDPI configurados."""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from . import theme
from .qt_compat import QtGui, QtWidgets, enable_high_dpi


def _dark_palette() -> QtGui.QPalette:
    pal = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    colors = {
        role.Window: theme.BG_0,
        role.Base: theme.BG_PANEL_SOLID,
        role.AlternateBase: theme.BG_1,
        role.WindowText: theme.TEXT,
        role.Text: theme.TEXT,
        role.Button: theme.BG_PANEL_SOLID,
        role.ButtonText: theme.TEXT,
        role.Highlight: theme.ACCENT,
        role.HighlightedText: theme.BG_0,
        role.ToolTipBase: theme.BG_PANEL_SOLID,
        role.ToolTipText: theme.TEXT,
        role.PlaceholderText: theme.TEXT_MUTED,
        role.Link: theme.ACCENT,
    }
    for r, c in colors.items():
        pal.setColor(r, QtGui.QColor(c))
    return pal


def create_app(argv: Optional[Sequence[str]] = None) -> QtWidgets.QApplication:
    """Devuelve la QApplication existente o crea una nueva configurada para el HUD."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        enable_high_dpi()
        app = QtWidgets.QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName("JARVIS")
    app.setApplicationDisplayName("J.A.R.V.I.S")
    app.setOrganizationName("JarvisLocal")
    theme.load_fonts()
    app.setFont(theme.font(theme.FONT_UI, 14))
    app.setPalette(_dark_palette())
    return app
