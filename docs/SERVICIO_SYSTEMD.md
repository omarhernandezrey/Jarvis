# JARVIS como servicio systemd de usuario

JARVIS arranca solo al iniciar sesión, se reinicia si se cae y se maneja con
`systemctl --user`. Reemplaza al autostart `.desktop` (que quedaba roto y no
tenía reinicio).

## Instalación / reinstalación

```bash
bash scripts/install-systemd-service.sh
```

Idempotente. Hace: para instancias manuales → desactiva
`~/.config/autostart/jarvis.desktop` (lo renombra a `.disabled`) → copia
`scripts/jarvis.service` a `~/.config/systemd/user/` → `daemon-reload` →
`enable --now`.

## Manejo

| Acción | Comando |
|---|---|
| Estado | `systemctl --user status jarvis` |
| Arrancar | `systemctl --user start jarvis` |
| Detener | `systemctl --user stop jarvis` |
| Reiniciar | `systemctl --user restart jarvis` |
| Logs en vivo | `journalctl --user -u jarvis -f` |
| Logs recientes | `journalctl --user -u jarvis -n 50 --no-pager` |
| Desactivar arranque automático | `systemctl --user disable jarvis` |
| Reactivarlo | `systemctl --user enable jarvis` |

## Qué hace la unidad (`scripts/jarvis.service`)

- **Arranque automático**: `WantedBy=graphical-session.target` — al habilitar se
  crea `~/.config/systemd/user/graphical-session.target.wants/jarvis.service`,
  así arranca cada vez que se abre la sesión gráfica.
- **En segundo plano**: es un servicio del gestor `systemd --user`, vive
  mientras dure la sesión. `PartOf=graphical-session.target` → se detiene solo
  y limpio al cerrar sesión.
- **Reinicio ante fallo**: `Restart=on-failure` + `RestartSec=5`. Se reinicia si
  el proceso muere por señal, código ≠ 0 o timeout. **Cerrar la ventana es una
  salida limpia (código 0) y NO relanza** — es deliberado. Para que relance
  también al cerrar la ventana: cambiar a `Restart=always`.
- **Antibucle**: `StartLimitBurst=5` en `StartLimitIntervalSec=120`. Si falla 5
  veces en 2 minutos, systemd se rinde y deja el servicio en `failed`
  (`systemctl --user reset-failed jarvis` para reintentar).
- **Rutas absolutas + entorno**: `WorkingDirectory=/home/omar/Documentos/Jarvis`
  (el paquete `jarvis_local` no está instalado en el venv, se importa desde el
  cwd) y `ExecStart=…/.venv/bin/python -m jarvis_local.ui.hud`. El display
  (`WAYLAND_DISPLAY`, `DISPLAY`, `XAUTHORITY`) y el bus de sesión los aporta el
  propio gestor `systemd --user`.
- **Ollama**: corre como servicio de **sistema** (`systemctl status ollama`,
  `enabled`). La unidad sólo declara `After=ollama.service` `Wants=ollama.service`
  para el orden de arranque.
- **Logs**: a journald, con `SyslogIdentifier=jarvis`.

## Sin procesos duplicados

- `~/.config/autostart/jarvis.desktop` → renombrado a `.disabled` (GNOME y el
  `systemd-xdg-autostart-generator` sólo miran `*.desktop`).
- La unidad generada `app-jarvis@autostart.service` desaparece al hacer
  `daemon-reload` sin la fuente `.desktop`.
- Único punto de arranque: `jarvis.service`.

Para volver al autostart `.desktop` (no recomendado):
`systemctl --user disable --now jarvis` y
`mv ~/.config/autostart/jarvis.desktop.disabled ~/.config/autostart/jarvis.desktop`.
