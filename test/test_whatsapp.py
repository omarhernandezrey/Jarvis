"""Tests de envio de WhatsApp y contactos"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import jarvis_local.tools.whatsapp as wa
from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus


def _con_entorno_de_prueba(fn):
    """Store temporal de contactos y apertura capturada (no abre ventanas)."""
    original_path = wa.CONTACTS_PATH
    original_open = wa._open_whatsapp
    wa.CONTACTS_PATH = original_path + ".test"
    aperturas = []

    def fake_open(phone, message):
        aperturas.append((phone, message))
        return "web"

    wa._open_whatsapp = fake_open
    try:
        if os.path.exists(wa.CONTACTS_PATH):
            os.remove(wa.CONTACTS_PATH)
        fn(aperturas)
    finally:
        if os.path.exists(wa.CONTACTS_PATH):
            os.remove(wa.CONTACTS_PATH)
        wa.CONTACTS_PATH = original_path
        wa._open_whatsapp = original_open


# --- Enrutamiento del parser ---


def test_intent_enviar_whatsapp():
    r = parse_intent("enviale un whatsapp a juan diciendo que ya voy en camino")
    assert r.kind == "tool_execute"
    assert r.tool == "send_whatsapp"
    assert r.arguments["to"] == "juan"
    assert "ya voy en camino" in r.arguments["message"]


def test_intent_whatsapp_a_numero():
    r = parse_intent("manda un whatsapp al 3001234567 diciendo hola")
    assert r.tool == "send_whatsapp"
    assert r.arguments["to"] == "3001234567"
    assert r.arguments["message"] == "hola"


def test_intent_whatsapp_incompleto_pregunta():
    r = parse_intent("enviale un whatsapp a juan")
    assert r.kind == "ambiguous"


def test_intent_agregar_contacto():
    r = parse_intent("agrega el contacto juan con numero 3001234567")
    assert r.tool == "add_contact"
    assert r.arguments["name"] == "juan"
    assert "3001234567" in r.arguments["phone"]


def test_intent_listar_contactos():
    r = parse_intent("muestrame mis contactos")
    assert r.tool == "list_contacts"


def test_intent_correo_no_robado():
    r = parse_intent("envia un correo a omar asunto hola mensaje que tal")
    assert r.tool == "send_email"


# --- Herramientas ---


def test_enviar_a_numero_directo():
    def caso(aperturas):
        plan = wa.send_whatsapp("300 123 4567", "hola senor")
        assert plan.status == ActionStatus.EXECUTED
        assert aperturas == [("573001234567", "hola senor")]
    _con_entorno_de_prueba(caso)


def test_enviar_a_contacto_guardado():
    def caso(aperturas):
        assert wa.add_contact("Juan Perez", "3009876543").status == ActionStatus.EXECUTED
        plan = wa.send_whatsapp("juan", "nos vemos")
        assert plan.status == ActionStatus.EXECUTED
        assert aperturas == [("573009876543", "nos vemos")]
    _con_entorno_de_prueba(caso)


def test_contacto_inexistente_explica():
    def caso(aperturas):
        plan = wa.send_whatsapp("desconocido", "hola")
        assert plan.status == ActionStatus.ERROR
        assert "no tengo el numero" in plan.result.lower()
        assert not aperturas
    _con_entorno_de_prueba(caso)


def test_numero_internacional_se_respeta():
    def caso(aperturas):
        wa.send_whatsapp("+1 555 123 4567", "hi")
        assert aperturas[0][0] == "15551234567"
    _con_entorno_de_prueba(caso)


def test_listar_contactos_tool():
    def caso(aperturas):
        wa.add_contact("maria", "3111111111")
        plan = wa.list_contacts()
        assert "maria" in plan.result
        assert "573111111111" in plan.result
    _con_entorno_de_prueba(caso)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de whatsapp pasaron.")
