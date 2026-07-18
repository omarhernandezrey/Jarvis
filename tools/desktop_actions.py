"""
JARVIS Local - Acciones de escritorio (Fase 4)
Cambiar ventana (Alt+Tab), capturas de pantalla y reproducir musica local.

En Linux con GNOME/Wayland no hay una forma confiable de manipular ventanas
de OTRAS apps desde afuera sin una extension de GNOME instalada (Wayland no
expone esa API por diseno, a diferencia de Windows): minimizar-todo, encajar
la ventana activa y cambiar de ventana por comando quedan sin soporte ahi, y
lo dicen con un mensaje claro en vez de fallar a medias o no hacer nada.
Captura de pantalla y musica local si funcionan igual en los dos SO.
"""
import ctypes
import os
import random
import re
import shutil
import subprocess
import time
import urllib.parse
from datetime import datetime

from jarvis_local.config import IS_WINDOWS, user_dir
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

SCREENSHOTS_DIR = (os.path.expandvars(r"%USERPROFILE%\Pictures\Capturas JARVIS")
                   if IS_WINDOWS else
                   os.path.join(user_dir("pictures"), "Capturas JARVIS"))
MUSIC_DIR = user_dir("music")
_MUSIC_EXTS = (".mp3", ".wav", ".flac", ".m4a", ".wma", ".ogg", ".aac")

_WAYLAND_UNSUPPORTED = (
    "No puedo manejar otras ventanas en este escritorio Linux, senor: "
    "Wayland no lo permite sin una extension de GNOME instalada."
)

# Codigos de tecla virtuales de Windows
_VK_MENU = 0x12   # Alt
_VK_TAB = 0x09
_VK_LWIN = 0x5B
_VK_M = 0x4D
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_RIGHT = 0x27
_VK_DOWN = 0x28
_KEYEVENTF_KEYUP = 0x0002


def _combo(*vks: int) -> None:
    """Pulsa una combinacion de teclas (modificadores primero). Windows."""
    user32 = ctypes.windll.user32
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def _no_soportado(action: str, reason: str) -> ActionPlan:
    plan = ActionPlan(action=action, risk=RiskLevel.EXECUTE, reason=reason)
    plan.status = ActionStatus.ERROR
    plan.error = "no soportado en Wayland"
    plan.result = _WAYLAND_UNSUPPORTED
    return plan


def minimize_all() -> ActionPlan:
    """Minimiza todas las ventanas (Win+M). Solo Windows."""
    if not IS_WINDOWS:
        return _no_soportado("minimizar_todo", "Minimizar todas las ventanas")
    plan = ActionPlan(action="minimizar_todo", risk=RiskLevel.EXECUTE,
                      reason="Minimizar todas las ventanas")
    try:
        _combo(_VK_LWIN, _VK_M)
        plan.result = "Todas las ventanas minimizadas, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude minimizar las ventanas: {e}"
    return plan


_SNAP_KEYS = {
    "izquierda": (_VK_LEFT, "a la izquierda"),
    "derecha": (_VK_RIGHT, "a la derecha"),
    "maximizar": (_VK_UP, "maximizada"),
    "minimizar": (_VK_DOWN, "minimizada"),
}


def snap_window(direction: str) -> ActionPlan:
    """Acomoda la ventana activa: izquierda, derecha, maximizar, minimizar
    (Win+flechas, el snap nativo de Windows)."""
    d = (direction or "").lower().strip()
    plan = ActionPlan(action="acomodar_ventana", params={"direccion": d},
                      risk=RiskLevel.EXECUTE,
                      reason="Acomodar la ventana activa")
    if d not in _SNAP_KEYS:
        plan.status = ActionStatus.ERROR
        plan.error = f"direccion invalida: {d}"
        plan.result = ("Puedo poner la ventana a la izquierda, a la derecha, "
                       "maximizarla o minimizarla, senor.")
        return plan
    if not IS_WINDOWS:
        return _no_soportado("acomodar_ventana", "Acomodar la ventana activa")
    try:
        vk, descripcion = _SNAP_KEYS[d]
        _combo(_VK_LWIN, vk)
        plan.result = f"Ventana {descripcion}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude acomodar la ventana: {e}"
    return plan


