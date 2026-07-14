"""
JARVIS Local - Parser de intenciones deterministico (Fase 4)
Mapea lenguaje natural espanol a herramientas locales.
Sin regex fragiles. Sin Ollama. Solo keywords y extraccion de argumentos.
"""
import os
import re

from jarvis_local.intent.schemas import IntentResult
from jarvis_local.safety.permissions import is_command_blocked, is_within_allowed

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


def _extract_close_candidate(text: str) -> str | None:
    """Extrae el posible nombre de app despues del verbo de cierre."""
    m = re.search(
        r'(?:cierra|cierrame|cerrar|termina|terminar|finaliza|finalizar)\s+'
        r'(?:la\s+|el\s+)?(?:aplicacion\s+|app\s+|programa\s+)?(.+)',
        text, re.IGNORECASE)
    if not m:
        return None
    cand = m.group(1).strip().strip('"\'').rstrip('.!?').strip()
    if not cand or any(w in cand.lower() for w in _NOT_APP_WORDS) \
            or "jarvis" in cand.lower():
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


# Extensiones que indican archivo local, no sitio web
_FILE_EXTS = (".exe", ".msc", ".bat", ".cmd", ".txt", ".pdf", ".doc", ".docx",
              ".xls", ".xlsx", ".png", ".jpg", ".mp3", ".mp4", ".zip", ".py")


def _looks_like_domain(text: str) -> bool:
    t = text.strip().lower()
    if " " in t or "\\" in t:
        return False
    if t.endswith(_FILE_EXTS):
        return False
    return bool(re.match(r'^(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?$', t))


_NUM_WORDS = {"primera": 1, "uno": 1, "una": 1, "segunda": 2, "dos": 2,
              "tercera": 3, "tres": 3, "cuarta": 4, "cuatro": 4,
              "quinta": 5, "cinco": 5}


def _parse_fase5(m: str) -> IntentResult | None:
    """Intents de Fase 5: empleo en Computrabajo y navegador automatizado."""
    low = m.lower()

    # --- ABRIR OFERTA N ---
    m_open = re.search(r'(?:abre|abrir|muestra|ver)\s+(?:la\s+)?(?:oferta|vacante|empleo)\s+(?:numero\s+)?(\w+)', low)
    if m_open:
        tok = m_open.group(1)
        num = int(tok) if tok.isdigit() else _NUM_WORDS.get(tok, 0)
        if num:
            return IntentResult(kind="tool_execute", tool="open_job",
                                arguments={"number": num},
                                reason=f"Abrir oferta {num}")

    # --- BUSCAR EMPLEO ---
    m_job = re.search(
        r'(?:busca(?:r|me)?|encuentra|consigueme|quiero|hay)\s+(?:un\s+|una\s+)?'
        r'(?:trabajo|empleo|vacante(?:s)?|oferta(?:s)?)\s*'
        r'(?:de\s+|como\s+|para\s+)?(.*)', low)
    if m_job and re.search(r'\b(trabajo|empleo|vacante|oferta)', low):
        resto = m_job.group(1).strip().rstrip('.!?')
        ciudad = ""
        m_ciudad = re.search(r'\s+en\s+(.+)$', resto)
        if m_ciudad:
            ciudad = m_ciudad.group(1).strip()
            resto = resto[:m_ciudad.start()].strip()
        puesto = resto.strip()
        if not puesto:
            return IntentResult(
                kind="ambiguous",
                clarification=("De que cargo busco empleo, senor? Por ejemplo: "
                               "'busca trabajo de desarrollador en Bogota'."),
                reason="Cargo no especificado")
        return IntentResult(kind="tool_read", tool="search_jobs",
                            arguments={"puesto": puesto, "ciudad": ciudad},
                            reason=f"Buscar empleo de {puesto}")

    # --- MOSTRAR OFERTAS EN EL NAVEGADOR ---
    if re.search(r'\b(muestra(?:me)?|abre|ver)\b.*\b(ofertas|vacantes|empleos|computrabajo)\b', low):
        return IntentResult(kind="tool_execute", tool="show_jobs",
                            arguments={"puesto": "", "ciudad": ""},
                            reason="Mostrar ofertas en el navegador")

    # --- NAVEGADOR AUTOMATIZADO ---
    m_nav = re.search(r'(?:navega|navegar|controla\s+el\s+navegador)\s+(?:a|hasta|hacia)?\s*(.+)', low)
    if m_nav:
        return IntentResult(kind="tool_execute", tool="browser_navigate",
                            arguments={"url": m_nav.group(1).strip().rstrip('.!?')},
                            reason="Navegar con el navegador controlado")

    if re.search(r'\b(cierra|cerrar)\s+(?:el\s+)?navegador\b', low):
        return IntentResult(kind="tool_execute", tool="close_browser",
                            reason="Cerrar navegador automatizado")

    return None


