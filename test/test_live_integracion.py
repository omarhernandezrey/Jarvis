"""TAREA D2 — tests `live`: pegan a los servicios externos REALES.

No corren por defecto (`addopts = -m 'not live'`). Se ejecutan con
`pytest -m live` y en el job nocturno de CI. Sirven para detectar cuando una
API externa cambia de forma y rompe lo que el código espera — algo que los
tests mockeados no pueden ver.

    pytest -m live            # solo estos
    pytest -m "live and not slow"
"""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from jarvis_local.safety.policy import ActionStatus

pytestmark = pytest.mark.live


def _sin_red() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3).close()
        return False
    except OSError:
        return True


skip_sin_red = pytest.mark.skipif(_sin_red(), reason="sin conexión a internet")


@skip_sin_red
def test_open_meteo_clima_real():
    from jarvis_local.tools.weather import get_weather

    plan = get_weather("Bogota")
    assert plan.status == ActionStatus.EXECUTED
    assert "grados" in plan.result.lower()
    assert "bogot" in plan.result.lower()


@skip_sin_red
def test_open_meteo_ciudad_inexistente_no_rompe():
    from jarvis_local.tools.weather import get_weather

    plan = get_weather("Ciudad Que No Existe XYZ 999")
    assert plan.status == ActionStatus.ERROR
    assert "no encontre" in plan.result.lower()


@skip_sin_red
def test_wikipedia_real():
    from jarvis_local.tools.wiki import wiki_summary

    plan = wiki_summary("Gabriel Garcia Marquez")
    assert plan.status == ActionStatus.EXECUTED
    assert "wikipedia" in plan.result.lower()
    assert len(plan.result) > 80


@skip_sin_red
def test_nominatim_geocodifica_un_poi_real():
    from jarvis_local.tools.location import geocode_osm

    d = geocode_osm("torre eiffel")
    assert d is not None
    assert "eiffel" in d["name"].lower() or "eiffel" in d["country"].lower()
    assert -90 <= d["latitude"] <= 90 and -180 <= d["longitude"] <= 180


@skip_sin_red
def test_wolframalpha_real():
    from jarvis_local.tools.wolfram import ask_wolfram, has_app_id

    if not has_app_id():
        pytest.skip("WolframAlpha sin app_id en secrets.yaml")
    plan = ask_wolfram("derivada de x^2")
    assert plan.status == ActionStatus.EXECUTED
    assert "2" in plan.result and "x" in plan.result.lower()


@skip_sin_red
def test_ip_publica_real():
    from jarvis_local.tools.ip_info import get_ip

    plan = get_ip()
    assert plan.status == ActionStatus.EXECUTED
    assert "IP publica" in plan.result


@skip_sin_red
@pytest.mark.slow
def test_empleo_computrabajo_real():
    from jarvis_local.tools.jobs import search_jobs

    plan = search_jobs("desarrollador", "Bogota")
    # puede no devolver ofertas si el portal cambia; lo importante es que no crashea
    assert plan.status in (ActionStatus.EXECUTED, ActionStatus.ERROR)
    assert plan.result
