"""PLAN_EJECUCION FASE D — el fallback de éxito no debe existir.

El patrón cazado: una capa baja devuelve un ActionPlan sin `.result` (o un
None), y la capa de arriba rellena el hueco con "Operacion completada." /
"Hecho, senor." — una acción NO hecha (BLOCKED / ERROR / PLANNED) reportada
como hecha. `describe_outcome` invierte el defecto: lo desconocido se dice.
"""
import inspect
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
from jarvis_local.tools._utils import describe_outcome

# Frases que afirman éxito. Si aparecen sin un resultado real detrás, es la
# mentira que este test persigue.
_EXITO = re.compile(
    r"operaci[oó]n completada|hecho,?\s*se[nñ]or|listo,?\s*se[nñ]or|"
    r"correctamente|realizado con [eé]xito|ejecutad[oa] con [eé]xito|"
    r"\bhecho\b\.?\s*$",
    re.IGNORECASE)


@pytest.mark.parametrize("status", list(ActionStatus))
def test_ningun_estado_sin_mensaje_finge_exito(status):
    """Un plan en CUALQUIER estado, sin `.result` ni `.error`, no puede salir
    como un éxito."""
    plan = ActionPlan(action="accion_x", risk=RiskLevel.EXECUTE)
    plan.status = status
    texto = describe_outcome(plan, tool="accion_x")
    assert not _EXITO.search(texto), (
        f"estado {status.value!r} sin mensaje produce texto de éxito: {texto!r}")
    # y además dice algo, no cadena vacía
    assert texto.strip()


def test_executed_sin_resultado_avisa_que_no_se_puede_confirmar():
    plan = ActionPlan(action="accion_x", risk=RiskLevel.EXECUTE)
    plan.status = ActionStatus.EXECUTED   # dice "hecho" pero no dejó nada
    texto = describe_outcome(plan, tool="accion_x").lower()
    assert "no puedo confirmar" in texto or "no informó" in texto


def test_none_no_es_exito():
    texto = describe_outcome(None, tool="accion_x").lower()
    assert not _EXITO.search(texto)
    assert "no" in texto and ("devolvió" in texto or "sé si funcion" in texto)


def test_estado_desconocido_se_reporta_como_desconocido():
    class Raro:
        result = ""
        error = ""
        status = None
    texto = describe_outcome(Raro(), tool="accion_x").lower()
    assert not _EXITO.search(texto)
    assert "no" in texto and "confirmar" in texto


def test_resultado_real_pasa_intacto():
    """Control positivo: si la herramienta SÍ informó, se respeta tal cual."""
    plan = ActionPlan(action="x", risk=RiskLevel.EXECUTE)
    plan.status = ActionStatus.EXECUTED
    plan.result = "Volumen al 40 por ciento, senor."
    assert describe_outcome(plan, tool="x") == "Volumen al 40 por ciento, senor."


def test_error_se_redacta():
    plan = ActionPlan(action="x", risk=RiskLevel.EXECUTE)
    plan.status = ActionStatus.ERROR
    plan.error = "fallo con token=supersecreto1234567890"
    texto = describe_outcome(plan, tool="x")
    assert "supersecreto1234567890" not in texto
    assert "Error" in texto


# --- integración: los tres puntos que antes tenían el fallback ---------------


def test_execute_tool_write_no_finge_exito_con_plan_bloqueado(monkeypatch):
    import jarvis_local.jarvis as J

    def _fake(_args):
        p = ActionPlan(action="cosa_peligrosa", risk=RiskLevel.DELETE)
        p.status = ActionStatus.BLOCKED   # bloqueada, sin .result
        return p

    monkeypatch.setitem(J._WRITE_TOOLS, "cosa_peligrosa", _fake)
    texto = J._execute_tool_write("cosa_peligrosa", {})
    assert not _EXITO.search(texto), texto
    assert "bloquea" in texto.lower()


def test_execute_tool_read_no_finge_exito_sin_resultado(monkeypatch):
    import jarvis_local.jarvis as J

    monkeypatch.setitem(J._READ_TOOLS, "consulta_muda",
                        lambda _a: ActionPlan(action="consulta_muda", risk=RiskLevel.READ))
    texto = J._execute_tool_read("consulta_muda", {})
    assert not _EXITO.search(texto), texto


def test_registry_execute_no_finge_exito(monkeypatch):
    from jarvis_local.agent import registry

    real = registry.get_tool

    class _T:
        name = "muda"
        parameters = {"type": "object", "properties": {}, "required": []}
        needs_confirmation = False

        def run(self, **_kw):
            p = ActionPlan(action="muda", risk=RiskLevel.EXECUTE)
            p.status = ActionStatus.EXECUTED   # "hecho" sin mensaje
            return p

    monkeypatch.setattr(registry, "get_tool",
                        lambda n: _T() if n == "muda" else real(n))
    texto, pendiente = registry.execute("muda", {})
    assert pendiente is False
    assert not _EXITO.search(texto), texto
    assert "confirmar" in texto.lower() or "no informó" in texto.lower()


def test_no_queda_el_literal_de_exito_en_los_puntos_de_choque():
    """Guarda de regresión: el fallback "Operacion completada." no vuelve a
    aparecer en las funciones que traducen resultados de herramientas."""
    import jarvis_local.jarvis as J
    from jarvis_local.agent import registry

    for fn in (J._execute_tool_read, J._execute_tool_write, registry.execute):
        src = inspect.getsource(fn)
        assert "Operacion completada" not in src, fn.__qualname__
        assert "Hecho, senor" not in src, fn.__qualname__


if __name__ == "__main__":
    print("usa pytest (parametrize + monkeypatch)")
