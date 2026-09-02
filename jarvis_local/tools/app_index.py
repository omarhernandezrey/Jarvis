"""
JARVIS Local - Indice dinamico de aplicaciones instaladas (Fase 3)
Escanea las apps instaladas (Get-StartApps en Windows, archivos .desktop en
Linux) y permite abrir cualquiera por su nombre con busqueda difusa. El
indice se cachea en disco para que la busqueda sea instantanea.
"""
import configparser
import difflib
import glob
import json
import os
import re
import subprocess
import time

from jarvis_local.config import BASE_DIR, IS_WINDOWS
from jarvis_local.tools._utils import normalize_text as _normalize

INDEX_PATH = str(BASE_DIR / "data" / "apps_index.json")
INDEX_MAX_AGE_SECONDS = 7 * 24 * 3600  # re-escanear cada 7 dias

# Entradas del menu inicio que no son aplicaciones abribles
_EXCLUDE_NAME_MARKERS = [
    "desinstalar", "uninstall", "documentation", "documentacion", "manual",
    "release notes", "faq", "learn more", "website", "ayuda", "novedades",
    "screenshot history", "reference documentation",
]
_EXCLUDE_APPID_SUFFIXES = (".url", ".chm", ".txt", ".html", ".md")

# Directorios estandar donde Linux/GNOME registra los .desktop de las apps
# instaladas (orden: sistema, sistema local, del usuario).
_LINUX_DESKTOP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    # snapd registra aqui el .desktop de cada app instalada por snap (Chrome,
    # WhatsApp, Obsidian, etc. suelen venir asi en Ubuntu) -- sin este
    # directorio el indice se pierde cualquier app instalada por snap.
    "/var/lib/snapd/desktop/applications",
    # flatpak, por si el equipo tambien las usa.
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
]

_cache: list | None = None

# Nombre común (marca ajena o genérico) -> qué buscar en el índice real. En
# este equipo la ofimática es LibreOffice: "abre word" debe abrir Writer, no
# "Passwords and Keys". Se prueban en orden; si ninguno resuelve, se usa el
# nombre tal cual (así en Windows "word" sigue encontrando el Word real).
_SYNONYMS: dict[str, list[str]] = {
    "word": ["libreoffice writer"],
    "excel": ["libreoffice calc"],
    "powerpoint": ["libreoffice impress"],
    "power point": ["libreoffice impress"],
    "access": ["libreoffice base"],
    "office": ["libreoffice"],
    "libreoffice": ["libreoffice"],
    "libre office": ["libreoffice"],
    "ofimatica": ["libreoffice"],
    "procesador de texto": ["libreoffice writer"],
    "hoja de calculo": ["libreoffice calc"],
    "presentaciones": ["libreoffice impress"],
    "presentacion": ["libreoffice impress"],
    # editores / IDEs: el nombre corto o coloquial -> lo instalado
    "vscode": ["visual studio code", "code"],
    "vs code": ["visual studio code", "code"],
    "vs-code": ["visual studio code", "code"],
    "visual studio": ["visual studio code", "code"],
    "editor de codigo": ["visual studio code", "code"],
    # gestor de archivos (nombre real, ingles y espanol)
    "archivos": ["files", "nautilus"],
    "explorador": ["files", "nautilus"],
    "explorador de archivos": ["files", "nautilus"],
    "gestor de archivos": ["files", "nautilus"],
    "administrador de archivos": ["files", "nautilus"],
    "nautilus": ["files"],
    "finder": ["files"],
    # navegador generico -> el que haya
    "navegador": ["google chrome", "chrome", "firefox", "brave", "edge"],
    "navegador web": ["google chrome", "chrome", "firefox", "brave", "edge"],
    "browser": ["google chrome", "chrome", "firefox"],
    # otros coloquiales
    "bloc de notas": ["text editor", "notepad", "gedit"],
    "editor de texto": ["text editor", "gedit", "notepad"],
    "calculadora": ["calculator", "gnome calculator"],
    "ajustes": ["settings", "configuracion"],
    "configuracion": ["settings"],
    "musica": ["spotify"],
}


def _is_launchable(name: str, appid: str) -> bool:
    n = _normalize(name)
    if any(marker in n for marker in _EXCLUDE_NAME_MARKERS):
        return False
    a = appid.lower()
    if a.startswith(("http://", "https://")):
        return False
    return not a.endswith(_EXCLUDE_APPID_SUFFIXES)


