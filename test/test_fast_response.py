"""
Tests de la capa de respuestas instantaneas (capa 1 de la cascada).

Regresion importante: las formulas de cortesia se comparaban con re.search
sobre el mensaje entero, asi que cualquier peticion que CONTUVIERA un saludo
se respondia como saludo y nunca bajaba al agente. Casos reales que fallaban:
  "que tal anda mi maquina de recursos"  -> "que tal" -> saludo
  "buenas, abre chrome"                  -> "buenas"  -> saludo
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.fast_response import fast_respond

# ---------- La cortesia sigue siendo instantanea ----------

def test_saludos_responden_al_instante():
    for frase in ("hola", "hola jarvis", "buenas tardes", "buenos dias senor",
                  "hey jarvis", "que tal", "que tal jarvis", "saludos"):
        assert fast_respond(frase) is not None, frase


def test_gracias_y_despedidas():
    for frase in ("gracias", "muchas gracias jarvis", "adios",
                  "chao jarvis", "hasta luego"):
        assert fast_respond(frase) is not None, frase


def test_estado_de_jarvis():
    for frase in ("como estas", "todo bien", "como estas jarvis"):
        assert fast_respond(frase) is not None, frase


def test_hora_y_fecha():
    assert fast_respond("que hora es") is not None
    assert fast_respond("que dia es hoy") is not None


# ---------- Una peticion con saludo NO es un saludo ----------

def test_peticion_con_cortesia_no_se_traga():
    """El bug original: estas frases devolvian el saludo y no hacian nada."""
    casos = [
        "que tal anda mi maquina de recursos",   # -> estado del sistema
        "buenas, abre chrome",                   # -> abrir app
        "hola jarvis, cual es el clima en Bogota",
        "gracias, ahora busca trabajo de disenador",
        "como esta la memoria ram de mi pc",     # NO es "como estas"
        "que tal si me cuentas un chiste",
        "hola, necesito que tomes una captura",
    ]
    for frase in casos:
        assert fast_respond(frase) is None, (
            f"'{frase}' se respondio como cortesia y nunca llegaria al agente")


def test_estado_del_pc_no_es_estado_de_jarvis():
    """'como estas' (JARVIS) vs 'como esta la ram' (el computador)."""
    assert fast_respond("como estas") is not None
    assert fast_respond("como esta el uso de cpu") is None


def test_mensaje_normal_va_al_llm():
    assert fast_respond("de que color es el cielo") is None
    assert fast_respond("") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: Todos los tests de respuestas instantaneas pasaron.")
