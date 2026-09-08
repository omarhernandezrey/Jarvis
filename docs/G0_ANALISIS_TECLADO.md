# G0 — Análisis: teclado y ratón sintéticos (sin código)

FASE G. **No se implementa nada hasta que el usuario fije el alcance a partir
de esto.**

## El problema de fondo

`ydotool` inyecta eventos de entrada en `/dev/uinput`. El kernel los entrega a
**la superficie que tenga el foco de teclado en ese instante**. `ydotool` no
sabe —no *puede* saber— en qué ventana escribe.

Consecuencia: teclear texto en una terminal enfocada con `sudo` fresco ejecuta
comandos **rodeando todo lo construido**:

| Capa | Qué la rodea el teclado sintético |
|---|---|
| Guardia único de shell (`is_command_blocked`, blocklist, anti-ofuscación) | No pasa por ahí: el texto va directo al PTY de la terminal. |
| E1 — lista de intocables | No hay `wm_class` ni `pid` que comprobar: es una pulsación. |
| E2 — confirmación de lo destructivo | La pulsación no es un `ActionPlan` con riesgo. |
| D2 — auditoría append-only | Nada que registrar salvo que G lo añada explícitamente. |
| F4.2 — guardia de ventanas | El foco puede cambiar entre "compruebo" y "tecleo" (TOCTOU). |

Es un **diputado confuso**: JARVIS se vuelve una fuente de entrada con toda la
autoridad del usuario y sin traza. Y no es solo la terminal: puede teclear en
un campo de contraseña, en un compositor de correo, pulsar "Eliminar cuenta",
arrastrar al de la papelera.

---

## 1. ¿Para qué hace falta de verdad teclado sintético?

Casos concretos, y si ya están cubiertos:

| Caso | ¿Cubierto ya? | Valor real |
|---|---|---|
| "Escribe mi dirección en este formulario" (texto libre en GUI) | No | **El caso estrella — y el más peligroso.** Poco frecuente; el modo de fallo (teclear en el campo/ventana equivocada) es grave. |
| "Pulsa Enter / Escape / Tab / flechas" para navegar una app que JARVIS acaba de abrir | No | Bajo pero real: p. ej. tras `enfocar_ventana`, "guarda" → Ctrl+S. |
| "Página siguiente" en una presentación (PageDown / F5 / flechas) | No | Nicho real: presentador manos libres. Baja frecuencia. |
| "Cambia de ventana" / "trae X al frente" | **Sí** — `switch_window`, `enfocar_ventana` (F4.2) | — |
| "Cierra esta ventana" | **Sí** — `cerrar_ventana` (F4.2, con confirmación y VERIFY) | — |
| Play/pausa, siguiente, volumen, brillo | **Sí** — `playerctl`, `wpctl`, `brightnessctl` (fases anteriores) | — |
| "Dicta esto y mételo en el editor" (texto largo al foco) | No | Real, pero se sirve mejor guardando a fichero, o dejándolo en el portapapeles para que el humano pegue (un Ctrl+V suyo). |
| Rellenar un prompt de contraseña de `sudo` | — | **Nunca. Prohibido explícitamente.** |
| Juegos / apps sin API | — | Fuera del alcance de un asistente. |

**Respuesta honesta: el subconjunto útil y de bajo riesgo es pequeño.** Se
reduce a un puñado de teclas de navegación/confirmación declaradas (Enter,
Esc, Tab, flechas, PageUp/Down, F5, Ctrl+S) para pilotar una app que JARVIS
ya tiene delante. **El texto libre —donde está casi todo el valor que la
gente imagina— es exactamente lo que hay que prohibir**, y la mayor parte de
ese valor se cubre mejor con "escríbelo en un fichero" o "déjalo en el
portapapeles".

---

## 2. ¿Se puede acotar a un alcance seguro?

Sí, con capas que se acumulan. Ninguna sola basta:

1. **Allowlist de teclas/atajos, cero texto libre.** Un `enum` fijo:
   `enter, escape, tab, arriba/abajo/izquierda/derecha, re_pag, av_pag,
   inicio, fin, f5, guardar (Ctrl+S), deshacer (Ctrl+Z)`. **Ningún método
   acepta una cadena arbitraria.** Con solo teclas de navegación no se puede
   teclear `rm -rf`; `Enter` a secas en una terminal solo ejecuta lo que ya
   estuviera escrito (riesgo residual pequeño, no nulo).
2. **Negarse si la ventana enfocada es una terminal.** Ahora es viable:
   `listar_ventanas` → la que tiene `has_focus:true` → su `wm_class` contra
   una **denylist** (`org.gnome.Ptyxis` —la de este equipo—, `org.gnome.
   Terminal`, `kgx`/Console, `Alacritty`, `foot`, `xterm`, `konsole`,
   `wezterm`, `kitty`, `tilix`, `terminator`, `st`) **y** contra los
   intocables de E1, **y** contra prompts modales (`gcr-prompter`, modal de
   `org.gnome.Shell`). **Fail-closed:** si no se puede identificar la ventana
   enfocada, no se teclea.
