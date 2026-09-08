# Ventanas JARVIS — extensión de GNOME Shell

**Estado: NO INSTALADA. Pendiente de revisión (F4.2 se detiene aquí).**

Da a JARVIS lo mínimo para operar ventanas en Wayland: **listar, enfocar,
cerrar**. Nada de mover, redimensionar ni organizar.

## Por qué existe

En GNOME 50 / Wayland no hay API soportada para listar o cerrar ventanas de
apps nativas sin código dentro del compositor: `org.gnome.Shell.Eval` está
desactivado y `org.gnome.Shell.Introspect.GetWindows` da `AccessDenied`
(ver `docs/F4_INVESTIGACION_VENTANAS.md`). Una extensión es la única vía.

## Qué expone

D-Bus, bus de **sesión**:
`org.gnome.Shell` → objeto `/org/gnome/Shell/Extensions/VentanasJarvis`
→ interfaz `org.gnome.Shell.Extensions.VentanasJarvis`.

| Método | Entrada | Salida | Efecto |
|---|---|---|---|
| `List` | — | JSON: array de ventanas | Solo lectura |
| `Details(winid)` | `u` | JSON: una ventana | Solo lectura |
| `Activate(winid)` | `u` | — | Enfoca (cambia de workspace si hace falta) |
| `Close(winid)` | `u` | — | `meta_window.delete()` — cierre educado; la app puede pedir guardar. **Nunca** kill. |

`List`/`Details` devuelven: `id, wm_class, wm_class_instance, pid, title,
window_type, frame_type, has_focus, on_current_workspace` (+ en `Details`:
`maximized, fullscreen, minimized, can_close`).

## Origen y licencia

Recorte de **Window Calls** de ickyicky
(<https://github.com/ickyicky/window-calls>), **GPL-2.0-or-later**.
`extension.js` y este directorio son GPL-2.0-or-later (`./LICENSE`). El resto
del proyecto JARVIS es MIT; esta extensión es un **programa aparte** que se
comunica con JARVIS solo por D-Bus (separación a distancia), no se enlaza con
su código.

De los 20 métodos del original se conservan 4. El resto se ha **eliminado**
(no comentado): `Move`, `MoveResize`, `Resize`, `MoveToWorkspace`,
`Maximize`, `Minimize`, `Unmaximize`, `Unminimize`, `MakeFullscreen`,
`MakeAbove`, `UnmakeAbove`, `GetTitle`, `GetFrameRect`, `GetFrameBounds`.
Cambios propios: bug de `_get_window_by_wid` corregido, nombre de interfaz
propio, timestamps reales en `Activate`/`Close`, payload reducido.

## Instalar (cuando se apruebe)

```sh
cp -r "gnome-extension/ventanas-jarvis@local" \
      ~/.local/share/gnome-shell/extensions/
# cerrar sesión y volver a entrar (Wayland no recarga el shell en caliente)
gnome-extensions enable ventanas-jarvis@local
```

## Desinstalar / interruptor de emergencia

```sh
gnome-extensions disable ventanas-jarvis@local            # desde la sesión
# o, si el shell no responde, desde un TTY (Ctrl+Alt+F3):
dconf write /org/gnome/shell/disable-user-extensions true
rm -rf ~/.local/share/gnome-shell/extensions/ventanas-jarvis@local
```

Runbook completo: `docs/RECUPERACION_GNOME.md`.
