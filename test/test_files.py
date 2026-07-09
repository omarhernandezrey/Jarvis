"""
Tests de herramientas de archivos - Fase 2
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.tools.files import (
    list_files,
    search_files,
    create_file,
    create_directory,
    copy_file,
    move_file,
    rename_file,
    plan_delete,
    read_metadata,
)
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.safety.permissions import is_within_allowed

TEST_DIR = Path(os.path.expandvars(r"%USERPROFILE%\Documents"))
TEST_NAME = "_jarvis_test_fase2_"


def setup():
    """Crea carpetas de prueba."""
    p = TEST_DIR / TEST_NAME
    if p.exists():
        import shutil
        shutil.rmtree(str(p))
    p.mkdir(exist_ok=True)
    return p


def teardown(p: Path):
    if p.exists():
        import shutil
        shutil.rmtree(str(p))


def test_list_files_allowed():
    p = setup()
    (p / "test.txt").write_text("hola")
    plan = list_files(str(p))
    assert plan.action == "listar_archivos"
    teardown(p)


def test_search_files():
    p = setup()
    (p / "reporte_2026.txt").write_text("data")
    (p / "otro.txt").write_text("otro")
    plan = search_files("reporte", str(p))
    assert plan.action == "buscar_archivos"
    teardown(p)


def test_create_file_simulated():
    p = setup()
    plan = create_file(str(p / "nuevo.txt"), "contenido")
    assert plan.action == "crear_archivo"
    assert plan.status == ActionStatus.PLANNED
    teardown(p)


def test_create_directory_simulated():
    p = setup()
    plan = create_directory(str(p / "nueva_carpeta"))
    assert plan.action == "crear_carpeta"
    assert plan.status == ActionStatus.PLANNED
    teardown(p)


def test_copy_simulated():
    p = setup()
    (p / "origen.txt").write_text("data")
    plan = copy_file(str(p / "origen.txt"), str(p / "destino.txt"))
    assert plan.action == "copiar_archivo"
    assert plan.status == ActionStatus.PLANNED
    teardown(p)


def test_rename_simulated():
    p = setup()
    (p / "viejo.txt").write_text("data")
    plan = rename_file(str(p / "viejo.txt"), "nuevo.txt")
    assert plan.action == "renombrar"
    assert plan.status == ActionStatus.PLANNED
    teardown(p)


def test_plan_delete_blocked():
    p = setup()
    (p / "borrar.txt").write_text("data")
    plan = plan_delete(str(p / "borrar.txt"))
    assert plan.action == "borrar"
    assert plan.status == ActionStatus.BLOCKED
    teardown(p)


def test_list_blocked_outside():
    plan = list_files(r"C:\Windows")
    assert plan.status == ActionStatus.BLOCKED


def test_create_blocked_outside():
    plan = create_file(r"C:\Windows\test.txt")
    assert plan.status == ActionStatus.BLOCKED


def test_metadata():
    p = setup()
    (p / "info.txt").write_text("test data")
    plan = read_metadata(str(p / "info.txt"))
    assert plan.action == "leer_metadatos"
    teardown(p)


if __name__ == "__main__":
    test_list_files_allowed()
    test_search_files()
    test_create_file_simulated()
    test_create_directory_simulated()
    test_copy_simulated()
    test_rename_simulated()
    test_plan_delete_blocked()
    test_list_blocked_outside()
    test_create_blocked_outside()
    test_metadata()
    print("OK: Todos los tests de archivos pasaron.")
