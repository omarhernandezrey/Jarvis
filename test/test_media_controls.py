"""PLAN_EJECUCION FASE J · J4 — timeouts en las llamadas a wpctl/pactl/
playerctl: ninguna puede colgar el turno indefinidamente."""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.config import IS_WINDOWS
from jarvis_local.tools import media_controls as mc

solo_linux = pytest.mark.skipif(IS_WINDOWS, reason="usa wpctl/pactl/playerctl de Linux")


@solo_linux
def test_wpctl_lleva_timeout(monkeypatch):
    llamadas = []

    def fake_run(args, **kw):
        llamadas.append(kw)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(mc.subprocess, "run", fake_run)
    mc._wpctl("get-volume", "@DEFAULT_AUDIO_SINK@")
    assert llamadas[0].get("timeout")


@solo_linux
def test_pactl_lleva_timeout(monkeypatch):
    llamadas = []

    def fake_run(args, **kw):
        llamadas.append(kw)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(mc.subprocess, "run", fake_run)
    mc._pactl("get-sink-volume", "@DEFAULT_SINK@")
    assert llamadas[0].get("timeout")


@solo_linux
def test_playerctl_lleva_timeout(monkeypatch):
    llamadas = []

    def fake_run(args, **kw):
        llamadas.append(kw)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(mc.subprocess, "run", fake_run)
    mc._playerctl("status")
    assert llamadas[0].get("timeout")


@solo_linux
def test_wpctl_colgado_no_revienta_get_volume(monkeypatch):
    """Si wpctl se cuelga, `_get_volume_linux` degrada a (None, False) en vez
    de dejar TimeoutExpired sin capturar."""
    def _cuelga(args, **kw):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kw["timeout"])

    monkeypatch.setattr(mc.subprocess, "run", _cuelga)
    assert mc._get_volume_linux() == (None, False)


@solo_linux
def test_playerctl_colgado_no_revienta_status(monkeypatch):
    def _cuelga(args, **kw):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kw["timeout"])

    monkeypatch.setattr(mc.subprocess, "run", _cuelga)
    assert mc._player_status() is None


if __name__ == "__main__":
    print("usa pytest (estas pruebas usan fixtures)")
