"""
JARVIS Local - Herramientas de Archivos (Fase 2)
Listar, buscar, crear, copiar, mover, renombrar y plan de borrado.
Todas las operaciones pasan por validacion de permisos y politica de seguridad.
"""
import os
from pathlib import Path

from jarvis_local.safety.permissions import is_within_allowed
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy


def _validate_path(path_str: str, require_exist: bool = False) -> tuple[bool, Path | None, ActionPlan | None]:
    allowed, resolved = is_within_allowed(path_str)
    if not allowed:
        plan = policy.block(f"Ruta fuera de carpetas permitidas: {path_str}")
        return False, None, plan
    if require_exist and not resolved.exists():
        plan = policy.block(f"La ruta no existe: {path_str}")
        return False, None, plan
    return True, resolved, None


def list_files(path_str: str) -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str, require_exist=True)
    if blocked:
        return blocked
    items = []
    try:
        for entry in sorted(resolved.iterdir()):
            item_type = "DIR" if entry.is_dir() else "FILE"
            size = entry.stat().st_size if entry.is_file() else 0
            items.append(f"  [{item_type}] {entry.name} ({size} bytes)")
    except PermissionError:
        return policy.block(f"Sin permisos para leer: {path_str}")
    plan = ActionPlan(
        action="listar_archivos",
        params={"path": str(resolved)},
        paths_affected=[str(resolved)],
        risk=RiskLevel.READ,
        reason="Operacion de solo lectura",
    )
    result = "\n".join(items) if items else "(directorio vacio)"
    plan.result = result
    plan.status = ActionStatus.EXECUTED
    return plan


def search_files(name: str, path_str: str) -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str, require_exist=True)
    if blocked:
        return blocked
    matches = []
    try:
        for root, dirs, files in os.walk(str(resolved)):
            for f in files:
                if name.lower() in f.lower():
                    matches.append(str(Path(root) / f))
    except PermissionError:
        pass
    plan = ActionPlan(
        action="buscar_archivos",
        params={"name": name, "path": str(resolved)},
        paths_affected=[str(resolved)],
        risk=RiskLevel.READ,
        reason="Operacion de solo lectura",
    )
    plan.result = "\n".join(matches) if matches else f"No se encontro '{name}'"
    plan.status = ActionStatus.EXECUTED
    return plan


def create_file(path_str: str, content: str = "") -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str)
    if blocked:
        return blocked
    if resolved.exists():
        return policy.block(f"El archivo ya existe: {path_str}")
    plan = ActionPlan(
        action="crear_archivo",
        params={"path": str(resolved), "content_size": len(content)},
        paths_affected=[str(resolved)],
        risk=RiskLevel.CREATE,
        reason="Crear archivo",
    )
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content or "", encoding="utf-8")
        plan.result = f"Archivo creado: {resolved}"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error al crear archivo: {e}"
    return plan


def create_directory(path_str: str) -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str)
    if blocked:
        return blocked
    if resolved.exists():
        return policy.block(f"La carpeta ya existe: {path_str}")
    plan = ActionPlan(
        action="crear_carpeta",
        params={"path": str(resolved)},
        paths_affected=[str(resolved)],
        risk=RiskLevel.CREATE,
        reason="Crear carpeta",
    )
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        plan.result = f"Carpeta creada: {resolved}"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error al crear carpeta: {e}"
    return plan


def copy_file(src_str: str, dst_str: str) -> ActionPlan:
    ok1, src, blocked = _validate_path(src_str, require_exist=True)
    if blocked:
        return blocked
    ok2, dst, blocked = _validate_path(dst_str)
    if blocked:
        return blocked
    plan = ActionPlan(
        action="copiar_archivo",
        params={"origen": str(src), "destino": str(dst)},
        paths_affected=[str(src), str(dst)],
        risk=RiskLevel.CREATE,
        reason="Copiar archivo",
    )
    try:
        import shutil as _shutil
        if src.is_dir():
            _shutil.copytree(str(src), str(dst))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(str(src), str(dst))
        plan.result = f"Copiado: {src} -> {dst}"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error al copiar: {e}"
    return plan


def move_file(src_str: str, dst_str: str) -> ActionPlan:
    ok1, src, blocked = _validate_path(src_str, require_exist=True)
    if blocked:
        return blocked
    ok2, dst, blocked = _validate_path(dst_str)
    if blocked:
        return blocked
    plan = ActionPlan(
        action="mover_archivo",
        params={"origen": str(src), "destino": str(dst)},
        paths_affected=[str(src), str(dst)],
        risk=RiskLevel.CREATE,
        reason="Mover archivo",
    )
    try:
        import shutil as _shutil
        dst.parent.mkdir(parents=True, exist_ok=True)
        _shutil.move(str(src), str(dst))
        plan.result = f"Movido: {src} -> {dst}"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error al mover: {e}"
    return plan


def rename_file(path_str: str, new_name: str) -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str, require_exist=True)
    if blocked:
        return blocked
    new_path = resolved.parent / new_name
    ok2, _, blocked2 = _validate_path(str(new_path))
    if blocked2:
        return blocked2
    plan = ActionPlan(
        action="renombrar",
        params={"ruta": str(resolved), "nuevo_nombre": new_name},
        paths_affected=[str(resolved), str(new_path)],
        risk=RiskLevel.CREATE,
        reason="Renombrar",
    )
    try:
        resolved.rename(new_path)
        plan.result = f"Renombrado: {resolved.name} -> {new_name}"
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"Error al renombrar: {e}"
    return plan


def plan_delete(path_str: str) -> ActionPlan:
    """Planifica borrado. NUNCA ejecuta, solo genera el plan."""
    ok, resolved, blocked = _validate_path(path_str, require_exist=True)
    if blocked:
        return blocked
    is_dir = resolved.is_dir()
    plan = ActionPlan(
        action="borrar",
        params={"path": str(resolved), "is_directory": is_dir},
        paths_affected=[str(resolved)],
        risk=RiskLevel.DELETE,
        reason=(
            "BORRADO detectado. Esta accion requiere DOBLE CONFIRMACION "
            "y sera implementada en una fase posterior. Por ahora, solo "
            "se muestra el plan. No se ejecutara nada."
        ),
    )
    plan.status = ActionStatus.BLOCKED
    plan.simulation_result = (
        f"[BORRADO BLOQUEADO] Se eliminaria: {resolved} "
        f"({'directorio' if is_dir else 'archivo'}). "
        f"El borrado no esta habilitado en esta fase."
    )
    return plan


def read_metadata(path_str: str) -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str, require_exist=True)
    if blocked:
        return blocked
    try:
        st = resolved.stat()
        info = {
            "nombre": resolved.name,
            "tipo": "directorio" if resolved.is_dir() else "archivo",
            "tamano": st.st_size,
            "modificado": st.st_mtime,
            "creado": st.st_ctime,
        }
    except OSError as e:
        return policy.block(f"Error al leer metadatos: {e}")
    plan = ActionPlan(
        action="leer_metadatos",
        params={"path": str(resolved)},
        paths_affected=[str(resolved)],
        risk=RiskLevel.READ,
        reason="Operacion de solo lectura",
    )
    plan.result = str(info)
    plan.status = ActionStatus.EXECUTED
    return plan
