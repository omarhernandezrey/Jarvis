"""PLAN_EJECUCION FASE D · D5 — banco: EFECTO y FALLO FORZADO.

El banco de routing (jarvis_local/eval/cases, 60/60) mide enrutado y
seguridad. Estas dos clases NO existían:

  EFECTO       — pedir algo y comprobar EN LA MÁQUINA que ocurrió de verdad.
                 Contraparte de D1: sin esto el banco no distingue "JARVIS
                 dijo que lo hizo" de "lo hizo".
  FALLO FORZADO — pedir algo imposible (app inexistente, ruta sin permiso,
                 multimedia sin reproductor). La respuesta correcta es un
                 error claro que diga qué se intentó, nunca un éxito
                 inventado. Y un verify NONE se reporta CON salvedad — el
                 banco lo exige, no lo tolera.
"""
import os
import re
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.config import user_dir
from jarvis_local.safety.policy import ActionStatus

# Frase que afirma éxito. Un FALLO FORZADO que la produzca es exactamente la
# mentira que este banco persigue.
_EXITO = re.compile(
    r"operaci[oó]n completada|hecho,?\s*se[nñ]or|listo,?\s*se[nñ]or|"
    r"abierto correctamente|correctamente\.|con [eé]xito|\bhecho\b\.?\s*$",
    re.IGNORECASE)


def _tmp(nombre: str) -> str:
    return os.path.join(user_dir("documents"), nombre)


# ════════════════════════════════════════════════════════════════════════════
# CLASE 1 — EFECTO: se hace y se comprueba en la máquina
# ════════════════════════════════════════════════════════════════════════════


def test_efecto_crear_fichero_contenido_y_tamano_reales():
    from jarvis_local.tools.files import create_file

    ruta = _tmp("_banco_d5_efecto.txt")
    contenido = "línea uno\nlínea dos con ñ y áéí\n"
    try:
        plan = create_file(ruta, contenido)
        assert plan.status == ActionStatus.EXECUTED
        assert plan.params["verify"]["ok"] is True
        # comprobación INDEPENDIENTE del plan: leer el disco
        real = open(ruta, encoding="utf-8").read()
        assert real == contenido
        assert os.path.getsize(ruta) == len(contenido.encode("utf-8"))
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def test_efecto_crear_carpeta_existe_de_verdad():
    from jarvis_local.tools.files import create_directory

    ruta = _tmp("_banco_d5_carpeta")
    try:
        plan = create_directory(ruta)
        assert plan.status == ActionStatus.EXECUTED
        assert os.path.isdir(ruta)
    finally:
        if os.path.isdir(ruta):
            os.rmdir(ruta)


def test_efecto_volumen_al_30_y_se_relee():
    """Volumen al 30 y se COMPRUEBA. Tres desenlaces honestos según lo que la
    máquina permita — y ninguno es un 'volumen al 30' afirmado a ciegas:

      1. hay lectura de audio  -> EXECUTED, verify True, get_volume() ≈ 30
      2. hay herramienta pero no lectura (CI con wpctl sin sink) -> EXECUTED,
         verify None, mensaje CON salvedad
      3. no hay ni wpctl ni pactl (contenedor pelado) -> ERROR que dice
         qué se intentó ('Intenté: ...')

    Lo que el banco PROHÍBE: EXECUTED + "volumen al 30" sin verify detrás.
    """
    from jarvis_local.tools.media_controls import get_volume, set_volume

    inicial = get_volume()
    plan = set_volume(30)
    v = plan.params["verify"]["ok"]

    if plan.status == ActionStatus.ERROR:                       # desenlace 3
        assert v is False
        assert "intenté" in plan.result.lower()
        assert not _EXITO.search(plan.result)
        return
    assert plan.status == ActionStatus.EXECUTED
    if v is None:                                               # desenlace 2
        assert "no pude confirmar" in plan.result.lower()
        return
    # desenlace 1: comprobación independiente contra el sistema real
    assert v is True
    try:
        assert inicial is not None and abs(get_volume() - 30) <= 4
    finally:
        set_volume(inicial)


def test_efecto_recordatorio_queda_programado_con_su_hora():
    from datetime import datetime, timedelta

    from jarvis_local.tools import reminders as rem

    orig = rem.REMINDERS_PATH
    tmp = _tmp("_banco_d5_reminders.json")
    rem.REMINDERS_PATH = tmp
    try:
        with patch.object(rem, "_arm", lambda *a, **k: None):
            plan = rem.set_reminder("sacar la basura", minutes=45)
        assert plan.status == ActionStatus.EXECUTED
        guardados = rem._load_store()
        assert len(guardados) == 1
        assert guardados[0]["text"] == "sacar la basura"
        cuando = datetime.fromisoformat(guardados[0]["when"])
        esperado = datetime.now() + timedelta(minutes=45)
        assert abs((cuando - esperado).total_seconds()) < 90
    finally:
        rem.REMINDERS_PATH = orig
        if os.path.exists(tmp):
            os.remove(tmp)


