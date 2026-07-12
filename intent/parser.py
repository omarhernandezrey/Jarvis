"""
JARVIS Local - Parser de intenciones deterministico (Fase 4)
Mapea lenguaje natural espanol a herramientas locales.
Sin regex fragiles. Sin Ollama. Solo keywords y extraccion de argumentos.
"""
import os
import re
from jarvis_local.intent.schemas import IntentResult
from jarvis_local.safety.permissions import is_within_allowed, is_command_blocked
from jarvis_local.tools.apps import ALLOWED_APP_NAMES

_APP_ALIASES = {
    "chrome": ["chrome", "google chrome", "navegador", "google"],
    "vscode": ["vscode", "vs code", "visual studio code", "code", "visual studio"],
    "explorador": ["explorador", "explorador de archivos", "file explorer", "archivos"],
    "powershell": ["powershell", "power shell", "ps"],
    "wsl": ["wsl", "ubuntu", "linux"],
    "terminal": ["terminal", "windows terminal", "wt", "cmd"],
    "notepad": ["notepad", "bloc de notas", "bloc", "editor de texto", "notes"],
    "calculadora": ["calculadora", "calc", "calculador"],
    "control": ["panel de control", "control panel", "control"],
    "configuracion": ["configuracion", "ajustes", "settings", "config"],
    "cmd": ["simbolo del sistema", "simbolo", "command prompt"],
    "taskmgr": ["administrador de tareas", "task manager", "taskmgr", "tareas"],
    "edge": ["edge", "microsoft edge", "msedge"],
    "firefox": ["firefox", "mozilla firefox", "mozilla"],
}


def _match_app_name(text: str) -> str | None:
    t = text.lower()
    for app_name, aliases in _APP_ALIASES.items():
        for alias in aliases:
            if alias in t:
                return app_name
    return None


# Palabras que indican que el objeto de "abrir" no es una aplicacion
_NOT_APP_WORDS = ("archivo", "carpeta", "fichero", "documento", "directorio",
                  "comando", "script", "ruta")


def _extract_app_candidate(text: str) -> str | None:
    """Extrae el posible nombre de app despues del verbo de apertura."""
    # "ejecuta" se excluye: ese verbo es para comandos (run_command)
    m = re.search(
        r'(?:abre|abrir|lanza|lanzar|inicia|iniciar)\s+'
        r'(?:la\s+|el\s+)?(?:aplicacion\s+|app\s+|programa\s+)?(.+)',
        text, re.IGNORECASE)
    if not m:
        return None
    cand = m.group(1).strip().strip('"\'').rstrip('.!?').strip()
    if not cand or any(w in cand.lower() for w in _NOT_APP_WORDS):
        return None
    return cand


def _resolve_path(path_str: str) -> str:
    """Expande variables de entorno y normaliza ruta."""
    return os.path.normpath(os.path.expandvars(path_str.strip(" \"'")))


def _extract_quoted(text: str) -> tuple[str | None, str]:
    """Extrae el primer argumento entre comillas. Retorna (argumento, resto)."""
    m = re.search(r'["\u201c]([^"]*?)["\u201d]', text)
    if m:
        return m.group(1), text[:m.start()] + " " + text[m.end():]
    return None, text


