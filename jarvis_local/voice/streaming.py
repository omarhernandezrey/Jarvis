"""
JARVIS Local - Respuesta hablada por streaming (Fase 6)

Antes, JARVIS esperaba a que el LLM terminara TODA la respuesta y recien
entonces empezaba a hablar: en CPU eso son 30-60 segundos de silencio. Ahora
parte la respuesta en frases a medida que se generan y habla la primera
mientras el modelo sigue escribiendo las siguientes.

La latencia hasta la primera palabra baja de ~40 s a ~5 s. El modelo no es mas
rapido; simplemente deja de hacer esperar al usuario.
"""
import queue
import re
import threading
from collections.abc import Callable, Iterator

# Corta en fin de frase. El minimo evita hablar fragmentos sueltos ("Si.") y
# el maximo evita quedarse mudo si el modelo escribe un parrafo sin puntuacion.
_FIN_DE_FRASE = re.compile(r'(?<=[.!?:;])\s+|\n+')
MIN_CHARS = 25
MAX_CHARS = 220


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Extrae las frases completas del buffer. Devuelve (frases, resto)."""
    frases: list[str] = []
    resto = buffer

    while True:
        # Primer fin de frase que deje un fragmento con cuerpo suficiente. Si
        # solo miraramos el primero, una frase corta ("Si.") bloquearia todo el
        # resto del buffer: hay que seguir buscando el siguiente corte valido.
        corte_frase = None
        for m in _FIN_DE_FRASE.finditer(resto):
            if m.start() >= MIN_CHARS:
                corte_frase = m
                break
        if corte_frase is not None:
            frases.append(resto[:corte_frase.start() + 1].strip())
            resto = resto[corte_frase.end():]
            continue

        # Sin puntuacion pero ya muy largo: cortar en el ultimo espacio
        if len(resto) > MAX_CHARS:
            corte = resto.rfind(" ", MIN_CHARS, MAX_CHARS)
            if corte == -1:
                corte = MAX_CHARS
            frases.append(resto[:corte].strip())
            resto = resto[corte:].lstrip()
            continue
        break

    return [f for f in frases if f], resto


def speak_stream(token_iter: Iterator[str],
                 speak_fn: Callable[[str], None],
                 on_token: Callable[[str], None] | None = None) -> str:
    """
    Consume los tokens del LLM, habla por frases y devuelve el texto completo.

    El habla corre en un hilo aparte con una cola: generar y hablar van en
    paralelo, y las frases se pronuncian en orden sin solaparse.

    Args:
        token_iter: iterador de tokens del modelo
        speak_fn: funcion de TTS (bloqueante) que reproduce una frase
        on_token: callback opcional por token (para ir imprimiendo en pantalla)
    """
    cola: queue.Queue[str | None] = queue.Queue()
    completo: list[str] = []

    def _hablador():
        while True:
            frase = cola.get()
            if frase is None:  # centinela de fin
                break
            try:
                speak_fn(frase)
            except Exception:
                pass  # que un fallo de audio no tumbe la conversacion

    hilo = threading.Thread(target=_hablador, daemon=True)
    hilo.start()

    buffer = ""
    try:
        for token in token_iter:
            if not token:
                continue
            completo.append(token)
            if on_token:
                on_token(token)
            buffer += token
            frases, buffer = split_sentences(buffer)
            for f in frases:
                cola.put(f)
    finally:
        if buffer.strip():
            cola.put(buffer.strip())
        cola.put(None)
        hilo.join(timeout=180)

    return "".join(completo).strip()
