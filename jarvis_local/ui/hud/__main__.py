"""Permite `python -m jarvis_local.ui.hud`. JARVIS_HUD=pro|legacy elige cuál
se abre (por defecto "pro") — ver jarvis_local.ui.hud_select."""
from jarvis_local.ui.hud_select import open_desktop_hud

if __name__ == "__main__":
    raise SystemExit(open_desktop_hud())