def parse_intent(message: str) -> IntentResult:
    m = message.strip()

    # --- ABRIR APLICACION ---
    if any(kw in m.lower() for kw in ["abre", "abrir", "lanza", "lanzar",
                                         "inicia", "iniciar", "ejecuta"]):
        app = _match_app_name(m)
        if app:
            return IntentResult(
                kind="tool_execute", tool="open_app", arguments={"app": app},
                reason=f"Abrir {app}")
        # No esta en los alias fijos: buscar en el indice de apps instaladas
        cand = _extract_app_candidate(m)
        if cand:
            try:
                from jarvis_local.tools.app_index import find_app
                if find_app(cand):
                    return IntentResult(
                        kind="tool_execute", tool="open_app",
                        arguments={"app": cand},
                        reason=f"Abrir {cand} (app instalada)")
            except Exception:
                pass

    # --- LISTAR ARCHIVOS ---
    m_list = re.search(
        r'(?:lista|listar|muestra|mostrar|ver?)\s+(?:los\s+)?(?:archivos|ficheros|contenido|elementos|documentos)?\s*(?:de|en|del)?\s+(.*)',
        m, re.IGNORECASE)
    if m_list:
        path = _resolve_path(m_list.group(1).strip())
        if not path or path in (".", ""):
            path = os.path.expandvars(r"%USERPROFILE%\Documents")
        allowed, _ = is_within_allowed(path)
        if allowed:
            return IntentResult(kind="tool_read", tool="list_files", arguments={"path": path},
                                reason="Operacion de solo lectura")
        return IntentResult(kind="ambiguous",
                            clarification=f"La ruta '{path}' no esta en las carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- BUSCAR ARCHIVO ---
    m_search = re.search(
        r'(?:busca|buscar|encuentra|encontrar|localiza|localizar)\s+(?:el\s+)?(?:archivo|fichero|documento)?\s*["\u201c]?([^"]+?)["\u201d]?\s*(?:en|dentro de)?\s+(.*)',
        m, re.IGNORECASE)
    if m_search:
        name = m_search.group(1).strip()
        path_str = m_search.group(2).strip()
        if not path_str:
            path_str = os.path.expandvars(r"%USERPROFILE%\Documents")
        path = _resolve_path(path_str)
        allowed, _ = is_within_allowed(path)
        if allowed:
            return IntentResult(kind="tool_read", tool="search_files",
                                arguments={"name": name, "path": path},
                                reason="Operacion de solo lectura")
        return IntentResult(kind="ambiguous",
                            clarification=f"La ruta '{path}' no esta en las carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- CREAR CARPETA ---
    m_cd = re.search(
        r'(?:crea|crear|genera|generar)\s+(?:una\s+)?(?:carpeta|directorio)\s+(?:llamada|llamado|con\s+nombre)?\s*["\u201c]?([^"]+?)["\u201d]?\s*(?:en|dentro de)?\s*(.*)',
        m, re.IGNORECASE)
    if m_cd:
        name = m_cd.group(1).strip().rstrip(".!?")
        path_str = m_cd.group(2).strip() if m_cd.group(2) else ""
        if not path_str:
            path_str = os.path.expandvars(r"%USERPROFILE%\Documents")
        path = _resolve_path(path_str)
        allowed, _ = is_within_allowed(path)
        if allowed:
            full_path = os.path.join(path, name)
            return IntentResult(kind="tool_execute", tool="create_directory",
                                arguments={"path": full_path},
                                reason="Crear carpeta")
        return IntentResult(kind="ambiguous",
                            clarification=f"La ruta '{path}' no esta en las carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- CREAR ARCHIVO ---
    m_cf = re.search(
        r'(?:crea|crear|genera|generar)\s+(?:un\s+)?(?:archivo|fichero|documento)\s+(?:llamado|llamada|con\s+nombre)?\s*["\u201c]?([^"]+?)["\u201d]?\s*(?:en|dentro de|con\s+contenido)?\s*(.*)',
        m, re.IGNORECASE)
    if m_cf:
        name = m_cf.group(1).strip().rstrip(".!?")
        rest = m_cf.group(2).strip() if m_cf.group(2) else ""
        content = ""
        path_str = os.path.expandvars(r"%USERPROFILE%\Documents")
        if "contenido" in rest.lower():
            parts = rest.split("contenido", 1)
            path_part = parts[0].strip()
            content = parts[1].strip(" :\"'") if len(parts) > 1 else ""
            if path_part:
                path_str = _resolve_path(path_part)
        elif rest:
            path_str = _resolve_path(rest)
        path = path_str
        allowed, _ = is_within_allowed(path)
        if allowed:
            full_path = os.path.join(path, name)
            return IntentResult(kind="tool_execute", tool="create_file",
                                arguments={"path": full_path, "content": content},
                                reason="Crear archivo")
        return IntentResult(kind="ambiguous",
                            clarification=f"La ruta '{path}' no esta en las carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- COPIAR ---
    m_cp = re.search(
        r'(?:copia|copiar|duplica|duplicar)\s+(.+)\s+a\s+(.+)',
        m, re.IGNORECASE)
    if m_cp:
        src = _resolve_path(m_cp.group(1).strip())
        dst = _resolve_path(m_cp.group(2).strip())
        a1, _ = is_within_allowed(src)
        a2, _ = is_within_allowed(dst)
        if a1 and a2:
            return IntentResult(kind="tool_execute", tool="copy_file",
                                arguments={"src": src, "dst": dst},
                                reason="Copiar archivo")
        return IntentResult(kind="ambiguous",
                            clarification="Una de las rutas no esta en carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- MOVER ---
    m_mv = re.search(
        r'(?:mueve|mover|traslada|trasladar)\s+(.+)\s+a\s+(.+)',
        m, re.IGNORECASE)
    if m_mv:
        src = _resolve_path(m_mv.group(1).strip())
        dst = _resolve_path(m_mv.group(2).strip())
        a1, _ = is_within_allowed(src)
        a2, _ = is_within_allowed(dst)
        if a1 and a2:
            return IntentResult(kind="tool_execute", tool="move_file",
                                arguments={"src": src, "dst": dst},
                                reason="Mover archivo")
        return IntentResult(kind="ambiguous",
                            clarification="Una de las rutas no esta en carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- RENOMBRAR ---
    if any(kw in m.lower() for kw in ["renombra", "renombrar", "cambia nombre"]):
        m_rn = re.search(
            r'(?:renombra|renombrar|cambia\s+nombre\s+(?:de|del)?)\s+(.+)\s+a\s+(.+)',
            m, re.IGNORECASE)
        if m_rn:
            src = _resolve_path(m_rn.group(1).strip())
            new_name = m_rn.group(2).strip().rstrip(".!?")
            a1, _ = is_within_allowed(src)
            if a1:
                return IntentResult(kind="tool_execute", tool="rename_file",
                                    arguments={"path": src, "new_name": new_name},
                                    reason="Renombrar archivo")
            return IntentResult(kind="ambiguous",
                                clarification="La ruta no esta en carpetas permitidas.",
                                reason="Ruta fuera de whitelist")

    # --- BORRAR ---
    m_del = re.search(
        r'(?:borra|borrar|elimina|eliminar|suprime|suprimir|quita|quitar)\s+(?:el\s+)?(?:archivo|fichero|carpeta|directorio)?\s*(.*)',
        m, re.IGNORECASE)
    if m_del:
        path = _resolve_path(m_del.group(1).strip())
        allowed, _ = is_within_allowed(path)
        if allowed:
            return IntentResult(kind="tool_plan", tool="delete_file",
                                arguments={"path": path},
                                reason="BORRADO requiere confirmacion explicita")
        return IntentResult(kind="ambiguous",
                            clarification="La ruta no esta en carpetas permitidas.",
                            reason="Ruta fuera de whitelist")

    # --- EJECUTAR COMANDO ---
    m_exec = re.search(
        r'(?:ejecuta|ejecutar|corre|correr|lanza|lanzar|run)\s+(?:el\s+)?(?:comando|orden|script)?\s*(.*)',
        m, re.IGNORECASE)
    if m_exec:
        cmd = m_exec.group(1).strip().strip("'\"")
        blocked, reason = is_command_blocked(cmd)
        if blocked:
            return IntentResult(kind="unsupported", reason=reason,
                                clarification=f"Comando bloqueado: {reason}")
        return IntentResult(kind="tool_execute", tool="run_command",
                            arguments={"command": cmd},
                            reason="Ejecutar comando")

    # --- INFO DE ARCHIVO ---
    m_info = re.search(
        r'(?:info|informacion|datos|metadatos|detalles)\s+(?:del?|sobre|acerca\s+de)?\s+(?:archivo|fichero)?\s*(.*)',
        m, re.IGNORECASE)
    if m_info:
        path = _resolve_path(m_info.group(1).strip())
        allowed, _ = is_within_allowed(path)
        if allowed:
            return IntentResult(kind="tool_read", tool="file_info",
                                arguments={"path": path}, reason="Operacion de solo lectura")

    # --- APPS (genérico, sin app especifica) ---
    if any(kw in m.lower() for kw in ["abre", "abrir", "lanza", "ejecuta"]):
        return IntentResult(kind="ambiguous",
                            clarification="Que aplicacion quieres abrir? Puedo abrir cualquier app instalada: dime su nombre (por ejemplo Chrome, WhatsApp, Word, Notion).",
                            reason="App no especificada")

    return IntentResult(kind="chat")
