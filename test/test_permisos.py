"""PLAN_EJECUCION FASE E · E2 — modelo de permisos.

Los tres niveles, el renderizador de confirmación y la puerta de sudo
(nunca implícito).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionStatus, RiskLevel


@pytest.mark.parametrize("risk, esperado", [
    (RiskLevel.NONE, "auto"),
    (RiskLevel.READ, "auto"),
    (RiskLevel.CREATE, "verificar"),
    (RiskLevel.EXECUTE, "verificar"),
    (RiskLevel.DELETE, "confirmar"),
    (RiskLevel.CRITICAL, "confirmar"),
])
def test_los_tres_niveles(risk, esperado):
    assert permisos.nivel(risk) == esperado
    assert permisos.exige_confirmacion(risk) is (esperado == "confirmar")


def test_texto_confirmacion_muestra_que_y_sobre_que():
    t = permisos.texto_confirmacion(
        "matar el proceso", "chrome",
        {"PID": 4321, "comando": "/usr/bin/chrome --type=renderer", "usuario": "omar"})
    assert "Voy a matar el proceso: chrome" in t
    assert "PID: 4321" in t
    assert "/usr/bin/chrome --type=renderer" in t
    assert "/confirmar" in t and "/cancelar" in t


def test_bloqueo_por_sudo_trae_la_regla_y_la_alternativa():
    plan = permisos.bloqueo_por_sudo(
        "systemctl_sistema", "reiniciar cups.service",
        hazlo_tu="sudo systemctl restart cups.service")
    assert plan.status == ActionStatus.BLOCKED
    assert "no uso sudo" in plan.result.lower()
    assert "/etc/sudoers.d/jarvis" in plan.result
    assert "visudo" in plan.result
    assert "NOPASSWD" in plan.result                  # la regla concreta
    assert "sudo systemctl restart cups.service" in plan.result   # la alternativa
    assert "operacion completada" not in plan.result.lower()


def test_bloqueo_por_sudo_matar_otro_usuario_no_da_regla_falsa():
    plan = permisos.bloqueo_por_sudo(
        "kill_otro_usuario", "matar el proceso 1 (root)",
        hazlo_tu="sudo kill 1")
    assert plan.status == ActionStatus.BLOCKED
    assert "no hay regla" in plan.result.lower() or "hazlo tú" in plan.result.lower()


def test_proceso_propio_es_del_usuario():
    assert permisos.proceso_es_del_usuario(os.getpid()) is True


@pytest.mark.skipif(os.getuid() == 0,
                    reason="ejecutando como root: root 'posee' todos los procesos "
                           "(caso CI en contenedor); la distinción solo aplica sin root")
def test_proceso_de_root_no_es_del_usuario():
    # PID 1 (systemd) es de root; un usuario normal no lo posee
    r = permisos.proceso_es_del_usuario(1)
    assert r in (False, None)   # False normal; None si psutil no puede leerlo


def test_proceso_inexistente_devuelve_none():
    assert permisos.proceso_es_del_usuario(999_999_999) is None


def test_unidad_de_usuario_vs_sistema():
    assert permisos.unidad_es_de_sistema("user") is False
    assert permisos.unidad_es_de_sistema("system") is True
    assert permisos.unidad_es_de_sistema("") is True          # por defecto, sistema
    assert permisos.unidad_es_de_sistema(None) is True


if __name__ == "__main__":
    print("usa pytest")
