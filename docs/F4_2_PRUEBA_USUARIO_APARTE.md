# F4.2 (paso 2) — ejercitar la extensión en un usuario aparte

**Nunca en la sesión de trabajo.** La extensión se prueba en el usuario
`jarvistest`, dentro de un **`gnome-shell` anidado y sin cabeza** (headless):
un compositor de verdad, aislado, que no toca la sesión de `omar`.

Ejecutado 2026-09-08. Resultado: **los 4 métodos funcionan y el shell
sobrevive a los errores.** Detalle abajo.

---

## 1. Montaje (una sola vez) — ya hecho, aquí por si hay que rehacerlo

```sh
# 1. Crear el usuario de pruebas (cuenta local desechable)
sudo useradd -m -s /bin/bash -c "JARVIS F4 window-extension test account" jarvistest
printf 'jarvistest:pruebaF4segura99\n' | sudo chpasswd     # contraseña de usar y tirar

# 2. Linger: crea /run/user/1001 y arranca systemd --user sin login gráfico
sudo loginctl enable-linger jarvistest

# 3. Instalar la extensión en el home de jarvistest (desde la raíz del repo)
sudo -u jarvistest mkdir -p /home/jarvistest/.local/share/gnome-shell/extensions
sudo cp -r "gnome-extension/ventanas-jarvis@local" \
           /home/jarvistest/.local/share/gnome-shell/extensions/
sudo chown -R jarvistest:jarvistest /home/jarvistest/.local

# 4. Habilitarla en el dconf de jarvistest
sudo -u jarvistest env XDG_RUNTIME_DIR=/run/user/1001 \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus \
     dconf write /org/gnome/shell/enabled-extensions "['ventanas-jarvis@local']"
```

> El UID de `jarvistest` aquí es **1001**. Si en otra máquina es distinto,
> cambia `/run/user/1001` en todo lo que sigue por `/run/user/$(id -u jarvistest)`.

**Qué necesita tener dentro el usuario de pruebas:**
- la extensión en `~/.local/share/gnome-shell/extensions/ventanas-jarvis@local/`
  y activada en `enabled-extensions` (pasos 3-4);
- `linger` activo (paso 2), para tener `/run/user/1001` y un bus de sesión;
- nada más: el `gnome-shell --headless` trae su propio compositor; las apps
  de prueba (`gnome-calculator`, `gnome-text-editor`) ya están en el sistema.
- NO necesita: sesión gráfica propia, pertenecer a grupos especiales, GPU
  (el shell headless usa render por software), ni tocar GDM.

## 2. Scripts de ayuda (en el home de jarvistest)

Creados durante la prueba, quedan ahí para repetir:

| Script | Qué hace |
|---|---|
| `/home/jarvistest/run_nested.sh` | Lanza `gnome-shell --headless --virtual-monitor 1280x720 --wayland` en segundo plano; PID en `~/nested.pid`, log en `~/nested-shell.log` |
| `/home/jarvistest/launch_app.sh <cmd…>` | Lanza una app GUI **dentro** del shell anidado (`WAYLAND_DISPLAY=wayland-0`); imprime su PID |
| `/home/jarvistest/wjq.sh <acción> [id]` | Llama a la extensión por D-Bus. Acciones: `info`, `intro`, `list`, `details <id>`, `activate <id>`, `close <id>`, `log` |

## 3. Ciclo de prueba (repetible)

