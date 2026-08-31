"""
JARVIS Local - Spotify
Busca y reproduce canciones en la cuenta de Spotify del usuario via la API
oficial (Web API, libreria spotipy). Requiere Premium: la API de Spotify no
permite controlar la reproduccion remota con cuentas gratuitas.

Si la app oficial de Spotify no esta abierta en este PC, JARVIS la abre solo
y espera a que aparezca como dispositivo Connect antes de reproducir (ver
docs/spotify.md). Un cliente headless como spotifyd seria mas comodo pero hoy
no es viable: falla al descifrar el audio por un bug abierto en librespot
(spotifyd#1385).

Configuracion en secrets.yaml:
    spotify:
      client_id: "..."
      client_secret: "..."
      redirect_uri: "http://127.0.0.1:8888/callback"

La primera reproduccion abre el navegador para autorizar la cuenta; el token
queda cacheado en data/.spotify_cache y se refresca solo despues.
"""
import shutil
import subprocess
import time

from jarvis_local.config import BASE_DIR, get_secrets
from jarvis_local.logging_config import get_logger
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

logger = get_logger("tools.spotify")

SCOPES = "user-modify-playback-state user-read-playback-state"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
# Cuantos segundos esperar a que la app recien abierta se registre como
# dispositivo Connect. Con menos, la primera peticion del dia falla por
# pura carrera con el arranque de la app.
ESPERA_APERTURA_SEGUNDOS = 15


def has_credentials() -> bool:
    cfg = get_secrets().get("spotify", {}) or {}
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    placeholders = ("TU-CLIENT-ID", "TU-CLIENT-SECRET", "")
    return client_id not in placeholders and client_secret not in placeholders


def _client():
    """Cliente autenticado de Spotify, o None si falta spotipy o configurar."""
    if not has_credentials():
        return None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        return None
    cfg = get_secrets()["spotify"]
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    auth = SpotifyOAuth(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        redirect_uri=cfg.get("redirect_uri", DEFAULT_REDIRECT_URI),
        scope=SCOPES,
        cache_path=str(data_dir / ".spotify_cache"),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def _pc_device(devices: list[dict]) -> dict | None:
    return next((d for d in devices if d.get("type") == "Computer"), None)


def _abrir_spotify_y_esperar(sp) -> str | None:
    """Abre la app de Spotify en este PC y espera a que aparezca como
    dispositivo Connect. None si no esta instalada o no llega a tiempo."""
    spotify_bin = shutil.which("spotify")
    if not spotify_bin:
        return None
    try:
        subprocess.Popen([spotify_bin], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        logger.error(f"No se pudo abrir Spotify: {e}")
        return None

    for _ in range(ESPERA_APERTURA_SEGUNDOS):
        time.sleep(1)
        pc = _pc_device(sp.devices().get("devices", []))
        if pc:
            return pc["id"]
    return None


def _device_id(sp) -> str | None:
    """ID del dispositivo Spotify Connect a usar.

    Prefiere SIEMPRE este PC sobre el celular, un altavoz u otro aparato de
    la cuenta: JARVIS corre en este equipo, y el usuario espera que la
    musica suene aqui. Si la app no esta abierta, la abre y espera; el flag
    "is_active" de Spotify no sirve para decidir esto por si solo -- marca
    como activo el ultimo dispositivo usado, que a menudo es el celular.
    Solo si no se puede abrir la app en este PC se cae al dispositivo activo
    o, en su defecto, al primero disponible.
    """
    devices = sp.devices().get("devices", [])
    esta_pc = _pc_device(devices)
    if esta_pc:
        return esta_pc["id"]

    abierto = _abrir_spotify_y_esperar(sp)
    if abierto:
        return abierto

    if not devices:
        return None
    activo = next((d for d in devices if d.get("is_active")), None)
    return (activo or devices[0])["id"]


def play_song(query: str) -> ActionPlan:
    """Busca una cancion (o artista) por nombre y la reproduce en Spotify."""
    query = (query or "").strip()
    plan = ActionPlan(action="reproducir_spotify", params={"cancion": query},
                      risk=RiskLevel.EXECUTE, reason="Reproducir en Spotify")

    if not query:
        plan.status = ActionStatus.ERROR
        plan.result = "Que cancion desea escuchar, senor?"
        return plan

    if not has_credentials():
        plan.status = ActionStatus.ERROR
        plan.result = (
            "Spotify no esta configurado, senor. Cree una app gratis en "
            "developer.spotify.com/dashboard y agregue client_id y "
            "client_secret a secrets.yaml."
        )
        return plan

    sp = _client()
    if sp is None:
        plan.status = ActionStatus.ERROR
        plan.result = "Falta instalar la libreria de Spotify: pip install spotipy."
        return plan

    try:
        resultados = sp.search(q=query, type="track", limit=1)
        items = resultados.get("tracks", {}).get("items", [])
        if not items:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre '{query}' en Spotify, senor."
            return plan

        track = items[0]
        device_id = _device_id(sp)
        if device_id is None:
            plan.status = ActionStatus.ERROR
            plan.result = (
                "No pude abrir Spotify en este equipo, senor. Verifique que "
                "este instalado, o abralo usted mismo e intente de nuevo."
            )
            return plan

        sp.start_playback(device_id=device_id, uris=[track["uri"]])
        artistas = ", ".join(a["name"] for a in track.get("artists", []))
        nombre = track.get("name", query)
        plan.result = (f"Reproduciendo '{nombre}' de {artistas} en Spotify, senor."
                       if artistas else
                       f"Reproduciendo '{nombre}' en Spotify, senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        msg = str(e)
        plan.status = ActionStatus.ERROR
        plan.error = msg
        status = getattr(e, "http_status", None)
        if status == 403 or "premium" in msg.lower():
            plan.result = ("Spotify rechazo la reproduccion, senor. Esta "
                           "funcion requiere una cuenta Premium.")
        elif status == 404:
            plan.result = ("El dispositivo dejo de estar disponible justo "
                           "antes de reproducir, senor. Intentelo de nuevo.")
        elif status == 401:
            plan.result = ("Spotify rechazo la credencial, senor. Puede que "
                           "haya que autorizar la app de nuevo.")
        elif status == 429:
            plan.result = "Spotify esta limitando las solicitudes, senor. Espere un momento."
        else:
            plan.result = f"No pude reproducir en Spotify, senor: {msg}"
        logger.error(f"Error reproduciendo en Spotify: {e}")
    return plan
