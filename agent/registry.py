"""
JARVIS Local - Registro de herramientas (Fase 6)
Fuente unica de verdad: cada herramienta define su esquema JSON (para que el
LLM sepa cuando y como llamarla) y su ejecutor (la funcion real).

El LLM recibe estos esquemas via tool calling nativo de Ollama y decide cual
usar. Las herramientas de riesgo (borrar, correo, ocultar) devuelven un plan
que exige /confirmar: el modelo NUNCA ejecuta acciones destructivas por si solo.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from jarvis_local.safety.policy import ActionPlan, ActionStatus


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict           # JSON Schema de los argumentos
    run: Callable[..., object]  # devuelve ActionPlan o str
    needs_confirmation: bool = False
    aliases: list[str] = field(default_factory=list)

    def schema(self) -> dict:
        """Formato de tool calling de Ollama/OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props,
            "required": required or list(props.keys())}


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


# --- Ejecutores (import perezoso: arrancar JARVIS no debe cargar todo) ---

def _open_app(app: str):
    from jarvis_local.tools.apps import open_app
    return open_app(app)


def _close_app(app: str):
    from jarvis_local.tools.apps import close_app
    return close_app(app)


def _close_all_apps():
    from jarvis_local.tools.apps import close_all_apps
    return close_all_apps()


def _set_reminder(texto: str, minutos: int = 0, hora: str = ""):
    from jarvis_local.tools.reminders import set_reminder
    return set_reminder(texto, minutos, hora)


def _list_reminders():
    from jarvis_local.tools.reminders import list_reminders
    return list_reminders()


def _cancel_reminder(cual: str = "todos"):
    from jarvis_local.tools.reminders import cancel_reminder
    return cancel_reminder(cual)


def _send_whatsapp(para: str, mensaje: str):
    from jarvis_local.tools.whatsapp import send_whatsapp
    return send_whatsapp(para, mensaje)


def _window_control(accion: str):
    from jarvis_local.tools.desktop_actions import minimize_all, snap_window
    accion = (accion or "").lower()
    if accion in ("minimizar_todo", "escritorio", "todo"):
        return minimize_all()
    return snap_window(accion)


def _daily_briefing():
    from jarvis_local.tools.briefing import daily_briefing
    return daily_briefing()


def _read_clipboard():
    from jarvis_local.tools.reader import read_clipboard
    return read_clipboard()


def _read_file(ruta: str):
    from jarvis_local.tools.reader import read_file_aloud
    return read_file_aloud(ruta)


def _power_control(accion: str):
    from jarvis_local.tools import power
    accion = (accion or "").lower()
    if accion in ("bloquear", "bloqueo"):
        return power.lock_pc()
    if accion == "apagar":
        return power.shutdown_pc()
    if accion == "reiniciar":
        return power.restart_pc()
    if accion in ("suspender", "dormir", "hibernar"):
        return power.suspend_pc()
    if accion in ("cancelar", "cancelar_apagado"):
        return power.cancel_shutdown()
    return f"No entiendo la accion de energia '{accion}'."


def _volume_control(accion: str, nivel: int = 50):
    from jarvis_local.tools import media_controls as mc
    accion = (accion or "").lower()
    if accion in ("subir", "sube", "aumentar"):
        return mc.volume_up()
    if accion in ("bajar", "baja", "reducir"):
        return mc.volume_down()
    if accion in ("silenciar", "mute", "silencio"):
        return mc.volume_mute(True)
    if accion in ("activar", "desmutear", "sonido"):
        return mc.volume_mute(False)
    if accion in ("nivel", "fijar", "poner"):
        return mc.set_volume(int(nivel))
    return f"No entiendo la accion de volumen '{accion}'."


def _media_control(accion: str):
    from jarvis_local.tools import media_controls as mc
    accion = (accion or "").lower()
    if accion in ("pausar", "pausa", "reanudar", "reproducir"):
        return mc.media_play_pause()
    if accion in ("siguiente", "proxima"):
        return mc.media_next()
    if accion in ("anterior", "previa"):
        return mc.media_previous()
    return f"No entiendo la accion multimedia '{accion}'."


def _list_files(path: str = ""):
    import os

    from jarvis_local.tools.files import list_files
    return list_files(path or os.path.expandvars(r"%USERPROFILE%\Documents"))


def _search_files(name: str, path: str = ""):
    import os

    from jarvis_local.tools.files import search_files
    return search_files(name, path or os.path.expandvars(r"%USERPROFILE%\Documents"))


