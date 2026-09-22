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
import re
import shutil
import subprocess
import time

from jarvis_local.config import BASE_DIR, get_secrets
from jarvis_local.logging_config import get_logger
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

logger = get_logger("tools.spotify")

SCOPES = ("user-modify-playback-state user-read-playback-state "
          "user-read-recently-played user-library-modify "
          "playlist-read-private playlist-read-collaborative")
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"

REAUTH_MSG = ("El acceso a su cuenta de Spotify caduco o fue revocado, senor. "
              "Vuelva a autorizar con:\n"
              "  python -m jarvis_local.cli --reauth-spotify")
# Cuantos segundos esperar a que la app recien abierta se registre como
# dispositivo Connect. Con menos, la primera peticion del dia falla por
# pura carrera con el arranque de la app.
ESPERA_APERTURA_SEGUNDOS = 15
# Candidatos a pedir en la busqueda de texto libre (ultimo recurso, ver
# _buscar_track): con varios se puede preferir una coincidencia EXACTA de
# nombre sobre lo que Spotify puso primero por relevancia.
CANDIDATOS_BUSQUEDA = 5

_TITULO_ARTISTA = re.compile(r'^(.+)\s+de\s+(.+)$', re.IGNORECASE)


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
        # NUNCA abrir el navegador por su cuenta en una peticion normal (puede
        # venir por voz, headless...). Si el token esta muerto se da un mensaje
        # accionable; la re-autorizacion se hace con `--reauth-spotify`.
        open_browser=False,
    )
    # Sin token cacheado valido NO se crea el cliente: `spotipy.Spotify`
    # llamaria a auth.get_access_token() sin codigo, que imprime la URL de
    # autorizacion y BLOQUEA en input() esperando que el usuario pegue la
    # URL de retorno -> cuelga JARVIS (visto en el banco de pruebas).
    # get_cached_token() lee/refresca el cache sin pedir nada por stdin.
    try:
        token = auth.get_cached_token()
    except Exception:  # noqa: BLE001
        token = None
    if not token:
        return None
    return spotipy.Spotify(auth_manager=auth)


_CACHE_PATH = BASE_DIR / "data" / ".spotify_cache"


def _es_error_auth(e: Exception) -> bool:
    """El fallo es de autenticacion/token, no de reproduccion."""
    if getattr(e, "http_status", None) == 401:
        return True
    n = type(e).__name__.lower()
    m = str(e).lower()
    return ("oauth" in n or "invalid_grant" in m or "refresh token" in m
            or "no token" in m or "revoked" in m)


def reauthorize() -> str:
    """Borra el token cacheado y corre el flujo OAuth (abre el navegador una
    vez). Para el comando `--reauth-spotify`, no para una peticion normal."""
    if not has_credentials():
        return ("Spotify no esta configurado, senor. Agregue client_id y "
                "client_secret a secrets.yaml.")
    try:
        import spotipy  # noqa: F401
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        return "Falta instalar la libreria de Spotify: pip install spotipy."
    _CACHE_PATH.unlink(missing_ok=True)
    cfg = get_secrets()["spotify"]
    auth = SpotifyOAuth(
        client_id=cfg["client_id"], client_secret=cfg["client_secret"],
        redirect_uri=cfg.get("redirect_uri", DEFAULT_REDIRECT_URI),
        scope=SCOPES, cache_path=str(_CACHE_PATH), open_browser=True,
    )
    auth.get_access_token(as_dict=False)
    return "Spotify autorizado, senor. Ya puedo reproducir su musica."


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


_PALABRAS_VACIAS_MIN = 2  # ignora "el", "la", "de", "yo"... al comparar titulos


def _resolver_artista(sp, nombre: str) -> dict | None:
    """Busca un artista por nombre libre. Tolera tildes/mayusculas distintas
    (la busqueda de artista de Spotify es mucho mas permisiva que su filtro
    de campo `artist:`, que exige coincidencia casi exacta con tildes)."""
    items = sp.search(q=nombre, type="artist", limit=1).get("artists", {}).get("items", [])
    return items[0] if items else None


