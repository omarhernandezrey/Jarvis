"""
JARVIS Local - Preseleccion lexica de herramientas (RESPALDO)

OBSOLETO como via principal: lo reemplaza agent/retriever.py, que recupera las
herramientas por significado (embeddings). Este modulo solo se usa si el modelo
de embeddings no esta disponible.

Por que se reemplazo: la coincidencia por palabras clave devolvia una lista
VACIA ante lenguaje coloquial ("estoy buscando chamba de contador"), y con cero
herramientas el agente ni se invocaba, asi que el modelo nunca llegaba a razonar
sobre la frase. Agregar mas sinonimos no arregla el problema de fondo: siempre
faltara una palabra. El retriever semantico si relaciona "chamba" con "empleo".
"""
import re
import unicodedata

from jarvis_local.agent.registry import TOOLS, get_tool

# Pistas lexicas por herramienta. No son ordenes: solo acotan el catalogo.
_HINTS: dict[str, list[str]] = {
    "abrir_aplicacion": ["abre", "abrir", "abreme", "lanza", "inicia", "ejecuta",
                         "programa", "aplicacion", "app", "chrome", "whatsapp",
                         "word", "excel", "vscode", "wsl", "ubuntu", "terminal",
                         "spotify", "notion", "telegram", "calculadora"],
    "cerrar_aplicacion": ["cierra", "cerrar", "cierrame", "termina", "finaliza",
                          "salte de", "programa", "aplicacion", "app", "word",
                          "chrome", "whatsapp", "excel", "spotify"],
    "cerrar_todas_aplicaciones": ["cierra todo", "cierra todos", "cierralo todo",
                                  "todos los programas", "todas las aplicaciones",
                                  "todas las apps", "todas las ventanas"],
    "enviar_whatsapp": ["whatsapp", "wasap", "guasap", "mensaje a", "escribele",
                        "mandale un mensaje"],
    "organizar_ventanas": ["minimiza", "maximiza", "ventana", "escritorio",
                           "a la izquierda", "a la derecha"],
    "resumen_del_dia": ["resumen del dia", "ponme al dia", "como esta el dia",
                        "resumen de la manana", "informe del dia"],
    "leer_portapapeles": ["portapapeles", "lo que copie", "leeme lo copiado"],
    "leer_archivo": ["leeme el archivo", "lee el documento", "en voz alta",
                     "leeme las notas"],
    "energia_del_equipo": ["apaga el computador", "apaga el pc", "reinicia",
                           "bloquea", "suspende", "hiberna", "apagado",
                           "cancela el apagado"],
    "crear_recordatorio": ["recuerdame", "avisame", "alarma", "recordatorio",
                           "temporizador", "en minutos", "no se me olvide"],
    "listar_recordatorios": ["mis recordatorios", "que recordatorios",
                             "mis alarmas", "recordatorios pendientes"],
    "cancelar_recordatorio": ["cancela el recordatorio", "cancela la alarma",
                              "quita el recordatorio", "borra la alarma"],
    "controlar_volumen": ["volumen", "sube", "baja", "silencia", "silencio",
                          "mutea", "sonido", "mas fuerte", "mas duro",
                          "mas bajito"],
    "controlar_musica": ["pausa", "pausar", "reanuda", "siguiente cancion",
                         "cancion anterior", "cambia de cancion", "pista",
                         "tema"],
    "estado_del_sistema": ["sistema", "ram", "memoria", "cpu", "procesador",
                           "bateria", "disco", "recursos", "rendimiento",
                           "maquina", "equipo", "computador", "pc", "lento"],
    "ejecutar_comando": ["comando", "powershell", "consola", "terminal",
                         "ejecuta", "corre"],
    "listar_archivos": ["archivos", "carpeta", "directorio", "lista", "listar",
                        "muestra", "contenido", "documentos", "descargas"],
    "buscar_archivo": ["busca", "buscar", "encuentra", "archivo", "fichero",
                       "documento", "pdf", "donde esta"],
    "crear_carpeta": ["crea", "crear", "carpeta", "directorio", "nueva"],
    "crear_archivo": ["crea", "crear", "archivo", "fichero", "documento",
                      "escribe"],
    "borrar_archivo": ["borra", "borrar", "elimina", "eliminar", "quita",
                       "archivo", "suprime"],
    "ocultar_archivos": ["oculta", "ocultar", "esconde", "visible", "invisible",
                         "ocultos"],
    "clima": ["clima", "tiempo", "temperatura", "llover", "lluvia", "sol",
              "calor", "frio", "grados", "pronostico", "hace en"],
    "ubicar_lugar": ["donde queda", "donde esta", "ubicacion", "ubica", "mapa",
                     "distancia", "lejos", "cerca", "kilometros", "llegar"],
    "wikipedia": ["quien es", "quien fue", "quien era", "quien escribio",
                  "quien invento", "hablame de", "cuentame de", "que sabes de",
                  "biografia", "historia de", "que es el", "que es la",
                  "informacion sobre", "acerca de"],
    "noticias": ["noticias", "titulares", "actualidad", "prensa", "paso hoy",
                 "esta pasando"],
    "calcular": ["calcula", "calcular", "cuanto es", "suma", "resta",
                 "multiplica", "divide", "resultado", "ecuacion", "raiz",
                 "porcentaje", "matematica"],
    "preguntar_wolframalpha": ["wolfram", "cuanto mide", "cuanta poblacion",
                               "cuantos habitantes", "velocidad de",
                               "distancia de la", "formula"],
    "mi_direccion_ip": ["ip", "direccion ip", "red", "internet"],
    "proximos_eventos": ["evento", "eventos", "agenda", "calendario", "cita",
                         "reunion", "programado"],
    "contar_chiste": ["chiste", "gracioso", "divertido", "reir", "risa",
                      "aburrido", "entretenme", "humor"],
    "abrir_sitio_web": ["abre", "abrir", "pagina", "sitio", "web", "navega",
                        "entra", "punto com", ".com", ".co", "github",
                        "youtube", "google", "facebook", "instagram"],
    "buscar_en_google": ["busca en google", "googlea", "buscar en internet",
                         "busca en la web", "investiga"],
    "reproducir_en_youtube": ["youtube", "video", "cancion", "reproduce",
                              "pon", "escuchar", "musica", "tema", "artista"],
    "reproducir_musica_local": ["musica", "cancion", "reproduce", "pon",
                                "escuchar", "playlist"],
    "navegar_con_selenium": ["navegador", "selenium", "controla el navegador",
                             "automatiza"],
    "cerrar_navegador": ["cierra el navegador", "cerrar navegador"],
    "buscar_empleo": ["trabajo", "empleo", "vacante", "vacantes", "oferta",
                      "ofertas", "curriculum", "hoja de vida", "contratar",
                      "computrabajo", "linkedin", "puesto", "cargo"],
    "abrir_oferta_empleo": ["oferta", "vacante", "abre la", "numero",
                            "postular", "aplicar"],
    "mostrar_ofertas_empleo": ["ofertas", "portales", "muestrame", "computrabajo",
                               "elempleo", "linkedin"],
    "tomar_nota": ["nota", "apunta", "anota", "recordatorio", "escribe esto",
                   "toma nota"],
    "captura_de_pantalla": ["captura", "pantallazo", "screenshot", "foto de la",
                            "pantalla"],
    "cambiar_ventana": ["cambia de ventana", "cambiar ventana", "alt tab",
                        "otra ventana"],
    "enviar_correo": ["correo", "email", "mail", "envia", "enviar", "manda",
                      "escribele", "gmail"],
    "recordar": ["recuerda", "recordar", "memoriza", "no olvides", "ten en cuenta",
                 "guarda que", "acuerdate"],
}