def switch_window() -> ActionPlan:
    """Cambia a la ventana anterior (Alt+Tab). Solo Windows."""
    if not IS_WINDOWS:
        return _no_soportado("cambiar_ventana", "Cambiar de ventana (Alt+Tab)")
    plan = ActionPlan(action="cambiar_ventana", risk=RiskLevel.EXECUTE,
                      reason="Cambiar de ventana (Alt+Tab)")
    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(_VK_MENU, 0, 0, 0)
        user32.keybd_event(_VK_TAB, 0, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(_VK_TAB, 0, _KEYEVENTF_KEYUP, 0)
        user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
        plan.result = "Cambiando de ventana, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar de ventana: {e}"
    return plan


def _sanitize_filename(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    return clean or "captura"


def _screenshot_via_portal(dest_path: str, timeout_s: int = 10) -> None:
    """Pide una captura al compositor via xdg-desktop-portal.

    Es la unica forma que funciono en GNOME/Mutter bajo Wayland sin mostrar
    un dialogo: `grim` esta hecho para compositores wlroots (Sway) y aqui
    responde "compositor doesn't support wlr-screencopy-unstable-v1", y
    `gnome-screenshot` (Ubuntu 26.04) intenta un fallback a X11 que revienta
    porque no hay X11 real detras, solo Xwayland. El portal si funciona
    porque es el mecanismo que GNOME expone a proposito para esto.
    """
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    unique = bus.get_unique_name().lstrip(":").replace(".", "_")
    token = f"jarvis_{os.getpid()}_{int(time.time() * 1000)}"
    handle_path = f"/org/freedesktop/portal/desktop/request/{unique}/{token}"

    loop = GLib.MainLoop()
    result: dict = {}

    def _on_response(_conn, _sender, _path, _iface, _signal, params, *_a):
        result["code"], result["results"] = params.unpack()
        loop.quit()

    def _on_timeout():
        loop.quit()
        return False

    sub_id = bus.signal_subscribe(
        "org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request",
        "Response", handle_path, None, Gio.DBusSignalFlags.NONE, _on_response)
    try:
        builder = GLib.VariantBuilder(GLib.VariantType("a{sv}"))
        builder.add_value(GLib.Variant("{sv}", ("handle_token", GLib.Variant("s", token))))
        builder.add_value(GLib.Variant("{sv}", ("interactive", GLib.Variant("b", False))))
        params = GLib.Variant.new_tuple(GLib.Variant("s", ""), builder.end())
        bus.call_sync(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot", "Screenshot", params, None,
            Gio.DBusCallFlags.NONE, timeout_s * 1000, None)
        GLib.timeout_add_seconds(timeout_s, _on_timeout)
        loop.run()
    finally:
        bus.signal_unsubscribe(sub_id)

    if not result or result.get("code") != 0:
        raise OSError("el portal de captura no respondio o la rechazo")
    uri = result["results"]["uri"]
    src = urllib.parse.unquote(uri.removeprefix("file://"))
    shutil.move(src, dest_path)


def take_screenshot(name: str = "") -> ActionPlan:
    """Captura la pantalla y la guarda con nombre personalizado en Imagenes."""
    plan = ActionPlan(action="captura_pantalla", params={"nombre": name},
                      risk=RiskLevel.EXECUTE,
                      reason="Guardar captura de pantalla en Imagenes")
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        base = _sanitize_filename(name) if name else \
            f"captura_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        path = os.path.join(SCREENSHOTS_DIR, f"{base}.png")
        if IS_WINDOWS:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(path, "PNG")
        else:
            _screenshot_via_portal(path)
        plan.paths_affected = [path]
        carpeta = "Imagenes\\Capturas JARVIS" if IS_WINDOWS else "Imagenes/Capturas JARVIS"
        plan.result = f"Captura guardada como {base}.png en {carpeta}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude tomar la captura: {e}"
    return plan


def find_music(song: str = "") -> list[str]:
    """Busca archivos de musica en la carpeta Musica."""
    found = []
    if not os.path.isdir(MUSIC_DIR):
        return found
    song_low = song.lower().strip()
    for root, _dirs, files in os.walk(MUSIC_DIR):
        for f in files:
            if f.lower().endswith(_MUSIC_EXTS) and \
                    (not song_low or song_low in f.lower()):
                found.append(os.path.join(root, f))
    return found


def play_music(song: str = "") -> ActionPlan:
    """Reproduce musica local de la carpeta Musica (aleatoria o por nombre)."""
    plan = ActionPlan(action="reproducir_musica", params={"cancion": song},
                      risk=RiskLevel.EXECUTE, reason="Reproducir musica local")
    try:
        matches = find_music(song)
        if not matches:
            plan.status = ActionStatus.ERROR
            if song:
                plan.result = (f"No encontre '{song}' en su carpeta de Musica, senor. "
                               "Puedo buscarla en YouTube si lo desea: diga "
                               f"'reproduce {song} en youtube'.")
            else:
                plan.result = ("Su carpeta de Musica esta vacia, senor. "
                               "Puedo reproducir desde YouTube: diga 'reproduce <cancion> en youtube'.")
            return plan
        elegida = random.choice(matches) if not song else matches[0]
        if IS_WINDOWS:
            os.startfile(elegida)
        else:
            subprocess.Popen(["xdg-open", elegida], shell=False)
        plan.paths_affected = [elegida]
        plan.result = f"Reproduciendo {os.path.basename(elegida)}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude reproducir musica: {e}"
    return plan