def _mejor_por_palabras(titulo: str, tracks: list[dict]) -> dict | None:
    """De una lista de canciones candidatas, la que mas se parece al titulo
    pedido por solapamiento de palabras (Jaccard: interseccion / union).
    None si ninguna comparte nada -- mejor no inventar una coincidencia sin
    ninguna relacion.

    Existe porque los pedidos de cancion suelen ser una PARAFRASIS de la
    letra, no el titulo exacto ("yo soy el rey" por "El Rey"): exigir texto
    exacto (via `track:"..."`) falla justo en el caso mas comun.

    Se usa la proporcion (Jaccard), no el conteo simple de palabras en
    comun: contar a secas empataba "El Rey" (comparte "rey") con "Soy
    Mexico" (comparte "soy") en 1 palabra cada una, y el desempate quedaba
    a merced del orden de iteracion de un set (no determinista entre
    ejecuciones). El titulo mas CORTO y mas parecido en proporcion al
    pedido gana ese empate porque "el rey" es una porcion mayor de "yo soy
    el rey" que "soy mexico".
    """
    palabras_pedido = set(titulo.lower().split())
    if not palabras_pedido or not tracks:
        return None
    mejor, mejor_puntaje = None, 0.0
    for t in tracks:
        palabras_track = set(t.get("name", "").lower().split())
        interseccion = palabras_pedido & palabras_track
        if not interseccion:
            continue
        puntaje = len(interseccion) / len(palabras_pedido | palabras_track)
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = t, puntaje
    return mejor


# Cuantas palabras del titulo probar, combinadas con el filtro de artista.
# "artist-top-tracks" esta bloqueado para apps nuevas (403, restriccion de
# Spotify) y `artist:"X" <varias palabras>` falla si el titulo es una
# parafrasis de la letra en vez del titulo exacto (measured: "artist:X yo
# soy el rey" -> 0 resultados). Probar UNA palabra significativa a la vez
# si funciona, y varias palabras cortas ("yo", "soy", "el") no distinguen
# nada -- se descartan.
_PALABRAS_A_PROBAR = 3


def _buscar_por_artista(sp, query: str) -> dict | None:
    """Si el usuario dijo '<cancion> de <artista>' (patron muy comun en
    espanol): resuelve el artista primero (tolera tildes) y prueba, una por
    una, las palabras mas significativas del titulo combinadas con el
    filtro exacto de artista -- acumula candidatos y se queda con el que
    mas palabras comparte con lo pedido. None si el patron no aplica, el
    artista no existe en Spotify, o ninguna palabra encontro nada.
    """
    m = _TITULO_ARTISTA.match(query.strip())
    if not m:
        return None
    titulo, nombre_artista = m.group(1).strip(), m.group(2).strip()
    if not titulo or not nombre_artista:
        return None
    artista = _resolver_artista(sp, nombre_artista)
    if artista is None:
        return None
    nombre_canonico = artista["name"].replace('"', "")

    palabras = sorted({w for w in titulo.lower().split()
                       if len(w) > _PALABRAS_VACIAS_MIN},
                      key=len, reverse=True)
    candidatos: dict[str, dict] = {}
    for palabra in palabras[:_PALABRAS_A_PROBAR]:
        items = sp.search(q=f'artist:"{nombre_canonico}" {palabra}',
                          type="track", limit=5).get("tracks", {}).get("items", [])
        for it in items:
            candidatos[it["uri"]] = it
    return _mejor_por_palabras(titulo, list(candidatos.values()))


