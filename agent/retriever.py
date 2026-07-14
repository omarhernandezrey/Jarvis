"""
JARVIS Local - Recuperacion semantica de herramientas (tool-RAG)

POR QUE EXISTE ESTE MODULO
--------------------------
La version anterior (selector.py) elegia que herramientas ofrecerle al LLM con
un diccionario de palabras clave. Eso tenia un fallo estructural: si ninguna
palabra coincidia, se le ofrecian CERO herramientas y el agente ni se invocaba,
asi que el modelo nunca llegaba a ver la frase. Medido en la bateria de
evaluacion, esto causaba fallos silenciosos:

    "estoy buscando chamba de contador"   -> 0 herramientas -> nunca razono
    "estoy buscando pega de disenador"    -> 0 herramientas -> nunca razono
    "y en Bogota?"                        -> 0 herramientas -> nunca razono

Ampliar la lista de sinonimos ("chamba", "pega", "camello"...) no arregla nada:
es fragilidad disfrazada de cobertura. Siempre habra una palabra que falte.

QUE HACE EN SU LUGAR
--------------------
Embebe una vez la descripcion de cada herramienta y, por cada mensaje, recupera
las k mas parecidas por similitud coseno (bge-m3, multilingue, local). "Chamba"
y "empleo" quedan cerca en el espacio vectorial aunque no compartan letras.

El puntaje ademas da una senal de CONFIANZA:
  - alta   -> se ofrecen las herramientas al LLM, que decide
  - baja   -> ninguna herramienta es plausible: la frase va a conversacion
El LLM sigue siendo quien decide; esto solo acota el catalogo para que un
modelo de 3B en CPU no tenga que razonar sobre 31 esquemas a la vez.

Si el modelo de embeddings no esta disponible, cae al selector lexico anterior:
peor, pero funcional (degradacion, no rotura).
"""
import numpy as np

from jarvis_local.agent.registry import TOOLS, get_tool
from jarvis_local.storage.semantic import cosine_similarity, embed

# Cuantas herramientas ofrecerle al modelo.
# Con 31 el prompt supera los 4000 tokens: el 3B tarda 1-2 min y elige mal.
# Con 6 seguia habiendo ruido: en "ando aburrido, dime algo divertido" el
# retriever ponia contar_chiste primero (0.73) y el modelo elegia wikipedia
# (0.45), que solo estaba ahi por relleno. Menos opciones, menos formas de
# equivocarse: la recuperacion tiene recall@4 suficiente y el modelo decide
# mejor sobre un catalogo corto.
TOP_K = 4

# Por debajo de esto, ninguna herramienta se considera plausible y la frase va
# a conversacion. Calibrado con la bateria: las peticiones reales puntuan >0.45
# y la charla ("de que color es el cielo") se queda por debajo.
UMBRAL_MINIMO = 0.42

_matriz: np.ndarray | None = None
_nombres: list[str] = []
_disponible: bool | None = None


def _texto_indexable(tool) -> str:
    """Lo que se embebe de cada herramienta: nombre + descripcion + ejemplos.

    Los ejemplos importan tanto como la descripcion: acercan el vector de la
    herramienta al lenguaje REAL del usuario ("chamba", "pega"), no al lenguaje
    formal con el que un programador describe una funcion.
    """
    ejemplos = " ".join(_EJEMPLOS.get(tool.name, []))
    return f"{tool.name.replace('_', ' ')}. {tool.description} {ejemplos}"


