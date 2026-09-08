# RECUPERACIÓN DE GNOME — si la extensión de ventanas rompe el escritorio

**Para leer desde el móvil con la pantalla del portátil en negro.**
FASE F, segunda mitad (F4). La extensión de ventanas corre DENTRO de
`gnome-shell` (el compositor). Si falla feo, puede llevarse la sesión por
delante. Esto es el plan de vuelta.

Máquina: `omar-HP-ProBook-440-G3` · GNOME Shell **50.1** · Wayland · GDM3.
Usuario: `omar` (con contraseña de sudo). Sesión gráfica en **tty2**.
GDM en **tty1**. Libres para login de texto: **tty3, tty4, tty5, tty6**
(systemd los arranca solos al cambiar a ellos; `NAutoVTs=6` por defecto).

---

## 0. VERIFICACIÓN PREVIA — hazlo AHORA, antes de implementar nada

1. Pulsa **Ctrl + Alt + F3**.
2. Debe aparecer una pantalla de texto con:
   `omar-HP-ProBook-440-G3 login:`
3. Escribe `omar`, Enter, tu contraseña, Enter. Debe darte un prompt `$`.
4. Escribe `exit`, Enter.
5. Vuelve al escritorio con **Ctrl + Alt + F2**
   (si el escritorio estuviera en otro tty, prueba F1).

Si el paso 2 NO muestra el `login:` → **la fase se replantea. No sigas.**
Avísame y lo hablamos: sin un TTY de rescate esta extensión no se toca.

> Nota: el número de tecla = número de VT. F1 = tty1 (GDM), F2 = tty2 (tu
> sesión), F3–F6 = consolas de texto. En algunos portátiles hay que pulsar
> además **Fn**. Prueba F3, F4, F5, F6 hasta que una dé el `login:`.

---

## 1. Qué puede pasar (y qué NO)

- **Lo más probable:** GNOME captura el error de la extensión, la marca como
  "Error" y sigue funcionando. Molesto, no grave. Se desactiva y ya.
- **Malo:** la extensión bloquea o revienta el bucle principal de
  `gnome-shell` → **toda la sesión Wayland cae**. En Wayland NO se puede
  reiniciar el shell en caliente: vuelves a GDM (pantalla de login gráfica).
  Las ventanas abiertas se pierden.
- **Peor:** entras, el shell cae al instante, vuelve GDM, entras otra vez,
  vuelve a caer → **bucle**. Aquí es donde hace falta este documento.
- Lo que NO pasa: la extensión no puede dañar el disco ni el sistema. El
  daño máximo es "trabajo sin guardar de las apps abiertas" + tener que
  desactivarla desde un TTY.

---

## 2. ESCENARIO A — la pantalla está mal pero puedo cambiar de TTY

Ej.: escritorio congelado, artefactos, el ratón no responde.

1. **Ctrl + Alt + F3** → `login:` → entra como `omar`.
2. Ejecuta el **interruptor maestro** (desactiva TODAS las extensiones de
   usuario; es el más seguro):

   ```
   dconf write /org/gnome/shell/disable-user-extensions true
   ```

3. Cierra la sesión gráfica rota para que arranque una nueva:

   ```
   loginctl terminate-user omar
   ```

   (esto cierra TODO lo de `omar`, incluida esta consola; es lo que quieres.
   Si pide autenticación o falla: `sudo loginctl terminate-user omar`, o
   `sudo systemctl restart gdm`)
4. Vuelve a **Ctrl + Alt + F1**, espera a GDM, entra normal.
   El escritorio arranca **sin ninguna extensión de usuario**.
5. Cuando quieras volver a activarlas (ya sin la nuestra, ver §5):

   ```
   dconf write /org/gnome/shell/disable-user-extensions false
   ```

---

## 3. ESCENARIO B — bucle de caída (entro → cae → vuelve GDM)

1. En la pantalla de GDM, **Ctrl + Alt + F3** → `login:` → entra como `omar`.
   (No hace falta haber iniciado sesión gráfica.)
2. Interruptor maestro:

   ```
   dconf write /org/gnome/shell/disable-user-extensions true
   ```

