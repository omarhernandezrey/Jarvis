"""
JARVIS Local - Notas rapidas (Fase 4)
Toma notas en archivos de texto dentro de Documentos y las abre en el Bloc de notas.
"""
import os
import subprocess
from datetime import datetime

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

NOTES_DIR = os.path.expandvars(r"%USERPROFILE%\Documents\JARVIS Notas")


def take_note(text: str, open_notepad: bool = True) -> ActionPlan:
    """Guarda una nota con fecha/hora y la abre en el Bloc de notas."""
    plan = ActionPlan(action="tomar_nota", params={"texto": text[:80]},
                      risk=RiskLevel.EXECUTE,
                      reason="Guardar nota en Documentos\\JARVIS Notas")
    try:
        os.makedirs(NOTES_DIR, exist_ok=True)
        now = datetime.now()
        path = os.path.join(NOTES_DIR, f"nota_{now.strftime('%Y-%m-%d')}.txt")
        linea = f"[{now.strftime('%H:%M')}] {text.strip()}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(linea)
        plan.paths_affected = [path]
        if open_notepad:
            subprocess.Popen([r"C:\Windows\System32\notepad.exe", path], shell=False)
        plan.result = (f"Nota guardada en {os.path.basename(path)}, senor."
                       + (" La abro en el Bloc de notas." if open_notepad else ""))
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude guardar la nota: {e}"
    return plan
