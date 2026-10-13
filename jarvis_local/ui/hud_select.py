"""Único punto de verdad para elegir entre el HUD pro y el HUD legado.

``JARVIS_HUD=pro|legacy`` (por defecto ``"pro"``) decide cuál se abre. Todo
lanzador real del HUD de escritorio debe pasar por :func:`open_desktop_hud`
en vez de importar ``jarvis_local.ui.hud.app.main`` directo — eso es
exactamente el bug que este módulo corrige: antes ``cli.py`` tenía su
propia copia de esta lógica y ``jarvis_local/ui/hud/launch_check.py`` (el
que de verdad usa el icono de escritorio, vía scripts/jarvis_launch.sh)
abría el HUD legado sin mirar ``JARVIS_HUD`` en absoluto.

Si el HUD pro falla al IMPORTARSE o al CREAR su ventana, se registra el
motivo en el log y se cae al HUD legado. Un fallo ya con la ventana en uso
(dentro del bucle de eventos) no cae a nada — no tiene sentido abrir una
segunda interfaz distinta a media sesión.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("jarvis.hud_select")


def open_desktop_hud() -> int:
    """Abre el HUD de escritorio (bloquea hasta que se cierra). Devuelve el
    código de salida del proceso."""
    which = os.environ.get("JARVIS_HUD", "pro").strip().lower()
    if which not in ("pro", "legacy"):
        logger.error(f"JARVIS_HUD={which!r} no reconocido (usa 'pro' o 'legacy'); usando 'pro'.")
        which = "pro"

    if which == "pro":
        try:
            from hud_pro.qt_compat import exec_app
            from jarvis_local.ui.hud_pro_runtime import create_window
            app, win = create_window()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"HUD pro no disponible ({e}); usando el HUD legado.")
            print(f"[HUD pro no disponible: {e}] Abriendo el HUD legado...")
        else:
            win.show()
            return int(exec_app(app))

    from jarvis_local.ui.hud import main as legacy_main
    return legacy_main()
