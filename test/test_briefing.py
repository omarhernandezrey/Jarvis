"""Tests del resumen del dia"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import jarvis_local.tools.briefing as brief
from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus


def _con_secciones(clima, agenda, noticias, fn):
    originales = (brief._seccion_clima, brief._seccion_agenda,
                  brief._seccion_noticias)
    brief._seccion_clima = lambda: clima
    brief._seccion_agenda = lambda: agenda
    brief._seccion_noticias = lambda: noticias
    try:
        fn()
    finally:
        (brief._seccion_clima, brief._seccion_agenda,
         brief._seccion_noticias) = originales


def test_intent_resumen():
    for frase in ("dame el resumen del dia", "resumen del dia",
                  "ponme al dia", "como esta el dia"):
        r = parse_intent(frase)
        assert r.tool == "daily_briefing", frase


def test_intent_clima_no_robado():
    r = parse_intent("clima en Bogota")
    assert r.tool == "weather"


def test_briefing_completo():
    def caso():
        plan = brief.daily_briefing()
        assert plan.status == ActionStatus.EXECUTED
        assert "senor" in plan.result
        assert "soleado" in plan.result
        assert "reunion" in plan.result
        assert "titular" in plan.result
        assert "No pude consultar" not in plan.result
    _con_secciones("soleado 20 grados", "reunion a las 3", "titular de hoy",
                   caso)


def test_briefing_tolera_fallos():
    def caso():
        plan = brief.daily_briefing()
        assert plan.status == ActionStatus.EXECUTED
        assert "soleado" in plan.result
        assert "no pude consultar" in plan.result.lower()
        assert "su agenda" in plan.result.lower() or "agenda" in plan.result.lower()
    _con_secciones("soleado 20 grados", None, None, caso)


def test_briefing_todo_caido_no_revienta():
    def caso():
        plan = brief.daily_briefing()
        assert plan.status == ActionStatus.EXECUTED
        assert "Hoy es" in plan.result
    _con_secciones(None, None, None, caso)


def test_saludo_coherente_con_la_hora():
    s = brief._saludo()
    assert s in ("Buenos dias", "Buenas tardes", "Buenas noches")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK: Todos los tests de briefing pasaron.")
