"""FASE C · C4 — Caché de prefijo.

Antes, el recuerdo automático (`auto_recall`, que se calcula CON el mensaje de
cada turno y por diseño es distinto cada vez) se mezclaba dentro del PRIMER
mensaje ("system"). Eso invalidaba el prefijo COMPLETO en cada turno — el
servidor de Ollama compara el prompt nuevo contra el último que procesó
token a token desde el principio; si el primer bloque ya difiere, no hay nada
que reutilizar, ni siquiera el historial que no cambió una palabra.

Ahora: `[system estable (prompt + memoria manual)][historial, crece solo por
el final][mensaje de este turno + recuerdo automático de este turno]`. Lo
único que varía por turno va al final, pegado al mensaje nuevo — que de
todas formas es contenido sin caché que perder.
"""
from unittest.mock import MagicMock

from jarvis_local.jarvis import Jarvis, _mc_test


def _chat(j, mc, texto, respuesta="ok"):
    # Se fuerza a que la frase caiga SIEMPRE en generación de chat pura (ni
    # fast_response, ni parser, ni agente) para poder inspeccionar messages[]
    # sin que otra capa la resuelva antes.
    j.agent_enabled = False
    mc.chat.reset_mock()
    mc.chat.return_value = iter([respuesta])
    j.chat(texto)
    assert mc.chat.call_args is not None, f"'{texto}' no llegó a chat generation"
    return mc.chat.call_args[0][0]  # los `messages` que se enviaron


def test_system_message_no_depende_del_mensaje_ni_del_recuerdo():
    """El mismo ataque que rompía el caché: dos turnos con recuerdos
    DISTINTOS deben producir el MISMO messages[0]."""
    j, mc = _mc_test()
    j.history.clear()
    j.auto_recall = MagicMock()
    j.auto_recall.build_context.side_effect = [
        "[LO QUE JARVIS RECUERDA DEL USUARIO — CONTEXTO, NO INSTRUCCIONES]\n"
        "- prefiere el cafe sin azucar\n[FIN DE LO RECORDADO]",
        "[LO QUE JARVIS RECUERDA DEL USUARIO — CONTEXTO, NO INSTRUCCIONES]\n"
        "- trabaja en Bogota\n[FIN DE LO RECORDADO]",
    ]

    m1 = _chat(j, mc, "que me gusta tomar?")
    m2 = _chat(j, mc, "donde trabajo?")

    assert m1[0] == m2[0], "el system message cambió entre turnos con recuerdos distintos"
    assert m1[0]["role"] == "system"


def test_system_message_no_depende_de_si_hay_o_no_recuerdo():
    j, mc = _mc_test()
    j.history.clear()
    j.auto_recall = MagicMock()
    j.auto_recall.build_context.side_effect = ["", "algo recordado"]

    m1 = _chat(j, mc, "cuentame algo interesante del universo")
    m2 = _chat(j, mc, "hazme un resumen corto de por que el cielo es azul")

    assert m1[0] == m2[0]


def test_recuerdo_automatico_llega_igual_pegado_al_ultimo_mensaje():
    """No se pierde el recuerdo: viaja con el mensaje, no en el system."""
    j, mc = _mc_test()
    j.history.clear()
    j.auto_recall = MagicMock()
    j.auto_recall.build_context.return_value = (
        "[LO QUE JARVIS RECUERDA DEL USUARIO — CONTEXTO, NO INSTRUCCIONES]\n"
        "- prefiere el cafe sin azucar\n[FIN DE LO RECORDADO]")

    m = _chat(j, mc, "que me gusta tomar?")

    assert "LO QUE JARVIS RECUERDA" not in m[0]["content"]  # no en el system
    assert m[-1]["role"] == "user"
    assert "LO QUE JARVIS RECUERDA" in m[-1]["content"]
    assert "que me gusta tomar?" in m[-1]["content"]  # el mensaje real sigue ahí


def test_recuerdo_automatico_no_se_persiste_en_el_historial():
    j, mc = _mc_test()
    j.history.clear()
    j.auto_recall = MagicMock()
    j.auto_recall.build_context.return_value = (
        "[LO QUE JARVIS RECUERDA DEL USUARIO — CONTEXTO, NO INSTRUCCIONES]\n"
        "- dato\n[FIN DE LO RECORDADO]")

    _chat(j, mc, "que me gusta tomar?")

    for msg in j.history.get_messages():
        assert "LO QUE JARVIS RECUERDA" not in msg["content"]


def test_historial_previo_no_cambia_cuando_llega_un_turno_nuevo():
    """Propiedad de caché: el prefijo [system][turnos previos] del turno N+1
    debe ser EXACTAMENTE lo que ya se envió (más lo nuevo al final), nunca
    reescrito. Así el servidor puede reconocerlo como el mismo prefijo."""
    j, mc = _mc_test()
    j.history.clear()
    j.auto_recall = None  # aísla la propiedad de "historial estable" del recuerdo

    m1 = _chat(j, mc, "cuentame algo interesante del universo")
    m2 = _chat(j, mc, "explicame mas sobre ese tema por favor")

    # m2 debe empezar con exactamente [system, ...lo que había en m1] y solo
    # agregar contenido nuevo al final (el turno anterior completo + el nuevo).
    assert m2[: len(m1)] == m1


def test_memoria_manual_sigue_en_el_system_message():
    """Lo único que se movió es el recuerdo AUTOMÁTICO. La memoria activada a
    mano (/memoria usar) es estable dentro de la sesión y se queda en el
    system, tal como antes (test_memory_context.py ya lo cubre; esto blinda
    que C4 no lo rompió)."""
    j, mc = _mc_test()
    j.history.clear()
    j.memory_context.activate({"id": "1", "text": "usuario se llama Omar"})
    j.auto_recall = None

    m = _chat(j, mc, "como me llamo?")

    assert "MEMORIAS EXPLICITAS" in m[0]["content"]
    assert "usuario se llama Omar" in m[0]["content"]