def _parse_fase4(m: str) -> IntentResult | None:
    """Intents de Fase 4: clima, web, sistema, wikipedia, correo, etc."""
    low = m.lower()

    # --- CLIMA ---
    if re.search(r'\b(clima|temperatura)\b', low):
        m_city = re.search(r'\b(?:clima|temperatura)\b(?:\s+\w+)?\s+(?:en|de)\s+(.+)',
                           low)
        city = m_city.group(1).strip().rstrip('.!?') if m_city else ""
        return IntentResult(kind="tool_read", tool="weather",
                            arguments={"city": city},
                            reason="Consultar clima")

    # --- UBICACION / DISTANCIA ---
    m_loc = re.search(
        r'(?:donde\s+queda|donde\s+esta|ubicacion\s+de|ubica|distancia\s+(?:a|hasta|entre\s+aqui\s+y)|que\s+tan\s+lejos\s+(?:esta|queda))\s+(.+)',
        low)
    if m_loc:
        place = m_loc.group(1).strip().rstrip('.!?')
        if place and not any(w in place for w in _NOT_APP_WORDS):
            return IntentResult(kind="tool_execute", tool="locate",
                                arguments={"place": place},
                                reason="Ubicar lugar en el mapa")

    # --- ESTADO DEL SISTEMA ---
    if re.search(r'\b(estado del sistema|uso de ram|uso de cpu|uso de memoria|'
                 r'bateria|cuanta ram|cuanta memoria|rendimiento del (?:sistema|equipo|pc))\b', low):
        return IntentResult(kind="tool_read", tool="system_status",
                            reason="Consultar estado del sistema")

    # --- EVENTOS (GOOGLE CALENDAR) ---
    if re.search(r'\b(proximos eventos|mis eventos|que eventos tengo|'
                 r'mi agenda|eventos del calendario|mi calendario)\b', low):
        return IntentResult(kind="tool_read", tool="calendar_events",
                            reason="Consultar Google Calendar")

    # --- BUSCAR EN GOOGLE ---
    m_gg = re.search(r'(?:busca|buscar|googlea|googlear)\s+(.+?)\s+en\s+google\b', low) \
        or re.search(r'busca(?:r)?\s+en\s+google\s+(.+)', low) \
        or re.search(r'googlea(?:r)?\s+(.+)', low)
    if m_gg:
        return IntentResult(kind="tool_execute", tool="google_search",
                            arguments={"query": m_gg.group(1).strip().rstrip('.!?')},
                            reason="Buscar en Google")

    # --- YOUTUBE / MUSICA ---
    m_yt = re.search(r'(?:reproduce|reproducir|pon|toca|tocar)\s+(.+?)\s+en\s+youtube\b', low)
    if m_yt:
        return IntentResult(kind="tool_execute", tool="youtube_play",
                            arguments={"query": m_yt.group(1).strip()},
                            reason="Reproducir en YouTube")
    if re.search(r'\b(?:pon|toca|reproduce)\s+(?:algo de\s+)?musica\b', low):
        m_song = re.search(r'musica\s+(?:de\s+)?(.+)', low)
        song = m_song.group(1).strip().rstrip('.!?') if m_song else ""
        return IntentResult(kind="tool_execute", tool="play_music",
                            arguments={"song": song},
                            reason="Reproducir musica local")
    m_play = re.search(r'(?:reproduce|reproducir)\s+(?:la\s+cancion\s+|el\s+video\s+)?(.+)', low)
    if m_play:
        return IntentResult(kind="tool_execute", tool="youtube_play",
                            arguments={"query": m_play.group(1).strip().rstrip('.!?')},
                            reason="Reproducir en YouTube")

    # --- NOTICIAS ---
    if re.search(r'\b(noticias|titulares)\b', low):
        return IntentResult(kind="tool_read", tool="news_headlines",
                            reason="Consultar titulares")

    # --- CORREO ---
    if re.search(r'\b(?:envia|enviar|manda|mandar)\b.*\b(?:correo|email|mail)\b', low):
        m_to = re.search(r'\b(?:a|para)\s+([\w.+-]+@[\w.-]+|\w+)', low)
        m_subj = re.search(r'\basunto\s*[:]?\s*(.+?)(?=\s+(?:mensaje|contenido|cuerpo|que diga)\b|$)', m, re.IGNORECASE)
        m_body = re.search(r'\b(?:mensaje|contenido|cuerpo|que diga)\s*[:]?\s*(.+)', m, re.IGNORECASE)
        if m_to and m_subj and m_body:
            return IntentResult(
                kind="tool_plan", tool="send_email",
                arguments={"to": m_to.group(1),
                           "subject": m_subj.group(1).strip(),
                           "body": m_body.group(1).strip()},
                reason="Enviar correo requiere confirmacion")
        return IntentResult(
            kind="ambiguous",
            clarification=('Para enviar un correo diga: "envia un correo a '
                           '<destinatario> asunto <asunto> mensaje <contenido>".'),
            reason="Faltan datos del correo")

    # --- CALCULAR (solo si hay numeros o constantes; si no, va al LLM) ---
    m_calc = re.search(r'\b(?:calcula(?:r)?|cuanto\s+es)\s+(.+)', low)
    if m_calc and re.search(r'\d|\bpi\b|\braiz\b', m_calc.group(1)):
        return IntentResult(kind="tool_read", tool="calculate",
                            arguments={"expression": m_calc.group(1).strip()},
                            reason="Calculo matematico local")

    # --- WOLFRAMALPHA ---
    m_wa = re.search(r'(?:pregunta(?:le)?\s+a\s+wolfram(?:alpha)?|wolfram)\s*[:]?\s*(.+)', low)
    if m_wa:
        return IntentResult(kind="tool_read", tool="wolfram",
                            arguments={"question": m_wa.group(1).strip()},
                            reason="Consultar WolframAlpha")

    # --- TOMAR NOTA ---
    m_note = re.search(r'\b(?:toma\s+nota|apunta|anota)\b\s*(?:de\s+|que\s+|:\s*)?(.+)',
                       m, re.IGNORECASE)
    if m_note:
        return IntentResult(kind="tool_execute", tool="take_note",
                            arguments={"text": m_note.group(1).strip()},
                            reason="Guardar nota")

    # --- CHISTE ---
    if re.search(r'\b(chiste|hazme reir|algo gracioso|cuentame algo divertido)\b', low):
        return IntentResult(kind="tool_read", tool="tell_joke",
                            reason="Contar un chiste")

    # --- DIRECCION IP ---
    if re.search(r'\b(mi ip|direccion ip|cual es (?:mi|la) ip)\b', low):
        return IntentResult(kind="tool_read", tool="get_ip",
                            reason="Consultar direccion IP")

    # --- CAMBIAR VENTANA ---
    if re.search(r'\b(cambia(?:r)?\s+(?:de\s+)?ventana|siguiente ventana|alt tab)\b', low):
        return IntentResult(kind="tool_execute", tool="switch_window",
                            reason="Cambiar de ventana")

    # --- CAPTURA DE PANTALLA ---
    if re.search(r'\b(captura de pantalla|toma una captura|haz una captura|'
                 r'screenshot|pantallazo)\b', low):
        m_name = re.search(r'(?:llamada|llamado|con\s+(?:el\s+)?nombre|como)\s+(.+)',
                           m, re.IGNORECASE)
        name = m_name.group(1).strip().strip('"\'').rstrip('.!?') if m_name else ""
        return IntentResult(kind="tool_execute", tool="screenshot",
                            arguments={"name": name},
                            reason="Captura de pantalla")

    # --- OCULTAR / MOSTRAR ARCHIVOS ---
    m_hide = re.search(r'oculta(?:r)?\s+(?:todos\s+)?(?:los\s+)?archivos\s+(?:de|en)\s+(.+)',
                       m, re.IGNORECASE)
    if m_hide:
        return IntentResult(kind="tool_plan", tool="hide_files",
                            arguments={"path": m_hide.group(1).strip(), "hide": True},
                            reason="Ocultar archivos requiere confirmacion")
    m_show = re.search(r'(?:muestra|mostrar|desoculta(?:r)?|haz\s+visibles)\s+(?:todos\s+)?(?:los\s+)?archivos\s+ocultos\s+(?:de|en)\s+(.+)',
                       m, re.IGNORECASE)
    if m_show:
        return IntentResult(kind="tool_plan", tool="hide_files",
                            arguments={"path": m_show.group(1).strip(), "hide": False},
                            reason="Mostrar archivos requiere confirmacion")

    # --- ABRIR SITIO WEB ---
    m_web = re.search(r'(?:abre|abrir|ve\s+a|entra\s+a|navega\s+a)\s+(?:la\s+|el\s+)?'
                      r'(?:pagina(?:\s+web)?|sitio(?:\s+web)?|web)\s+(?:de\s+)?(.+)',
                      low)
    if m_web:
        return IntentResult(kind="tool_execute", tool="open_website",
                            arguments={"site": m_web.group(1).strip().rstrip('.!?')},
                            reason="Abrir sitio web")
    m_open = re.search(r'(?:abre|abrir|ve\s+a|entra\s+a|navega\s+a)\s+(.+)', low)
    if m_open and _looks_like_domain(m_open.group(1).strip().rstrip('.!?')):
        return IntentResult(kind="tool_execute", tool="open_website",
                            arguments={"site": m_open.group(1).strip().rstrip('.!?')},
                            reason="Abrir sitio web")

    return None


