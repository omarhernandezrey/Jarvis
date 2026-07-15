"""Tests de recordatorios con alarma"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import jarvis_local.tools.reminders as rem
from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus


def _con_store_limpio(fn):
    """Ejecuta un test con un store temporal, sin tocar el real."""
    original = rem.REMINDERS_PATH
    rem.REMINDERS_PATH = original + ".test"
    hook_original = rem._notify_hook
    avisos = []
    rem._notify_hook = avisos.append
    try:
        if os.path.exists(rem.REMINDERS_PATH):
            os.remove(rem.REMINDERS_PATH)
        fn(avisos)
    finally:
        for t in rem._TIMERS.values():
            t.cancel()
        rem._TIMERS.clear()
        if os.path.exists(rem.REMINDERS_PATH):
            os.remove(rem.REMINDERS_PATH)
        rem.REMINDERS_PATH = original
        rem._notify_hook = hook_original


# --- Enrutamiento del parser ---


def test_intent_recordatorio_minutos():
    r = parse_intent("recuerdame en 20 minutos sacar la comida")
    assert r.kind == "tool_execute"
    assert r.tool == "set_reminder"
    assert r.arguments["minutes"] == 20
    assert "sacar la comida" in r.arguments["text"]


def test_intent_recordatorio_texto_antes():
    r = parse_intent("recuerdame sacar la comida en 20 minutos")
    assert r.tool == "set_reminder"
    assert r.arguments["minutes"] == 20
    assert "sacar la comida" in r.arguments["text"]


def test_intent_recordatorio_palabras():
    r = parse_intent("avisame en cinco minutos que revise el horno")
    assert r.tool == "set_reminder"
    assert r.arguments["minutes"] == 5


def test_intent_recordatorio_hora():
    r = parse_intent("recuerdame a las 3:30 de la tarde llamar a juan")
    assert r.tool == "set_reminder"
    assert r.arguments["at"] == "15:30"
    assert "llamar a juan" in r.arguments["text"]


def test_intent_recordatorio_media_hora():
    r = parse_intent("ponme una alarma en media hora")
    assert r.tool == "set_reminder"
    assert r.arguments["minutes"] == 30


def test_intent_alarma_sin_tiempo_pregunta():
    r = parse_intent("ponme una alarma")
    assert r.kind == "ambiguous"


def test_intent_recuerdame_sin_tiempo_va_al_agente():
    # sin tiempo es memoria permanente (herramienta 'recordar'), no alarma
    r = parse_intent("recuerdame que soy alergico al mani")
    assert r.tool != "set_reminder"


def test_intent_listar_recordatorios():
    r = parse_intent("que recordatorios tengo")
    assert r.tool == "list_reminders"


def test_intent_cancelar_recordatorio():
    r = parse_intent("cancela el recordatorio 2")
    assert r.tool == "cancel_reminder"
    assert r.arguments["which"] == "2"
    r = parse_intent("borra todos los recordatorios")
    assert r.tool == "cancel_reminder"
    assert r.arguments["which"] == "todos"


def test_intent_borrar_archivo_no_robado():
    r = parse_intent(r"borra C:\Users\herna\Documents\viejo.txt")
    assert r.tool == "delete_file"


# --- Herramienta: la alarma DE VERDAD suena ---


def test_alarma_suena():
    def caso(avisos):
        plan = rem.set_reminder("probar la alarma", minutes=0.03)  # ~1.8 s
        assert plan.status == ActionStatus.EXECUTED
        assert len(rem._load_store()) == 1
        time.sleep(4)
        assert avisos, "la alarma nunca disparo"
        assert "probar la alarma" in avisos[0]
        assert rem._load_store() == []  # se limpia al disparar
    _con_store_limpio(caso)


def test_listar_y_cancelar():
    def caso(avisos):
        rem.set_reminder("uno", minutes=60)
        rem.set_reminder("dos", minutes=120)
        listado = rem.list_reminders()
        assert "uno" in listado.result and "dos" in listado.result
        plan = rem.cancel_reminder("1")
        assert plan.status == ActionStatus.EXECUTED
        assert len(rem._load_store()) == 1
        plan = rem.cancel_reminder("todos")
        assert rem._load_store() == []
        assert not avisos  # nada debio sonar
    _con_store_limpio(caso)


def test_cancelar_por_texto():
    def caso(avisos):
        rem.set_reminder("sacar el arroz", minutes=60)
        rem.set_reminder("llamar al banco", minutes=60)
        rem.cancel_reminder("arroz")
        restantes = rem._load_store()
        assert len(restantes) == 1
        assert restantes[0]["text"] == "llamar al banco"
    _con_store_limpio(caso)


def test_rearme_tras_reinicio():
    def caso(avisos):
        # simular que JARVIS se cerro con un recordatorio pendiente
        rem._save_store([{"id": 7, "text": "pendiente viejo",
                          "when": (datetime.now() - timedelta(minutes=5)).isoformat()}])
        rem._loaded = False
        rem.ensure_loaded()
        time.sleep(4)
        assert avisos, "el recordatorio vencido no se aviso al reiniciar"
        assert "pendiente viejo" in avisos[0]
    _con_store_limpio(caso)


def test_hora_pasada_va_a_manana():
    hace_una_hora = datetime.now() - timedelta(hours=1)
    when = rem._parse_hora(f"{hace_una_hora.hour}:00")
    assert when > datetime.now()


def test_sin_tiempo_da_error_amable():
    def caso(avisos):
        plan = rem.set_reminder("algo")
        assert plan.status == ActionStatus.ERROR
        assert "cuando" in plan.result.lower()
    _con_store_limpio(caso)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de recordatorios pasaron.")
