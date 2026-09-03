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

SCOPES = "user-modify-playback-state user-read-playback-state"
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
        try:
            import spotipy  # noqa: F401
        except ImportError:
            plan.result = "Falta instalar la libreria de Spotify: pip install spotipy."
        else:
            # spotipy esta, pero no hay token cacheado valido: reautorizar.
            _CACHE_PATH.unlink(missing_ok=True)
            plan.result = REAUTH_MSG
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
        msg = str(e)
        plan.status = ActionStatus.ERROR
        plan.error = msg
        status = getattr(e, "http_status", None)
        if _es_error_auth(e):
            # token muerto y sin refresh posible: borrarlo y dar el comando
            _CACHE_PATH.unlink(missing_ok=True)
            plan.result = REAUTH_MSG
        elif status == 403 or "premium" in msg.lower():
            plan.result = ("Spotify rechazo la reproduccion, senor. Esta "
                           "funcion requiere una cuenta Premium.")
        elif status == 404:
            plan.result = ("El dispositivo dejo de estar disponible justo "
                           "antes de reproducir, senor. Intentelo de nuevo.")
        elif status == 429:
            plan.result = "Spotify esta limitando las solicitudes, senor. Espere un momento."
        else:
            plan.result = f"No pude reproducir en Spotify, senor: {msg}"
        logger.error(f"Error reproduciendo en Spotify: {e}")
    return plan
