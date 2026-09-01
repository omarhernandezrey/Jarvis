#!/bin/bash
# JARVIS Local - Instala el servicio systemd de USUARIO.
#
# Deja a JARVIS:
#   - arrancando solo al iniciar sesion (WantedBy=graphical-session.target),
#   - reiniciandose ante fallo (Restart=on-failure, RestartSec=5, antibucle),
#   - manejable con `systemctl --user {start,stop,restart,status} jarvis`,
#   - con logs en journald (`journalctl --user -u jarvis -f`).
#
# Ademas DESACTIVA el autostart .desktop para que JARVIS no se ejecute dos
# veces. Idempotente: se puede correr varias veces sin romper nada.
#
# Uso:  bash scripts/install-systemd-service.sh
set -euo pipefail

PROJ="/home/omar/Documentos/Jarvis"
UNIT_SRC="$PROJ/scripts/jarvis.service"
UNIT_DST="$HOME/.config/systemd/user/jarvis.service"
AUTOSTART="$HOME/.config/autostart/jarvis.desktop"

echo "== 1. Parar instancias lanzadas a mano =="
pkill -f "jarvis_local.ui.hud" 2>/dev/null && echo "  (procesos manuales terminados)" || echo "  (no habia)"
sleep 1

echo "== 2. Desactivar el autostart .desktop (evita doble arranque) =="
if [ -f "$AUTOSTART" ]; then
  mv -f "$AUTOSTART" "$AUTOSTART.disabled"
  echo "  $AUTOSTART -> .disabled"
else
  echo "  no hay .desktop activo (ok)"
fi

echo "== 3. Instalar la unidad de usuario =="
mkdir -p "$(dirname "$UNIT_DST")"
cp -f "$UNIT_SRC" "$UNIT_DST"
echo "  $UNIT_DST"

echo "== 4. Recargar systemd --user y habilitar =="
systemctl --user daemon-reload
systemctl --user enable jarvis.service
systemctl --user restart jarvis.service

echo "== 5. Estado =="
sleep 2
systemctl --user --no-pager status jarvis.service || true

echo
echo "Listo. Comandos:"
echo "  systemctl --user status jarvis"
echo "  systemctl --user restart jarvis"
echo "  systemctl --user stop jarvis"
echo "  journalctl --user -u jarvis -f"