def _buscar_track(sp, query: str) -> dict | None:
    """Busca una cancion. Si el patron '<cancion> de <artista>' aplica y
    encuentra algo entre lo mas popular de ese artista, se usa eso (mucho
    mas preciso); si no, se cae a la busqueda de texto libre de Spotify.
    """
    track = _buscar_por_artista(sp, query)
    if track:
        return track
    items = sp.search(q=query, type="track",
                      limit=CANDIDATOS_BUSQUEDA).get("tracks", {}).get("items", [])
    if not items:
        return None
    # El ranking de relevancia de Spotify a veces pone una version poco
    # conocida antes que la cancion exacta que se pidio (ver "I Wanna Be
    # Yours" -> "I WANNA BE YOUR SLAVE" de Maneskin). Sin "popularity"
    # disponible, una coincidencia EXACTA de nombre (sin importar mayusculas)
    # es la mejor senal barata que queda para desempatar a favor de la
    # version que el usuario realmente pidio.
    exacta = next((t for t in items
                   if t.get("name", "").lower() == query.strip().lower()), None)
    return exacta or items[0]


def _cliente_o_error(plan: ActionPlan):
    """Cliente autenticado de Spotify, o None tras dejar `plan` en ERROR con
    el mensaje accionable correspondiente (sin credenciales, falta spotipy,
    o sin token cacheado valido -- pide reautorizar). Extraido para no
    repetir este chequeo en cada funcion de tools/spotify.py."""
    if not has_credentials():
        plan.status = ActionStatus.ERROR
        plan.result = (
            "Spotify no esta configurado, senor. Cree una app gratis en "
            "developer.spotify.com/dashboard y agregue client_id y "
            "client_secret a secrets.yaml."
        )
        return None

    sp = _client()
    if sp is None:
        plan.status = ActionStatus.ERROR
        try:
            import spotipy  # noqa: F401
        except ImportError:
            plan.result = "Falta instalar la libreria de Spotify: pip install spotipy."
        else:
            # spotipy esta, pero no hay token cacheado valido: reautorizar.
            _CACHE_PATH.unlink(missing_ok=True)
            plan.result = REAUTH_MSG
        return None
    return sp


def _manejar_error_spotify(e: Exception, plan: ActionPlan, *,
                            msg_403: str | None = None,
                            msg_404: str | None = None,
                            msg_generic: str | None = None) -> None:
    """Traduce una excepcion de spotipy/la Web API a un ActionPlan.ERROR con
    mensaje accionable, mutando `plan` in-place. Mismo contrato de errores
    HTTP para las ~18 funciones de este modulo (auth/403/404/429/generico):
    se extrae porque es literalmente el mismo bloque, no una abstraccion
    prematura sobre codigo que aun podria divergir."""
    msg = str(e)
    plan.status = ActionStatus.ERROR
    plan.error = msg
    status = getattr(e, "http_status", None)
    if _es_error_auth(e):
        # token muerto y sin refresh posible: borrarlo y dar el comando
        _CACHE_PATH.unlink(missing_ok=True)
        plan.result = REAUTH_MSG
    elif status == 403 or "premium" in msg.lower():
        plan.result = msg_403 or (
            "Spotify rechazo la accion, senor. Esta funcion requiere una "
            "cuenta Premium.")
    elif status == 404:
        plan.result = msg_404 or (
            "El dispositivo dejo de estar disponible, senor. Intentelo de nuevo.")
    elif status == 429:
        plan.result = "Spotify esta limitando las solicitudes, senor. Espere un momento."
    else:
        prefix = msg_generic or "No pude completar la accion en Spotify"
        plan.result = f"{prefix}, senor: {msg}"
    logger.error(f"Error en Spotify: {e}")


def play_song(query: str) -> ActionPlan:
    """Busca una cancion (o artista) por nombre y la reproduce en Spotify."""
    query = (query or "").strip()
    plan = ActionPlan(action="reproducir_spotify", params={"cancion": query},
                      risk=RiskLevel.EXECUTE, reason="Reproducir en Spotify")

    if not query:
        plan.status = ActionStatus.ERROR
        plan.result = "Que cancion desea escuchar, senor?"
        return plan

    sp = _cliente_o_error(plan)
    if sp is None:
        return plan

    try:
        track = _buscar_track(sp, query)
        if track is None:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre '{query}' en Spotify, senor."
            return plan

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
        _manejar_error_spotify(
            e, plan,
            msg_403=("Spotify rechazo la reproduccion, senor. Esta funcion "
                     "requiere una cuenta Premium."),
            msg_404=("El dispositivo dejo de estar disponible justo antes de "
                     "reproducir, senor. Intentelo de nuevo."),
            msg_generic="No pude reproducir en Spotify")
    return plan