# Muletillas de cortesia: no aportan intencion y ensucian el analisis.
# "hazme el favor y abre el whatsapp" tiene el verbo "hazme", pero no es una
# accion: es una formula. Sin quitarla, se contaba como una segunda accion y la
# frase se tomaba por multi-accion.
_CORTESIA = re.compile(
    r'\b(?:hazme\s+el\s+favor\s+(?:de\s+|y\s+)?|hagame\s+el\s+favor\s+(?:de\s+|y\s+)?|'
    r'por\s+favor|podrias|podria|puedes|puede|quisiera\s+que|'
    r'necesito\s+que|quiero\s+que|me\s+gustaria\s+que)\b',
    re.IGNORECASE)

# Verbos que introducen una accion ejecutable.
_VERBO_ACCION = re.compile(
    r'\b(?:abre|abreme|abrir|cierra|cerrar|busca|buscame|buscar|pon|ponme|'
    r'reproduce|toma|tomame|manda|mandame|envia|enviame|lanza|inicia|muestra|'
    r'muestrame|dime|dame|ejecuta|corre|borra|elimina|crea|apunta|anota|'
    r'calcula|navega|listar|lista)\b',
    re.IGNORECASE)

# Conectores secuenciales inequivocos: "y luego", "y despues", "y tambien"...
_CONECTOR_SECUENCIAL = re.compile(
    r'\b(?:y\s+(?:luego|despues|tambien|ademas|de\s+paso|acto\s+seguido)|'
    r'luego\b|despues\b|acto\s+seguido)', re.IGNORECASE)


