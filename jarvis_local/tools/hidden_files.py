"""
JARVIS Local - Ocultar/mostrar archivos (Fase 4)
Oculta todos los archivos de una carpeta permitida o los hace visibles.
Accion de escritura: requiere plan + /confirmar.
"""
import contextlib
import json
import os
import subprocess
from pathlib import Path

from jarvis_local.config import IS_WINDOWS
from jarvis_local.safety.permissions import is_within_allowed
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy


def plan_hide(path: str, hide: bool = True) -> ActionPlan:
    """Crea el plan (pendiente de confirmacion) para ocultar/mostrar archivos."""
    action = "ocultar_archivos" if hide else "mostrar_archivos"
    verbo = "Ocultar" if hide else "Hacer visibles"
    norm = str(Path(path).expanduser().resolve())
    allowed, _ = is_within_allowed(norm)
    if not allowed:
        return policy.block(f"La ruta '{norm}' no esta en las carpetas permitidas.")
    if not Path(norm).is_dir():
        return policy.block(f"La carpeta '{norm}' no existe.")
    plan = ActionPlan(
        action=action,
        params={"path": norm, "hide": hide},
        paths_affected=[norm],
        risk=RiskLevel.EXECUTE,
        reason=f"{verbo} todos los archivos de {norm}",
        simulation_result=(f"[Plan pendiente] {verbo} todos los archivos de {norm}. "
                           "Escribe /confirmar para ejecutar o /cancelar."),
    )
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_hide(path: str, hide: bool = True) -> ActionPlan:
    """Ejecuta el ocultar/mostrar CONFIRMADO."""
    action = "ocultar_archivos" if hide else "mostrar_archivos"
    norm = str(Path(path).expanduser().resolve())
    plan = ActionPlan(action=action, params={"path": norm, "hide": hide},
                      paths_affected=[norm], risk=RiskLevel.EXECUTE,
                      status=ActionStatus.CONFIRMED)
    allowed, _ = is_within_allowed(norm)
    if not allowed or not Path(norm).is_dir():
        plan.status = ActionStatus.ERROR
        plan.result = f"Ruta invalida o no permitida: {norm}"
        return plan
    try:
        if IS_WINDOWS:
            _hide_windows(norm, hide)
        else:
            _hide_linux(norm, hide)
        n = len([f for f in os.listdir(norm)
                 if f != _MANIFEST_NAME and os.path.isfile(str(Path(norm) / f))])
        estado = "ocultos" if hide else "visibles"
        plan.result = f"Listo, senor. Los archivos de {norm} ahora estan {estado} ({n} elementos)."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude cambiar los atributos: {e}"
    return plan


def _hide_windows(norm: str, hide: bool):
    """Oculta/muestra archivos en Windows usando attrib."""
    flag = "+h" if hide else "-h"
    r = subprocess.run(["attrib", flag, str(Path(norm) / "*")],
                       capture_output=True, text=True, timeout=60, shell=False)
    if r.returncode != 0:
        # Antes se descartaba el CompletedProcess entero: un fallo real de
        # attrib (archivos de solo lectura/bloqueados, glob inválido) se
        # reportaba igual como "Listo, senor" -- execute_hide() ya tiene el
        # try/except para convertir esto en ActionStatus.ERROR, solo
        # faltaba levantar la excepción.
        raise RuntimeError(f"attrib {flag} falló (código {r.returncode}): "
                           f"{r.stderr.strip() or r.stdout.strip() or 'sin detalle'}")


_MANIFEST_NAME = ".jarvis_hidden_manifest.json"


def _manifest_path(norm: str) -> Path:
    return Path(norm) / _MANIFEST_NAME


def _leer_manifest(norm: str) -> set[str]:
    p = _manifest_path(norm)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _escribir_manifest(norm: str, nombres: set[str]) -> None:
    p = _manifest_path(norm)
    if not nombres:
        with contextlib.suppress(Exception):
            p.unlink(missing_ok=True)
        return
    p.write_text(json.dumps(sorted(nombres)), encoding="utf-8")


def _hide_linux(norm: str, hide: bool):
    """
    Oculta/muestra archivos en Linux renombrando con/sin prefijo '.'.
    En Linux, los archivos ocultos empiezan con punto.

    "Mostrar" solo revierte lo que ESTE comando ocultó -- antes
    `elif not hide and filename.startswith('.')` quitaba el punto a
    CUALQUIER dotfile de la carpeta, incluyendo los que ya estaban ahí
    antes de que JARVIS tocara nada (.gitignore, .env, metadata de un
    sincronizador...). Un manifiesto (_MANIFEST_NAME, un dotfile propio,
    nunca se oculta/muestra a sí mismo) registra los nombres originales de
    lo que SÍ ocultó, para no desocultar nada ajeno.
    """
    ocultados_por_jarvis = _leer_manifest(norm)
    for filename in os.listdir(norm):
        if filename == _MANIFEST_NAME:
            continue
        filepath = str(Path(norm) / filename)
        if not Path(filepath).is_file():
            continue
        if hide and not filename.startswith('.'):
            # Ocultar: añadir prefijo punto, recordar el nombre original
            os.rename(filepath, str(Path(norm) / ('.' + filename)))
            ocultados_por_jarvis.add(filename)
        elif (not hide and filename.startswith('.') and filename != '.'
              and filename[1:] in ocultados_por_jarvis):
            # Mostrar: quitar prefijo punto SOLO si JARVIS fue quien lo puso
            new_name = filename[1:]  # Quitar el punto inicial
            os.rename(filepath, os.path.join(norm, new_name))
            ocultados_por_jarvis.discard(new_name)
    _escribir_manifest(norm, ocultados_por_jarvis)