# ==========================================================================
# Paquete 1 -- Control avanzado por API
#
# A diferencia del control MPRIS generico de media_controls.py (pausa/
# siguiente/anterior/volumen del sistema, funciona con cualquier reproductor
# local), estas funciones hablan directo con la Web API de Spotify: siguen
# funcionando aunque el dispositivo activo sea remoto (celular, parlante
# Connect), y cubren capacidades que MPRIS no tiene (shuffle, repeat, cola,
# volumen del dispositivo Connect en vez del sistema operativo).
# ==========================================================================

def pause_playback() -> ActionPlan:
    """Pausa la reproduccion en Spotify via la Web API."""
    plan = ActionPlan(action="pausar_spotify", risk=RiskLevel.EXECUTE,
                      reason="Pausar en Spotify")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.pause_playback()
        plan.result = "Pausado, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(
            e, plan,
            msg_403="No hay musica reproduciendose en Spotify para pausar, senor.",
            msg_generic="No pude pausar Spotify")
    return plan


def resume_playback() -> ActionPlan:
    """Reanuda la reproduccion en Spotify via la Web API."""
    plan = ActionPlan(action="reanudar_spotify", risk=RiskLevel.EXECUTE,
                      reason="Reanudar en Spotify")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.start_playback()
        plan.result = "Reanudado, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(
            e, plan,
            msg_403=("No hay nada para reanudar en Spotify, senor. Pida una "
                     "cancion primero."),
            msg_generic="No pude reanudar Spotify")
    return plan


def next_track() -> ActionPlan:
    """Salta a la siguiente cancion en Spotify via la Web API."""
    plan = ActionPlan(action="siguiente_cancion_spotify", risk=RiskLevel.EXECUTE,
                      reason="Siguiente cancion en Spotify")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.next_track()
        plan.result = "Siguiente cancion, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude saltar la cancion en Spotify")
    return plan


def previous_track() -> ActionPlan:
    """Vuelve a la cancion anterior en Spotify via la Web API."""
    plan = ActionPlan(action="cancion_anterior_spotify", risk=RiskLevel.EXECUTE,
                      reason="Cancion anterior en Spotify")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.previous_track()
        plan.result = "Cancion anterior, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan,
                               msg_generic="No pude volver a la cancion anterior en Spotify")
    return plan


def set_volume(nivel: int) -> ActionPlan:
    """Fija el volumen de reproduccion en Spotify (0-100) en el dispositivo
    Connect activo -- a diferencia del volumen del sistema operativo, esto
    funciona aunque el dispositivo sea un celular o un parlante remoto."""
    nivel = max(0, min(100, int(nivel)))
    plan = ActionPlan(action="volumen_spotify", params={"nivel": nivel},
                      risk=RiskLevel.EXECUTE,
                      reason=f"Fijar volumen de Spotify a {nivel}")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.volume(nivel)
        plan.result = f"Volumen de Spotify al {nivel}%, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude ajustar el volumen de Spotify")
    return plan


def set_shuffle(activar: bool) -> ActionPlan:
    """Activa o desactiva el modo aleatorio en Spotify."""
    activar = bool(activar)
    plan = ActionPlan(action="aleatorio_spotify", params={"activar": activar},
                      risk=RiskLevel.EXECUTE,
                      reason="Activar aleatorio" if activar else "Desactivar aleatorio")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.shuffle(activar)
        plan.result = ("Modo aleatorio activado, senor." if activar
                       else "Modo aleatorio desactivado, senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude cambiar el modo aleatorio de Spotify")
    return plan