def _create_directory(path: str):
    from jarvis_local.tools.files import create_directory
    return create_directory(path)


def _create_file(path: str, content: str = ""):
    from jarvis_local.tools.files import create_file
    return create_file(path, content)


def _delete_file(path: str):
    from jarvis_local.safety.policy import policy
    from jarvis_local.tools.files import plan_delete
    plan = plan_delete(path)
    policy.pending_plan = plan
    return plan


def _run_command(command: str):
    from jarvis_local.tools.terminal import execute_command
    return execute_command(command)


def _weather(city: str = ""):
    from jarvis_local.tools.location import my_location
    from jarvis_local.tools.weather import get_weather
    if not city:
        loc = my_location()
        city = loc["city"] if loc else ""
    if not city:
        return "De que ciudad desea saber el clima, senor?"
    return get_weather(city)


def _locate(place: str):
    from jarvis_local.tools.location import locate
    return locate(place)


def _system_status():
    from jarvis_local.tools.system_info import system_status
    return system_status()


def _wiki(topic: str):
    from jarvis_local.tools.wiki import wiki_summary
    return wiki_summary(topic)


def _news():
    from jarvis_local.tools.news import headlines
    return headlines()


def _calculate(expression: str):
    from jarvis_local.tools.calculator import calculate
    from jarvis_local.tools.wolfram import ask_wolfram, has_app_id
    plan = calculate(expression)
    if plan.status == ActionStatus.ERROR and has_app_id():
        wa = ask_wolfram(expression)
        if wa.status != ActionStatus.ERROR:
            return wa
    return plan


def _wolfram(question: str):
    from jarvis_local.tools.wolfram import ask_wolfram
    return ask_wolfram(question)


def _joke():
    from jarvis_local.tools.jokes import tell_joke
    return tell_joke()


def _get_ip():
    from jarvis_local.tools.ip_info import get_ip
    return get_ip()


def _calendar():
    from jarvis_local.tools.gcalendar import upcoming_events
    return upcoming_events()


def _open_website(site: str):
    from jarvis_local.tools.web import open_website
    return open_website(site)


def _google(query: str):
    from jarvis_local.tools.web import google_search
    return google_search(query)


def _youtube(query: str):
    from jarvis_local.tools.web import youtube_play
    return youtube_play(query)


def _play_music(song: str = ""):
    from jarvis_local.tools.desktop_actions import play_music
    return play_music(song)


def _take_note(text: str):
    from jarvis_local.tools.notes import take_note
    return take_note(text)


def _screenshot(name: str = ""):
    from jarvis_local.tools.desktop_actions import take_screenshot
    return take_screenshot(name)


def _switch_window():
    from jarvis_local.tools.desktop_actions import switch_window
    return switch_window()


def _send_email(to: str, subject: str, body: str):
    from jarvis_local.tools.email_sender import plan_email
    return plan_email(to, subject, body)


def _hide_files(path: str, hide: bool = True):
    from jarvis_local.tools.hidden_files import plan_hide
    return plan_hide(path, hide)


def _search_jobs(puesto: str, ciudad: str = ""):
    from jarvis_local.tools.jobs import search_jobs
    return search_jobs(puesto, ciudad)


def _open_job(number: int):
    from jarvis_local.tools.jobs import open_job
    return open_job(int(number))


def _show_jobs(puesto: str = "", ciudad: str = ""):
    from jarvis_local.tools.browser import show_jobs_in_browser
    return show_jobs_in_browser(puesto, ciudad)


def _browser_navigate(url: str):
    from jarvis_local.tools.browser import navigate
    return navigate(url)


def _close_browser():
    from jarvis_local.tools.browser import close_browser
    return close_browser()


def _remember(text: str):
    from jarvis_local.config import BASE_DIR
    from jarvis_local.storage.memory import MemoryStore
    mem = MemoryStore(BASE_DIR / "data")
    item = mem.add(text)
    return (f"Lo recordare, senor: {text}" if item
            else "No pude guardar la memoria (limite alcanzado).")


# --- Definicion de las herramientas ---

