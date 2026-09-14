#!/usr/bin/env bash
# JARVIS Local - Instala (o desinstala) la entrada del menu de aplicaciones.
#
# Esto es DISTINTO del autoarranque (scripts/install-systemd-service.sh o
# ~/.config/autostart/): esto solo hace que "JARVIS" aparezca en el menu de
# aplicaciones de GNOME para lanzarlo a demanda, con doble clic, sin abrir
# una terminal. No arranca nada solo ni al iniciar sesion.
#
# Instala:
#   - ~/.local/share/applications/jarvis.desktop
#   - ~/.local/share/icons/hicolor/scalable/apps/jarvis.svg
#
# El lanzador (scripts/jarvis_launch.sh -> jarvis_local/ui/hud/launch_check.py)
# comprueba antes de abrir la ventana que Ollama este vivo (lo levanta si
# hace falta) y que la RAM no este ya al limite (docs/OPERACION_MEMORIA.md);
# si algo falla, avisa por notificacion de escritorio en vez de abrir una
# ventana rota.
#
# Uso:
#   bash scripts/install_desktop_entry.sh              # instalar
#   bash scripts/install_desktop_entry.sh --uninstall   # quitar
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
DESKTOP_DST="$APPS_DIR/jarvis.desktop"
ICON_DST="$ICON_DIR/jarvis.svg"

_refrescar_caches() {
  command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database "$APPS_DIR" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
  echo "== Quitando la entrada de JARVIS del menu de aplicaciones =="
  rm -fv "$DESKTOP_DST" "$ICON_DST"
  _refrescar_caches
  echo "Listo."
  exit 0
fi

echo "== 1. Ejecutable del lanzador =="
chmod +x "$REPO/scripts/jarvis_launch.sh"
echo "  $REPO/scripts/jarvis_launch.sh"

echo "== 2. Icono ($ICON_DST) =="
mkdir -p "$ICON_DIR"
cp -f "$REPO/scripts/assets/jarvis.svg" "$ICON_DST"

echo "== 3. Entrada .desktop ($DESKTOP_DST) =="
mkdir -p "$APPS_DIR"
sed "s|__REPO__|$REPO|" "$REPO/scripts/jarvis.desktop" > "$DESKTOP_DST"

echo "== 4. Refrescar cachés de GNOME (best-effort) =="
_refrescar_caches

echo
echo "Listo. Busca \"JARVIS\" en el menu de aplicaciones."
echo "Para quitarlo:  bash scripts/install_desktop_entry.sh --uninstall"