def test_efecto_nota_queda_escrita_en_el_archivo():
    from jarvis_local.tools import notes

    tmpdir = _tmp("_banco_d5_notas")
    os.makedirs(tmpdir, exist_ok=True)
    try:
        with patch.object(notes, "NOTES_DIR", tmpdir):
            plan = notes.take_note("comprar leche y pan", open_notepad=False)
        assert plan.status == ActionStatus.EXECUTED
        contenido = "".join(open(os.path.join(tmpdir, f), encoding="utf-8").read()
                            for f in os.listdir(tmpdir))
        assert "comprar leche y pan" in contenido
    finally:
        for f in os.listdir(tmpdir):
            os.remove(os.path.join(tmpdir, f))
        os.rmdir(tmpdir)


# ════════════════════════════════════════════════════════════════════════════
# CLASE 2 — FALLO FORZADO: error claro, jamás un éxito inventado
# ════════════════════════════════════════════════════════════════════════════


def test_fallo_abrir_app_inexistente():
    from jarvis_local.tools.apps import open_app

    plan = open_app("zzz_app_que_no_existe_9x")
    assert plan.status == ActionStatus.BLOCKED
    assert not _EXITO.search(plan.result), plan.result
    assert "no encontre" in plan.result.lower() or "no esta instalada" in plan.result.lower()


def test_fallo_crear_fichero_fuera_de_la_whitelist():
    from jarvis_local.tools.files import create_file

    plan = create_file("/etc/_banco_d5_prohibido.txt", "x")
    assert plan.status == ActionStatus.BLOCKED
    assert not _EXITO.search(plan.result)
    assert "permitida" in plan.result.lower() or "fuera" in plan.result.lower()
    assert not os.path.exists("/etc/_banco_d5_prohibido.txt")


def test_fallo_leer_fichero_fuera_de_la_whitelist():
    from jarvis_local.tools.reader import read_file_aloud

    plan = read_file_aloud("/etc/passwd")
    assert plan.status == ActionStatus.BLOCKED
    assert not _EXITO.search(plan.result)


def test_fallo_multimedia_sin_reproductor_no_dice_hecho():
    """'pon pausa' sin reproductor MPRIS: antes decía 'Hecho, senor.'."""
    from jarvis_local.tools import media_controls as mc

    def _sin_player(*_a, **_k):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="",
                                           stderr="No players found")

    with patch.object(mc, "IS_WINDOWS", False), \
         patch.object(mc, "_playerctl", side_effect=_sin_player):
        pausa = mc.media_play_pause()
        sig = mc.media_next()

    for plan in (pausa, sig):
        assert plan.status == ActionStatus.ERROR
        assert not _EXITO.search(plan.result), plan.result
        assert "reproductor" in plan.result.lower()
        assert plan.params["verify"]["ok"] is False


def test_fallo_borrado_bloqueado_no_es_operacion_completada():
    """EL caso concreto encontrado: plan_delete devolvía BLOCKED con .result
    vacío y execute()/_execute_tool_write lo reportaban como
    'Operacion completada.'. No puede volver."""
    import jarvis_local.jarvis as J
    from jarvis_local.agent.registry import execute

    archivo = _tmp("_banco_d5_no_borrar.txt")
    with open(archivo, "w", encoding="utf-8") as f:
        f.write("no me borres")
    try:
        # ruta agente
        texto, pendiente = execute("borrar_archivo", {"path": archivo})
        assert pendiente is False
        assert texto != "Operacion completada."
        assert not _EXITO.search(texto), texto
        assert os.path.exists(archivo)
        # ruta parser
        texto2 = J._execute_tool_write("delete_file", {"path": archivo})
        assert texto2 != "Operacion completada."
        assert not _EXITO.search(texto2), texto2
        assert os.path.exists(archivo)
    finally:
        os.remove(archivo)


def test_fallo_verify_none_se_reporta_con_salvedad_no_como_exito():
    """Un verify que no se puede comprobar (None) se reporta CON salvedad. El
    banco lo EXIGE: 'Hecho, senor.' a secas sería un fallo."""
    from jarvis_local.tools import media_controls as mc

    # Windows: las teclas multimedia no exponen estado legible -> None
    with patch.object(mc, "IS_WINDOWS", True), \
         patch.object(mc, "_press", lambda *a, **k: None):
        plan = mc.media_play_pause()

    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "no pude confirmar" in plan.result.lower()
    assert plan.result.strip() != "Hecho, senor."


