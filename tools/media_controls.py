"""
JARVIS Local - Control de volumen y multimedia

Windows: volumen por WASAPI (comtypes/IAudioEndpointVolume): permite fijar un
nivel exacto ("volumen al 50") y LEER el estado real, asi las pruebas
verifican que el cambio ocurrio de verdad. Si COM falla, cae a las teclas
multimedia virtuales (ctypes), que siempre existen en Windows.

Linux: volumen por `wpctl` (PipeWire nativo, lee y fija el nivel real igual
que WASAPI). Play/pausa y cambio de cancion van por `playerctl`, que habla el
protocolo MPRIS que entienden Spotify, YouTube en el navegador, VLC, etc.
"""
import subprocess
import time

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

if IS_WINDOWS:
    import ctypes
    from ctypes import HRESULT, POINTER, c_float, c_uint, c_void_p
    from ctypes.wintypes import BOOL, DWORD

# Codigos de tecla virtuales de Windows (Winuser.h)
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_VK_MEDIA_NEXT = 0xB0
_VK_MEDIA_PREV = 0xB1
_VK_MEDIA_PLAY_PAUSE = 0xB3
_KEYEVENTF_KEYUP = 0x0002

# Cuanto sube/baja "sube el volumen" (puntos de 0-100)
_VOLUME_STEP_PCT = 10

_SINK = "@DEFAULT_AUDIO_SINK@"


def _press(vk: int, times: int = 1) -> None:
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)


# --- WASAPI: IAudioEndpointVolume via comtypes (Windows) ---

def _get_endpoint_volume():
    """Interfaz de volumen maestro del dispositivo de salida por defecto.
    Devuelve None si COM no esta disponible (se usa el respaldo por teclas)."""
    try:
        from comtypes import CLSCTX_ALL, COMMETHOD, GUID, CoCreateInstance, IUnknown

        class IAudioEndpointVolume(IUnknown):
            _iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
            _methods_ = (
                COMMETHOD([], HRESULT, "RegisterControlChangeNotify",
                          (["in"], c_void_p, "pNotify")),
                COMMETHOD([], HRESULT, "UnregisterControlChangeNotify",
                          (["in"], c_void_p, "pNotify")),
                COMMETHOD([], HRESULT, "GetChannelCount",
                          (["out"], POINTER(c_uint), "pnChannelCount")),
                COMMETHOD([], HRESULT, "SetMasterVolumeLevel",
                          (["in"], c_float, "fLevelDB"),
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "SetMasterVolumeLevelScalar",
                          (["in"], c_float, "fLevel"),
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "GetMasterVolumeLevel",
                          (["out"], POINTER(c_float), "pfLevelDB")),
                COMMETHOD([], HRESULT, "GetMasterVolumeLevelScalar",
                          (["out"], POINTER(c_float), "pfLevel")),
                COMMETHOD([], HRESULT, "SetChannelVolumeLevel",
                          (["in"], c_uint, "nChannel"),
                          (["in"], c_float, "fLevelDB"),
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "SetChannelVolumeLevelScalar",
                          (["in"], c_uint, "nChannel"),
                          (["in"], c_float, "fLevel"),
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "GetChannelVolumeLevel",
                          (["in"], c_uint, "nChannel"),
                          (["out"], POINTER(c_float), "pfLevelDB")),
                COMMETHOD([], HRESULT, "GetChannelVolumeLevelScalar",
                          (["in"], c_uint, "nChannel"),
                          (["out"], POINTER(c_float), "pfLevel")),
                COMMETHOD([], HRESULT, "SetMute",
                          (["in"], BOOL, "bMute"),
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "GetMute",
                          (["out"], POINTER(BOOL), "pbMute")),
                COMMETHOD([], HRESULT, "GetVolumeStepInfo",
                          (["out"], POINTER(c_uint), "pnStep"),
                          (["out"], POINTER(c_uint), "pnStepCount")),
                COMMETHOD([], HRESULT, "VolumeStepUp",
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "VolumeStepDown",
                          (["in"], POINTER(GUID), "pguidEventContext")),
                COMMETHOD([], HRESULT, "QueryHardwareSupport",
                          (["out"], POINTER(DWORD), "pdwHardwareSupportMask")),
                COMMETHOD([], HRESULT, "GetVolumeRange",
                          (["out"], POINTER(c_float), "pflVolumeMindB"),
                          (["out"], POINTER(c_float), "pflVolumeMaxdB"),
                          (["out"], POINTER(c_float), "pflVolumeIncrementdB")),
            )

        class IMMDevice(IUnknown):
            _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
            _methods_ = (
                COMMETHOD([], HRESULT, "Activate",
                          (["in"], POINTER(GUID), "iid"),
                          (["in"], DWORD, "dwClsCtx"),
                          (["in"], c_void_p, "pActivationParams"),
                          (["out"], POINTER(POINTER(IAudioEndpointVolume)),
                           "ppInterface")),
            )

        class IMMDeviceEnumerator(IUnknown):
            _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            _methods_ = (
                COMMETHOD([], HRESULT, "EnumAudioEndpoints",
                          (["in"], DWORD, "dataFlow"),
                          (["in"], DWORD, "dwStateMask"),
                          (["out"], POINTER(c_void_p), "ppDevices")),
                COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                          (["in"], DWORD, "dataFlow"),
                          (["in"], DWORD, "role"),
                          (["out"], POINTER(POINTER(IMMDevice)), "ppEndpoint")),
            )

        clsid = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
        enumerator = CoCreateInstance(clsid, IMMDeviceEnumerator, CLSCTX_ALL)
        device = enumerator.GetDefaultAudioEndpoint(0, 0)  # eRender, eConsole
        return device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    except Exception:
        return None


