"""
JARVIS Local - Lectura en voz alta

"leeme el portapapeles" o "leeme el archivo notas.txt": devuelve el texto
como resultado, y el canal normal de JARVIS (consola + TTS si esta activo)
lo lee. El portapapeles se lee con la API nativa de Windows (ctypes).
"""
import ctypes
import os

from jarvis_local.safety.permissions import is_within_allowed
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

# Limite de lo que se lee en voz alta: mas alla de esto el TTS se eterniza
MAX_CHARS = 2000

_TEXT_EXTS = (".txt", ".md", ".log", ".csv", ".json", ".py", ".yaml", ".yml",
              ".ini", ".xml", ".html")

_CF_UNICODETEXT = 13


def _win32_clipboard():
    """user32/kernel32 con los tipos de retorno correctos (punteros de 64
    bits: sin restype explicito ctypes los trunca a 32 y revienta)."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    return user32, kernel32


def _get_clipboard_text() -> str | None:
    """Texto del portapapeles via Win32. None si no se pudo abrir."""
    user32, kernel32 = _win32_clipboard()
    if not user32.OpenClipboard(0):
        return None
    try:
        handle = user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return ""  # no hay texto copiado (puede haber una imagen)
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _recortar(texto: str) -> tuple[str, bool]:
    texto = texto.strip()
    if len(texto) <= MAX_CHARS:
        return texto, False
    return texto[:MAX_CHARS].rsplit(" ", 1)[0], True


def read_clipboard() -> ActionPlan:
    """Lee el texto copiado en el portapapeles."""
    plan = ActionPlan(action="leer_portapapeles", risk=RiskLevel.READ,
                      reason="Operacion de solo lectura")
    try:
        texto = _get_clipboard_text()
        if texto is None:
            raise OSError("no pude abrir el portapapeles")
        if not texto.strip():
            plan.result = ("El portapapeles no tiene texto, senor. "
                           "Copie algo primero.")
            plan.status = ActionStatus.EXECUTED
            return plan
        recortado, truncado = _recortar(texto)
        plan.result = f"El portapapeles dice, senor: {recortado}"
        if truncado:
            plan.result += " ... y continua, pero lo dejo ahi."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude leer el portapapeles: {e}"
    return plan


def _buscar_en_documentos(nombre: str) -> str | None:
    """Si dieron solo un nombre, buscarlo en Documentos (primer match)."""
    base = os.path.expandvars(r"%USERPROFILE%\Documents")
    objetivo = nombre.lower()
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.lower() == objetivo:
                return os.path.join(root, f)
    return None


def read_file_aloud(path: str) -> ActionPlan:
    """Lee el contenido de un archivo de texto en una carpeta permitida."""
    plan = ActionPlan(action="leer_archivo", params={"ruta": path},
                      risk=RiskLevel.READ, reason="Operacion de solo lectura")
    path = os.path.expandvars((path or "").strip(" \"'"))
    if not path:
        plan.status = ActionStatus.ERROR
        plan.error = "sin ruta"
        plan.result = "Que archivo le leo, senor?"
        return plan
    if not os.path.isabs(path) and os.sep not in path:
        encontrado = _buscar_en_documentos(path)
        if encontrado:
            path = encontrado
    allowed, resolved = is_within_allowed(path)
    if not allowed:
        plan.status = ActionStatus.BLOCKED
        plan.result = (f"La ruta '{path}' no esta en las carpetas permitidas, "
                       "senor.")
        return plan
    try:
        if not os.path.isfile(resolved):
            plan.status = ActionStatus.ERROR
            plan.error = "no existe"
            plan.result = f"No encontre el archivo '{path}', senor."
            return plan
        if not str(resolved).lower().endswith(_TEXT_EXTS):
            plan.status = ActionStatus.ERROR
            plan.error = "formato no soportado"
            plan.result = ("Solo puedo leer archivos de texto por ahora, "
                           "senor (txt, md, csv, json...).")
            return plan
        with open(resolved, encoding="utf-8", errors="replace") as f:
            contenido = f.read()
        if not contenido.strip():
            plan.result = f"El archivo {os.path.basename(str(resolved))} esta vacio, senor."
            plan.status = ActionStatus.EXECUTED
            return plan
        recortado, truncado = _recortar(contenido)
        plan.paths_affected = [str(resolved)]
        plan.result = (f"Leo {os.path.basename(str(resolved))}, senor: "
                       f"{recortado}")
        if truncado:
            plan.result += " ... y continua, pero lo dejo ahi."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude leer el archivo: {e}"
    return plan
