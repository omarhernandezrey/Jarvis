"""
JARVIS Local - Respuestas instantaneas sin Ollama.
Personalidad JARVIS: formal, alterna entre "senor" y "senor Omar".
"""
import random
import re
from datetime import datetime

_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Formas de dirigirse al usuario (como JARVIS real)
_TRATO = ["senor", "senor Omar"]

# Regex compiladas como constantes del módulo (rendimiento)
_RE_SALUDO = re.compile(r'\b(hola|hey|hi|buenas|buenos dias|buenos tardes|buenas noches|saludos|que tal|que hay)\b')
_RE_HORA = re.compile(r'\b(que hora es|hora actual|dime la hora|que horas son|la hora)\b')
_RE_FECHA = re.compile(r'\b(que dia es|que fecha|fecha de hoy|dia de hoy|que dia estamos|cual es la fecha)\b')
_RE_QUIEN = re.compile(r'\b(quien eres|que eres|presentate|como te llamas)\b')
_RE_CAPACIDADES = re.compile(r'\b(que puedes|que sabes|capacidades|funciones|puedes hacer|para que sirves)\b')
_RE_GRACIAS = re.compile(r'\b(gracias|muchas gracias|te lo agradezco|genial|perfecto|excelente|muy bien|chevere|bacano)\b')
_RE_ADIOS = re.compile(r'\b(adios|hasta luego|hasta manana|nos vemos|chao|bye|hasta pronto|me voy)\b')
_RE_ESTADO = re.compile(r'\b(como estas|todo bien|como vas|estas bien)\b')


def _sr() -> str:
    """Alterna aleatoriamente entre 'senor' y 'senor Omar'."""
    return random.choice(_TRATO)


def _normalize(text: str) -> str:
    t = text.lower().strip()
    for k, v in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n",
                 "¿":"","¡":"","?":"","!":"",",":"",".":""}.items():
        t = t.replace(k, v)
    return t


# "Jarvis" es un nombre inventado: el STT (faster-whisper) lo transcribe
# distinto casi cada vez -- "Janbis", "Yarbis", "Harves"... Mismas variantes
# que usa voice/continuous.py para la palabra de activacion del modo manos
# libres; sin esto, "hola jarvis" mal transcrito no se reconocia como saludo
# y bajaba por TODA la cascada hasta el LLM (~19-60s) en vez de responder al
# instante.
_VARIANTES_JARVIS = {
    "jarvis", "yarbis", "yarvis", "garbis", "gerbis", "janbis",
    "jarbis", "harvis", "carvis", "yarbi", "garbi", "arbis",
    "jarbees", "jarvises", "garvis", "jervis", "jarbez",
    "jarbes", "jarves", "charvis", "charbis",
}

# Palabras que pueden acompanar a una formula de cortesia sin cambiar su
# sentido: "hola jarvis, buenas tardes senor" sigue siendo solo un saludo.
_RELLENO = _VARIANTES_JARVIS | {
    "senor", "senior", "sr", "omar", "por", "favor", "muy",
    "buenos", "buenas", "dias", "tardes", "noches", "y", "a", "ti", "tu",
    "usted", "todo", "bien", "pues", "che", "amigo", "que", "tal", "hay",
    "como", "estas", "esta", "va", "vas",
}


def _es_solo_cortesia(m: str, patron: str) -> bool:
    """True si el mensaje es SOLO la formula (saludo, gracias, despedida...).

    Sin esto, "que tal anda mi maquina de recursos" se responde como un saludo
    ("que tal" hace match) y nunca llega al agente. Igual "buenas, abre chrome".
    Se quita la formula y, si queda alguna palabra con contenido, el mensaje es
    una peticion de verdad: que siga bajando por la cascada.
    """
    resto = re.sub(patron, " ", m)
    return not [w for w in resto.split() if w not in _RELLENO]


def fast_respond(message: str) -> str | None:
    """
    Respuesta instantanea sin Ollama, o None si requiere razonamiento.
    Todas las respuestas usan tono JARVIS: formal, "senor"/"senor Omar".
    """
    m = _normalize(message)

    # --- SALUDOS ---
    if _RE_SALUDO.search(m) and _es_solo_cortesia(m, _RE_SALUDO.pattern):
        # Si el usuario dijo EXPLICITAMENTE "buenos dias/tardes/noches", se le
        # responde en el mismo registro (puede ser turno de noche, o cortesia a
        # una hora rara). Si solo dijo "hola", se usa la hora real del reloj.
        if re.search(r'\bbuen[oa]s?\s+noches\b', m):
            franja = "noche"
        elif re.search(r'\bbuen[oa]s?\s+tardes\b', m):
            franja = "tarde"
        elif re.search(r'\bbuen[oa]s?\s+dias\b', m):
            franja = "manana"
        else:
            h = datetime.now().hour
            franja = "manana" if h < 12 else "tarde" if h < 18 else "noche"

        if franja == "manana":
            return f"Buenos dias, {_sr()}. Sistemas en linea y listos. En que le puedo asistir?"
        if franja == "tarde":
            return f"Buenas tardes, {_sr()}. Todos los sistemas operando normalmente. Como puedo ayudarle?"
        return f"Buenas noches, {_sr()}. JARVIS en linea. En que le puedo ser de ayuda?"

    # --- HORA ---
    if _RE_HORA.search(m):
        ahora = datetime.now()
        return f"Son las {ahora.strftime('%H:%M')}, {_sr()}."

    # --- FECHA ---
    if _RE_FECHA.search(m):
        ahora = datetime.now()
        return f"Hoy es {_DIAS[ahora.weekday()]}, {ahora.day} de {_MESES[ahora.month - 1]} de {ahora.year}, {_sr()}."

    # --- QUIEN ERES ---
    if _RE_QUIEN.search(m):
        return (f"Soy JARVIS, su asistente de inteligencia artificial personal, {_sr()}. "
                "Opero localmente en su computador. Puedo gestionar archivos, abrir aplicaciones, "
                "ejecutar comandos y responder preguntas usando el modelo de lenguaje local.")

    # --- QUE PUEDES HACER ---
    if _RE_CAPACIDADES.search(m):
        return (f"A sus ordenes, {_sr()}. Puedo gestionar archivos, abrir aplicaciones como Chrome y VS Code, "
                "ejecutar comandos de terminal, responder preguntas y razonar usando el modelo local qwen2.5. "
                "Todo opera de forma privada en su propio equipo.")

    # --- GRACIAS ---
    if _RE_GRACIAS.search(m) and _es_solo_cortesia(m, _RE_GRACIAS.pattern):
        return f"A sus ordenes, {_sr()}. Para eso estoy."

    # --- DESPEDIDA ---
    if _RE_ADIOS.search(m) and _es_solo_cortesia(m, _RE_ADIOS.pattern):
        return f"Hasta luego, {_sr()}. Estare disponible cuando me necesite."

    # --- ESTADO (de JARVIS, no del computador: "como estas" != "como esta la ram") ---
    if _RE_ESTADO.search(m) and _es_solo_cortesia(m, _RE_ESTADO.pattern):
        return f"Todos los sistemas operando con normalidad, {_sr()}. Listo para asistirle."

    return None