def es_multi_accion(message: str) -> bool:
    """La frase pide DOS o mas acciones.

    El parser resuelve una sola intencion: si intenta estas, ejecuta la primera
    mitad y descarta la segunda en silencio.

    Se exige (a) dos verbos de accion unidos por "y", o (b) un conector
    secuencial explicito. Contar verbos a secas daria falsos positivos con las
    formulas de cortesia, por eso se quitan antes.
    """
    limpio = _CORTESIA.sub(" ", message)
    verbos = _VERBO_ACCION.findall(limpio)
    if len(verbos) >= 2 and re.search(r'\by\b', limpio, re.IGNORECASE):
        return True
    return bool(_CONECTOR_SECUENCIAL.search(limpio)) and len(verbos) >= 1


# Punto de corte entre las dos acciones: "... Y (LUEGO) abre chrome"
_CORTE = re.compile(
    r'\s*\b(?:y\s+(?:luego|despues|tambien|ademas|de\s+paso|acto\s+seguido)\s+|'
    r'y\s+(?=(?:abre|abreme|cierra|busca|buscame|pon|ponme|reproduce|toma|'
    r'manda|envia|lanza|inicia|muestra|muestrame|dime|dame|ejecuta|corre|'
    r'borra|elimina|crea|apunta|anota|calcula|navega)\b)|'
    r'(?:luego|despues|acto\s+seguido)\s+(?=\w))\s*',
    re.IGNORECASE)