3. Además, quita NUESTRA extensión de la lista de activas (por si el
   interruptor maestro se ignorara en tu build):

   ```
   dconf write /org/gnome/shell/enabled-extensions "@as []"
   ```

   Esto vacía la lista. Guarda antes lo que había, para restaurar:

   ```
   dconf read /org/gnome/shell/enabled-extensions
   ```

   (apúntalo en el móvil; hoy es
   `['ding@rastersoft.com', 'ubuntu-dock@ubuntu.com', 'tiling-assistant@ubuntu.com']`)
4. Y borra la carpeta de la extensión para que no pueda cargarse:

   ```
   rm -rf ~/.local/share/gnome-shell/extensions/ventanas-jarvis@local
   ```

   (el UUID exacto lo fija F4.2; será `…@local`. Si dudas:
   `ls ~/.local/share/gnome-shell/extensions/` y borra la que NO sea de
   Ubuntu/Canonical.)
5. **Ctrl + Alt + F1** → GDM → entra. Debe entrar limpio.
6. Restaura lo que quieras (§5).

---

## 4. ESCENARIO C — no responde nada, ni Ctrl+Alt+F3

Último recurso.

1. Mantén pulsado el botón de encendido ~10 s hasta que se apague.
2. Enciende. En cuanto veas el menú de GRUB (o pulsa **Esc**/**Shift** al
   arrancar para que salga), elige:
   **Advanced options for Ubuntu → … (recovery mode)**.
3. En el menú de recovery: **root — Drop to root shell prompt**.
4. Monta en escritura y desactiva las extensiones del usuario `omar`
   escribiendo su base de datos dconf a mano:

   ```
   mount -o remount,rw /
   sudo -u omar DBUS_SESSION_BUS_ADDRESS=/dev/null \
     dconf write /org/gnome/shell/disable-user-extensions true
   rm -rf /home/omar/.local/share/gnome-shell/extensions/ventanas-jarvis@local
   ```

5. `reboot`. Arranca normal, entra. Sin extensiones de usuario.

Si el paso 4 da problemas con dconf, alternativa directa sobre el fichero:

   ```
   rm -f /home/omar/.config/dconf/user
   ```

   (borra TODA la config dconf de `omar` — vuelve a valores por defecto de
   GNOME; se puede rehacer. Es seguro para el sistema.)

---

## 5. Volver a la normalidad después del susto

1. Confirma que la carpeta de la extensión NO está:

   ```
   ls ~/.local/share/gnome-shell/extensions/
   ```

2. Reactiva las extensiones legítimas de Ubuntu:

   ```
   dconf write /org/gnome/shell/disable-user-extensions false
   dconf write /org/gnome/shell/enabled-extensions \
     "['ding@rastersoft.com', 'ubuntu-dock@ubuntu.com', 'tiling-assistant@ubuntu.com']"
   ```

3. Cierra y abre sesión (o reinicia). Comprueba:

   ```
   gnome-extensions list --enabled
   ```

---

## 6. Comandos de rescate — resumen para copiar

| Qué | Comando |
|---|---|
| Desactivar TODAS las extensiones de usuario | `dconf write /org/gnome/shell/disable-user-extensions true` |
| Reactivarlas | `dconf write /org/gnome/shell/disable-user-extensions false` |
| Ver qué extensiones están activas | `dconf read /org/gnome/shell/enabled-extensions` |
| Vaciar la lista de activas | `dconf write /org/gnome/shell/enabled-extensions "@as []"` |
| Borrar la extensión de JARVIS | `rm -rf ~/.local/share/gnome-shell/extensions/ventanas-jarvis@local` |
| Cerrar la sesión gráfica rota | `loginctl terminate-user omar` |
| Ver por qué cayó el shell | `journalctl -b 0 _COMM=gnome-shell -e` |

Todos funcionan **como `omar`, sin sudo**, desde un TTY. Verificado
2026-09-07: `dconf write` y `gsettings set` sobre `disable-user-extensions`
escriben y se revierten sin privilegios; `journalctl` del shell se lee sin
sudo.

---

## 7. Interruptor desde JARVIS (lo añade F4.2)

F4.2 dará a JARVIS una herramienta para **desactivar su propia extensión sin
tocar el compositor**: escribe `disable-user-extensions`/`enabled-extensions`
por `gsettings` (no mata `gnome-shell`, no usa D-Bus del shell). Si JARVIS
responde pero el escritorio va raro, esa es la primera vía —  este documento
es para cuando JARVIS tampoco responde.
