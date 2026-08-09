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


if __name__ == "__main__":
    test_plan_hide_valid()
    test_plan_show_valid()
    test_plan_hide_blocked_outside()
    test_plan_hide_blocked_nonexistent()
    if not IS_WINDOWS:
        test_hide_linux()
        test_show_linux()
    print("OK: Todos los tests de hidden_files pasaron.")
