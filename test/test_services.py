"""PLAN_EJECUCION FASE E · E4 — servicios systemd.

`systemctl` se simula. Se comprueban: E1 (unidades intocables), E2 (system ->
sudo con regla concreta), solo user por defecto, y el VERIFY (releer el estado;
un systemctl que devuelve 0 y deja el servicio igual = ERROR).
"""
import os
import re
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import services as S

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or", re.I)


def _cp(stdout="", rc=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _show_out(load="loaded", active="inactive", sub="dead", ufs="enabled"):
    return (f"LoadState={load}\nActiveState={active}\nSubState={sub}\n"
            f"UnitFileState={ufs}\n")


class _Systemctl:
    """Simula `_systemctl(scope, *args)`. `estados` mapea unidad -> ActiveState
    y las acciones lo mutan."""

    def __init__(self, estados=None, rc_accion=0, stderr="", muta=True):
        self.estados = dict(estados or {})
        self.rc_accion = rc_accion
        self.stderr = stderr
        self.muta = muta            # False = la acción "tiene éxito" pero no cambia nada
        self.llamadas = []

    def __call__(self, scope, *args):
        self.llamadas.append((scope, args))
        if args and args[0] == "show":
            unit = args[1]
            act = self.estados.get(unit)
            if act is None:
                return _cp(_show_out(load="not-found", active="inactive"))
            return _cp(_show_out(active=act, sub="running" if act == "active" else "dead"))
        if args and args[0] in ("start", "stop", "restart"):
            unit = args[1]
            if self.rc_accion == 0 and self.muta:
                self.estados[unit] = "inactive" if args[0] == "stop" else "active"
            return _cp(rc=self.rc_accion, stderr=self.stderr)
        return _cp()


def _patch(monkeypatch, sysctl, hay=True):
    from jarvis_local.safety import permisos
    monkeypatch.setattr(S, "_systemctl", sysctl)
    monkeypatch.setattr(S, "_hay_systemctl", lambda: hay)
    # sin instalación de paquetes en curso salvo que el test la active
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: False)


# --- lectura -------------------------------------------------------------


def test_status_de_servicio_activo(monkeypatch):
    _patch(monkeypatch, _Systemctl({"cups.service": "active"}))
    plan = S.service_status("cups")
    assert plan.status == ActionStatus.EXECUTED
    assert "active" in plan.result and "cups.service" in plan.result


def test_status_servicio_inexistente(monkeypatch):
    _patch(monkeypatch, _Systemctl({}))
    plan = S.service_status("no_existe_xyz")
    assert "no encontré" in plan.result.lower()


def test_sin_systemctl_lo_dice(monkeypatch):
    _patch(monkeypatch, _Systemctl({}), hay=False)
    plan = S.service_status("cups")
    assert plan.status == ActionStatus.ERROR
    assert "systemctl" in plan.result.lower()


# --- plan_service: reglas ---------------------------------------------


def test_unidad_intocable_bloqueada(monkeypatch):
    _patch(monkeypatch, _Systemctl({"NetworkManager.service": "active"}))
    plan = S.plan_service("parar", "NetworkManager", scope="system")
    assert plan.status == ActionStatus.BLOCKED
    assert "no voy a tocar" in plan.result.lower()
    assert "red" in plan.result.lower()
    assert not _EXITO.search(plan.result)


def test_servicio_de_sistema_pide_sudo_con_regla_concreta(monkeypatch):
    _patch(monkeypatch, _Systemctl({"cups.service": "active"}))
    plan = S.plan_service("reiniciar", "cups", scope="system")
    assert plan.status == ActionStatus.BLOCKED
    assert "no uso sudo" in plan.result.lower()
    assert "cups.service" in plan.result
    assert "systemctl start cups.service" in plan.result   # <UNIDAD> sustituido
    assert "<UNIDAD>" not in plan.result


def test_servicio_de_usuario_valido_queda_pendiente(monkeypatch):
    _patch(monkeypatch, _Systemctl({"syncthing.service": "inactive"}))
    plan = S.plan_service("iniciar", "syncthing", scope="user")
    assert plan.status == ActionStatus.PLANNED
    t = plan.simulation_result
    assert "syncthing.service" in t and "estado ahora: inactive" in t
    assert "/confirmar" in t and "/cancelar" in t


def test_accion_desconocida(monkeypatch):
    _patch(monkeypatch, _Systemctl({"x.service": "active"}))
    plan = S.plan_service("explota", "x")
    assert plan.status == ActionStatus.BLOCKED
    assert "iniciar, parar o reiniciar" in plan.result


# --- execute_service: VERIFY releyendo el estado -----------------------


def test_iniciar_ok_y_verifica(monkeypatch):
    sc = _Systemctl({"syncthing.service": "inactive"})
    _patch(monkeypatch, sc)
    plan = S.execute_service("iniciar", "syncthing", scope="user")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "active" in plan.result


def test_systemctl_rc0_pero_servicio_no_arranca_es_error(monkeypatch):
    # la acción "tiene éxito" (rc 0) pero el estado no cambia
    sc = _Systemctl({"syncthing.service": "inactive"}, muta=False)
    _patch(monkeypatch, sc)
    plan = S.execute_service("iniciar", "syncthing", scope="user")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert "quedó en inactive" in plan.result or "no en active" in plan.result
    assert not _EXITO.search(plan.result)


def test_systemctl_falla_rc_no_cero(monkeypatch):
    sc = _Systemctl({"syncthing.service": "inactive"}, rc_accion=1,
                    stderr="Failed to start syncthing.service: Unit not found.")
    _patch(monkeypatch, sc)
    plan = S.execute_service("iniciar", "syncthing", scope="user")
    assert plan.status == ActionStatus.ERROR
    assert "no pude" in plan.result.lower()
    assert "Unit not found" in plan.result


def test_execute_re_chequea_intocables(monkeypatch):
    _patch(monkeypatch, _Systemctl({"gdm.service": "active"}))
    plan = S.execute_service("parar", "gdm", scope="system")
    assert plan.status == ActionStatus.BLOCKED


def test_no_toca_servicios_con_instalacion_de_paquetes_en_curso(monkeypatch):
    from jarvis_local.safety import permisos
    _patch(monkeypatch, _Systemctl({"syncthing.service": "active"}))
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: True)
    plan = S.plan_service("reiniciar", "syncthing", scope="user")
    assert plan.status == ActionStatus.BLOCKED
    assert "instalación" in plan.result or "actualización" in plan.result


if __name__ == "__main__":
    print("usa pytest")
