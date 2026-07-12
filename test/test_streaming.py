"""
Tests del habla por streaming (Fase 6).
Sin audio real: el TTS se sustituye por una funcion que registra lo que se
"habla" y cuando. Asi se verifica lo que importa: que JARVIS empiece a hablar
antes de que el modelo termine de escribir.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.voice.streaming import MAX_CHARS, speak_stream, split_sentences

# ---------- Corte en frases ----------

def test_corta_en_fin_de_frase():
    frases, resto = split_sentences(
        "Buenas tardes, senor Omar. Todos los sistemas operan con normalidad. Y ahora")
    assert len(frases) == 2
    assert frases[0].startswith("Buenas tardes")
    assert frases[1].startswith("Todos los sistemas")
    assert resto == "Y ahora"


def test_no_corta_frases_muy_cortas():
    """'Si.' no debe irse solo al TTS: suena entrecortado."""
    frases, resto = split_sentences("Si. Claro")
    assert frases == []
    assert resto == "Si. Claro"


def test_corta_si_no_hay_puntuacion():
    """Un parrafo sin puntos no debe dejar mudo a JARVIS."""
    largo = "palabra " * 60
    frases, resto = split_sentences(largo)
    assert frases
    assert all(len(f) <= MAX_CHARS for f in frases)


def test_buffer_incompleto_se_conserva():
    frases, resto = split_sentences("Estoy pensando en algo que")
    assert frases == []
    assert resto == "Estoy pensando en algo que"


def test_salto_de_linea_corta():
    frases, resto = split_sentences("Primera linea de la respuesta\nSegunda parte")
    assert len(frases) == 1
    assert "Primera linea" in frases[0]


# ---------- Bucle de habla ----------

def test_habla_todas_las_frases_en_orden():
    dichas = []
    tokens = iter(["Buenas tardes, senor. ", "Los sistemas estan en linea. ",
                   "Como puedo asistirle?"])
    completo = speak_stream(tokens, dichas.append)

    assert "Buenas tardes" in completo and "asistirle" in completo
    assert len(dichas) >= 2
    # el orden se respeta
    assert dichas[0].startswith("Buenas tardes")
    assert "asistirle" in dichas[-1]


def test_habla_antes_de_terminar_de_generar():
    """El corazon de la mejora: la primera frase suena mientras el modelo
    sigue escribiendo, no al final."""
    dichas: list[tuple[str, float]] = []
    t0 = time.time()

    def _tokens():
        yield "Buenas tardes, senor Omar. "   # frase 1 completa, ya hablable
        for _ in range(5):
            time.sleep(0.15)                  # el modelo sigue generando lento
            yield "mas texto que tarda "

    def _speak(texto):
        dichas.append((texto, time.time() - t0))

    completo = speak_stream(_tokens(), _speak)
    generacion_total = time.time() - t0

    assert dichas, "no hablo nada"
    primera = dichas[0][1]
    assert primera < generacion_total / 2, (
        f"la primera frase sono a los {primera:.2f}s de {generacion_total:.2f}s: "
        "no esta hablando en paralelo")
    assert "Buenas tardes" in completo


def test_no_pierde_el_final_sin_puntuacion():
    dichas = []
    completo = speak_stream(iter(["Una respuesta que termina sin punto final"]),
                            dichas.append)
    assert "sin punto final" in completo
    assert dichas and "sin punto final" in dichas[-1]


def test_fallo_de_audio_no_rompe_la_respuesta():
    """Si el TTS falla, el texto igual se devuelve completo."""
    def _speak_roto(_texto):
        raise RuntimeError("tarjeta de sonido ocupada")

    completo = speak_stream(iter(["Primera frase completa aqui. ", "Segunda parte."]),
                            _speak_roto)
    assert "Primera frase" in completo and "Segunda parte" in completo


def test_stream_vacio():
    dichas = []
    assert speak_stream(iter([]), dichas.append) == ""
    assert dichas == []


def test_on_token_recibe_cada_token():
    vistos = []
    speak_stream(iter(["a", "b", "c"]), lambda _t: None, on_token=vistos.append)
    assert vistos == ["a", "b", "c"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: Todos los tests de streaming pasaron.")
