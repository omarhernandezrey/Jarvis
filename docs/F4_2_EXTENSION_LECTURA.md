# F4.2 (paso 1) — lectura y recorte de Window Calls

Antes de vendorizar nada. La extensión va a correr **dentro de gnome-shell**,
así que este código pasa a ser responsabilidad nuestra. Lo que no se entienda
o no se use, no entra.

Fuente leída: `github.com/ickyicky/window-calls` @ `c2da096` (2026-06-18),
`extension.js` completo (295 líneas) + `metadata.json` + `Readme.md`. También
`github.com/hseliger/window-calls-extended` @ `344103e` para comparar.

---

## 1. Licencia y vendorizado

- **`extension.js` lleva `SPDX-License-Identifier: GPL-2.0-or-later`** en la
  cabecera (no hay fichero `LICENSE` en el repo original, pero el SPDX es
  vinculante).
- GPL-2.0-or-later **permite** redistribuir y modificar, incluido meterlo en
  otro proyecto, **siempre que**: (a) el fichero derivado siga siendo
  GPL-2.0-or-later, (b) se conserven los avisos de copyright/licencia, (c) se
  indiquen los cambios.
- JARVIS es **MIT**. No hay conflicto: la extensión es un **programa
  independiente** que se comunica con JARVIS **solo por D-Bus** (separación a
  distancia; no hay enlazado ni import entre ambos). Se vendoriza en su propio
  directorio `gnome-extension/ventanas-jarvis@local/` con:
  - su cabecera GPL-2.0-or-later + atribución a ickyicky y lista de cambios,
  - copia completa de la GPL-2.0 en `./LICENSE`.
- El `README` del proyecto y el del directorio dejan claro el límite de
  licencia. **Conclusión: el vendorizado está permitido y hecho de forma
  limpia.**

---

## 2. Qué hace cada método del original (los 20)

| Método | Qué hace | ¿Entra? |
|---|---|---|
| `List()` | `global.get_window_actors()` → JSON con props básicas de cada ventana (`wm_class`, `pid`, `id`, `title`, tipo, geometría, workspace, foco). | **SÍ** |
| `Details(winid)` | Como `List` pero de una ventana y con más campos (`can_close`, `maximized`, `focus`, áreas de trabajo…). Varios campos (`display`, `area*`) `JSON.stringify`an a `{}` — inútiles. | **SÍ, recortado** |
| `GetTitle(winid)` | Devuelve el título como string (para evitar romper `jq` con caracteres raros del JSON). | NO — `List`/`Details` ya traen `title`; JARVIS no usa `jq`. |
| `GetFrameRect(winid)` | Geometría del marco (x,y,w,h). | NO — posicionamiento, fuera de alcance. |
| `GetFrameBounds(winid)` | Bordes del marco. El propio Readme dice que "dejó de funcionar sobre GNOME 43". | NO — roto + fuera de alcance. |
| `MoveToWorkspace(winid, n)` | Mueve la ventana a otro workspace. | NO — organizar. |
| `Move` / `Resize` / `MoveResize` | Mover y/o redimensionar. | NO — mover. |
| `MakeFullscreen(winid)` | Pone la ventana a pantalla completa. | NO. |
| `Maximize` / `Unmaximize` | (Des)maximiza. | NO — organizar. |
| `Minimize` / `Unminimize` | (Des)minimiza. | NO — organizar. |
| `Activate(winid)` | Enfoca la ventana; si está en otro workspace, `workspace.activate_with_focus`. | **SÍ** |
| `Close(winid)` | `meta_window.delete(ts)` — cierre educado (la app puede pedir guardar). `win.kill()` está comentado. | **SÍ** |
| `MakeAbove` / `UnmakeAbove` | Fijar "siempre encima". | NO — fuera de alcance. |

Alcance de F4.2 = listar, enfocar, cerrar → **List, Details, Activate, Close.**
Los otros 16 se **borran** (no se dejan comentados).

---

## 3. Lo que NO entendía / defectos encontrados

1. **Bug real en `_get_window_by_wid` (líneas 107-115 del original):**

   ```js
   _get_window_by_wid(winid) {
     let win = global.get_window_actors().find(w => w.meta_window.get_id() == winid);
     if (!w) {                       // <-- `w` no existe en este scope; la var es `win`
       throw new Error('winid not found');
     }
     return win;
   }
   ```

   En un módulo ESM (modo estricto siempre) `!w` lanza
   `ReferenceError: w is not defined` cada vez que se llama — y lo llaman
   `Details`, `GetTitle`, `Activate`, `Close`, etc. `List()` es el único que
   no pasa por ahí, por eso "listar" funciona y la gente no lo nota tanto.
   **Corregido** en nuestra versión: variable única `actor`, comprobación y
   `throw` claros (`ventana <id> no encontrada`).

2. **`Activate`/`Close` pasan `0` como timestamp.** `0` = "usa la hora
   actual", tolerado pero no correcto; con `0` la prevención de robo de foco
   de Mutter puede ignorar el `activate`. **Cambiado** a
   `global.get_current_time()`.

3. **`Details` devuelve basura parcial:** `display`, `area`, `area_all`,
   `area_cust` son `Meta.Rectangle`/objetos que `JSON.stringify` convierte en
   `{}`. No aportan nada. **Eliminados**; `Details` queda con los campos que
   JARVIS sí usa (para el texto de confirmación, el guardia de intocables y
   el VERIFY): `id, wm_class, wm_class_instance, pid, title, window_type,
   frame_type, has_focus, on_current_workspace, maximized, fullscreen,
   minimized, can_close`.

4. **`window-calls-extended`** (la variante) tiene un `List()` más limpio
   pero **no** tiene `Activate` ni `Close` — solo `List` + getters de la
   ventana enfocada. No cubre el alcance; descartada como base, aunque su
   `List` inspiró el nuestro (más plano).

Nada más quedó sin entender. El resto es `global.get_window_actors()` +
llamadas directas a la API de `Meta.Window` (`get_wm_class`, `get_pid`,
`get_id`, `has_focus`, `get_workspace`, `activate_with_focus`, `delete`),
todas documentadas y estables desde hace años.

---

## 4. Lo que queda en `gnome-extension/ventanas-jarvis@local/`

- `extension.js` — 4 métodos (`List`, `Details`, `Activate`, `Close`),
  ~130 líneas con cabecera y comentarios. Interfaz D-Bus propia
  `org.gnome.Shell.Extensions.VentanasJarvis` en
  `/org/gnome/Shell/Extensions/VentanasJarvis` (nombre propio para no
  colisionar con Window Calls si estuviera instalado).
- `metadata.json` — uuid `ventanas-jarvis@local`, `shell-version`
  `["48","49","50"]`, `session-modes: ["user"]`.
- `README.md` — qué expone, origen, límite de licencia, instalar/desinstalar,
  interruptor de emergencia.
- `LICENSE` — GPL-2.0 completa.

**No instalado. No cableado a JARVIS todavía.** Los siguientes pasos de F4.2
(usuario de pruebas, herramientas `listar_ventanas`/`enfocar_ventana`/
`cerrar_ventana` con confirmación + intocables + VERIFY) van en commits
aparte, tras tu revisión de este.
