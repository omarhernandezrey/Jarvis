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
from jarvis_local.safety.policy import ActionPlan, RiskLevel

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


def _pactl(*args: str) -> subprocess.CompletedProcess:
    """Estrategia DISTINTA a wpctl para el reintento de VERIFY (D1): habla el
    protocolo pulse (PipeWire lo expone vía pipewire-pulse). Si no está
    instalado, lanza FileNotFoundError y el llamador lo trata como "no pude"."""
    return subprocess.run(["pactl", *args], capture_output=True, text=True)


_PA_SINK = "@DEFAULT_SINK@"


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


def _set_volume_linux_wpctl(level: int) -> str:
    out = _wpctl("set-volume", _SINK, f"{level}%")
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "wpctl set-volume fallo")
    if level > 0:
        _wpctl("set-mute", _SINK, "0")
    return "wpctl set-volume"


def _set_volume_linux_pactl(level: int) -> str:
    out = _pactl("set-sink-volume", _PA_SINK, f"{level}%")
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "pactl set-sink-volume fallo")
    if level > 0:
        _pactl("set-sink-mute", _PA_SINK, "0")
    return "pactl set-sink-volume"


def _set_volume_windows(level: int) -> str:
    ep = _get_endpoint_volume()
    if ep is None:
        raise OSError("control de volumen COM no disponible")
    ep.SetMasterVolumeLevelScalar(level / 100.0, None)
    if level > 0 and ep.GetMute():
        ep.SetMute(False, None)
    return "WASAPI SetMasterVolumeLevelScalar"


def set_volume(level: int) -> ActionPlan:
    """Fija el volumen maestro a un nivel exacto (0-100), COMPROBANDO el efecto.

    D1: tras aplicar, se lee el volumen real. Si no cuadra, se reintenta con
    una vía distinta (pactl en Linux; un handle COM nuevo en Windows) y se
    vuelve a leer. Si sigue sin cuadrar, el plan queda en ERROR: JARVIS no
    dice "volumen al 50" si el volumen no está al 50.
    """
    from jarvis_local.tools import verify as _v

    level = max(0, min(int(level), 100))
    plan = _plan("fijar_volumen", f"Fijar el volumen al {level}%")
    plan.params = {"nivel": level}

    if not IS_WINDOWS:
        estrategias = [_set_volume_linux_wpctl, _set_volume_linux_pactl]
    else:
        estrategias = [_set_volume_windows, _set_volume_windows]

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, aplicar in enumerate(estrategias):
        try:
            metodo = aplicar(level)
        except Exception as e:
            tried.append(f"{getattr(aplicar, '__name__', 'estrategia')} falló ({e})")
            outcome = _v.VerifyOutcome(False, str(e), "aplicar")
            continue
        _v.grace()
        outcome = _v.volume_settled(level)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento con vía alterna)"

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Volumen al {level} por ciento, senor.",
        fail_msg=f"No pude dejar el volumen al {level} por ciento, senor.",
    )


def _step_volume_linux_wpctl(delta: int) -> str:
    signo = "+" if delta > 0 else "-"
    # -l 1.0: sin este limite, wpctl deja subir el volumen por encima del
    # 100% (hasta 150% por defecto) en vez de topar como hace WASAPI.
    out = _wpctl("set-volume", "-l", "1.0", _SINK, f"{abs(delta)}%{signo}")
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "wpctl set-volume fallo")
    if delta > 0:
        _wpctl("set-mute", _SINK, "0")
    return "wpctl set-volume"


def _step_volume_linux_pactl(delta: int) -> str:
    signo = "+" if delta > 0 else "-"
    out = _pactl("set-sink-volume", _PA_SINK, f"{signo}{abs(delta)}%")
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "pactl set-sink-volume fallo")
    if delta > 0:
        _pactl("set-sink-mute", _PA_SINK, "0")
    return "pactl set-sink-volume"


