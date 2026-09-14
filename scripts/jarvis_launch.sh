#!/usr/bin/env bash
# Lanzador del HUD para el .desktop de escritorio (scripts/jarvis.desktop).
# Comprueba precondiciones (Ollama vivo, memoria segun
# docs/OPERACION_MEMORIA.md) antes de abrir la ventana -- ver
# jarvis_local/ui/hud/launch_check.py. Si algo falla, avisa por notificacion
# de escritorio y sale sin abrir una ventana rota.
set -euo pipefail
REPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
cd "$REPO"
exec "$REPO/.venv/bin/python" -m jarvis_local.ui.hud.launch_check
