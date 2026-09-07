"""
JARVIS Local - Herramientas de Archivos (Fase 2)
Listar, buscar, crear, copiar, mover, renombrar y plan de borrado.
Todas las operaciones pasan por validacion de permisos y politica de seguridad.
"""
import os
import re
from pathlib import Path

from jarvis_local.safety.permissions import is_within_allowed
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy

# Nombres reservados en Windows que no pueden usarse como nombres de archivo
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Caracteres no permitidos en nombres de archivo
_INVALID_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def _validate_filename(name: str) -> tuple[bool, str]:
    """
    Valida que un nombre de archivo sea seguro y válido.
    Returns:
        (True, "") si es válido.
        (False, razón) si no es válido.
    """
    if not name or not name.strip():
        return False, "El nombre no puede estar vacio"

    # Eliminar espacios al inicio y final
    name = name.strip()

    # Verificar caracteres no permitidos
    if _INVALID_FILENAME_CHARS.search(name):
        return False, (
            "El nombre contiene caracteres no permitidos: / \\ : * ? \" < > |"
        )

    # Verificar nombres reservados de Windows
    name_upper = name.upper().split('.')[0]  # Sin extensión
    if name_upper in _WINDOWS_RESERVED_NAMES:
        return False, f"'{name}' es un nombre reservado del sistema"

    # Verificar que no empiece o termine con punto o espacio
    if name.startswith('.') or name.startswith(' '):
        return False, "El nombre no puede empezar con punto o espacio"
    if name.endswith('.') or name.endswith(' '):
        return False, "El nombre no puede terminar con punto o espacio"

    # Verificar longitud máxima
    if len(name) > 255:
        return False, "El nombre excede 255 caracteres"

    return True, ""


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
        for root, _dirs, files in os.walk(str(resolved)):
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
    from jarvis_local.tools import verify as _v

    contenido = content or ""

    def _escribir_pathlib() -> str:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(contenido, encoding="utf-8")
        return "Path.write_text"

    def _escribir_lowlevel() -> str:
        # Estrategia DISTINTA: descriptor crudo + fsync (descarta un buffer de
        # write_text que no llegó a disco).
        resolved.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(resolved), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            os.write(fd, contenido.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return "os.write + fsync"

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, escribir in enumerate((_escribir_pathlib, _escribir_lowlevel)):
        try:
            metodo = escribir()
        except Exception as e:
            tried.append(f"{getattr(escribir, '__name__', 'estrategia')}: {e}")
            outcome = _v.VerifyOutcome(False, str(e), "escribir")
            continue
        outcome = _v.file_written(resolved, contenido)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento con escritura cruda + fsync)"

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Archivo creado: {resolved}",
        fail_msg=f"No pude crear el archivo {resolved} con el contenido pedido, senor.")


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
    from jarvis_local.tools import verify as _v

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, crear in enumerate((
        lambda: (resolved.mkdir(parents=True, exist_ok=True), "Path.mkdir")[1],
        lambda: (os.makedirs(str(resolved), exist_ok=True), "os.makedirs")[1],
    )):
        try:
            metodo = crear()
        except Exception as e:
            tried.append(f"estrategia {i}: {e}")
            outcome = _v.VerifyOutcome(False, str(e), "mkdir")
            continue
        outcome = _v.dir_created(resolved)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Carpeta creada: {resolved}",
        fail_msg=f"No pude crear la carpeta {resolved}, senor.")


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
    import shutil as _shutil

    from jarvis_local.tools import verify as _v

    def _copiar_shutil() -> str:
        if src.is_dir():
            _shutil.copytree(str(src), str(dst))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(str(src), str(dst))
        return "shutil.copy"

    def _copiar_crudo() -> str:
        if src.is_dir():
            raise RuntimeError("copia cruda no cubre carpetas")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            _shutil.copyfileobj(fsrc, fdst)
            fdst.flush()
            os.fsync(fdst.fileno())
        return "copyfileobj + fsync"

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, copiar in enumerate((_copiar_shutil, _copiar_crudo)):
        try:
            metodo = copiar()
        except Exception as e:
            tried.append(f"{getattr(copiar, '__name__', 'estrategia')}: {e}")
            outcome = _v.VerifyOutcome(False, str(e), "copiar")
            continue
        outcome = _v.copied(src, dst)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento con copia cruda + fsync)"

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Copiado: {src} -> {dst}",
        fail_msg=f"No pude copiar {src} a {dst}, senor.")


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
    import shutil as _shutil

    from jarvis_local.tools import verify as _v

    def _mover_shutil() -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        _shutil.move(str(src), str(dst))
        return "shutil.move"

    def _mover_copia_y_borra() -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            _shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
            _shutil.rmtree(str(src))
        else:
            _shutil.copy2(str(src), str(dst))
            os.remove(str(src))
        return "copy2 + remove"

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, mover in enumerate((_mover_shutil, _mover_copia_y_borra)):
        try:
            metodo = mover()
        except Exception as e:
            tried.append(f"{getattr(mover, '__name__', 'estrategia')}: {e}")
            outcome = _v.VerifyOutcome(False, str(e), "mover")
            continue
        outcome = _v.moved(src, dst)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break
        if i == 0:
            plan.reason += " (reintento: copiar y borrar)"

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Movido: {src} -> {dst}",
        fail_msg=f"No pude mover {src} a {dst}, senor.")


def rename_file(path_str: str, new_name: str) -> ActionPlan:
    ok, resolved, blocked = _validate_path(path_str, require_exist=True)
    if blocked:
        return blocked

    # Validar el nuevo nombre
    valid, reason = _validate_filename(new_name)
    if not valid:
        return policy.block(f"Nombre no valido: {reason}")

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
    import shutil as _shutil

    from jarvis_local.tools import verify as _v

    viejo = Path(str(resolved))  # copia: resolved.rename muta el objeto

    tried: list[str] = []
    outcome = _v.VerifyOutcome(None, "no se intentó nada", "")
    for i, renombrar in enumerate((
        lambda: (viejo.rename(new_path), "Path.rename")[1],
        lambda: (_shutil.move(str(viejo), str(new_path)), "shutil.move")[1],
    )):
        try:
            metodo = renombrar()
        except Exception as e:
            tried.append(f"estrategia {i}: {e}")
            outcome = _v.VerifyOutcome(False, str(e), "renombrar")
            continue
        outcome = _v.moved(viejo, new_path)
        tried.append(f"{metodo} -> {outcome.detail}")
        if outcome.ok is not False:
            break

    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=f"Renombrado: {viejo.name} -> {new_name}",
        fail_msg=f"No pude renombrar {viejo.name} a {new_name}, senor.")


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
    # Sin .result, los llamadores que hacen `plan.result or "Operacion
    # completada."` (agent/registry.execute, jarvis.py) reportaban un borrado
    # BLOQUEADO como si se hubiera hecho. Mismo motivo que policy.block().
    plan.result = (
        f"No borro nada, senor: el borrado de archivos no esta habilitado "
        f"todavia. Se eliminaria {resolved} "
        f"({'carpeta' if is_dir else 'archivo'})."
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