# Frases de ejemplo por herramienta. NO son reglas de coincidencia (nada compara
# texto contra esto): son material para el embedding, para que el vector de la
# herramienta quede cerca de como habla la gente de verdad.
_EJEMPLOS: dict[str, list[str]] = {
    "abrir_aplicacion": [
        "abre chrome", "abreme el navegador", "lanza whatsapp",
        "necesito spotify abierto", "inicia visual studio code",
        "prendeme la calculadora",
    ],
    "cerrar_aplicacion": [
        "cierra word", "cierra el chrome", "cierrame whatsapp",
        "termina spotify", "cierra la calculadora", "sal de excel",
    ],
    "cerrar_todas_aplicaciones": [
        "cierra todos los programas", "cierra todas las aplicaciones",
        "cierra todo lo que abriste", "cierralo todo",
    ],
    "estado_del_sistema": [
        "como anda mi maquina", "cuanta ram estoy usando", "mi pc esta lento",
        "como va la bateria", "que tiene ocupado el procesador",
        "revisa los recursos del equipo",
    ],
    "clima": [
        "que clima hace en Bogota", "va a llover manana", "hace frio en Cali",
        "que temperatura hay", "pronostico del tiempo", "esta soleado?",
    ],
    "buscar_empleo": [
        "busca trabajo de desarrollador", "hay vacantes de contador",
        "estoy buscando chamba", "consigueme pega de disenador",
        "ofertas laborales en Medellin", "quiero cambiar de empleo",
    ],
    "abrir_oferta_empleo": [
        "abre la oferta 2", "muestrame la primera vacante",
        "abreme la segunda", "quiero ver esa oferta",
    ],
    "wikipedia": [
        "quien es Gabriel Garcia Marquez", "hablame de Simon Bolivar",
        "quien diablos invento el telefono", "que sabes sobre la penicilina",
        "cuentame de la historia de Roma",
    ],
    "noticias": [
        "que paso hoy en el mundo", "dame los titulares",
        "echale un ojo a las noticias", "novedades de hoy",
    ],
    "contar_chiste": [
        "cuentame un chiste", "dime algo gracioso", "hazme reir",
        "ando aburrido", "algo divertido",
    ],
    "buscar_en_google": [
        "busca en google recetas", "googlea eso", "investiga en internet",
        "buscame informacion en la web",
    ],
    "abrir_sitio_web": [
        "abre github.com", "entra a youtube", "llevame a la pagina de gmail",
        "necesito abrir el correo web", "navega a wikipedia",
    ],
    "reproducir_en_youtube": [
        "pon musica en youtube", "reproduce hotel california",
        "ponme un video de", "quiero escuchar una cancion en youtube",
    ],
    "reproducir_musica_local": [
        "pon musica", "se me antoja escuchar algo", "reproduce mi playlist",
        "quiero oir musica",
    ],
    "tomar_nota": [
        "toma nota de esto", "apuntame que tengo que llamar al banco",
        "anota que compre cafe", "recuerdame esto por escrito",
    ],
    "captura_de_pantalla": [
        "toma una captura", "hazme un pantallazo", "screenshot de la pantalla",
        "captura lo que se ve",
    ],
    "enviar_correo": [
        "envia un correo a Omar", "mandale un mail al jefe",
        "escribele un correo diciendo que llego tarde",
    ],
    "buscar_archivo": [
        "busca el archivo informe.pdf", "donde esta mi documento",
        "encuentra el fichero de notas",
    ],
    "listar_archivos": [
        "lista los archivos de Documentos", "muestrame el contenido de Descargas",
        "que hay en mi carpeta de escritorio",
    ],
    "crear_carpeta": ["crea una carpeta llamada proyectos"],
    "crear_archivo": ["crea un archivo de texto con mis notas"],
    "borrar_archivo": ["borra el archivo viejo.txt", "elimina ese documento"],
    "ocultar_archivos": ["oculta los archivos de esa carpeta"],
    "calcular": [
        "cuanto es 5 mas 3 por 2", "calcula el 15 por ciento de 200",
        "resuelve x + 135 = 345",
    ],
    "preguntar_wolframalpha": [
        "cuanta poblacion tiene Japon", "a que distancia esta la luna",
        "cual es la velocidad de la luz",
    ],
    "ubicar_lugar": [
        "donde queda Tokio", "que tan lejos esta Cartagena",
        "ubicame ese lugar en el mapa",
    ],
    "mi_direccion_ip": ["cual es mi ip", "que direccion ip tengo"],
    "proximos_eventos": [
        "que tengo agendado", "mis proximos eventos", "como esta mi agenda",
    ],
    "ejecutar_comando": ["ejecuta dir", "corre el comando ipconfig"],
    "cambiar_ventana": ["cambia de ventana", "pasa a la otra ventana"],
    "mostrar_ofertas_empleo": ["muestrame las ofertas en el navegador"],
    "navegar_con_selenium": ["navega con el navegador controlado"],
    "cerrar_navegador": ["cierra el navegador automatizado"],
    "recordar": [
        "recuerda que soy alergico a los mariscos",
        "no olvides que prefiero el cafe sin azucar",
        "ten en cuenta que trabajo en Bogota",
    ],
}


def _construir_indice() -> bool:
    """Embebe las herramientas una sola vez. True si el indice quedo listo."""
    global _matriz, _nombres, _disponible
    if _disponible is not None:
        return _disponible

    textos = [_texto_indexable(t) for t in TOOLS]
    vectores = embed(textos)
    if vectores is None:
        _disponible = False
        return False

    _matriz = np.array(vectores, dtype=np.float32)
    _nombres = [t.name for t in TOOLS]
    _disponible = True
    return True


def rank_tools(message: str) -> list[tuple[str, float]]:
    """Herramientas ordenadas por similitud semantica con el mensaje."""
    if not message.strip() or not _construir_indice():
        return []
    q = embed([message])
    if not q:
        return []
    scores = cosine_similarity(np.array(q[0], dtype=np.float32), _matriz)
    pares = list(zip(_nombres, (float(s) for s in scores), strict=False))
    pares.sort(key=lambda x: -x[1])
    return pares


def select_tools(message: str, top_k: int = TOP_K,
                 umbral: float = UMBRAL_MINIMO) -> list[dict]:
    """Esquemas de las herramientas plausibles para este mensaje.

    Lista vacia = nada es plausible ni siquiera semanticamente: la frase es
    conversacion y no vale la pena gastar una llamada al LLM con herramientas.
    """
    ranking = rank_tools(message)
    if not ranking:
        # Sin embeddings: respaldo lexico (peor, pero mejor que nada)
        from jarvis_local.agent.selector import select_tools as lexico
        return lexico(message)

    if ranking[0][1] < umbral:
        return []

    elegidas = [n for n, s in ranking[:top_k] if s >= umbral * 0.85]
    return [get_tool(n).schema() for n in elegidas if get_tool(n)]


def selected_names(message: str, top_k: int = TOP_K,
                   umbral: float = UMBRAL_MINIMO) -> list[str]:
    ranking = rank_tools(message)
    if not ranking:
        from jarvis_local.agent.selector import selected_names as lexico
        return lexico(message)
    if ranking[0][1] < umbral:
        return []
    return [n for n, s in ranking[:top_k] if s >= umbral * 0.85]


def confidence(message: str) -> float:
    """Similitud de la mejor herramienta: senal de confianza del enrutamiento."""
    ranking = rank_tools(message)
    return ranking[0][1] if ranking else 0.0


def reset_index():
    """Fuerza reconstruir el indice (util en tests)."""
    global _matriz, _nombres, _disponible
    _matriz, _nombres, _disponible = None, [], None
