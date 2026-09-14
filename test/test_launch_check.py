"""Precondiciones del lanzador de escritorio (jarvis_local/ui/hud/launch_check.py).

El .desktop apunta aquí (via scripts/jarvis_launch.sh) para no abrir NUNCA una
ventana rota: si Ollama no responde (y no se puede levantar) o la máquina ya
está en el modo de fallo por memoria de docs/OPERACION_MEMORIA.md, se avisa
por notificación de escritorio y no se llega a abrir Qt.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.ui.hud import launch_check


def test_todo_bien_no_bloquea(monkeypatch):
    monkeypatch.setattr(launch_check, "_ollama_vivo", lambda: True)
    from jarvis_local.agent import memory_guard
    monkeypatch.setattr(memory_guard, "snapshot",
                        lambda: {"disponible": True, "ajustado": False,
                                 "en_swap": False, "degradado": False})
    assert launch_check.check_preconditions() is None


def test_memoria_ajustada_bloquea_antes_de_mirar_ollama(monkeypatch):
    llamadas = []
    monkeypatch.setattr(launch_check, "_ollama_vivo",
                        lambda: llamadas.append("ollama") or True)
    from jarvis_local.agent import memory_guard
    monkeypatch.setattr(memory_guard, "snapshot",
                        lambda: {"disponible": True, "ajustado": True,
                                 "en_swap": False, "mem_available_kb": 512_000})
    error = launch_check.check_preconditions()
    assert error is not None
    assert "RAM" in error
    assert "500 MB" in error
    assert "ollama" not in llamadas  # se bloquea antes, ni se llega a mirar


def test_memoria_ajustada_y_en_swap_lo_dice(monkeypatch):
    from jarvis_local.agent import memory_guard
    monkeypatch.setattr(memory_guard, "snapshot",
                        lambda: {"disponible": True, "ajustado": True,
                                 "en_swap": True, "mem_available_kb": 300_000})
    error = launch_check.check_preconditions()
    assert "swap" in error.lower()


def test_memoria_no_medible_no_bloquea(monkeypatch):
    """Windows u otro SO sin /proc/meminfo: memory_guard no-op, no bloquea."""
    from jarvis_local.agent import memory_guard
    monkeypatch.setattr(memory_guard, "snapshot", lambda: {"disponible": False})
    monkeypatch.setattr(launch_check, "_ollama_vivo", lambda: True)
    assert launch_check.check_preconditions() is None


def test_ollama_caido_y_se_levanta_no_bloquea(monkeypatch):
    from jarvis_local.agent import memory_guard
    monkeypatch.setattr(memory_guard, "snapshot",
                        lambda: {"disponible": True, "ajustado": False})
    monkeypatch.setattr(launch_check, "_ollama_vivo", lambda: False)
    monkeypatch.setattr(launch_check, "_levantar_ollama", lambda: True)
    assert launch_check.check_preconditions() is None


def test_ollama_caido_y_no_se_puede_levantar_bloquea(monkeypatch):
    from jarvis_local.agent import memory_guard
    monkeypatch.setattr(memory_guard, "snapshot",
                        lambda: {"disponible": True, "ajustado": False})
    monkeypatch.setattr(launch_check, "_ollama_vivo", lambda: False)
    monkeypatch.setattr(launch_check, "_levantar_ollama", lambda: False)
    error = launch_check.check_preconditions()
    assert error is not None
    assert "ollama serve" in error.lower()


def test_levantar_ollama_prueba_systemctl_con_timeout_y_sin_sleeps_reales(monkeypatch):
    """`_levantar_ollama` no debe colgarse nunca: cada subprocess.run lleva
    timeout, y aquí se comprueba que además reintenta con time.sleep (se
    stubea para no ralentizar el test)."""
    comandos = []

    def fake_run(cmd, **kw):
        comandos.append(cmd)
        assert kw.get("timeout"), f"sin timeout: {cmd}"
        raise launch_check.subprocess.TimeoutExpired(cmd=cmd, timeout=kw["timeout"])

    dormido = []
    monkeypatch.setattr(launch_check.subprocess, "run", fake_run)
    monkeypatch.setattr(launch_check.time, "sleep", lambda s: dormido.append(s))
    monkeypatch.setattr(launch_check, "_ollama_vivo", lambda: False)

    assert launch_check._levantar_ollama() is False
    assert len(comandos) == 2  # sudo -n systemctl y --user systemctl
    assert len(dormido) == launch_check._REINTENTOS_OLLAMA


def test_main_no_abre_hud_si_falla_precondicion(monkeypatch):
    """Si check_preconditions() falla, main() no debe ni importar la app Qt."""
    monkeypatch.setattr(launch_check, "check_preconditions", lambda: "algo fallo")
    notificado = {}

    def fake_notify(mensaje, **kw):
        notificado["mensaje"] = mensaje
        from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
        plan = ActionPlan(action="x", risk=RiskLevel.EXECUTE, reason="x")
        plan.status = ActionStatus.EXECUTED
        return plan

    monkeypatch.setattr("jarvis_local.tools.notify.send_notification", fake_notify)
    rc = launch_check.main()
    assert rc == 1
    assert notificado["mensaje"] == "algo fallo"


def test_main_abre_hud_si_todo_bien(monkeypatch):
    monkeypatch.setattr(launch_check, "check_preconditions", lambda: None)
    llamado = {}

    def fake_hud_main():
        llamado["ok"] = True
        return 0

    monkeypatch.setattr("jarvis_local.ui.hud.app.main", fake_hud_main)
    assert launch_check.main() == 0
    assert llamado.get("ok") is True


if __name__ == "__main__":
    print("usa pytest (estas pruebas usan fixtures)")