def _step_volume_windows(delta: int) -> str:
    ep = _get_endpoint_volume()
    if ep is not None:
        actual = round(ep.GetMasterVolumeLevelScalar() * 100)
        nuevo = max(0, min(actual + delta, 100))
        ep.SetMasterVolumeLevelScalar(nuevo / 100.0, None)
        if delta > 0 and ep.GetMute():
            ep.SetMute(False, None)
        return "WASAPI SetMasterVolumeLevelScalar"
    _press(_VK_VOLUME_UP if delta > 0 else _VK_VOLUME_DOWN, abs(delta) // 2 or 1)
    return "tecla multimedia de volumen"


def _change_volume(delta: int, action: str, reason: str, ok_msg: str) -> ActionPlan:
    """Sube/baja el volumen COMPROBANDO que se movió en el sentido pedido (D1).

    Si tras el 1er intento el volumen no cambió (o cambió al revés), se
    reintenta con otra vía y se vuelve a leer. Sin verde, el plan es ERROR.
    """
    from jarvis_local.tools import verify as _v

    plan = _plan(action, reason)
    direction = 1 if delta > 0 else -1
    before = get_volume()
    plan.params = {"antes": before}

    if not IS_WINDOWS:
        estrategias = [_step_volume_linux_wpctl, _step_volume_linux_pactl]
    else:
        estrategias = [_step_volume_windows, _step_volume_windows]

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, aplicar in enumerate(estrategias):
        try:
            metodo = aplicar(delta)
        except Exception as e:
            tried.append(f"{getattr(aplicar, '__name__', 'estrategia')} falló ({e})")
            outcome = _v.VerifyOutcome(False, str(e), "aplicar")
            continue
        _v.grace()
        outcome = _v.volume_changed(before, direction=direction)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento con vía alterna)"

    after = get_volume()
    plan.params["ahora"] = after
    cola = f" Quedo al {after} por ciento, senor." if after is not None else " Senor."
    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"{ok_msg}{cola}",
        fail_msg="No pude cambiar el volumen, senor.",
    )


def volume_up() -> ActionPlan:
    return _change_volume(_VOLUME_STEP_PCT, "subir_volumen",
                          "Subir el volumen del sistema", "Volumen arriba.")


def volume_down() -> ActionPlan:
    return _change_volume(-_VOLUME_STEP_PCT, "bajar_volumen",
                          "Bajar el volumen del sistema", "Volumen abajo.")


def _mute_linux_wpctl(mute: bool) -> str:
    out = _wpctl("set-mute", _SINK, "1" if mute else "0")
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "wpctl set-mute fallo")
    return "wpctl set-mute"


def _mute_linux_pactl(mute: bool) -> str:
    out = _pactl("set-sink-mute", _PA_SINK, "1" if mute else "0")
    if out.returncode != 0:
        raise OSError(out.stderr.strip() or "pactl set-sink-mute fallo")
    return "pactl set-sink-mute"


def _mute_windows(mute: bool) -> str:
    ep = _get_endpoint_volume()
    if ep is not None:
        ep.SetMute(mute, None)
        return "WASAPI SetMute"
    # con teclas solo hay alternar: pulsar solo si el estado difiere
    if is_muted() is not mute:
        _press(_VK_VOLUME_MUTE)
    return "tecla multimedia mute"


def volume_mute(mute: bool = True) -> ActionPlan:
    """Silencia (mute=True) o reactiva (mute=False) el sonido, COMPROBÁNDOLO (D1).

    Tras aplicar, se lee el estado real de silencio. Si no coincide, se
    reintenta por otra vía y se vuelve a leer. Sin verde, ERROR.
    """
    from jarvis_local.tools import verify as _v

    accion = "silenciar" if mute else "activar_sonido"
    plan = _plan(accion, "Silenciar el sonido" if mute else "Activar el sonido")
    plan.params = {"mute": mute}

    if not IS_WINDOWS:
        estrategias = [_mute_linux_wpctl, _mute_linux_pactl]
    else:
        estrategias = [_mute_windows, _mute_windows]

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, aplicar in enumerate(estrategias):
        try:
            metodo = aplicar(mute)
        except Exception as e:
            tried.append(f"{getattr(aplicar, '__name__', 'estrategia')} falló ({e})")
            outcome = _v.VerifyOutcome(False, str(e), "aplicar")
            continue
        _v.grace()
        outcome = _v.mute_settled(mute)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento con vía alterna)"

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg="Silenciado, senor." if mute else "Sonido activado, senor.",
        fail_msg="No pude silenciar el sonido, senor." if mute
        else "No pude reactivar el sonido, senor.",
    )


def _playerctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["playerctl", *args], capture_output=True, text=True)


def _player_status() -> str | None:
    """'Playing' / 'Paused' / 'Stopped', o None si NO hay reproductor MPRIS
    activo (o no se pudo consultar)."""
    if IS_WINDOWS:
        return None
    try:
        out = _playerctl("status")
    except OSError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _player_fingerprint() -> str | None:
    """Huella de la pista actual (título + artista + trackid). Cambia al pasar
    de canción. None si no hay reproductor."""
    if IS_WINDOWS:
        return None
    try:
        out = _playerctl("metadata", "--format",
                         "{{title}}|{{artist}}|{{mpris:trackid}}")
    except OSError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