def dividir_acciones(message: str) -> list[str]:
    """Parte una peticion multi-accion en sus clausulas.

    Se hace aqui, de forma determinista, porque el modelo de 3B NO encadena por
    su cuenta: aun devolviendole el resultado de la primera herramienta, no pide
    la segunda (medido: 0/2 en los casos encadenados de la bateria). Dividir la
    frase y correr el agente sobre cada mitad es fiable y no depende de una
    capacidad que el modelo local no tiene.
    """
    if not es_multi_accion(message):
        return [message]
    partes = [p.strip(" ,.;") for p in _CORTE.split(_CORTESIA.sub(" ", message))]
    partes = [p for p in partes if p and _VERBO_ACCION.search(p)]
    return partes if len(partes) >= 2 else [message]


# Conectores de continuidad al inicio: son muletillas, no referencias.
# "ahora abre whatsapp" trae su propio objeto (whatsapp) y se resuelve sola.
_MULETILLA_INICIAL = re.compile(r'^\s*(?:y|ahora|luego|entonces|despues)\b[,\s]*',
                                re.IGNORECASE)

# Referencias que NO nombran su objeto: hay que ir a buscarlo al turno anterior.
_DEICTICO = re.compile(
    r'\b(?:la|el|lo)\s+(?:primera?|segunda?|tercera?|cuarta?|quinta?|'
    r'anterior|ultima?|mismo)\b|'
    r'\b(?:eso|esa|ese|esos|esas|aquello|ahi|alli)\b',
    re.IGNORECASE)


def es_anaforica(message: str) -> bool:
    """La frase NO se entiende sin el turno anterior.

    Cuidado con pasarse: "ahora abre whatsapp" empieza con un conector, pero
    nombra su objeto y se resuelve sola. Si se la manda al agente por
    "anaforica", se pierde el camino rapido del parser y el modelo pequeno falla.
    Solo son anaforicas las que apuntan a algo sin nombrarlo ("abreme la
    segunda") o a las que les falta el verbo/objeto ("y en Bogota?").
    """
    if _DEICTICO.search(message):
        return True
    resto = _MULETILLA_INICIAL.sub("", message).strip()
    if resto == message.strip():
        return False  # no empezaba por conector: es una frase autonoma
    # Empezaba por conector: solo es anaforica si lo que queda no se sostiene
    # solo, es decir, si no trae un verbo de accion ("y en Bogota?").
    return not _VERBO_ACCION.search(resto)