```sh
# arrancar el compositor anidado
sudo -u jarvistest bash /home/jarvistest/run_nested.sh
sleep 8

# estado de la extensión (debe decir: Estado: ACTIVE)
sudo -u jarvistest bash /home/jarvistest/wjq.sh info

# abrir un par de ventanas dentro del compositor anidado
sudo -u jarvistest bash /home/jarvistest/launch_app.sh gnome-calculator ; sleep 5
sudo -u jarvistest bash /home/jarvistest/launch_app.sh gnome-text-editor ; sleep 5

# LISTAR — JSON con id, wm_class, pid, title, has_focus, …
sudo -u jarvistest bash /home/jarvistest/wjq.sh list

# DETALLE de una ventana (usa un id del List)
sudo -u jarvistest bash /home/jarvistest/wjq.sh details <ID>

# ENFOCAR esa ventana; volver a List y comprobar has_focus:true en ella
sudo -u jarvistest bash /home/jarvistest/wjq.sh activate <ID>
sudo -u jarvistest bash /home/jarvistest/wjq.sh list

# CERRAR esa ventana; volver a List y comprobar que ya no está
sudo -u jarvistest bash /home/jarvistest/wjq.sh close <ID>
sudo -u jarvistest bash /home/jarvistest/wjq.sh list

# camino de error: un id que no existe -> error D-Bus limpio, sin caída
sudo -u jarvistest bash /home/jarvistest/wjq.sh details 999999
sudo -u jarvistest bash /home/jarvistest/wjq.sh close   999999

# parar el compositor anidado
sudo -u jarvistest bash -c 'kill $(cat /home/jarvistest/nested.pid)'
```

## 4. Resultado de la ejecución del 2026-09-08

`gnome-shell` anidado (mutter 50.1, render por software) arrancó bien.
Extensión `ventanas-jarvis@local`: **Estado ACTIVE**, interfaz D-Bus
`org.gnome.Shell.Extensions.VentanasJarvis` con exactamente `List`,
`Details`, `Activate`, `Close`.

| Prueba | Resultado |
|---|---|
| `List()` sin apps | `[]` |
| Abrir `gnome-calculator`, `List()` | 1 ventana: `id`, `wm_class=org.gnome.Calculator`, `pid`, `title="Calculadora"`, `has_focus:true`, `on_current_workspace:true` |
| Abrir `gnome-text-editor`, `List()` | 2 ventanas; `has_focus` pasó al editor (la nueva) |
| `Details(<calc>)` | mismos campos + `maximized:0`, `fullscreen:false`, `minimized:false`, `can_close:true` |
| `Activate(<calc>)` | `List()` después: `has_focus:true` en la calculadora, `false` en el editor — **el foco cambió de verdad** |
| `Close(<calc>)` | `List()` después: la calculadora **desaparece**; su proceso termina |
| `Close(<editor>)` | `List()` después: `[]` |
| `Details(999999)` / `Close(999999)` | `GDBus.Error…JSError.Error: ventana 999999 no encontrada` — **error limpio, el shell NO cae** (confirma el bug corregido del original) |
| Sesión de `omar` | intacta: `gnome-shell --mode=ubuntu` sigo corriendo, `enabled-extensions` sin cambios, `~/.local/share/gnome-shell/extensions/` no existe |

## 5. Limpieza

```sh
# parar procesos de jarvistest (los daemons de systemd --user reviven solos al reusar)
sudo loginctl terminate-user jarvistest

# dejar de tener daemons de jarvistest 24/7 (opcional; hay que rehacer enable-linger para volver a probar)
sudo loginctl disable-linger jarvistest

# borrar del todo la cuenta de pruebas (cuando F4.2 esté cerrado)
sudo loginctl disable-linger jarvistest
sudo userdel -r jarvistest
```

Ahora mismo: sesión de `jarvistest` terminada (0 procesos), cuenta + extensión
+ scripts conservados, `linger` activo para poder repetir sin fricción.

---

## Siguiente (paso 3, NO hecho — para tras el 2)

Cablear en JARVIS `listar_ventanas` / `enfocar_ventana` / `cerrar_ventana`
(`llm_visible=False`), contra esta misma interfaz D-Bus:
- `cerrar_ventana` = destructivo (modelo de permisos E2): confirmación
  mostrando **qué** ventana (título + wm_class + pid);
- guardia de intocables (E1): nunca cerrar/enfocar una ventana cuyo `pid` o
  `wm_class` esté en la lista;
- VERIFY real: tras `Close`, releer `List()` y confirmar que la ventana ya no
  está; tras `Activate`, confirmar `has_focus:true`;
- interruptor: `gnome-extensions disable ventanas-jarvis@local` /
  `dconf write /org/gnome/shell/disable-user-extensions true`, sin matar el
  compositor.