# El "pon pausa" que reproducía una canción llamada "pausa" y nadie se enteró:
# el caso que D1 tiene que cazar. Estas herramientas SIEMPRE decían "Hecho,
# senor." — incluso sin ningún reproductor (playerctl salía con código != 0 y
# se ignoraba). Ahora: si no hay reproductor -> ERROR claro. Si lo hay, se
# comprueba que el estado/la pista cambió de verdad.

def _run_media(cmd: str, kind: str, vk: int, action: str, reason: str,
               ok_msg: str, fail_no_player: str, fail_no_effect: str) -> ActionPlan:
    from jarvis_local.tools import verify as _v

    plan = _plan(action, reason)

    if IS_WINDOWS:
        try:
            _press(vk)
        except Exception as e:
            return _v.finish(plan, _v.VerifyOutcome(False, str(e), "keybd_event"),
                             ok_msg=ok_msg,
                             fail_msg="No pude enviar la tecla multimedia, senor.")
        return _v.finish(
            plan,
            _v.VerifyOutcome(None, "las teclas multimedia de Windows no exponen "
                             "estado legible para comprobar el efecto", "keybd_event"),
            ok_msg=ok_msg, fail_msg="")

    # Linux: ¿hay algún reproductor?
    antes_status = _player_status()
    if antes_status is None:
        return _v.finish(
            plan,
            _v.VerifyOutcome(False, "playerctl no encuentra ningún reproductor "
                             "MPRIS activo", "playerctl status"),
            ok_msg=ok_msg, fail_msg=fail_no_player)
    antes_fp = _player_fingerprint()

    def _verificar() -> _v.VerifyOutcome:
        if kind == "toggle":
            ahora = _player_status()
            if ahora is None:
                return _v.VerifyOutcome(None, "no pude releer el estado del reproductor",
                                        "playerctl status")
            if ahora != antes_status:
                return _v.VerifyOutcome(True, f"{antes_status} -> {ahora}",
                                        "playerctl status")
            return _v.VerifyOutcome(False, f"el estado sigue en {ahora}",
                                    "playerctl status")
        # kind == "track"
        ahora_fp = _player_fingerprint()
        if ahora_fp is None:
            return _v.VerifyOutcome(None, "no pude releer la pista", "playerctl metadata")
        if ahora_fp != antes_fp:
            return _v.VerifyOutcome(True, "la pista cambió", "playerctl metadata")
        return _v.VerifyOutcome(False, "la pista no cambió", "playerctl metadata")

    estrategias = [(cmd,), ("--all-players", cmd)]
    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, args in enumerate(estrategias):
        out = _playerctl(*args)
        if out.returncode != 0:
            tried.append(f"playerctl {' '.join(args)} rc={out.returncode} "
                         f"({out.stderr.strip()})")
            outcome = _v.VerifyOutcome(False, out.stderr.strip() or "playerctl falló",
                                       "playerctl")
            continue
        _v.grace(0.25)
        outcome = _verificar()
        tried.append(f"playerctl {' '.join(args)} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento con --all-players)"

    return _v.finish(plan, outcome, tried=tried, ok_msg=ok_msg,
                     fail_msg=fail_no_effect)


def media_play_pause() -> ActionPlan:
    return _run_media(
        "play-pause", "toggle", _VK_MEDIA_PLAY_PAUSE,
        "pausar_reproducir", "Pausar o reanudar la reproduccion",
        ok_msg="Hecho, senor.",
        fail_no_player="No hay ningún reproductor activo, senor: no hay nada que "
                       "pausar ni reanudar.",
        fail_no_effect="Le di a pausa/reanudar pero el reproductor no cambió de "
                       "estado, senor.")


def media_next() -> ActionPlan:
    return _run_media(
        "next", "track", _VK_MEDIA_NEXT,
        "siguiente_cancion", "Pasar a la siguiente cancion",
        ok_msg="Siguiente cancion, senor.",
        fail_no_player="No hay ningún reproductor activo, senor: no hay ninguna "
                       "cola de la que pasar de canción.",
        fail_no_effect="Pedí la siguiente canción pero la pista no cambió, senor.")


def media_previous() -> ActionPlan:
    return _run_media(
        "previous", "track", _VK_MEDIA_PREV,
        "cancion_anterior", "Volver a la cancion anterior",
        ok_msg="Cancion anterior, senor.",
        fail_no_player="No hay ningún reproductor activo, senor: no hay ninguna "
                       "cola a la que volver.",
        fail_no_effect="Pedí la canción anterior pero la pista no cambió, senor.")