_REPEAT_MODOS = {"cancion": "track", "lista": "context", "no": "off"}


def set_repeat(modo: str) -> ActionPlan:
    """Fija el modo de repeticion en Spotify: 'cancion' (repite la pista
    actual), 'lista' (repite la playlist/album/contexto) o 'no' (apagado)."""
    modo = (modo or "").strip().lower()
    plan = ActionPlan(action="repetir_spotify", params={"modo": modo},
                      risk=RiskLevel.EXECUTE, reason=f"Repetir: {modo}")
    if modo not in _REPEAT_MODOS:
        plan.status = ActionStatus.ERROR
        plan.result = "Diga si quiere repetir la cancion, la lista, o desactivarlo, senor."
        return plan
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        sp.repeat(_REPEAT_MODOS[modo])
        mensajes = {"cancion": "Repitiendo esta cancion, senor.",
                    "lista": "Repitiendo la lista, senor.",
                    "no": "Repeticion desactivada, senor."}
        plan.result = mensajes[modo]
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude cambiar la repeticion en Spotify")
    return plan


def now_playing() -> ActionPlan:
    """Que esta sonando ahora mismo en Spotify (solo lectura)."""
    plan = ActionPlan(action="que_suena_spotify", risk=RiskLevel.READ,
                      reason="Consultar que suena en Spotify")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        actual = sp.current_playback()
        item = (actual or {}).get("item")
        if not item:
            plan.result = "No hay nada sonando en Spotify, senor."
            plan.status = ActionStatus.EXECUTED
            return plan
        nombre = item.get("name", "?")
        artistas = ", ".join(a["name"] for a in item.get("artists", []))
        dispositivo = (actual.get("device") or {}).get("name", "un dispositivo")
        estado = "sonando" if actual.get("is_playing") else "en pausa"
        base = f"'{nombre}' de {artistas}" if artistas else f"'{nombre}'"
        plan.result = f"{base} esta {estado} en {dispositivo}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude consultar que suena en Spotify")
    return plan


def add_to_queue(query: str) -> ActionPlan:
    """Agrega una cancion a la cola de Spotify sin interrumpir lo que suena."""
    query = (query or "").strip()
    plan = ActionPlan(action="agregar_a_cola_spotify", params={"cancion": query},
                      risk=RiskLevel.EXECUTE, reason="Agregar a la cola de Spotify")
    if not query:
        plan.status = ActionStatus.ERROR
        plan.result = "Que cancion agrego a la cola, senor?"
        return plan
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        track = _buscar_track(sp, query)
        if track is None:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre '{query}' en Spotify, senor."
            return plan
        sp.add_to_queue(track["uri"])
        artistas = ", ".join(a["name"] for a in track.get("artists", []))
        nombre = track.get("name", query)
        plan.result = (f"Agregue '{nombre}' de {artistas} a la cola, senor."
                       if artistas else f"Agregue '{nombre}' a la cola, senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan,
                               msg_generic="No pude agregar la cancion a la cola de Spotify")
    return plan


# ==========================================================================
# Paquete 2 -- Playlists y descubrimiento
# ==========================================================================

def _resolver_playlist(sp, nombre: str) -> dict | list[dict] | None:
    """(playlist) si hay una coincidencia clara por nombre parcial entre las
    playlists del usuario (hasta las primeras 50); la lista de candidatas si
    hay varias; None si ninguna. Mismo patron que _resolver_dispositivo."""
    low = (nombre or "").strip().lower()
    if not low:
        return None
    playlists = sp.current_user_playlists(limit=50).get("items", [])
    cand = [p for p in playlists if low in (p.get("name") or "").lower()]
    if len(cand) == 1:
        return cand[0]
    return cand or None


