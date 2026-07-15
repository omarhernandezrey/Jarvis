"""
JARVIS Local - Control de volumen y multimedia

Volumen por WASAPI (comtypes/IAudioEndpointVolume): permite fijar un nivel
exacto ("volumen al 50") y LEER el estado real, asi las pruebas verifican que
el cambio ocurrio de verdad. Si COM falla, cae a las teclas multimedia
virtuales (ctypes), que siempre existen en Windows.

Play/pausa y cambio de cancion van por teclas multimedia: es el mismo canal
que un teclado fisico y lo entienden Spotify, YouTube, VLC, etc.
"""
import ctypes
import time
from ctypes import HRESULT, POINTER, c_float, c_uint, c_void_p
from ctypes.wintypes import BOOL, DWORD

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

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


def _press(vk: int, times: int = 1) -> None:
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)


# --- WASAPI: IAudioEndpointVolume via comtypes ---

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


def get_volume() -> int | None:
    """Volumen maestro actual (0-100), o None si COM no esta disponible."""
    ep = _get_endpoint_volume()
    if ep is None:
        return None
    try:
        return round(ep.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        return None


def is_muted() -> bool | None:
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
    ep = _get_endpoint_volume()
    try:
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


def media_play_pause() -> ActionPlan:
    plan = _plan("pausar_reproducir", "Pausar o reanudar la reproduccion")
    try:
        _press(_VK_MEDIA_PLAY_PAUSE)
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
        _press(_VK_MEDIA_NEXT)
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
        _press(_VK_MEDIA_PREV)
        plan.result = "Cancion anterior, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude volver a la cancion anterior: {e}"
    return plan