def parse_intent(message: str) -> IntentResult:
    m = message.strip()

    # Peticion con dos acciones: el parser solo sabe resolver una y descartaria
    # la otra sin avisar. Que la maneje el agente (encadena herramientas).
    if es_multi_accion(m):
        return IntentResult(kind="chat", reason="Peticion multi-accion: la resuelve el agente")

    # Referencia a un turno anterior: el parser no tiene contexto y acabaria
    # inventando el argumento. Que la resuelva el agente, que si lo tiene.
    if es_anaforica(m):
        return IntentResult(kind="chat", reason="Referencia al contexto: la resuelve el agente")

    # --- FASE 5: empleo y navegador automatizado (antes que fase4 para
    #     que "busca trabajo ... en bogota" no se confunda con Google) ---
    fase5 = _parse_fase5(m)
    if fase5 is not None:
        return fase5

    # --- FASE 4: clima, web, sistema, wikipedia, correo, etc. ---
    fase4 = _parse_fase4(m)
    if fase4 is not None:
        return fase4

    # --- WIKIPEDIA (despues de fase4 para no robar "hablame del clima...") ---
    m_wiki = re.search(
        r'(?:quien\s+(?:es|fue|era)|hablame\s+(?:de|sobre)|que\s+sabes\s+(?:de|sobre)|'
        r'cuentame\s+(?:de|sobre|acerca\s+de))\s+(.+)',
        m, re.IGNORECASE)
    if m_wiki:
        topic = m_wiki.group(1).strip().rstrip('.!?')
        low_topic = topic.lower()
        if topic and not any(w in low_topic for w in ("ti", "tu", "jarvis", "usted")):
            return IntentResult(kind="tool_read", tool="wiki",
                                arguments={"topic": topic},
                                reason="Consultar Wikipedia")

    # --- CERRAR APLICACION ---
    # (despues de fase5, para que "cierra el navegador" siga siendo
    #  close_browser, el Chrome automatizado de Selenium)
    if re.search(r'\b(?:cierra|cierrame|cerrar)\b', m, re.IGNORECASE):
        low = m.lower()
        # "cierra todos los programas", "cierra todas las apps", "cierra todo"
        if re.search(r'\b(?:cierra|cierrame|cerrar)\b.*\btod(?:o|os|as)\b', low) \
                and (re.search(r'\b(?:programas?|aplicaciones|apps?|ventanas)\b', low)
                     or re.search(r'\b(?:cierra|cierrame|cerrar)\s+todo\b', low)):
            return IntentResult(kind="tool_execute", tool="close_all_apps",
                                reason="Cerrar todos los programas abiertos")
        app = _match_app_name(m)
        if app:
            return IntentResult(kind="tool_execute", tool="close_app",
                                arguments={"app": app},
                                reason=f"Cerrar {app}")
        cand = _extract_close_candidate(m)
        if cand:
            return IntentResult(kind="tool_execute", tool="close_app",
                                arguments={"app": cand},
                                reason=f"Cerrar {cand}")

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
    # El objeto ("archivos", "carpeta"...) es OBLIGATORIO y los verbos van con
    # \b. Sin eso, el patron viejo (ver? sin delimitador y objeto opcional)
    # capturaba la silaba "ver" dentro de "llo-ver-": "va a llover en Medellin"
    # se enrutaba a listar_archivos con path="Medellin".
    m_list = re.search(
        r'\b(?:lista|listar|muestra|mostrar|ver)\b\s+(?:los\s+|las\s+|el\s+|la\s+)?'
        r'\b(?:archivos|ficheros|contenido|elementos|documentos|carpeta|directorio)\b'
        r'\s*(?:de|en|del)?\s*(.*)',
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
    # Alta precision: solo enruta aqui si hay una senal INEQUIVOCA de que se
    # busca un archivo, y no cualquier cosa. Antes el sustantivo era opcional,
    # asi que "busca" a secas y "busca pega de disenador" caian en buscar_archivo.
    # Ahora se exige el sustantivo (archivo/fichero/documento) O un nombre con
    # extension (informe.pdf). Lo demas lo decide el LLM, no una regex.
    m_search = (
        re.search(
            r'\b(?:busca|buscar|encuentra|encontrar|localiza|localizar)\b\s+(?:el\s+|la\s+)?'
            r'\b(?:archivo|fichero|documento)\b\s*'
            r'["\u201c]?([^"]+?)["\u201d]?\s*(?:en|dentro de)\s+(.*)',
            m, re.IGNORECASE)
        or re.search(
            r'\b(?:busca|buscar|encuentra|encontrar|localiza|localizar)\b\s+'
            r'["\u201c]?([^\s"]+\.\w{2,5})["\u201d]?\s*(?:en|dentro de)\s+(.*)',
            m, re.IGNORECASE)
    )
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
