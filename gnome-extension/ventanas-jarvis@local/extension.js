/* extension.js — ventanas-jarvis@local
 *
 * Expone por D-Bus, en la sesión, lo justo para que JARVIS pueda LISTAR,
 * ENFOCAR y CERRAR ventanas en Wayland (donde no hay API soportada para
 * hacerlo sin código en el compositor — ver docs/F4_INVESTIGACION_VENTANAS.md).
 *
 * Origen: recorte de "Window Calls" de ickyicky
 * (https://github.com/ickyicky/window-calls), GPL-2.0-or-later. De sus 20
 * métodos se conservan 4 (List, Details, Activate, Close); el resto —mover,
 * redimensionar, maximizar, minimizar, workspaces, always-on-top, fullscreen,
 * GetFrameRect/Bounds, GetTitle— se ha ELIMINADO por quedar fuera del alcance
 * de F4.2 y para reducir la superficie de código que corre en gnome-shell.
 * Cambios propios respecto al original: bug de `_get_window_by_wid` corregido
 * (usaba una variable inexistente `w`), nombre de interfaz D-Bus propio para
 * no colisionar con Window Calls si estuviera instalado, timestamps reales en
 * Activate/Close, payload de List/Details reducido a lo que JARVIS usa.
 *
 * Este archivo es GPL-2.0-or-later (ver ./LICENSE). El resto del proyecto
 * JARVIS es MIT; este es un programa aparte que se comunica solo por D-Bus
 * (separación a distancia), no se enlaza con el código de JARVIS.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

import Gio from 'gi://Gio';

const IFACE = 'org.gnome.Shell.Extensions.VentanasJarvis';
const PATH = '/org/gnome/Shell/Extensions/VentanasJarvis';

const DBUS_IFACE = `
<node>
  <interface name="${IFACE}">
    <!-- Devuelve un JSON: array de ventanas con sus propiedades básicas. -->
    <method name="List">
      <arg type="s" direction="out" name="windows_json" />
    </method>
    <!-- Devuelve un JSON: propiedades detalladas de UNA ventana. -->
    <method name="Details">
      <arg type="u" direction="in"  name="winid" />
      <arg type="s" direction="out" name="window_json" />
    </method>
    <!-- Enfoca una ventana (cambia de workspace si hace falta). -->
    <method name="Activate">
      <arg type="u" direction="in" name="winid" />
    </method>
    <!-- Pide el cierre de una ventana (delete: la app puede pedir guardar).
         NUNCA hace kill forzado. -->
    <method name="Close">
      <arg type="u" direction="in" name="winid" />
    </method>
  </interface>
</node>`;

/** Propiedades que se leen de cada Meta.Window para List(). Deliberadamente
 *  corto: lo que JARVIS necesita para mostrar, filtrar y comprobar. */
function windowSummary(w) {
  return {
    id: w.get_id(),
    wm_class: w.get_wm_class(),
    wm_class_instance: w.get_wm_class_instance(),
    pid: w.get_pid(),
    title: w.get_title(),
    window_type: w.get_window_type(),        // 0 = NORMAL
    frame_type: w.get_frame_type(),          // 0 = NORMAL (con marco)
    has_focus: w.has_focus(),
    on_current_workspace: w.located_on_workspace?.(
      global.workspace_manager.get_active_workspace()),
  };
}

export default class VentanasJarvisExtension {
  enable() {
    this._dbus = Gio.DBusExportedObject.wrapJSObject(DBUS_IFACE, this);
    this._dbus.export(Gio.DBus.session, PATH);
  }

  disable() {
    this._dbus?.flush();
    this._dbus?.unexport();
    this._dbus = null;
  }

  /** Actor de ventana por id, o excepción clara si no existe. */
  _actor(winid) {
    const actor = global.get_window_actors()
      .find(a => a.meta_window.get_id() === winid);
    if (!actor) {
      throw new Error(`ventana ${winid} no encontrada`);
    }
    return actor;
  }

  List() {
    const arr = global.get_window_actors()
      .map(a => windowSummary(a.meta_window));
    return JSON.stringify(arr);
  }

  Details(winid) {
    const w = this._actor(winid).meta_window;
    const d = {
      ...windowSummary(w),
      maximized: w.get_maximized?.() ?? 0,
      fullscreen: w.is_fullscreen?.() ?? false,
      minimized: w.minimized ?? false,
      can_close: w.can_close?.() ?? true,
    };
    return JSON.stringify(d);
  }

  Activate(winid) {
    const w = this._actor(winid).meta_window;
    const ts = global.get_current_time();
    const ws = w.get_workspace();
    if (ws) {
      ws.activate_with_focus(w, ts);
    } else {
      w.activate(ts);
    }
  }

  Close(winid) {
    const w = this._actor(winid).meta_window;
    // delete() = petición de cierre educada: la app puede mostrar
    // "¿guardar cambios?". Nunca kill().
    w.delete(global.get_current_time());
  }
}
