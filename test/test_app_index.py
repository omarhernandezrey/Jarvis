"""
Tests del indice dinamico de aplicaciones instaladas - Fase 3
Usan un indice falso en memoria para no depender de las apps del equipo
ni lanzar ninguna aplicacion real.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.tools import app_index
from jarvis_local.tools.app_index import _is_launchable, _normalize, find_app

_FAKE_INDEX = [
    {"name": "WhatsApp", "appid": "5319275A.WhatsAppDesktop!App", "norm": "whatsapp"},
    {"name": "Word", "appid": "Microsoft.Office.WINWORD.EXE.15", "norm": "word"},
    {"name": "WordPad", "appid": "wordpad.exe", "norm": "wordpad"},
    {"name": "Notion", "appid": "com.electron.notion", "norm": "notion"},
    {"name": "Notepad++", "appid": "notepad++.exe", "norm": "notepad++"},
    {"name": "Android Studio", "appid": "studio64.exe", "norm": "android studio"},
    {"name": "Telegram Desktop", "appid": "Telegram!App", "norm": "telegram desktop"},
]

# Índice tipo Linux con LibreOffice y una app cuyo nombre contiene "word".
_FAKE_INDEX_LINUX = [
    {"name": "Passwords and Keys", "appid": "org.gnome.seahorse.Application.desktop",
     "norm": "passwords and keys"},
    {"name": "LibreOffice 26.2 Writer", "appid": "libreoffice_writer.desktop",
     "norm": "libreoffice 26.2 writer"},
    {"name": "LibreOffice 26.2 Calc", "appid": "libreoffice_calc.desktop",
     "norm": "libreoffice 26.2 calc"},
    {"name": "LibreOffice 26.2 Impress", "appid": "libreoffice_impress.desktop",
     "norm": "libreoffice 26.2 impress"},
    {"name": "LibreOffice 26.2", "appid": "libreoffice_libreoffice.desktop",
     "norm": "libreoffice 26.2"},
]


def _with_fake_index(fn):
    old = app_index._cache
    app_index._cache = list(_FAKE_INDEX)
    try:
        fn()
    finally:
        app_index._cache = old


def test_normalize():
    assert _normalize("Configuración") == "configuracion"
    assert _normalize("  WORD ") == "word"


def test_excludes_non_apps():
    assert not _is_launchable("Desinstalar Lightshot", "unins000.exe")
    assert not _is_launchable("Node.js website", "https://nodejs.org/")
    assert not _is_launchable("Ayuda WinRAR", "winrar.chm")
    assert _is_launchable("WhatsApp", "5319275A.WhatsAppDesktop!App")


def test_find_exact_beats_prefix():
    def check():
        r = find_app("word")
        assert r and r[0]["name"] == "Word"  # exacto gana a WordPad
    _with_fake_index(check)


def test_find_partial():
    def check():
        r = find_app("telegram")
        assert r and r[0]["name"] == "Telegram Desktop"
    _with_fake_index(check)


def test_find_fuzzy():
    def check():
        r = find_app("guasap")  # como suena al dictarlo
        # difuso: puede no encontrarlo, pero si encuentra debe ser WhatsApp
        if r:
            assert r[0]["name"] == "WhatsApp"
        r2 = find_app("notio")
        assert r2 and r2[0]["name"] == "Notion"
    _with_fake_index(check)


def test_find_nothing():
    def check():
        assert find_app("zzz_app_inexistente_9x") == []
        assert find_app("") == []
    _with_fake_index(check)


def _with_index(idx, fn):
    old = app_index._cache
    app_index._cache = list(idx)
    try:
        fn()
    finally:
        app_index._cache = old


def test_contains_needs_word_boundary():
    """'word' NO debe casar dentro de 'passwords' (era el bug de 'abre word')."""
    def check():
        names = [m["name"] for m in find_app("word", use_synonyms=False)]
        assert "Passwords and Keys" not in names
    _with_index(_FAKE_INDEX_LINUX, check)


def test_synonyms_map_office_to_libreoffice():
    def check():
        assert find_app("word")[0]["name"] == "LibreOffice 26.2 Writer"
        assert find_app("excel")[0]["name"] == "LibreOffice 26.2 Calc"
        assert find_app("powerpoint")[0]["name"] == "LibreOffice 26.2 Impress"
        assert find_app("libre office")[0]["name"].startswith("LibreOffice")
        assert find_app("office")[0]["name"].startswith("LibreOffice")
    _with_index(_FAKE_INDEX_LINUX, check)


def test_synonyms_off_falls_back_to_raw_name():
    """Con el índice Windows (Word real) y sin LibreOffice, 'word' → Word."""
    def check():
        assert find_app("word")[0]["name"] == "Word"
    _with_fake_index(check)


def test_real_index_builds():
    """El escaneo real debe encontrar apps en este equipo (solo lectura)."""
    apps = app_index.get_index()
    assert len(apps) > 10
    assert all("name" in a and "appid" in a and "norm" in a for a in apps)


if __name__ == "__main__":
    test_normalize()
    test_excludes_non_apps()
    test_find_exact_beats_prefix()
    test_find_partial()
    test_find_fuzzy()
    test_find_nothing()
    test_real_index_builds()
    print("OK: Todos los tests del indice de apps pasaron.")


# ── TAREA B7: sinónimos ES/EN y nombre corto de IDE / gestor de archivos ──────
_FAKE_INDEX_B7 = [
    {"name": "Visual Studio Code", "appid": "code.desktop", "norm": "visual studio code"},
    {"name": "Files", "appid": "org.gnome.Nautilus.desktop", "norm": "files"},
    {"name": "Google Chrome", "appid": "google-chrome.desktop", "norm": "google chrome"},
    {"name": "Firefox", "appid": "firefox_firefox.desktop", "norm": "firefox"},
    {"name": "Text Editor", "appid": "org.gnome.TextEditor.desktop", "norm": "text editor"},
    {"name": "Calculator", "appid": "org.gnome.Calculator.desktop", "norm": "calculator"},
]


def test_b7_sinonimos_ide_y_archivos():
    def check():
        assert find_app("vscode")[0]["name"] == "Visual Studio Code"
        assert find_app("vs code")[0]["name"] == "Visual Studio Code"
        assert find_app("editor de codigo")[0]["name"] == "Visual Studio Code"
        assert find_app("archivos")[0]["name"] == "Files"
        assert find_app("nautilus")[0]["name"] == "Files"
        assert find_app("explorador de archivos")[0]["name"] == "Files"
        assert find_app("navegador")[0]["name"] in ("Google Chrome", "Firefox")
        assert find_app("calculadora")[0]["name"] == "Calculator"
    _with_index(_FAKE_INDEX_B7, check)


def test_b7_app_no_instalada_devuelve_vacio():
    """Lo que NO está instalado sigue dando [] (open_app avisa con claridad)."""
    def check():
        assert find_app("android studio") == []
        assert find_app("photoshop") == []
    _with_index(_FAKE_INDEX_B7, check)
