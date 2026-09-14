"""Arranque del HUD para el lanzador de escritorio (.desktop), sin terminal.

Antes de abrir la ventana Qt comprueba las precondiciones: que Ollama esté
vivo (si no, intenta levantarlo) y que la máquina no esté ya en el modo de
fallo por memoria que documenta `docs/OPERACION_MEMORIA.md`. Si algo falla,
se avisa por notificación de escritorio y se sale SIN abrir una ventana rota
-- nunca finge que arrancó.

Uso:  .venv/bin/python -m jarvis_local.ui.hud.launch_check
(el .desktop instalado por scripts/install_desktop_entry.sh apunta aquí a
través de scripts/jarvis_launch.sh)
"""
from __future__ import annotations

import subprocess
import sys
import time

_REINTENTOS_OLLAMA = 10
_ESPERA_REINTENTO_S = 1.0


def _ollama_vivo() -> bool:
    from jarvis_local.ollama_client.client import OllamaClient
    return OllamaClient().is_running()


def _levantar_ollama() -> bool:
    """Intenta arrancar el servicio de Ollama (unidad de sistema o de
    usuario, según cuál exista) y espera a que responda. Best-effort: cada
    intento lleva su propio timeout, nunca cuelga esperando un `sudo`
    interactivo (`-n`)."""
    intentos = (
        ["sudo", "-n", "systemctl", "start", "ollama.service"],
        ["systemctl", "--user", "start", "ollama.service"],
    )
    for cmd in intentos:
        try:
            subprocess.run(cmd, capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if _ollama_vivo():
            return True

    for _ in range(_REINTENTOS_OLLAMA):
        time.sleep(_ESPERA_REINTENTO_S)
        if _ollama_vivo():
            return True
    return False


def check_preconditions() -> str | None:
    """None si se puede arrancar. Si no, el mensaje de error a mostrar."""
    from jarvis_local.agent import memory_guard

    snap = memory_guard.snapshot()
    if snap.get("disponible") and snap.get("ajustado"):
        libre_mb = snap["mem_available_kb"] // 1024
        extra = (" y el sistema ya está en swap" if snap.get("en_swap") else "")
        return (f"RAM al límite ({libre_mb} MB disponibles{extra}): no hay "
                "sitio para cargar los modelos sin empezar a paginar. Cierre "
                "alguna aplicación antes de abrir JARVIS -- ver "
                "docs/OPERACION_MEMORIA.md.")

    if not _ollama_vivo() and not _levantar_ollama():
        return ("Ollama no responde y no pude levantarlo (ni con `sudo "
                "systemctl start ollama`, ni --user). Arránquelo a mano con "
                "`ollama serve` o revise `systemctl status ollama` y "
                "reintente.")
    return None


def main() -> int:
    error = check_preconditions()
    if error:
        from jarvis_local.tools.notify import send_notification
        send_notification(error, titulo="JARVIS no pudo arrancar", urgencia="critical")
        print(f"[jarvis-launch] {error}", file=sys.stderr)
        return 1

    from jarvis_local.ui.hud.app import main as hud_main
    return hud_main()


if __name__ == "__main__":
    raise SystemExit(main())