def play_playlist(name: str) -> ActionPlan:
    """Reproduce una playlist propia del usuario por nombre parcial."""
    name = (name or "").strip()
    plan = ActionPlan(action="reproducir_playlist_spotify", params={"name": name},
                      risk=RiskLevel.EXECUTE, reason="Reproducir playlist en Spotify")
    if not name:
        plan.status = ActionStatus.ERROR
        plan.result = "Que playlist quiere escuchar, senor?"
        return plan
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        r = _resolver_playlist(sp, name)
        if r is None:
            plan.status = ActionStatus.BLOCKED
            plan.result = f"No encuentro ninguna playlist suya que case con '{name}', senor."
            return plan
        if isinstance(r, list):
            plan.status = ActionStatus.BLOCKED
            plan.result = (
                f"Hay varias playlists que casan con '{name}', senor: "
                + ", ".join(p.get("name", "?") for p in r) + ". Dime el nombre exacto.")
            return plan
        device_id = _device_id(sp)
        if device_id is None:
            plan.status = ActionStatus.ERROR
            plan.result = (
                "No pude abrir Spotify en este equipo, senor. Verifique que "
                "este instalado, o abralo usted mismo e intente de nuevo.")
            return plan
        sp.start_playback(device_id=device_id, context_uri=r["uri"])
        plan.result = f"Reproduciendo la playlist '{r.get('name', name)}', senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude reproducir la playlist en Spotify")
    return plan


def play_album(query: str) -> ActionPlan:
    """Busca y reproduce un album completo en Spotify."""
    query = (query or "").strip()
    plan = ActionPlan(action="reproducir_album_spotify", params={"query": query},
                      risk=RiskLevel.EXECUTE, reason="Reproducir album en Spotify")
    if not query:
        plan.status = ActionStatus.ERROR
        plan.result = "Que album quiere escuchar, senor?"
        return plan
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        items = sp.search(q=query, type="album", limit=5).get("albums", {}).get("items", [])
        if not items:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre el album '{query}' en Spotify, senor."
            return plan
        exacto = next((a for a in items
                       if a.get("name", "").lower() == query.lower()), None)
        album = exacto or items[0]
        device_id = _device_id(sp)
        if device_id is None:
            plan.status = ActionStatus.ERROR
            plan.result = (
                "No pude abrir Spotify en este equipo, senor. Verifique que "
                "este instalado, o abralo usted mismo e intente de nuevo.")
            return plan
        sp.start_playback(device_id=device_id, context_uri=album["uri"])
        artistas = ", ".join(a["name"] for a in album.get("artists", []))
        nombre = album.get("name", query)
        plan.result = (f"Reproduciendo el album '{nombre}' de {artistas}, senor."
                       if artistas else f"Reproduciendo el album '{nombre}', senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude reproducir el album en Spotify")
    return plan


def play_radio(query: str) -> ActionPlan:
    """Inicia una 'radio' basada en un artista o cancion. El endpoint oficial
    de recomendaciones (`recommendations`, como `artist-top-tracks`) esta
    restringido por Spotify para apps nuevas sin "extended quota mode" y
    puede fallar: si lo hace, se cae a reproducir el catalogo del artista
    resuelto, o la propia cancion buscada como ultimo recurso -- nunca se
    finge una radio que no se pudo armar."""
    query = (query or "").strip()
    plan = ActionPlan(action="radio_spotify", params={"query": query},
                      risk=RiskLevel.EXECUTE, reason="Iniciar radio en Spotify")
    if not query:
        plan.status = ActionStatus.ERROR
        plan.result = "De que artista o cancion hago la radio, senor?"
        return plan
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        device_id = _device_id(sp)
        if device_id is None:
            plan.status = ActionStatus.ERROR
            plan.result = (
                "No pude abrir Spotify en este equipo, senor. Verifique que "
                "este instalado, o abralo usted mismo e intente de nuevo.")
            return plan

        artista = _resolver_artista(sp, query)
        track = None if artista else _buscar_track(sp, query)
        if not artista and track is None:
            plan.status = ActionStatus.ERROR
            plan.result = f"No encontre '{query}' en Spotify, senor."
            return plan

        seed_uris = None
        try:
            if artista:
                rec = sp.recommendations(seed_artists=[artista["id"]], limit=20)
            else:
                rec = sp.recommendations(seed_tracks=[track["id"]], limit=20)
            seed_uris = [t["uri"] for t in rec.get("tracks", [])] or None
        except Exception:
            seed_uris = None

        if seed_uris:
            sp.start_playback(device_id=device_id, uris=seed_uris)
            plan.result = f"Radio de '{query}' iniciada, senor."
            plan.status = ActionStatus.EXECUTED
            return plan

        if artista:
            sp.start_playback(device_id=device_id, context_uri=artista["uri"])
            plan.result = (
                "Spotify no me dio recomendaciones para esta cuenta, senor. "
                f"Reproduciendo el catalogo de {artista['name']} en su lugar.")
            plan.status = ActionStatus.EXECUTED
            return plan

        sp.start_playback(device_id=device_id, uris=[track["uri"]])
        nombre = track.get("name", query)
        plan.result = (
            "Spotify no me dio recomendaciones para esta cuenta, senor. "
            f"Reproduciendo '{nombre}' en su lugar.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude iniciar la radio en Spotify")
    return plan


