# Lanzador de escritorio — JARVIS sin terminal

Cómo abrir el HUD como una aplicación normal de GNOME: doble clic (o Enter)
desde el menú de aplicaciones, sin abrir una terminal. Esto es **distinto**
del autoarranque (ver más abajo): solo añade la entrada al menú, no hace que
JARVIS se lance solo en ningún momento.

## Qué se instala

| Archivo instalado | Origen en el repo |
| --- | --- |
| `~/.local/share/applications/jarvis.desktop` | `scripts/jarvis.desktop` (plantilla, con `__REPO__` sustituido por la ruta real) |
| `~/.local/share/icons/hicolor/scalable/apps/jarvis.svg` | `scripts/assets/jarvis.svg` |

El `.desktop` apunta a `scripts/jarvis_launch.sh`, que localiza el repo por su
propia ruta (`readlink -f "$0"`) y ejecuta
`.venv/bin/python -m jarvis_local.ui.hud.launch_check` — **no**
`jarvis_local.ui.hud` directamente.

### `launch_check.py`: precondiciones antes de abrir la ventana

`jarvis_local/ui/hud/launch_check.py` comprueba, antes de crear la
`QGuiApplication`:

1. **Memoria** (`jarvis_local/agent/memory_guard.py`, umbral de
   `docs/OPERACION_MEMORIA.md`): si `MemAvailable` está por debajo de
   ~800 MB (`ajustado`), no hay sitio para cargar los modelos sin empezar a
   paginar — se bloquea el arranque.
2. **Ollama vivo**: si `OllamaClient.is_running()` da `False`, se intenta
   `sudo -n systemctl start ollama.service` y, si no, `systemctl --user
   start ollama.service` (ambos con timeout, nunca cuelgan esperando una
   contraseña interactiva), reintentando la comprobación hasta 10 s.

Si cualquiera de las dos falla, se manda una notificación de escritorio
(`jarvis_local.tools.notify.send_notification`, urgencia `critical`) con el
motivo exacto y se sale con código 1 **sin** abrir Qt — nunca una ventana a
medio cargar. Verificado en vivo parando `ollama.service` a mano y
comprobando que `check_preconditions()` lo detecta, lo revive con
`systemctl start` y dejó de bloquear en 1,4 s.

El icono es el orbe del HUD (mismos colores de
`jarvis_local/ui/hud/qml/Design.qml`: `bgVoid`/`coreDeep`/`azure`/`cyan`/
`coreHot`), y `jarvis_local/ui/hud/app.py` llama a
`app.setDesktopFileName("jarvis")` — sin esto Qt usa el nombre del
ejecutable (`python3`) como identificador ante el compositor y GNOME no
puede agrupar la ventana con su icono en el dash/dock.

## Instalar y quitar

```sh
bash scripts/install_desktop_entry.sh              # instalar
bash scripts/install_desktop_entry.sh --uninstall  # quitar
```

Idempotente: correrlo varias veces no rompe nada. El `--uninstall` borra
exactamente los dos archivos de la tabla de arriba y refresca las cachés de
GNOME (`update-desktop-database`, `gtk-update-icon-cache`, best-effort si
no están instalados).

## Autoarranque: NO está activado — opciones y coste de memoria

Esto es aparte del `.desktop` del menú. **Deliberadamente no se activó**:
en esta máquina, JARVIS residente compite por RAM con Ollama, y la memoria
es el modo de fallo por defecto del equipo (`docs/OPERACION_MEMORIA.md`).

**Hallazgo durante esta tarea**: `systemctl --user is-enabled jarvis.service`
estaba en `enabled` desde una sesión anterior (1 de septiembre) —
autoarranque real, aunque `inactive` en el momento de revisarlo (no se había
disparado desde el último login gráfico). Se **desactivó**
(`systemctl --user disable jarvis.service`) para que el estado de la
máquina coincida con "sin autoarranque todavía". El archivo de la unidad
sigue instalado; reactivarlo es un solo comando (abajo).

Hay dos mecanismos ya preparados en el repo — ninguno activo hoy:

| Opción | Cómo se activa | Qué añade sobre el otro | Coste de memoria |
| --- | --- | --- | --- |
| **`~/.config/autostart/`** (spec XDG, ya existe como `jarvis.desktop.disabled` de una prueba anterior) | `mv ~/.config/autostart/jarvis.desktop.disabled ~/.config/autostart/jarvis.desktop` | Nada: lo lanza GNOME una vez al iniciar sesión, sin supervisión. Si el proceso muere, no se relanza. | Igual que el de abajo — ver nota |
| **`systemd --user`** (`scripts/jarvis.service`, instalable con `scripts/install-systemd-service.sh`) | `systemctl --user enable --now jarvis.service` | Reinicio automático si crashea (`Restart=on-failure`), logs en `journalctl --user -u jarvis`, `systemctl status/stop/restart` | Igual que el de arriba — ver nota |

**Nota sobre el coste real**: el mecanismo de arranque no cambia cuánta RAM
usa JARVIS — es el mismo proceso de todas formas. Medido en vivo (HUD recién
abierto, sin haber chateado todavía): **~248 MB de RSS** (Python +
PySide6/Qt Quick + shaders). Ese es el coste fijo de tener la ventana
abierta, autoarrancada o no.

Lo que sí cambia con el uso, autoarrancado o no (`docs/OPERACION_MEMORIA.md`):
en cuanto se manda un mensaje, Ollama carga bge-m3 (~1,3 GB) +
llama3.2:3b (~2,3 GB) y los mantiene en RAM 30 min tras cada uso
(`keep_alive: 30m`, fijado en FASE C). Eso son **~3,6 GB adicionales**,
sea cual sea el mecanismo de arranque. La diferencia real de tener
autoarranque es de **hábito de uso**, no de mecanismo: con la ventana
siempre abierta e invitando a usarla, es más probable que ese pico de
~3,6 GB se dispare varias veces por sesión en vez de solo cuando se decide
abrir JARVIS a propósito desde el menú (lo que esta tarea sí deja listo).

Para activar cualquiera de las dos más adelante:

```sh
# Opción A — autostart XDG (más simple, sin supervisión)
mv ~/.config/autostart/jarvis.desktop.disabled ~/.config/autostart/jarvis.desktop

# Opción B — systemd --user (supervisado, con logs y reinicio ante fallo)
bash scripts/install-systemd-service.sh
```

`install-systemd-service.sh` ya desactiva el autostart XDG si estuviera
activo (evita el doble arranque) — las dos opciones son mutuamente
excluyentes por diseño del propio script.