3. **Confirmación siempre (E2)** mostrando las teclas exactas y la ventana
   enfocada exacta (título + `wm_class`), por el flujo `/confirmar`. **Re-
   comprobar el foco al ejecutar**: si la ventana enfocada cambió entre el
   plan y el `/confirmar`, abortar.
4. **Límite de velocidad**: máximo N eventos/s y un tope duro por acción.
5. **Interruptor global** (`data/teclado_activo.json`, **por defecto
   apagado**). Apagado = toda herramienta de teclado devuelve BLOCKED. El
   usuario opta explícitamente.
6. **Auditoría D2** de cada intento (permitido / bloqueado / ejecutado) con
   las teclas y la ventana objetivo.
7. **Sin ratón en v1.** Un clic sintético es peor: el objetivo es un píxel,
   ni siquiera una ventana; puede caer en "Confirmar borrado". No hay caso de
   asistente que lo necesite y que `enfocar_ventana` + atajos no cubran.

**Riesgo residual con todo esto:** la carrera de foco (una notificación roba
el foco entre la comprobación y la inyección) y el `Enter` sobre una terminal
con una línea peligrosa a medio escribir. Pequeños, no nulos.

---

## 3. El portapapeles de escritura: separarlo

**Sí, claramente.** `escribir_portapapeles(texto)` es otra clase de riesgo:

- **No ejecuta nada.** El peor caso es que el usuario pegue el texto donde no
  quería — pero **lo pega una persona**, con lo que hay un humano en el bucle
  en el momento de la acción.
- Pisa lo que el usuario tuviera copiado: molestia menor. Se mitiga
  guardando el contenido anterior para poder restaurarlo ("deshaz").
- **Salvedad Wayland:** `xclip` escribe el portapapeles **de X11** (vía
  Xwayland); apps Wayland nativas pueden no verlo, y el portapapeles necesita
  un proceso vivo que lo sirva. Para Wayland de verdad hace falta
  `wl-clipboard` (`wl-copy`), **que no está instalado** en este equipo. Es un
  prerrequisito de entorno, más ligero que el de `ydotool`.
- **Valor real y frecuente:** "copia este comando para que lo pegue", "pon mi
  correo en el portapapeles", "copia lo último que dijiste". El Ctrl+V del
  humano es la frontera de seguridad.

---

## Recomendación

1. **Portapapeles de escritura: hacerlo ya, como pieza propia y pequeña.**
   `escribir_portapapeles(texto)` — EXECUTE, VERIFY releyéndolo, guardar y
   poder restaurar el contenido anterior, confirmación cuando el texto sea
   largo o parezca comando/URL/secreto, auditoría D2, interruptor,
   prerrequisito `wl-clipboard` (instalarlo; si no, `xclip` con la limitación
   dicha). Barato, útil, bajo riesgo. Sería "FASE G, solo portapapeles".

2. **Teclado sintético: versión deliberadamente mínima, o aplazarlo.** Mi
   lectura honesta: el subconjunto seguro (allowlist de atajos, negativa si
   el foco es una terminal, confirmación + re-chequeo, límite de velocidad,
   interruptor, auditoría) **es implementable y acotable**, pero el valor es
   flaco — compra sobre todo "pulsa Enter / PageDown / Ctrl+S en una app que
   ya estoy pilotando". El texto libre que la gente quiere es justo lo
   prohibido. **Recomendación: aplazar el teclado sintético hasta que haya
   una necesidad concreta y recurrente que solo él resuelva.** Si la hay
   ahora, implementar **solo** la versión de atajos allowlistados, **nunca**
   un método `escribir(texto)`. Texto libre por teclado sintético: no, con el
   modelo de seguridad de este proyecto.

3. **Ratón: quitarlo del roadmap** (o aplazarlo indefinidamente). Los clics
   sintéticos son estrictamente peores que el teclado y no hay caso de
   asistente que `enfocar_ventana` + atajos no cubra.

---

## Prerrequisitos de entorno (cuando toque)

- **Portapapeles:** `sudo apt install wl-clipboard`. Sin grupo ni demonio.
- **Teclado (si se hace):** `sudo apt install ydotool`; arrancar `ydotoold`
  (servicio de usuario); `sudo usermod -aG input omar` (para `/dev/uinput`,
  que hoy es `crw------- root`, sin udev rule); **reiniciar Claude Code** para
  heredar el grupo (`OPERACION_MEMORIA.md` §5); comprobar `id -nG`. Si no se
  puede dejar operativo, se implementa igual y se marca NO VERIFICABLE en
  vivo desde el principio (como F2/F3).
