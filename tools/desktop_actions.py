"""
JARVIS Local - Acciones de escritorio (Fase 4)
Cambiar ventana (Alt+Tab), capturas de pantalla y reproducir musica local.
"""
import ctypes
import os
import random
import re
import time
from datetime import datetime

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

SCREENSHOTS_DIR = os.path.expandvars(r"%USERPROFILE%\Pictures\Capturas JARVIS")
MUSIC_DIR = os.path.expandvars(r"%USERPROFILE%\Music")
_MUSIC_EXTS = (".mp3", ".wav", ".flac", ".m4a", ".wma", ".ogg", ".aac")

# Codigos de tecla virtuales de Windows
_VK_MENU = 0x12   # Alt
_VK_TAB = 0x09
_KEYEVENTF_KEYUP = 0x0002


def switch_window() -> ActionPlan:
    """Cambia a la ventana anterior (Alt+Tab)."""
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


def take_screenshot(name: str = "") -> ActionPlan:
    """Captura la pantalla y la guarda con nombre personalizado en Imagenes."""
    plan = ActionPlan(action="captura_pantalla", params={"nombre": name},
                      risk=RiskLevel.EXECUTE,
                      reason="Guardar captura de pantalla en Imagenes")
    try:
        from PIL import ImageGrab
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        base = _sanitize_filename(name) if name else \
            f"captura_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        path = os.path.join(SCREENSHOTS_DIR, f"{base}.png")
        img = ImageGrab.grab()
        img.save(path, "PNG")
        plan.paths_affected = [path]
        plan.result = f"Captura guardada como {base}.png en Imagenes\\Capturas JARVIS, senor."
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
            if f.lower().endswith(_MUSIC_EXTS):
                if not song_low or song_low in f.lower():
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
        os.startfile(elegida)
        plan.paths_affected = [elegida]
        plan.result = f"Reproduciendo {os.path.basename(elegida)}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude reproducir musica: {e}"
    return plan