# ==========================================================================
# Paquete 3 -- Multi-dispositivo
# ==========================================================================

def _resolver_dispositivo(objetivo: str, devices: list[dict]) -> dict | list[dict] | None:
    """(device) si hay una coincidencia clara por nombre parcial; la lista
    de candidatos si hay varias; None si ninguna. Mismo patron que
    tools/bluetooth.py::_resolver."""
    low = (objetivo or "").strip().lower()
    if not low:
        return None
    cand = [d for d in devices if low in (d.get("name") or "").lower()]
    if len(cand) == 1:
        return cand[0]
    return cand or None


def _formatear_dispositivos(devices: list[dict]) -> str:
    if not devices:
        return "no hay ninguno"
    return ", ".join(
        f"{'* ' if d.get('is_active') else ''}{d.get('name', '?')}" for d in devices)


def list_devices() -> ActionPlan:
    """Lista los dispositivos Spotify Connect disponibles (solo lectura)."""
    plan = ActionPlan(action="listar_dispositivos_spotify", risk=RiskLevel.READ,
                      reason="Listar dispositivos Spotify Connect")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        devices = sp.devices().get("devices", [])
        if not devices:
            plan.result = "No veo ningun dispositivo Spotify Connect disponible, senor."
        else:
            plan.result = f"Dispositivos de Spotify, senor: {_formatear_dispositivos(devices)}."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude listar los dispositivos de Spotify")
    return plan


def transfer_playback(device: str) -> ActionPlan:
    """Cambia la reproduccion de Spotify a otro dispositivo Connect por
    nombre parcial (celular, parlante, este PC...)."""
    device = (device or "").strip()
    plan = ActionPlan(action="cambiar_dispositivo_spotify", params={"device": device},
                      risk=RiskLevel.EXECUTE, reason="Cambiar dispositivo de Spotify")
    if not device:
        plan.status = ActionStatus.ERROR
        plan.result = "A que dispositivo cambio la musica, senor?"
        return plan
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        devices = sp.devices().get("devices", [])
        r = _resolver_dispositivo(device, devices)
        if r is None:
            plan.status = ActionStatus.BLOCKED
            plan.result = (
                f"No encuentro ningun dispositivo que case con '{device}', senor. "
                f"Disponibles: {_formatear_dispositivos(devices)}.")
            return plan
        if isinstance(r, list):
            plan.status = ActionStatus.BLOCKED
            plan.result = (
                f"Hay varios dispositivos que casan con '{device}', senor: "
                + ", ".join(d.get("name", "?") for d in r) + ". Dime el nombre exacto.")
            return plan
        sp.transfer_playback(device_id=r["id"], force_play=True)
        plan.result = f"Musica en {r.get('name', device)}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude cambiar el dispositivo de Spotify")
    return plan


