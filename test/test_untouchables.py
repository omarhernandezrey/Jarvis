"""PLAN_EJECUCION FASE E · E1 — lista de intocables (guardia duro).

Antes de que E3/E4 puedan matar procesos o parar servicios: lo que NUNCA se
toca, ni a petición explícita. Matar gnome-shell = perder la sesión.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.safety.untouchables import (
    is_untouchable_process,
    is_untouchable_unit,
    own_pids,
)


@pytest.mark.parametrize("name", [
    "gnome-shell", "mutter", "systemd", "systemd-logind", "dbus-daemon",
    "NetworkManager", "sshd", "ollama", "llama-server",          # [base]
    "gdm3", "gdm-session-worker", "Xwayland", "gnome-session-binary",
    "wpa_supplicant", "ModemManager", "polkitd", "pipewire",
    "pipewire-pulse", "wireplumber", "systemd-journald", "systemd-resolved",
    "dbus-broker",                                               # [+E1]
    "dockerd", "docker", "containerd", "containerd-shim",        # [+E1·b]
])
def test_proceso_critico_es_intocable(name):
    ok, motivo = is_untouchable_process(name=name)
    assert ok is True
    assert motivo and len(motivo) > 15          # explica POR QUÉ


@pytest.mark.parametrize("name", [
    "chrome", "firefox", "code", "python", "node", "slack", "spotify",
    "libreoffice", "gedit", "htop", "vlc",
])
def test_app_de_usuario_no_es_intocable(name):
    ok, _ = is_untouchable_process(name=name)
    assert ok is False


def test_comm_truncado_a_15_chars_tambien_casa():
    # `ps` corta `comm` a 15: gnome-session-binary -> "gnome-session-b"
    assert is_untouchable_process(name="gnome-session-b")[0] is True
    assert is_untouchable_process(name="mutter-x11-fram")[0] is True
    assert is_untouchable_process(name="gdm-session-wor")[0] is True


def test_match_por_cmdline_cuando_el_nombre_es_generico():
    ok, _ = is_untouchable_process(
        name="llama-server",
        cmdline="/usr/local/lib/ollama/llama-server --model ... --port 46841")
    assert ok is True
    # 'ollama' como palabra en la ruta del binario
    ok2, _ = is_untouchable_process(
        name="ollama", cmdline="/usr/local/bin/ollama serve")
    assert ok2 is True


def test_pid_1_es_intocable():
    ok, motivo = is_untouchable_process(name="cualquiera", pid=1)
    assert ok is True and "init" in motivo.lower()


def test_jarvis_no_se_mata_a_si_mismo():
    ok, motivo = is_untouchable_process(name="python", pid=os.getpid())
    assert ok is True and ("yo" in motivo.lower() or "ejecut" in motivo.lower())
    assert os.getpid() in own_pids()


def test_falso_positivo_ollama_helper_no_casa():
    ok, _ = is_untouchable_process(
        name="python", cmdline="python /home/omar/ollama_helper_de_terceros.py")
    assert ok is False


# --- unidades systemd (E4) --------------------------------------------------


@pytest.mark.parametrize("unit", [
    "gdm.service", "NetworkManager.service", "dbus.service",
    "systemd-logind.service", "ssh.service", "ollama.service",
    "wpa_supplicant.service", "polkit.service", "systemd-journald.service",
    "user@1000.service", "docker.service", "containerd.service",   # [+E1·b]
])
def test_unidad_critica_es_intocable(unit):
    ok, motivo = is_untouchable_unit(unit)
    assert ok is True and motivo

    # sin sufijo .service también
    if unit.endswith(".service") and not unit.startswith("user@"):
        assert is_untouchable_unit(unit[:-len(".service")])[0] is True


@pytest.mark.parametrize("unit", [
    "cups.service", "bluetooth.service", "cron.service",
    "unattended-upgrades.service", "chrony.service",
])
def test_unidad_no_critica_no_es_intocable(unit):
    assert is_untouchable_unit(unit)[0] is False


if __name__ == "__main__":
    print("usa pytest")
