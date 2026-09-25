"""Test del flujo /confirmar para DELETE (borrar_archivo / ocultar_archivos).

El objetivo es que estas operaciones (risk=DELETE) sean REALES tras /confirmar,
no bloqueadas con "no disponible en esta fase".
"""
import pytest

from jarvis_local.safety.policy import ActionStatus, policy


def _permitir_tmp(monkeypatch, tmp_path):
    """Anade tmp_path a ALLOWED_FOLDERS para que las operaciones no sean
    bloqueadas por seguridad (el test usa archivos temporales que no estan
    en las carpetas reales del usuario)."""
    import jarvis_local.safety.permissions as permissions
    monkeypatch.setattr(permissions, "ALLOWED_FOLDERS",
                       permissions.ALLOWED_FOLDERS + [str(tmp_path)])


def test_borrar_archivo_crea_plan_pendiente(tmp_path, monkeypatch):
    """plan_delete devuelve un plan PLANNED (no BLOCKED) y lo pone en pending_plan."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.files import plan_delete

    f = tmp_path / "test_borrar.txt"
    f.write_text("contenido")
    plan = plan_delete(str(f))

    assert plan.status == ActionStatus.PLANNED, f"status={plan.status.value}"
    assert policy.pending_plan is plan
    policy.pending_plan = None          # limpiar


def test_policy_confirm_no_bloquea_delete(tmp_path, monkeypatch):
    """confirm() debe marcar DELETE como CONFIRMED, no BLOCKED."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.files import plan_delete

    f = tmp_path / "test_confirm.txt"
    f.write_text("contenido")
    plan_delete(str(f))

    confirmed = policy.confirm()
    assert confirmed is not None
    assert confirmed.status == ActionStatus.CONFIRMED, f"status={confirmed.status.value}"
    assert policy.pending_plan is None        # consumido
    if f.exists():                           # limpiar si no se ejecuto
        f.unlink()


def test_execute_delete_borra_archivo_real(tmp_path, monkeypatch):
    """execute_delete_file realmente borra el archivo tras la confirmacion."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.files import execute_delete_file

    f = tmp_path / "test_real.txt"
    f.write_text("borame")
    assert f.exists()

    plan = execute_delete_file(str(f))
    assert plan.status == ActionStatus.EXECUTED, plan.result
    assert not f.exists(), "el archivo debio ser borrado"


def test_execute_delete_borra_carpeta_real(tmp_path, monkeypatch):
    """execute_delete_file tambien borra directorios."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.files import execute_delete_file

    d = tmp_path / "carpeta_test"
    d.mkdir()
    (d / "a.txt").write_text("x")
    (d / "b.txt").write_text("y")
    assert d.exists()

    plan = execute_delete_file(str(d))
    assert plan.status == ActionStatus.EXECUTED, plan.result
    assert not d.exists(), "la carpeta debio ser borrada"


def test_execute_delete_archivo_inexistente(tmp_path, monkeypatch):
    """Si el archivo no existe, devuelve ERROR, no crash."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.files import execute_delete_file

    plan = execute_delete_file(str(tmp_path / "nunca_existio.txt"))
    assert plan.status == ActionStatus.ERROR
    assert "no existe" in plan.result


def test_ocultar_archivos_crea_plan_pendiente(tmp_path, monkeypatch):
    """ocultar_archivos devuelve PLANNED y lo pone en pending_plan."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.hidden_files import plan_hide

    d = tmp_path / "carpeta_visible"
    d.mkdir()
    (d / "visible.txt").write_text("x")
    plan = plan_hide(str(d), hide=True)

    assert plan.status == ActionStatus.PLANNED, f"status={plan.status.value}"
    assert policy.pending_plan is plan
    policy.pending_plan = None          # limpiar


def test_policy_confirm_para_ocultar(tmp_path, monkeypatch):
    """confirm() funciona para ocultar_archivos (risk=DELETE)."""
    _permitir_tmp(monkeypatch, tmp_path)
    from jarvis_local.tools.hidden_files import plan_hide

    d = tmp_path / "carpeta_ocultar"
    d.mkdir()
    (d / "x.txt").write_text("y")
    plan_hide(str(d), hide=True)

    confirmed = policy.confirm()
    assert confirmed is not None
    assert confirmed.status == ActionStatus.CONFIRMED
    policy.pending_plan = None
    # restaurar visibilidad para no dejar basura
    from jarvis_local.tools.hidden_files import execute_hide
    execute_hide(str(d), hide=False)
