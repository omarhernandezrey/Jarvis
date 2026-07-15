"""Tests de lectura en voz alta (portapapeles y archivos)"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.reader import (
    _get_clipboard_text,
    read_clipboard,
    read_file_aloud,
)

DOCS = os.path.expandvars(r"%USERPROFILE%\Documents")


def _set_clipboard(text: str) -> bool:
    """Pone texto en el portapapeles real (Win32, con tipos de 64 bits)."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    if not user32.OpenClipboard(0):
        return False
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    finally:
        user32.CloseClipboard()


# --- Enrutamiento del parser ---


def test_intent_leer_portapapeles():
    for frase in ("leeme el portapapeles", "lee el portapapeles",
                  "que hay en el portapapeles"):
        r = parse_intent(frase)
        assert r.tool == "read_clipboard", frase


def test_intent_leer_archivo():
    r = parse_intent("leeme el archivo notas.txt")
    assert r.tool == "read_file"
    assert r.arguments["path"] == "notas.txt"


def test_intent_leer_noticias_no_robado():
    # "lee las noticias" no es un archivo
    r = parse_intent("lee las noticias")
    assert r.tool == "news_headlines"


# --- Portapapeles real (se guarda y restaura el del usuario) ---


def test_leer_portapapeles_real():
    original = _get_clipboard_text() or ""
    try:
        assert _set_clipboard("prueba de lectura de jarvis")
        plan = read_clipboard()
        assert plan.status == ActionStatus.EXECUTED
        assert "prueba de lectura de jarvis" in plan.result
    finally:
        _set_clipboard(original)


def test_portapapeles_vacio():
    original = _get_clipboard_text() or ""
    try:
        _set_clipboard("")
        plan = read_clipboard()
        assert plan.status == ActionStatus.EXECUTED
        assert "no tiene texto" in plan.result.lower()
    finally:
        _set_clipboard(original)


# --- Archivos ---


def test_leer_archivo_real():
    path = os.path.join(DOCS, "_jarvis_test_lectura.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("contenido de prueba para leer en voz alta")
    try:
        plan = read_file_aloud(path)
        assert plan.status == ActionStatus.EXECUTED
        assert "contenido de prueba" in plan.result
    finally:
        os.remove(path)


def test_leer_archivo_por_nombre():
    path = os.path.join(DOCS, "_jarvis_test_nombre.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("encontrado por nombre")
    try:
        plan = read_file_aloud("_jarvis_test_nombre.txt")
        assert plan.status == ActionStatus.EXECUTED
        assert "encontrado por nombre" in plan.result
    finally:
        os.remove(path)


def test_leer_archivo_largo_se_recorta():
    path = os.path.join(DOCS, "_jarvis_test_largo.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("palabra " * 1000)  # ~8000 caracteres
    try:
        plan = read_file_aloud(path)
        assert plan.status == ActionStatus.EXECUTED
        assert len(plan.result) < 2300
        assert "lo dejo ahi" in plan.result
    finally:
        os.remove(path)


def test_ruta_fuera_de_whitelist_bloqueada():
    plan = read_file_aloud(r"C:\Windows\System32\drivers\etc\hosts")
    assert plan.status == ActionStatus.BLOCKED


def test_archivo_inexistente():
    plan = read_file_aloud(os.path.join(DOCS, "no_existe_9x.txt"))
    assert plan.status == ActionStatus.ERROR


def test_formato_no_soportado():
    path = os.path.join(DOCS, "_jarvis_test.exe")
    with open(path, "w", encoding="utf-8") as f:
        f.write("binario falso")
    try:
        plan = read_file_aloud(path)
        assert plan.status == ActionStatus.ERROR
        assert "texto" in plan.result.lower()
    finally:
        os.remove(path)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de lectura pasaron.")