# ==========================================================================
# Paquete 4 -- Biblioteca personal
# ==========================================================================

def like_current_track() -> ActionPlan:
    """Guarda la cancion que suena ahora en 'Me Gusta' (Liked Songs)."""
    plan = ActionPlan(action="guardar_en_favoritos_spotify", risk=RiskLevel.CREATE,
                      reason="Guardar cancion actual en Me Gusta")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        actual = sp.current_playback()
        item = (actual or {}).get("item")
        if not item:
            plan.status = ActionStatus.ERROR
            plan.result = "No hay ninguna cancion sonando en Spotify para guardar, senor."
            return plan
        sp.current_user_saved_tracks_add([item["id"]])
        artistas = ", ".join(a["name"] for a in item.get("artists", []))
        nombre = item.get("name", "?")
        plan.result = (f"Guarde '{nombre}' de {artistas} en Me Gusta, senor."
                       if artistas else f"Guarde '{nombre}' en Me Gusta, senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude guardar la cancion en Me Gusta")
    return plan


def recently_played(limite: int = 10) -> ActionPlan:
    """Lista lo reproducido recientemente en Spotify (solo lectura)."""
    limite = 10 if limite is None else int(limite)
    limite = max(1, min(50, limite))
    plan = ActionPlan(action="reproducido_recientemente_spotify", params={"limite": limite},
                      risk=RiskLevel.READ, reason="Consultar reproducido recientemente")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        items = sp.current_user_recently_played(limit=limite).get("items", [])
        if not items:
            plan.result = "No hay historial reciente en Spotify, senor."
            plan.status = ActionStatus.EXECUTED
            return plan
        vistos: set[str] = set()
        lineas = []
        for it in items:
            track = it.get("track", {})
            nombre = track.get("name", "?")
            artistas = ", ".join(a["name"] for a in track.get("artists", []))
            etiqueta = f"{nombre} - {artistas}" if artistas else nombre
            if etiqueta in vistos:
                continue
            vistos.add(etiqueta)
            lineas.append(etiqueta)
        plan.result = "Reproducido recientemente, senor: " + "; ".join(lineas) + "."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude consultar el historial de Spotify")
    return plan


def resume_last_played() -> ActionPlan:
    """Reanuda lo ultimo reproducido en Spotify. Si queda un contexto activo
    (pausado), lo retoma; si la sesion se perdio del todo, cae al historial
    reciente y reproduce la ultima cancion escuchada."""
    plan = ActionPlan(action="reanudar_ultimo_spotify", risk=RiskLevel.EXECUTE,
                      reason="Reanudar lo ultimo reproducido en Spotify")
    sp = _cliente_o_error(plan)
    if sp is None:
        return plan
    try:
        actual = sp.current_playback()
        if actual and actual.get("item"):
            sp.start_playback()
            nombre = actual["item"].get("name", "?")
            plan.result = f"Retomando '{nombre}', senor."
            plan.status = ActionStatus.EXECUTED
            return plan

        recientes = sp.current_user_recently_played(limit=1).get("items", [])
        if not recientes:
            plan.status = ActionStatus.ERROR
            plan.result = "No tengo nada reciente que reanudar en Spotify, senor."
            return plan
        track = recientes[0].get("track", {})
        device_id = _device_id(sp)
        if device_id is None:
            plan.status = ActionStatus.ERROR
            plan.result = (
                "No pude abrir Spotify en este equipo, senor. Verifique que "
                "este instalado, o abralo usted mismo e intente de nuevo.")
            return plan
        sp.start_playback(device_id=device_id, uris=[track["uri"]])
        nombre = track.get("name", "?")
        artistas = ", ".join(a["name"] for a in track.get("artists", []))
        plan.result = (f"Reanudando '{nombre}' de {artistas}, senor."
                       if artistas else f"Reanudando '{nombre}', senor.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        _manejar_error_spotify(e, plan, msg_generic="No pude reanudar lo ultimo en Spotify")
    return plan
