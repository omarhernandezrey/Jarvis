"""
Tests del indice dinamico de aplicaciones instaladas - Fase 3
Usan un indice falso en memoria para no depender de las apps del equipo
ni lanzar ninguna aplicacion real.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.tools import app_index
from jarvis_local.tools.app_index import find_app, _normalize, _is_launchable


_FAKE_INDEX = [
    {"name": "WhatsApp", "appid": "5319275A.WhatsAppDesktop!App", "norm": "whatsapp"},
    {"name": "Word", "appid": "Microsoft.Office.WINWORD.EXE.15", "norm": "word"},
    {"name": "WordPad", "appid": "wordpad.exe", "norm": "wordpad"},
    {"name": "Notion", "appid": "com.electron.notion", "norm": "notion"},
    {"name": "Notepad++", "appid": "notepad++.exe", "norm": "notepad++"},
    {"name": "Android Studio", "appid": "studio64.exe", "norm": "android studio"},
    {"name": "Telegram Desktop", "appid": "Telegram!App", "norm": "telegram desktop"},
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