def _scan_installed_apps_windows() -> list:
    """Ejecuta Get-StartApps y devuelve [{name, appid, norm}, ...]."""
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=90,
                         encoding="utf-8", errors="replace")
    data = json.loads(out.stdout)
    if isinstance(data, dict):
        data = [data]
    apps = []
    seen = set()
    for item in data:
        name = (item.get("Name") or "").strip()
        appid = (item.get("AppID") or "").strip()
        if not name or not appid or not _is_launchable(name, appid):
            continue
        key = _normalize(name)
        if key in seen:
            continue
        seen.add(key)
        apps.append({"name": name, "appid": appid, "norm": key})
    return apps


def _scan_installed_apps_linux() -> list:
    """Lee los .desktop de las apps instaladas. El "appid" es el nombre de
    archivo .desktop (lo que espera `gtk-launch`)."""
    apps = []
    seen = set()
    for base_dir in _LINUX_DESKTOP_DIRS:
        for path in glob.glob(os.path.join(base_dir, "*.desktop")):
            appid = os.path.basename(path)
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
            except (OSError, UnicodeDecodeError, configparser.Error):
                continue
            if "Desktop Entry" not in parser:
                continue
            entry = parser["Desktop Entry"]
            if entry.get("Type", "Application") != "Application":
                continue
            if entry.getboolean("NoDisplay", fallback=False):
                continue
            if entry.getboolean("Hidden", fallback=False):
                continue
            name = (entry.get("Name") or "").strip()
            if not name or not _is_launchable(name, appid):
                continue
            key = _normalize(name)
            if key in seen:
                continue
            seen.add(key)
            apps.append({"name": name, "appid": appid, "norm": key})
    return apps


def scan_installed_apps() -> list:
    """Devuelve [{name, appid, norm}, ...] de las apps instaladas."""
    return _scan_installed_apps_windows() if IS_WINDOWS else _scan_installed_apps_linux()


def refresh_index(force: bool = False) -> list:
    """Reconstruye el indice si no existe, esta viejo o force=True."""
    global _cache
    if not force:
        # ya cargado en esta sesion: no re-escanear a mitad de camino
        # (los tests inyectan un indice falso en _cache).
        if _cache is not None:
            return _cache
        if os.path.exists(INDEX_PATH):
            age = time.time() - os.path.getmtime(INDEX_PATH)
            if age < INDEX_MAX_AGE_SECONDS:
                return get_index()
    apps = scan_installed_apps()
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(apps, f, ensure_ascii=False, indent=1)
    _cache = apps
    return apps


def get_index() -> list:
    """Devuelve el indice (memoria > disco > escaneo)."""
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(INDEX_PATH):
        try:
            with open(INDEX_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
            return _cache
        except (json.JSONDecodeError, OSError):
            pass
    return refresh_index(force=True)


def find_app(query: str, use_synonyms: bool = True) -> list:
    """Busca apps por nombre. Devuelve [{name, appid, norm}] ordenado
    por relevancia: exacto > prefijo > contiene > palabras > difuso.

    Con `use_synonyms`, un nombre conocido (p.ej. "word", "office") se
    reescribe primero a lo que hay instalado (LibreOffice); si eso no
    resuelve, se busca el nombre tal cual.
    """
    q = _normalize(query)
    if not q:
        return []
    if use_synonyms and q in _SYNONYMS:
        for alt in _SYNONYMS[q]:
            hit = find_app(alt, use_synonyms=False)
            if hit:
                return hit
    # refresh_index respeta la antigüedad (7 días): barato si está fresco,
    # re-escanea si caducó. Antes se leía get_index() a secas y el índice
    # podía quedar meses obsoleto → apps nuevas (p.ej. LibreOffice) invisibles.
    index = refresh_index()

    exact, prefix, contains, words = [], [], [], []
    q_words = set(q.split())
    # "contiene" sólo cuenta si empieza en frontera de palabra: así "word" NO
    # cae en "passwords and keys" (era el bug de "abre word").
    contains_re = re.compile(r"\b" + re.escape(q))
    for app in index:
        norm = app["norm"]
        if norm == q:
            exact.append(app)
        elif norm.startswith(q):
            prefix.append(app)
        elif contains_re.search(norm):
            contains.append(app)
        elif q_words and q_words.issubset(set(norm.split())):
            words.append(app)

    # dentro de cada nivel, el nombre mas corto primero
    for bucket in (prefix, contains, words):
        bucket.sort(key=lambda a: len(a["norm"]))
    results = exact + prefix + contains + words

    if not results:
        by_norm = {a["norm"]: a for a in index}
        close = difflib.get_close_matches(q, by_norm.keys(), n=3, cutoff=0.75)
        results = [by_norm[n] for n in close]
    return results


def launch_app(appid: str) -> None:
    """Lanza una app por su AppID (AUMID en Windows, .desktop en Linux)."""
    if IS_WINDOWS:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{appid}"],
                         shell=False)
    else:
        subprocess.Popen(["gtk-launch", appid], shell=False)