# Cuantas herramientas como maximo se le ofrecen al modelo
MAX_TOOLS = 6


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s.]", " ", t)


def score_tools(message: str) -> list[tuple[str, int]]:
    """Puntua cada herramienta por coincidencias lexicas con el mensaje."""
    m = _norm(message)
    puntajes: list[tuple[str, int]] = []
    for tool in TOOLS:
        pistas = _HINTS.get(tool.name, [])
        p = 0
        for pista in pistas:
            if pista in m:
                # Las pistas multipalabra son mas especificas: valen mas
                p += 3 if " " in pista else 1
        if p:
            puntajes.append((tool.name, p))
    puntajes.sort(key=lambda x: (-x[1], x[0]))
    return puntajes


def select_tools(message: str, max_tools: int = MAX_TOOLS) -> list[dict]:
    """Esquemas de las herramientas plausibles para este mensaje.

    Lista vacia = ninguna herramienta encaja; el agente ni siquiera se invoca
    y la frase va directo al chat normal (mas rapido y mas natural).
    """
    seleccion = [name for name, _ in score_tools(message)[:max_tools]]
    return [get_tool(n).schema() for n in seleccion if get_tool(n)]


def selected_names(message: str, max_tools: int = MAX_TOOLS) -> list[str]:
    return [n for n, _ in score_tools(message)[:max_tools]]