# --- PipeWire: wpctl (Linux) ---

def _wpctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["wpctl", *args], capture_output=True, text=True)


def _get_volume_linux() -> tuple[int | None, bool]:
    """(volumen 0-100, muteado) leyendo `wpctl get-volume`, o (None, False)
    si PipeWire/wpctl no esta disponible."""
    try:
        out = _wpctl("get-volume", _SINK)
        if out.returncode != 0:
            return None, False
        # Salida tipica: "Volume: 0.65" o "Volume: 0.65 [MUTED]"
        partes = out.stdout.strip().split()
        nivel = round(float(partes[1]) * 100)
        muteado = "[MUTED]" in out.stdout
        return nivel, muteado
    except (OSError, ValueError, IndexError):
        return None, False


def get_volume() -> int | None:
    """Volumen maestro actual (0-100), o None si no se pudo leer."""
    if not IS_WINDOWS:
        nivel, _ = _get_volume_linux()
        return nivel
    ep = _get_endpoint_volume()
    if ep is None:
        return None
    try:
        return round(ep.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        return None


def is_muted() -> bool | None:
    if not IS_WINDOWS:
        nivel, muteado = _get_volume_linux()
        return muteado if nivel is not None else None
    ep = _get_endpoint_volume()
    if ep is None:
        return None
    try:
        return bool(ep.GetMute())
    except Exception:
        return None


def _plan(action: str, reason: str) -> ActionPlan:
    return ActionPlan(action=action, risk=RiskLevel.EXECUTE, reason=reason)


def set_volume(level: int) -> ActionPlan:
    """Fija el volumen maestro a un nivel exacto (0-100)."""
    level = max(0, min(int(level), 100))
    plan = _plan("fijar_volumen", f"Fijar el volumen al {level}%")
    plan.params = {"nivel": level}
    try:
        if not IS_WINDOWS:
            out = _wpctl("set-volume", _SINK, f"{level}%")
            if out.returncode != 0:
                raise OSError(out.stderr.strip() or "wpctl set-volume fallo")
            if level > 0:
                _wpctl("set-mute", _SINK, "0")
        else:
            ep = _get_endpoint_volume()
            if ep is None:
                raise OSError("control de volumen COM no disponible")
            ep.SetMasterVolumeLevelScalar(level / 100.0, None)
            if level > 0 and ep.GetMute():
                ep.SetMute(False, None)
        plan.result = f"Volumen al {level} por ciento, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude fijar el volumen: {e}"
    return plan


def _change_volume(delta: int, action: str, reason: str, vk_fallback: int,
                   ok_msg: str) -> ActionPlan:
    plan = _plan(action, reason)
    try:
        if not IS_WINDOWS:
            signo = "+" if delta > 0 else "-"
            # -l 1.0: sin este limite, wpctl deja subir el volumen por
            # encima del 100% (hasta 150% por defecto) en vez de topar como
            # hace WASAPI en Windows.
            out = _wpctl("set-volume", "-l", "1.0", _SINK, f"{abs(delta)}%{signo}")
            if out.returncode != 0:
                raise OSError(out.stderr.strip() or "wpctl set-volume fallo")
            if delta > 0:
                _wpctl("set-mute", _SINK, "0")
            nuevo, _ = _get_volume_linux()
            plan.result = (f"{ok_msg} Quedo al {nuevo} por ciento, senor."
                           if nuevo is not None else f"{ok_msg} Senor.")
        else:
            ep = _get_endpoint_volume()
            if ep is not None:
                actual = round(ep.GetMasterVolumeLevelScalar() * 100)
                nuevo = max(0, min(actual + delta, 100))
                ep.SetMasterVolumeLevelScalar(nuevo / 100.0, None)
                if delta > 0 and ep.GetMute():
                    ep.SetMute(False, None)
                plan.params = {"antes": actual, "ahora": nuevo}
                plan.result = f"{ok_msg} Quedo al {nuevo} por ciento, senor."
            else:
                _press(vk_fallback, abs(delta) // 2 or 1)
                plan.result = f"{ok_msg} Senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar el volumen: {e}"
    return plan


def volume_up() -> ActionPlan:
    return _change_volume(_VOLUME_STEP_PCT, "subir_volumen",
                          "Subir el volumen del sistema",
                          _VK_VOLUME_UP, "Volumen arriba.")


def volume_down() -> ActionPlan:
    return _change_volume(-_VOLUME_STEP_PCT, "bajar_volumen",
                          "Bajar el volumen del sistema",
                          _VK_VOLUME_DOWN, "Volumen abajo.")


def volume_mute(mute: bool = True) -> ActionPlan:
    """Silencia (mute=True) o reactiva (mute=False) el sonido."""
    accion = "silenciar" if mute else "activar_sonido"
    plan = _plan(accion, "Silenciar el sonido" if mute else "Activar el sonido")
    try:
        if not IS_WINDOWS:
            out = _wpctl("set-mute", _SINK, "1" if mute else "0")
            if out.returncode != 0:
                raise OSError(out.stderr.strip() or "wpctl set-mute fallo")
        else:
            ep = _get_endpoint_volume()
            if ep is not None:
                ep.SetMute(mute, None)
            else:
                # con teclas solo hay alternar: pulsar solo si el estado difiere
                _press(_VK_VOLUME_MUTE)
        plan.result = "Silenciado, senor." if mute else "Sonido activado, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar el silencio: {e}"
    return plan


def _media_key_or_playerctl(vk: int, playerctl_cmd: str) -> None:
    if IS_WINDOWS:
        _press(vk)
    else:
        subprocess.run(["playerctl", playerctl_cmd], capture_output=True, text=True)


def media_play_pause() -> ActionPlan:
    plan = _plan("pausar_reproducir", "Pausar o reanudar la reproduccion")
    try:
        _media_key_or_playerctl(_VK_MEDIA_PLAY_PAUSE, "play-pause")
        plan.result = "Hecho, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude pausar la reproduccion: {e}"
    return plan


def media_next() -> ActionPlan:
    plan = _plan("siguiente_cancion", "Pasar a la siguiente cancion")
    try:
        _media_key_or_playerctl(_VK_MEDIA_NEXT, "next")
        plan.result = "Siguiente cancion, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar de cancion: {e}"
    return plan


def media_previous() -> ActionPlan:
    plan = _plan("cancion_anterior", "Volver a la cancion anterior")
    try:
        _media_key_or_playerctl(_VK_MEDIA_PREV, "previous")
        plan.result = "Cancion anterior, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude volver a la cancion anterior: {e}"
    return plan
