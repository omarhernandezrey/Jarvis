"""
Tests de herramientas de archivos ocultos - Fase 4
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.config import IS_WINDOWS, user_dir
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools.hidden_files import execute_hide, plan_hide

TEST_DIR = Path(user_dir("documents"))
TEST_NAME = "_jarvis_test_hidden_"


def setup():
    """Crea carpeta de prueba con archivos."""
    p = TEST_DIR / TEST_NAME
    if p.exists():
        import shutil
        shutil.rmtree(str(p))
    p.mkdir(exist_ok=True)
    # Crear archivos de prueba
    (p / "archivo1.txt").write_text("test1")
    (p / "archivo2.txt").write_text("test2")
    (p / "archivo3.txt").write_text("test3")
    return p


def teardown(p: Path):
    if p.exists():
        import shutil
        shutil.rmtree(str(p))


def test_plan_hide_valid():
    """Plan de ocultar funciona para ruta válida."""
    p = setup()
    plan = plan_hide(str(p), hide=True)
    assert plan.status == ActionStatus.PLANNED
    teardown(p)


def test_plan_show_valid():
    """Plan de mostrar funciona para ruta válida."""
    p = setup()
    plan = plan_hide(str(p), hide=False)
    assert plan.status == ActionStatus.PLANNED
    teardown(p)


def test_plan_hide_blocked_outside():
    """Plan de ocultar bloqueado para ruta fuera de carpetas permitidas."""
    plan = plan_hide("/etc", hide=True)
    assert plan.status == ActionStatus.BLOCKED


def test_plan_hide_blocked_nonexistent():
    """Plan de ocultar bloqueado para carpeta inexistente."""
    plan = plan_hide(str(TEST_DIR / "_carpeta_inexistente_"), hide=True)
    assert plan.status == ActionStatus.BLOCKED


@pytest.mark.skipif(IS_WINDOWS, reason="Solo en Linux")
def test_hide_linux():
    """Ocultar archivos en Linux añade prefijo punto."""
    p = setup()
    plan = execute_hide(str(p), hide=True)
    assert plan.status == ActionStatus.EXECUTED
    # Verificar que los archivos ahora empiezan con punto
    files = os.listdir(str(p))
    for f in files:
        if f != '.' and not f.startswith('.'):
            # Si hay archivos sin prefijo, el test falla
            assert False, f"Archivo no ocultado: {f}"
    teardown(p)


@pytest.mark.skipif(IS_WINDOWS, reason="Solo en Linux")
def test_show_linux():
    """Mostrar archivos en Linux quita prefijo punto."""
    p = setup()
    # Primero ocultar
    execute_hide(str(p), hide=True)
    # Luego mostrar
    plan = execute_hide(str(p), hide=False)
    assert plan.status == ActionStatus.EXECUTED
    # Verificar que los archivos no empiezan con punto
    files = os.listdir(str(p))
    for f in files:
        assert not f.startswith('.'), f"Archivo sigue oculto: {f}"
    teardown(p)


@pytest.mark.skipif(IS_WINDOWS, reason="Solo en Linux")
def test_mostrar_no_toca_dotfiles_que_jarvis_no_ocultó():
    """Bug real encontrado en revisión: "mostrar archivos" quitaba el punto
    a CUALQUIER dotfile de la carpeta, no solo a los que el propio JARVIS
    había ocultado -- un .gitignore o .env que ya estaba ahí antes se
    desocultaba igual, un efecto colateral silencioso."""
    from jarvis_local.tools.hidden_files import execute_hide

    p = setup()
    try:
        preexistente = p / ".gitignore"
        preexistente.write_text("*.pyc\n")  # dotfile ajeno, ya estaba ahí

        execute_hide(str(p), hide=True)   # oculta archivo1/2/3.txt
        plan = execute_hide(str(p), hide=False)  # "mostrar"
        assert plan.status == ActionStatus.EXECUTED

        files = os.listdir(str(p))
        assert "archivo1.txt" in files  # lo que JARVIS ocultó, vuelve
        assert ".gitignore" in files, "un dotfile ajeno NO debe desocultarse"
        assert "gitignore" not in files
    finally:
        teardown(p)


@pytest.mark.skipif(IS_WINDOWS, reason="Solo en Linux")
def test_manifiesto_no_se_oculta_ni_se_cuenta_a_si_mismo():
    """El manifiesto que registra qué ocultó JARVIS es un dotfile propio:
    no debe aparecer como "elemento" contado ni tratarse como un archivo
    normal a ocultar/mostrar."""
    from jarvis_local.tools.hidden_files import _MANIFEST_NAME, execute_hide

    p = setup()
    try:
        plan = execute_hide(str(p), hide=True)
        assert plan.status == ActionStatus.EXECUTED
        assert "3 elementos" in plan.result, plan.result  # no cuenta el manifiesto
        assert (p / _MANIFEST_NAME).exists()
    finally:
        teardown(p)


def test_hide_windows_attrib_fallido_reporta_error(monkeypatch):
    """Bug real encontrado en revisión: _hide_windows descartaba el
    CompletedProcess de `attrib` entero -- un fallo real (archivos de solo
    lectura/bloqueados) se reportaba igual como "Listo, senor". No
    verificable en esta máquina (no es Windows): se fuerza IS_WINDOWS y se
    mockea subprocess.run para probar la lógica en aislado, con una
    carpeta real (tmp_path) para que is_within_allowed/is_dir no hagan falta
    mockearse también."""
    import subprocess as _subprocess

    import jarvis_local.tools.hidden_files as HF

    p = setup()
    try:
        monkeypatch.setattr(HF, "IS_WINDOWS", True)

        def _attrib_fallido(cmd, **kwargs):
            return _subprocess.CompletedProcess(cmd, returncode=5,
                                                stdout="", stderr="Acceso denegado.")

        monkeypatch.setattr(HF.subprocess, "run", _attrib_fallido)

        plan = HF.execute_hide(str(p), hide=True)

        assert plan.status == ActionStatus.ERROR, (
            "un fallo real de attrib se reportó como éxito"
        )
        assert "Acceso denegado" in plan.error or "5" in plan.error
    finally:
        teardown(p)


if __name__ == "__main__":
    test_plan_hide_valid()
    test_plan_show_valid()
    test_plan_hide_blocked_outside()
    test_plan_hide_blocked_nonexistent()
    if not IS_WINDOWS:
        test_hide_linux()
        test_show_linux()
    print("OK: Todos los tests de hidden_files pasaron.")
