"""
JARVIS Local - Notas rapidas (Fase 4)
Toma notas en archivos de texto dentro de Documentos y las abre en el Bloc de notas.
"""
import os
import subprocess
from datetime import datetime

from jarvis_local.config import user_dir
from jarvis_local.safety.permissions import get_app_path
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

NOTES_DIR = os.path.join(user_dir("documents"), "JARVIS Notas")


def _append_line(path: str, linea: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(linea)


def _append_line_fsync(path: str, linea: str) -> None:
    """Vía DISTINTA para el reintento de VERIFY (D1): descriptor en modo
    O_APPEND + fsync, por si el buffer del append normal no llegó a disco."""
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, linea.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def take_note(text: str, open_notepad: bool = True) -> ActionPlan:
    """Guarda una nota con fecha/hora y la abre en el Bloc de notas.

    D1 · VERIFY: una nota que no se guardó no se descubre hasta días después.
    Tras escribir se RELEE el archivo y se comprueba que la línea está ahí; si
    no, se reintenta con fsync antes de dar nada por hecho.
    """
    from jarvis_local.tools import verify as _v

    plan = ActionPlan(action="tomar_nota", params={"texto": text[:80]},
                      risk=RiskLevel.EXECUTE,
                      reason="Guardar nota en Documentos\\JARVIS Notas")
    try:
        os.makedirs(NOTES_DIR, exist_ok=True)
        now = datetime.now()
        path = os.path.join(NOTES_DIR, f"nota_{now.strftime('%Y-%m-%d')}.txt")
        linea = f"[{now.strftime('%H:%M')}] {text.strip()}\n"
        _append_line(path, linea)
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude guardar la nota: {e}"
        return plan

    plan.paths_affected = [path]
    outcome = _v.note_appended(path, linea)
    tried = [f"append -> {outcome.detail}"]
    if outcome.ok is False:
        plan.reason += " (reintento con append + fsync)"
        try:
            # relee por si fue un fallo de lectura transitorio; solo reescribe
            # si la línea de verdad no está (no duplicar la nota)
            if _v.note_appended(path, linea).ok is not True:
                _append_line_fsync(path, linea)
        except Exception as e:  # noqa: BLE001
            tried.append(f"append+fsync falló ({e})")
        else:
            outcome = _v.note_appended(path, linea)
            tried.append(f"append+fsync -> {outcome.detail}")

    if outcome.ok is not False and open_notepad:
        editor = get_app_path("notepad")
        if editor:
            subprocess.Popen([editor, path], shell=False)

    base = os.path.basename(path)
    return _v.finish(
        plan, outcome, tried=tried,
        ok_msg=(f"Nota guardada en {base}, senor."
                + (" La abro en el Bloc de notas." if open_notepad else "")),
        fail_msg=f"Escribí la nota en {base} pero al releer el archivo no aparece, senor.")