TOOLS: list[Tool] = [
    # Aplicaciones y sistema
    Tool("abrir_aplicacion",
         "Abre cualquier aplicacion instalada en el computador por su nombre "
         "(Chrome, WhatsApp, Word, VS Code, Spotify, WSL/Ubuntu, calculadora...). "
         "Usar cuando el usuario pida abrir, lanzar o iniciar un programa.",
         _obj({"app": _str("Nombre de la aplicacion, ej: 'whatsapp', 'chrome', 'word'")}),
         _open_app),

    Tool("cerrar_aplicacion",
         "Cierra una aplicacion o programa abierto por su nombre (Word, Chrome, "
         "WhatsApp, Spotify, calculadora...). Usar cuando el usuario pida "
         "cerrar, terminar o salir de un programa.",
         _obj({"app": _str("Nombre de la aplicacion a cerrar, ej: 'word', 'chrome'")}),
         _close_app),

    Tool("cerrar_todas_aplicaciones",
         "Cierra de una sola vez todos los programas que JARVIS abrio en esta "
         "sesion. Usar cuando el usuario pida cerrar todo o todos los programas.",
         _obj({}, []), _close_all_apps),

    Tool("controlar_volumen",
         "Controla el volumen del computador: subir, bajar, silenciar, activar "
         "el sonido o fijarlo a un nivel exacto (0-100).",
         _obj({"accion": _str("Una de: subir, bajar, silenciar, activar, nivel"),
               "nivel": _int("Nivel 0-100, solo si accion=nivel")}, ["accion"]),
         _volume_control),

    Tool("controlar_musica",
         "Controla la reproduccion multimedia en curso (Spotify, YouTube, "
         "etc.): pausar/reanudar, siguiente cancion o cancion anterior.",
         _obj({"accion": _str("Una de: pausar, siguiente, anterior")}),
         _media_control),

    Tool("crear_recordatorio",
         "Programa un recordatorio con alarma que sonara y hablara a la hora "
         "indicada. Usar cuando el usuario diga 'recuerdame en X minutos...' "
         "o 'avisame a las 3...'.",
         _obj({"texto": _str("Que hay que recordar"),
               "minutos": _int("Dentro de cuantos minutos avisar (0 si se usa hora)"),
               "hora": _str("Hora exacta en formato 24h HH:MM, ej '15:30'. Vacio si se usan minutos")},
              ["texto"]),
         _set_reminder),

    Tool("listar_recordatorios",
         "Lista los recordatorios y alarmas pendientes del usuario.",
         _obj({}, []), _list_reminders),

    Tool("cancelar_recordatorio",
         "Cancela recordatorios pendientes: por numero, por texto o todos.",
         _obj({"cual": _str("Numero del recordatorio, parte del texto, o 'todos'")}, []),
         _cancel_reminder),

    Tool("enviar_whatsapp",
         "Abre WhatsApp con un mensaje ya escrito para un contacto o numero. "
         "NO lo envia: el usuario solo pulsa enviar. Usar cuando pidan mandar "
         "un whatsapp o mensaje a alguien.",
         _obj({"para": _str("Nombre del contacto o numero de telefono"),
               "mensaje": _str("El texto del mensaje")}),
         _send_whatsapp),

    Tool("organizar_ventanas",
         "Organiza las ventanas del escritorio: minimizar todas, o poner la "
         "ventana activa a la izquierda, derecha, maximizarla o minimizarla.",
         _obj({"accion": _str("Una de: minimizar_todo, izquierda, derecha, "
                              "maximizar, minimizar")}),
         _window_control),

    Tool("resumen_del_dia",
         "Da un resumen completo del dia: fecha, clima actual, agenda del "
         "calendario y titulares de noticias, todo en una sola respuesta.",
         _obj({}, []), _daily_briefing),

    Tool("leer_portapapeles",
         "Lee en voz alta el texto que el usuario tiene copiado en el "
         "portapapeles.",
         _obj({}, []), _read_clipboard),

    Tool("leer_archivo",
         "Lee en voz alta el contenido de un archivo de texto (txt, md, csv, "
         "json) de las carpetas permitidas.",
         _obj({"ruta": _str("Ruta o nombre del archivo, ej 'notas.txt'")}),
         _read_file),

    Tool("energia_del_equipo",
         "Bloquear la sesion, apagar, reiniciar o suspender el computador, o "
         "cancelar un apagado programado. Apagar y reiniciar dan 60 segundos "
         "cancelables. NO usar para cerrar programas ni para apagar el sonido.",
         _obj({"accion": _str("Una de: bloquear, apagar, reiniciar, suspender, cancelar")}),
         _power_control),

    Tool("estado_del_sistema",
         "Informa el uso de CPU, memoria RAM, disco y el estado de la bateria "
         "de este computador.",
         _obj({}, []), _system_status),

    Tool("ejecutar_comando",
         "Ejecuta un comando de PowerShell en el computador. Solo para comandos "
         "de consulta seguros (dir, ipconfig, git status). Los comandos "
         "destructivos estan bloqueados.",
         _obj({"command": _str("El comando de PowerShell a ejecutar")}),
         _run_command),

    # Archivos
    Tool("listar_archivos",
         "Lista los archivos y carpetas de un directorio permitido "
         "(Documentos, Descargas, Escritorio, Musica, Imagenes, Videos).",
         _obj({"path": _str("Ruta de la carpeta. Vacio = Documentos")}, []),
         _list_files),

    Tool("buscar_archivo",
         "Busca archivos por nombre dentro de una carpeta permitida.",
         _obj({"name": _str("Nombre o parte del nombre del archivo"),
               "path": _str("Carpeta donde buscar. Vacio = Documentos")}, ["name"]),
         _search_files),

    Tool("crear_carpeta",
         "Crea una carpeta nueva en una ruta permitida.",
         _obj({"path": _str("Ruta completa de la carpeta a crear")}),
         _create_directory),

    Tool("crear_archivo",
         "Crea un archivo de texto con contenido en una ruta permitida.",
         _obj({"path": _str("Ruta completa del archivo"),
               "content": _str("Contenido del archivo")}, ["path"]),
         _create_file),

    Tool("borrar_archivo",
         "Prepara el borrado de un archivo. NO borra de inmediato: crea un plan "
         "que el usuario debe confirmar con /confirmar.",
         _obj({"path": _str("Ruta del archivo a borrar")}),
         _delete_file, needs_confirmation=True),

    Tool("ocultar_archivos",
         "Oculta (o vuelve visibles) todos los archivos de una carpeta. Requiere "
         "confirmacion del usuario.",
         _obj({"path": _str("Ruta de la carpeta"),
               "hide": {"type": "boolean",
                        "description": "true para ocultar, false para mostrar"}},
              ["path"]),
         _hide_files, needs_confirmation=True),

    # Informacion
    Tool("clima",
         "Dice el clima actual de cualquier ciudad del mundo: temperatura, "
         "humedad, viento y pronostico del dia.",
         _obj({"city": _str("Ciudad. Vacio = ciudad actual del usuario")}, []),
         _weather),

    Tool("ubicar_lugar",
         "Abre un lugar en Google Maps e informa la distancia desde la ubicacion "
         "actual del usuario.",
         _obj({"place": _str("Ciudad, pais o lugar a ubicar")}),
         _locate),

    Tool("wikipedia",
         "Cuenta informacion sobre una persona, lugar, empresa o tema, "
         "consultando Wikipedia. Usar cuando pregunten quien es alguien o "
         "que es algo del mundo real.",
         _obj({"topic": _str("Persona o tema a consultar")}),
         _wiki),

    Tool("noticias",
         "Lee los titulares principales de las noticias de hoy.",
         _obj({}, []), _news),

    Tool("calcular",
         "Resuelve una operacion o ecuacion matematica. Acepta lenguaje natural "
         "('5 mas 3 por 2') y ecuaciones ('x + 135 - 234 = 345').",
         _obj({"expression": _str("La expresion o ecuacion a resolver")}),
         _calculate),

    Tool("preguntar_wolframalpha",
         "Responde preguntas de datos y ciencia (distancias, poblaciones, "
         "conversiones, formulas) via WolframAlpha. Funciona mejor en ingles.",
         _obj({"question": _str("La pregunta factual")}),
         _wolfram),

    Tool("mi_direccion_ip",
         "Informa la direccion IP local y publica de este computador.",
         _obj({}, []), _get_ip),

    Tool("proximos_eventos",
         "Lista los proximos eventos del calendario de Google del usuario.",
         _obj({}, []), _calendar),

    Tool("contar_chiste",
         "Cuenta un chiste para entretener al usuario.",
         _obj({}, []), _joke),

    # Web
    Tool("abrir_sitio_web",
         "Abre una pagina web en el navegador del usuario.",
         _obj({"site": _str("Dominio o URL, ej: 'github.com', 'youtube.com'")}),
         _open_website),

    Tool("buscar_en_google",
         "Busca cualquier cosa en Google y abre los resultados en el navegador.",
         _obj({"query": _str("Lo que se quiere buscar")}),
         _google),

    Tool("reproducir_en_youtube",
         "Busca y reproduce una cancion o video en YouTube.",
         _obj({"query": _str("Cancion, artista o video a reproducir")}),
         _youtube),

    Tool("reproducir_musica_local",
         "Reproduce musica guardada en la carpeta Musica del computador.",
         _obj({"song": _str("Nombre de la cancion. Vacio = aleatoria")}, []),
         _play_music),

    Tool("navegar_con_selenium",
         "Abre una pagina en el navegador Chrome que JARVIS controla "
         "(automatizado). Usar solo si piden control del navegador.",
         _obj({"url": _str("URL a la que navegar")}),
         _browser_navigate),

    Tool("cerrar_navegador",
         "Cierra el navegador Chrome controlado por JARVIS.",
         _obj({}, []), _close_browser),

    # Empleo
    Tool("buscar_empleo",
         "Busca ofertas de trabajo en Computrabajo y LinkedIn, ordenadas de la "
         "mas reciente a la mas antigua, con empresa, salario y ubicacion.",
         _obj({"puesto": _str("Cargo buscado, ej: 'desarrollador', 'contador'"),
               "ciudad": _str("Ciudad. Vacio = toda Colombia")}, ["puesto"]),
         _search_jobs),

    Tool("abrir_oferta_empleo",
         "Abre en el navegador una de las ofertas de la ultima busqueda de empleo.",
         _obj({"number": _int("Numero de la oferta en la lista (1, 2, 3...)")}),
         _open_job),

    Tool("mostrar_ofertas_empleo",
         "Abre los portales de empleo (Computrabajo, El Empleo, LinkedIn) en el "
         "navegador, cada uno en su pestana, con la busqueda aplicada.",
         _obj({"puesto": _str("Cargo. Vacio = ultima busqueda"),
               "ciudad": _str("Ciudad")}, []),
         _show_jobs),

    # Escritorio y productividad
    Tool("tomar_nota",
         "Guarda una nota de texto con la fecha y hora, y la abre en el Bloc de notas.",
         _obj({"text": _str("El texto de la nota")}),
         _take_note),

    Tool("captura_de_pantalla",
         "Toma una captura de la pantalla y la guarda como imagen PNG.",
         _obj({"name": _str("Nombre del archivo. Vacio = fecha y hora")}, []),
         _screenshot),

    Tool("cambiar_ventana",
         "Cambia a la ventana anterior del escritorio (Alt+Tab).",
         _obj({}, []), _switch_window),

    Tool("enviar_correo",
         "Prepara el envio de un correo electronico. NO lo envia de inmediato: "
         "el usuario debe confirmar con /confirmar.",
         _obj({"to": _str("Destinatario: direccion de correo o nombre de contacto"),
               "subject": _str("Asunto del correo"),
               "body": _str("Cuerpo del mensaje")}),
         _send_email, needs_confirmation=True),

    Tool("recordar",
         "Guarda en la memoria permanente un dato que el usuario quiere que "
         "JARVIS recuerde para siempre (preferencias, datos personales, gustos).",
         _obj({"text": _str("El dato a recordar")}),
         _remember),
]

