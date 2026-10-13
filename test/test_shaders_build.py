"""PLAN_EJECUCION FASE J · J6 (deuda nombrada): `shaders/build.py` es un
script de build manual (no se llama durante una peticion real, por eso
quedo fuera de J4), pero su `subprocess.run` no tenia timeout -- un
`pyside6-qsb` colgado se comia el proceso para siempre. Blinda el timeout
anadido sin depender de que el compilador real este instalado ni tocar los
`.qsb` ya versionados."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis_local.ui.hud.shaders import build


def _con_un_frag_falso(monkeypatch, tmp_path):
    (tmp_path / "falso.frag").write_text("// shader de prueba\n")
    monkeypatch.setattr(build, "_HERE", tmp_path)
    monkeypatch.setattr(build, "_qsb", lambda: "pyside6-qsb")


def test_build_timeout_no_cuelga_y_devuelve_error(monkeypatch, tmp_path, capsys):
    _con_un_frag_falso(monkeypatch, tmp_path)

    def _run_que_cuelga(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    monkeypatch.setattr(build.subprocess, "run", _run_que_cuelga)
    assert build.build() == 1
    assert "no respondio" in capsys.readouterr().err


def test_build_propaga_fallo_del_compilador(monkeypatch, tmp_path, capsys):
    _con_un_frag_falso(monkeypatch, tmp_path)

    def _run_que_falla(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="error de sintaxis\n")

    monkeypatch.setattr(build.subprocess, "run", _run_que_falla)
    assert build.build() == 2
    assert "error de sintaxis" in capsys.readouterr().err


def test_build_compila_cuando_el_comando_responde(monkeypatch, tmp_path, capsys):
    _con_un_frag_falso(monkeypatch, tmp_path)
    llamadas = []

    def _run_ok(cmd, **kwargs):
        llamadas.append(cmd)
        assert kwargs.get("timeout") == 30
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(build.subprocess, "run", _run_ok)
    assert build.build() == 0
    assert len(llamadas) == 1
    assert "1 shader" in capsys.readouterr().out