def test_fallo_volumen_que_no_cuaja_es_error_con_lo_que_se_intento():
    from jarvis_local.tools import media_controls as mc

    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("jarvis_local.tools.verify.grace", lambda *a, **k: None), \
         patch.object(mc, "_wpctl", return_value=ok), \
         patch.object(mc, "_pactl", return_value=ok), \
         patch.object(mc, "get_volume", return_value=15):   # nunca llega a 30
        plan = mc.set_volume(30)

    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert "intenté" in plan.result.lower()          # dice QUÉ se intentó
    assert not _EXITO.search(plan.result)


# ════════════════════════════════════════════════════════════════════════════
# FASE E — procesos, servicios, notificaciones
# ════════════════════════════════════════════════════════════════════════════


def test_efecto_matar_un_proceso_de_prueba_y_comprobar_que_murio(monkeypatch):
    """EFECTO real: se lanza un proceso, se mata y se comprueba EN LA MÁQUINA
    (psutil.pid_exists) que dejó de existir."""
    import time

    from jarvis_local.safety import untouchables
    from jarvis_local.tools import processes

    # el proceso lo lanza el test, así que sería 'hijo de JARVIS': se protege
    # solo el propio runner para simular un proceso normal del usuario.
    monkeypatch.setattr(untouchables, "own_pids", lambda: {os.getpid()})

    proc = subprocess.Popen(["sleep", "37"])
    try:
        time.sleep(0.3)
        assert __import__("psutil").pid_exists(proc.pid)

        pk = processes.plan_kill(str(proc.pid))
        assert pk.status == ActionStatus.PLANNED
        assert f"PID: {proc.pid}" in pk.simulation_result

        done = processes.execute_kill(proc.pid)
        assert done.status == ActionStatus.EXECUTED
        assert done.params["verify"]["ok"] is True
        assert not __import__("psutil").pid_exists(proc.pid)     # comprobación independiente
    finally:
        if proc.poll() is None:
            proc.kill()


def test_fallo_intentar_matar_gnome_shell_se_bloquea(monkeypatch):
    """FALLO FORZADO: aunque se pida explícitamente, gnome-shell NO se mata.
    Se responde con el motivo y la alternativa, nunca un éxito."""
    from jarvis_local.tools import processes

    class _P:
        pid = 4242
        info = {"pid": 4242, "name": "gnome-shell"}
        def name(self): return "gnome-shell"
        def username(self): return "omar"
        def cmdline(self): return ["/usr/bin/gnome-shell"]

    class _Ps:
        NoSuchProcess = RuntimeError
        def process_iter(self, *a, **k): return [_P()]
        def Process(self, pid): return _P()
        def pid_exists(self, pid): return True

    monkeypatch.setattr(processes, "_psutil", lambda: _Ps())

    for plan in (processes.plan_kill("gnome-shell"), processes.execute_kill(4242)):
        assert plan.status == ActionStatus.BLOCKED
        assert "gnome-shell" in plan.result
        assert not _EXITO.search(plan.result)
        assert "sesión" in plan.result.lower() or "sesion" in plan.result.lower()


def test_fallo_servicio_de_sistema_pide_sudo_no_lo_hace_a_ciegas(monkeypatch):
    from jarvis_local.tools import services

    class _Sc:
        def __call__(self, scope, *a):
            if a and a[0] == "show":
                return subprocess.CompletedProcess([], 0,
                    "LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\n", "")
            return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(services, "_systemctl", _Sc())
    monkeypatch.setattr(services, "_hay_systemctl", lambda: True)

    plan = services.plan_service("reiniciar", "cups", scope="system")
    assert plan.status == ActionStatus.BLOCKED
    assert "no uso sudo" in plan.result.lower()
    assert "cups.service" in plan.result and "<UNIDAD>" not in plan.result
    assert not _EXITO.search(plan.result)


def test_fallo_notificacion_sin_notify_send_error_claro(monkeypatch):
    from jarvis_local.tools.notify import send_notification

    monkeypatch.setattr("shutil.which", lambda _: None)
    plan = send_notification("algo")
    assert plan.status == ActionStatus.ERROR
    assert "notify-send" in plan.result and "libnotify-bin" in plan.result
    assert not _EXITO.search(plan.result)


def test_efecto_notificacion_rc0_se_reporta_con_salvedad(monkeypatch):
    """Que notify-send acepte el mensaje no prueba que se viera: verify None."""
    from jarvis_local.tools.notify import send_notification

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/notify-send")
    monkeypatch.setattr("subprocess.run",
                        lambda *a, **k: subprocess.CompletedProcess([], 0, "", ""))
    plan = send_notification("compilación lista", titulo="Build")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "no puedo confirmar" in plan.result.lower()


if __name__ == "__main__":
    print("usa pytest")
