"""PLAN_EJECUCION FASE E · E3 — procesos.

psutil se simula: no se mata nada real. Se comprueban las reglas duras
(E1 intocables, E2 sudo, no elegir por el usuario, SIGTERM→SIGKILL con
segundo aviso) y el VERIFY (un kill que deja el proceso vivo = ERROR).
"""
import os
import re
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.safety import permisos
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import processes as P

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or|correctamente\.", re.I)


class _NoSuchProcess(Exception):
    pass


class _AccessDenied(Exception):
    pass


class FakeProc:
    def __init__(self, pid, name, user="omar", cmd=None, vivo=True):
        self.pid = pid
        self._name = name
        self._user = user
        self._cmd = cmd or [name]
        self.vivo = vivo
        self.info = {"pid": pid, "name": name, "username": user}

    def name(self): return self._name
    def username(self): return self._user
    def cmdline(self): return list(self._cmd)
    def cpu_percent(self, _=None): return 0.0
    def memory_info(self): return type("M", (), {"rss": 10 * 1024 * 1024})()
    def status(self): return "running"
    def terminate(self): self.vivo = False        # por defecto: SIGTERM funciona
    def kill(self): self.vivo = False


class FakePsutil:
    NoSuchProcess = _NoSuchProcess
    AccessDenied = _AccessDenied
    STATUS_ZOMBIE = "zombie"

    def __init__(self, procs):
        self._procs = {p.pid: p for p in procs}

    def Process(self, pid):
        p = self._procs.get(int(pid))
        if p is None or not p.vivo:
            raise _NoSuchProcess(pid)
        return p

    def process_iter(self, attrs=None):
        return [p for p in self._procs.values() if p.vivo]

    def pid_exists(self, pid):
        p = self._procs.get(int(pid))
        return bool(p and p.vivo)

    def wait_procs(self, procs, timeout=None):
        return [], [p for p in procs if getattr(p, "vivo", False)]

    def cpu_percent(self, interval=0): return 0.0


@pytest.fixture
def _fake(monkeypatch):
    procs = [
        FakeProc(4321, "firefox", cmd=["/usr/bin/firefox"]),
        FakeProc(5000, "firefox", cmd=["/usr/bin/firefox", "--new-tab"]),
        FakeProc(900, "gnome-shell", cmd=["/usr/bin/gnome-shell"]),
        FakeProc(100, "postgres", user="postgres", cmd=["postgres", "-D", "/var/lib/pg"]),
        FakeProc(7777, "sleep", cmd=["sleep", "999"]),
    ]
    fp = FakePsutil(procs)
    monkeypatch.setattr(P, "_psutil", lambda: fp)
    # E2: 'mío' salvo postgres (otro usuario)
    monkeypatch.setattr(permisos, "proceso_es_del_usuario",
                        lambda pid: pid != 100)
    # por defecto, sin instalación de paquetes en curso (los tests que la
    # necesitan la activan)
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: False)
    return fp


# --- listar ---------------------------------------------------------------


def test_list_processes_formatea_y_ordena(_fake):
    plan = P.list_processes("ram", top=3)
    assert plan.status == ActionStatus.EXECUTED
    assert "MB RAM" in plan.result
    assert "firefox" in plan.result


# --- plan_kill: las reglas duras ---------------------------------------


def test_intocable_no_se_mata_ni_a_peticion_explicita(_fake):
    plan = P.plan_kill("gnome-shell")
    assert plan.status == ActionStatus.BLOCKED
    assert "no voy a matar" in plan.result.lower()
    assert "sesión" in plan.result.lower() or "sesion" in plan.result.lower()
    # explica por qué Y ofrece la alternativa
    assert "no lo mato yo" in plan.result.lower() or "cierra sesión" in plan.result.lower()
    assert not _EXITO.search(plan.result)


def test_pid_1_bloqueado(_fake):
    _fake._procs[1] = FakeProc(1, "systemd", user="root")
    plan = P.plan_kill("1")
    assert plan.status == ActionStatus.BLOCKED
    assert "init" in plan.result.lower()


def test_proceso_de_otro_usuario_pide_sudo(_fake):
    plan = P.plan_kill("100")
    assert plan.status == ActionStatus.BLOCKED
    assert "no uso sudo" in plan.result.lower()
    assert "sudo kill 100" in plan.result


def test_varios_matches_no_elige_jarvis(_fake):
    plan = P.plan_kill("firefox")
    assert plan.status == ActionStatus.BLOCKED
    assert "2 procesos" in plan.result
    assert "PID    4321" in plan.result and "PID    5000" in plan.result
    assert "dime el pid" in plan.result.lower()


def test_un_proceso_mio_queda_pendiente_mostrando_todo(_fake):
    plan = P.plan_kill("7777")
    assert plan.status == ActionStatus.PLANNED
    assert plan.params["pid"] == 7777
    t = plan.simulation_result
    assert "PID: 7777" in t and "usuario: omar" in t
    assert "sleep 999" in t
    assert "/confirmar" in t and "/cancelar" in t


# --- execute_kill: SIGTERM -> (segundo aviso) -> SIGKILL, con VERIFY -------


def test_sigterm_mata_y_verifica(_fake):
    plan = P.execute_kill(7777)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "SIGTERM" in plan.result
    assert not _fake.pid_exists(7777)


def test_sigterm_no_mata_no_finge_y_pide_segundo_confirmar(_fake):
    from jarvis_local.safety.policy import policy
    _fake._procs[7777].terminate = lambda: None      # SIGTERM no hace efecto

    plan = P.execute_kill(7777)
    assert plan.params["verify"]["ok"] is None       # NO es éxito
    assert not _EXITO.search(plan.result)
    assert "sigue vivo" in plan.result.lower()
    assert "sigkill" in plan.result.lower()
    # se armó un plan nuevo para el segundo /confirmar
    assert policy.pending_plan is not None
    assert policy.pending_plan.action == "forzar_matar_proceso"


def test_sigkill_que_no_mata_es_error_honesto(_fake):
    _fake._procs[7777].terminate = lambda: None
    _fake._procs[7777].kill = lambda: None           # ni SIGKILL hace efecto

    plan = P.execute_kill_force(7777)
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert "ni con sigkill" in plan.result.lower()
    assert not _EXITO.search(plan.result)


def test_execute_kill_re_chequea_intocables(_fake):
    # aunque se llame directo con un PID protegido, no lo mata
    plan = P.execute_kill(900)     # gnome-shell
    assert plan.status == ActionStatus.BLOCKED
    assert "gnome-shell" in plan.result


def test_proceso_de_root_con_instalacion_en_curso_se_bloquea(_fake, monkeypatch):
    """E1·c: un proceso del sistema mientras se instalan paquetes puede ser un
    script de mantenimiento -> no se toca hasta que la transacción acabe
    (y el mensaje habla de la instalación, no de sudo)."""
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: True)
    plan = P.plan_kill("100")   # postgres, de otro usuario
    assert plan.status == ActionStatus.BLOCKED
    assert "instalación" in plan.result or "actualización" in plan.result
    assert "sudo" not in plan.result.lower()


if __name__ == "__main__":
    print("usa pytest")