_BY_NAME = {t.name: t for t in TOOLS}


def get_tool(name: str) -> Tool | None:
    return _BY_NAME.get(name)


def all_schemas() -> list[dict]:
    """Esquemas JSON de todas las herramientas, para enviar al LLM."""
    return [t.schema() for t in TOOLS]


def tool_names() -> list[str]:
    return list(_BY_NAME)


def execute(name: str, arguments: dict) -> tuple[str, bool]:
    """
    Ejecuta una herramienta por nombre.

    Returns:
        (texto_resultado, requiere_confirmacion)
    """
    tool = get_tool(name)
    if tool is None:
        return f"No existe la herramienta '{name}'.", False

    # Filtrar argumentos que la herramienta no conoce (el LLM a veces inventa)
    validos = set(tool.parameters.get("properties", {}))
    args = {k: v for k, v in (arguments or {}).items() if k in validos}
    faltantes = [r for r in tool.parameters.get("required", []) if r not in args]
    if faltantes:
        return (f"Me falta un dato para {name}: {', '.join(faltantes)}. "
                "Puede indicarmelo, senor?"), False

    try:
        result = tool.run(**args)
    except Exception as e:
        from jarvis_local.safety.logger import logger
        logger.log_error(f"tool:{name}", str(e))
        return f"No pude ejecutar '{name}': {e}", False

    if isinstance(result, ActionPlan):
        pendiente = result.status in (ActionStatus.PLANNED, ActionStatus.CONFIRMED)
        texto = result.result or (str(result) if pendiente else "Operacion completada.")
        if pendiente:
            texto = str(result)
        return texto, pendiente
    return str(result), False
