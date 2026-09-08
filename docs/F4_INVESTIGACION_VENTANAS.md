# F4.1 — Investigación: ventanas en Wayland (sin código todavía)

Máquina: GNOME **Shell 50.1**, sesión **Wayland** (Mutter), GDM3, Ubuntu.
Alcance que hay que cubrir en F4.2: **listar ventanas, enfocar una, cerrarla.**
Mover/organizar quedan fuera.

---

## Opciones evaluadas

### A. Sin extensión — D-Bus contra `org.gnome.Shell`

| Método | Estado real (probado 2026-09-07) | Sirve |
|---|---|---|
| `org.gnome.Shell.Eval` | Devuelve `(false, '')` — **desactivado**. Solo funciona con `global.context.unsafe_mode = true` puesto a mano desde Looking Glass, por sesión, no persistente. Es un agujero de seguridad conocido. | ❌ |
| `org.gnome.Shell.Introspect.GetWindows` | La interfaz existe pero `GetWindows` → **`AccessDenied: GetWindows is not allowed`**. Restringida por un allowlist fijo de llamantes (xdg-desktop-portal-gnome). No hay forma de que JARVIS entre en esa lista. | ❌ |
| Cualquier otro método de ventanas en el bus de sesión | No existe. | ❌ |

**Conclusión: en GNOME 50 Wayland no hay ninguna vía D-Bus soportada para
listar/enfocar/cerrar ventanas sin extensión.**

### B. Sin extensión — Xwayland + `wmctrl`/`xdotool`

- Xwayland está corriendo (`:0`). Pero solo ve **apps X11**. Ahora mismo la
  única ventana de app real bajo X11 es `whatsapp-linux-desktop`; el resto
  (navegador, terminal, editor, Nautilus, apps de GNOME) son Wayland nativo
  e **invisibles** para herramientas X11.
- Cobertura: un puñado de ventanas en el mejor caso, e impredecible (depende
  de qué apps toque XWayland ese día).
- `wmctrl` y `xdotool` ni siquiera están instalados.
- **No sirve como capacidad general.** ❌

### C. Sin extensión — portales (`xdg-desktop-portal`)

- No hay portal de gestión de ventanas. Existen ScreenCast, RemoteDesktop,
  GlobalShortcuts; "listar/enfocar/cerrar ventanas" no. ❌

### D. Extensión de terceros mantenida que ya expone D-Bus

- **Window Calls** (`window-calls@domandoman.xyz`) y su fork **Window Calls
  Extended**: su único propósito es exponer en
  `org.gnome.Shell.Extensions.Windows` los métodos `List`, `Details`,
  `GetTitle`, `Activate`, `Close`, `Move`, `Resize`, `Maximize`, `Minimize`.
  Cubre exactamente F4.2 (y de sobra).
- Sigue siendo "código dentro del compositor", pero **no lo mantenemos
  nosotros**, es minúsculo, muy usado en proyectos de automatización, y su
  superficie es pequeña y auditable.
- Riesgo: Shell 50 es de agosto 2025, muy nueva. Hay que comprobar que
  existe una versión/fork cuyo `metadata.json` incluya `"50"` en
  `shell-version`, o adaptarlo (suele ser 1-2 líneas).
- Distribución: **vendored** en este repo (se copia a
  `~/.local/share/gnome-shell/extensions/`), sin depender de
  extensions.gnome.org.

### E. Extensión propia mínima por D-Bus

- ~120-200 líneas: un `Gio.DBusExportedObject` con
  `List()` (por `global.get_window_actors()` → `meta_window`),
  `Activate(id)` (`window.activate(global.get_current_time())`),
  `Close(id)` (`window.delete(...)`).
- Ventaja: la superficie es exactamente la que queremos y nada más; UUID
  nuestro; el interruptor de apagado va dentro.
- Coste: es el código de más riesgo del plan, escrito por nosotros,
  corriendo en el compositor. Más prueba manual en sesión aparte.

---

## Recomendación

**Opción D recortada, con E como plan B.**

1. Partir de **Window Calls / Window Calls Extended**, *vendored* bajo un UUID
   propio (`ventanas-jarvis@local`), **recortado** a lo que pide F4.2:
   `List`, `Details`, `Activate`, `Close`. **Quitar** `Move`, `Resize`,
   `Maximize`, `Minimize` — fuera de alcance y menos superficie de riesgo.
2. Añadir el **interruptor**: JARVIS lo desactiva por `gsettings`
   (`enabled-extensions` / `disable-user-extensions`), sin tocar
   `gnome-shell`. Documentado ya en `RECUPERACION_GNOME.md` §7.
3. Si adaptar a Shell 50 es más que trivial → caer a **E** (extensión propia
   mínima); el esfuerzo es parecido y el resultado más limpio y auditable.

**Por qué no "sin extensión":** A, B y C juntas no llegan al 20 % del
alcance y de forma frágil. En Wayland, listar/cerrar ventanas de apps
nativas **requiere** código en el compositor. La pregunta no es "extensión
sí/no" sino "cuánta y de quién": la respuesta es "la mínima, y partiendo de
una ya probada".

**Prueba (F4.2):** en un **usuario nuevo** (`sudo useradd -m jarvistest` +
sesión GNOME propia) o una sesión de repuesto, **nunca** en la sesión de
trabajo. La extensión se activa ahí, se ejercita `List/Activate/Close` con
VERIFY, y solo después se plantea instalarla en la sesión real.

---

## Datos de apoyo (verificados en vivo 2026-09-07)

- `busctl --user introspect org.gnome.Shell /org/gnome/Shell` → solo
  `.Eval` (s → bs) y `org.gnome.Shell.Extensions`. Nada de ventanas.
- `gdbus call … org.gnome.Shell.Eval 'true'` → `(false, '')`.
- `gdbus call … /org/gnome/Shell/Introspect …GetWindows` →
  `AccessDenied: GetWindows is not allowed`.
- Xwayland `:0` activo; `xlsclients` → `ibus-x11`, `whatsapp-linux-desktop`,
  `mutter-x11-frames` (solo WhatsApp es app real).
- Extensiones activas hoy: `ding`, `ubuntu-dock`, `tiling-assistant`
  (ninguna de gestión de ventanas por D-Bus).
- `~/.local/share/gnome-shell/extensions/` no existe aún.
