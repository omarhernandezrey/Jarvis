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
import subprocess
import time
import unicodedata

from jarvis_local.config import IS_WINDOWS

INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "apps_index.json")
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


def _normalize(text: str) -> str:
    """minusculas y sin acentos, para comparar nombres hablados."""
    t = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _is_launchable(name: str, appid: str) -> bool:
    n = _normalize(name)
    if any(marker in n for marker in _EXCLUDE_NAME_MARKERS):
        return False
    a = appid.lower()
    if a.startswith(("http://", "https://")):
        return False
    if a.endswith(_EXCLUDE_APPID_SUFFIXES):
        return False
    return True


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
    if not force and os.path.exists(INDEX_PATH):
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


def find_app(query: str) -> list:
    """Busca apps por nombre. Devuelve [{name, appid, norm}] ordenado
    por relevancia: exacto > prefijo > contiene > palabras > difuso."""
    q = _normalize(query)
    if not q:
        return []
    index = get_index()

    exact, prefix, contains, words = [], [], [], []
    q_words = set(q.split())
    for app in index:
        norm = app["norm"]
        if norm == q:
            exact.append(app)
        elif norm.startswith(q):
            prefix.append(app)
        elif q in norm:
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
