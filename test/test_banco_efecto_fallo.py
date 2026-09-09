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
    from jarvis_local.safety import permisos
    from jarvis_local.tools import services

    class _Sc:
        def __call__(self, scope, *a):
            if a and a[0] == "show":
                return subprocess.CompletedProcess([], 0,
                    "LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\n", "")
            return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(services, "_systemctl", _Sc())
    monkeypatch.setattr(services, "_hay_systemctl", lambda: True)
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: False)

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


def test_fallo_no_toca_el_sistema_con_una_instalacion_de_paquetes_en_curso(monkeypatch):
    """E1·c: con dpkg/apt corriendo, ni matar procesos del sistema, ni tocar
    servicios, ni apagar/reiniciar. Dice que espere, nunca finge que lo hizo."""
    from jarvis_local.safety import permisos
    from jarvis_local.tools import power, services

    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: True)

    class _Sc:
        def __call__(self, scope, *a):
            return subprocess.CompletedProcess([], 0,
                "LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\n", "")
    monkeypatch.setattr(services, "_systemctl", _Sc())
    monkeypatch.setattr(services, "_hay_systemctl", lambda: True)

    for plan in (services.plan_service("reiniciar", "syncthing", scope="user"),
                 power.shutdown_pc(), power.restart_pc()):
        assert plan.status == ActionStatus.BLOCKED
        assert "instalación" in plan.result or "actualización" in plan.result
        assert "espera" in plan.result.lower()
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


# ════════════════════════════════════════════════════════════════════════════
# FASE F — brillo, red/WiFi, Bluetooth
# ════════════════════════════════════════════════════════════════════════════


def _cp(out="", rc=0, err=""):
    return subprocess.CompletedProcess([], rc, out, err)


def test_efecto_brillo_se_relee_el_valor_real(monkeypatch):
    """EFECTO: se fija el brillo y se COMPRUEBA releyendo `brightnessctl get`,
    no el código de salida. El estado simulado cambia de verdad."""
    from jarvis_local.tools import brightness as B

    est = {"pct": 20}

    def _bctl(*a):
        if a[:2] == ("-m", "get"):
            return _cp(str(est["pct"]))
        if a[:2] == ("-m", "max"):
            return _cp("100")
        if a and a[0] == "set":
            est["pct"] = int(a[1].rstrip("%"))
            return _cp()
        return _cp()

    monkeypatch.setattr(B, "_hay_brightnessctl", lambda: True)
    monkeypatch.setattr(B, "_bctl", _bctl)
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)

    plan = B.set_brightness(42)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert est["pct"] == 42                       # comprobación independiente
    assert not _EXITO.search(plan.result)


def test_fallo_brillo_nunca_deja_la_pantalla_a_oscuras(monkeypatch):
    """FALLO FORZADO: pedir brillo 0 no puede dejar la pantalla negra sin
    forma de corregirlo. Se recorta al mínimo y se dice."""
    from jarvis_local.tools import brightness as B

    est = {"pct": 80}

    def _bctl(*a):
        if a[:2] == ("-m", "get"):
            return _cp(str(est["pct"]))
        if a[:2] == ("-m", "max"):
            return _cp("100")
        if a and a[0] == "set":
            est["pct"] = int(a[1].rstrip("%"))
            return _cp()
        return _cp()

    monkeypatch.setattr(B, "_hay_brightnessctl", lambda: True)
    monkeypatch.setattr(B, "_bctl", _bctl)
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)

    plan = B.set_brightness(0)
    assert est["pct"] == B.MIN_BRILLO_PCT
    assert f"{B.MIN_BRILLO_PCT}%" in plan.result


def test_fallo_brillo_sin_brightnessctl_error_claro(monkeypatch):
    """FALLO FORZADO real en esta máquina: no hay brightnessctl instalado."""
    from jarvis_local.tools import brightness as B

    monkeypatch.setattr(B, "_hay_brightnessctl", lambda: False)
    plan = B.set_brightness(60)
    assert plan.status == ActionStatus.ERROR
    assert "brightnessctl" in plan.result
    assert not _EXITO.search(plan.result)


class _FakeNmcli:
    def __init__(self):
        self.guardadas = {"CasaWifi": "802-11-wireless"}
        self.activas = set()

    def __call__(self, *a):
        if a[:2] == ("-t", "-f") and "WIFI-HW" in a:
            return _cp("enabled")
        if a[:2] == ("-t", "-f") and a[2] == "WIFI":
            return _cp("enabled")
        if a[:2] == ("-t", "-f") and a[2] == "NAME,TYPE" and "show" in a:
            return _cp("".join(f"{n}:{t}\n" for n, t in self.guardadas.items()))
        if a[:2] == ("-t", "-f") and a[2].startswith("NAME,STATE"):
            return _cp("".join(f"{n}:activated\n" for n in self.activas))
        if a[0] == "connection" and a[1] == "up":
            self.activas.add(a[2])
            return _cp()
        if a[0] == "connection" and a[1] == "down":
            self.activas.discard(a[2])
            return _cp()
        return _cp()


def _patch_nmcli(monkeypatch, fake, tx=False):
    from jarvis_local.safety import permisos
    from jarvis_local.tools import network as N
    monkeypatch.setattr(N, "_hay_nmcli", lambda: True)
    monkeypatch.setattr(N, "_nmcli", fake)
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: tx)


def test_efecto_conectar_wifi_verifica_que_quedo_activada(monkeypatch):
    """EFECTO: tras `nmcli connection up` se comprueba que la conexión está
    'activated' (estado real), no que el comando devolviera 0."""
    from jarvis_local.tools import network as N

    fake = _FakeNmcli()
    _patch_nmcli(monkeypatch, fake)
    plan = N.wifi_connect("CasaWifi")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "CasaWifi" in fake.activas                 # comprobación independiente


def test_fallo_conectar_wifi_no_guardada_no_finge(monkeypatch):
    """FALLO FORZADO: red que NetworkManager no tiene guardada -> BLOQUEADO
    que lista las que sí, nunca un 'conectado'."""
    from jarvis_local.tools import network as N

    _patch_nmcli(monkeypatch, _FakeNmcli())
    plan = N.wifi_connect("RedAjena")
    assert plan.status == ActionStatus.BLOCKED
    assert "CasaWifi" in plan.result
    assert not _EXITO.search(plan.result)


def test_fallo_wifi_la_contrasena_nunca_aparece_en_el_plan(monkeypatch):
    """Invariante F2: JARVIS no maneja contraseñas de WiFi — no hay ninguna en
    los parámetros ni en el resultado (solo activa conexiones guardadas)."""
    from jarvis_local.tools import network as N

    _patch_nmcli(monkeypatch, _FakeNmcli())
    plan = N.wifi_connect("CasaWifi")
    todo = (repr(plan.params) + " " + (plan.result or "") + " "
            + (plan.simulation_result or "")).lower()
    assert "psk" not in todo and "password" not in todo


def test_fallo_red_no_se_toca_con_instalacion_de_paquetes_en_curso(monkeypatch):
    """E1·c aplicado a F2: con dpkg/apt corriendo no se conecta ni se
    desconecta la red (un apt a medias sin red deja el sistema peor)."""
    from jarvis_local.tools import network as N

    _patch_nmcli(monkeypatch, _FakeNmcli(), tx=True)
    for plan in (N.wifi_connect("CasaWifi"), N.plan_disconnect("CasaWifi"),
                 N.plan_wifi_radio(False)):
        assert plan.status == ActionStatus.BLOCKED
        assert "instalación" in plan.result or "actualización" in plan.result
        assert not _EXITO.search(plan.result)


class _FakeBt:
    def __init__(self):
        self.paired = {"AA:AA:AA:AA:AA:01": "Sony WH-1000XM4"}
        self.connected = set()
        self.baja_falla = False

    def __call__(self, *a):
        if a == ("show",):
            return _cp("Controller B8:86:87:BE:8D:70 (public)\n\tPowered: yes\n")
        if a[:2] == ("devices", "Paired"):
            return _cp("".join(f"Device {m} {n}\n" for m, n in self.paired.items()))
        if a[:2] == ("devices", "Connected"):
            return _cp("".join(f"Device {m} {self.paired[m]}\n" for m in self.connected))
        if a[0] == "info":
            estado = "yes" if a[1] in self.connected else "no"
            return _cp(f"Device {a[1]}\n\tConnected: {estado}\n")
        if a[0] == "connect":
            self.connected.add(a[1])
            return _cp("Connection successful\n")
        if a[0] == "disconnect":
            if not self.baja_falla:
                self.connected.discard(a[1])
            return _cp("" if self.baja_falla else "Successful disconnected\n",
                       rc=1 if self.baja_falla else 0)
        return _cp()


def _patch_bt(monkeypatch, fake):
    from jarvis_local.tools import bluetooth as BT
    monkeypatch.setattr(BT, "_hay_bluetoothctl", lambda: True)
    monkeypatch.setattr(BT, "_bt", fake)
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)


def test_efecto_bluetooth_conectar_verifica_connected_yes(monkeypatch):
    """EFECTO: tras `bluetoothctl connect` se lee `Connected:` de
    `bluetoothctl info` — estado real, no el código de salida."""
    from jarvis_local.tools import bluetooth as BT

    fake = _FakeBt()
    _patch_bt(monkeypatch, fake)
    plan = BT.bt_connect("Sony")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "AA:AA:AA:AA:AA:01" in fake.connected        # comprobación independiente
    assert not _EXITO.search(plan.result)


def test_fallo_bluetooth_dispositivo_no_emparejado_no_finge(monkeypatch):
    """FALLO FORZADO: no se conecta a algo que no está emparejado -> BLOQUEADO
    que lista los emparejados, nunca un 'conectado'."""
    from jarvis_local.tools import bluetooth as BT

    _patch_bt(monkeypatch, _FakeBt())
    plan = BT.bt_connect("Bose QuietComfort")
    assert plan.status == ActionStatus.BLOCKED
    assert "Sony WH-1000XM4" in plan.result
    assert not _EXITO.search(plan.result)


def test_fallo_bluetooth_desconectar_que_no_cuaja_es_error(monkeypatch):
    """FALLO FORZADO: si el dispositivo sigue conectado tras el intento, es
    ERROR con lo que se intentó, no un 'desconectado'."""
    from jarvis_local.tools import bluetooth as BT

    fake = _FakeBt()
    fake.connected = {"AA:AA:AA:AA:AA:01"}
    fake.baja_falla = True
    _patch_bt(monkeypatch, fake)
    plan = BT.bt_disconnect("Sony")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert not _EXITO.search(plan.result)


def test_fallo_bluetooth_sin_bluetoothctl_error_claro(monkeypatch):
    from jarvis_local.tools import bluetooth as BT

    monkeypatch.setattr(BT, "_hay_bluetoothctl", lambda: False)
    plan = BT.bt_connect("lo que sea")
    assert plan.status == ActionStatus.ERROR
    assert "bluetoothctl" in plan.result
    assert not _EXITO.search(plan.result)


# ════════════════════════════════════════════════════════════════════════════
# FASE F · F4.2 — ventanas en Wayland
# ════════════════════════════════════════════════════════════════════════════


class _FakeShell:
    """List/Activate/Close simulados de la extensión ventanas-jarvis@local."""

    def __init__(self, wins):
        self.wins = wins

    def __call__(self, metodo, *cargs):
        import json as _j
        if metodo == "List":
            return True, repr((_j.dumps(self.wins),)), ""
        wid = int(cargs[0])
        w = next((x for x in self.wins if x["id"] == wid), None)
        if w is None:
            return False, "", f"…: ventana {wid} no encontrada"
        if metodo == "Activate":
            for x in self.wins:
                x["has_focus"] = x["id"] == wid
            return True, "()", ""
        if metodo == "Close":
            self.wins = [x for x in self.wins if x["id"] != wid]
            return True, "()", ""
        return False, "", "?"


def _w(id, title, wm_class, pid, focus=False):
    return {"id": id, "title": title, "wm_class": wm_class,
            "wm_class_instance": wm_class.lower(), "pid": pid, "window_type": 0,
            "frame_type": 0, "has_focus": focus, "on_current_workspace": True}


def _patch_win(monkeypatch, tmp_path, fake, responde=True):
    from jarvis_local.tools import ventanas as V
    monkeypatch.setattr(V, "_hay_gdbus", lambda: True)
    monkeypatch.setattr(V, "_extension_responde", lambda: responde)
    monkeypatch.setattr(V, "_call", fake)
    monkeypatch.setattr(V, "_SWITCH", tmp_path / "win.json")
    monkeypatch.setattr(V, "own_pids", lambda: {os.getpid()})
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)


def test_efecto_enfocar_ventana_mueve_el_foco(monkeypatch, tmp_path):
    """EFECTO: tras Activate se relee List() y se comprueba has_focus real."""
    from jarvis_local.tools import ventanas as V

    fake = _FakeShell([_w(1, "Calc", "org.gnome.Calculator", 900, focus=True),
                       _w(2, "gedit", "org.gnome.gedit", 901)])
    _patch_win(monkeypatch, tmp_path, fake)
    plan = V.focus_window("gedit")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert next(w for w in fake.wins if w["id"] == 2)["has_focus"] is True


def test_efecto_cerrar_ventana_desaparece_de_list(monkeypatch, tmp_path):
    """EFECTO: tras Close se relee List() y la ventana ya no está."""
    from jarvis_local.tools import ventanas as V

    fake = _FakeShell([_w(2, "gedit", "org.gnome.gedit", 901)])
    _patch_win(monkeypatch, tmp_path, fake)
    plan = V.execute_close_window(2)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert fake.wins == []


def test_fallo_cerrar_ventana_de_gnome_shell_se_bloquea(monkeypatch, tmp_path):
    """FALLO FORZADO: la ventana del compositor (E1 por wm_class) no se cierra."""
    from jarvis_local.tools import ventanas as V

    fake = _FakeShell([_w(9, "", "gnome-shell", 7777)])
    _patch_win(monkeypatch, tmp_path, fake)
    plan = V.plan_close_window("gnome-shell")
    assert plan.status == ActionStatus.BLOCKED
    assert not _EXITO.search(plan.result)


def test_fallo_cerrar_ventana_del_propio_jarvis_se_bloquea_por_pid(monkeypatch, tmp_path):
    """FALLO FORZADO: E1 por pid — nunca la ventana del propio JARVIS."""
    from jarvis_local.tools import ventanas as V

    fake = _FakeShell([_w(5, "JARVIS", "python3", os.getpid())])
    _patch_win(monkeypatch, tmp_path, fake)
    plan = V.plan_close_window("JARVIS")
    assert plan.status == ActionStatus.BLOCKED
    assert "propio JARVIS" in plan.result


def test_fallo_ventanas_sin_extension_dice_como_instalar(monkeypatch, tmp_path):
    """FALLO FORZADO: sin la extensión por D-Bus, ERROR claro, nunca en silencio."""
    from jarvis_local.tools import ventanas as V

    _patch_win(monkeypatch, tmp_path, _FakeShell([]), responde=False)
    plan = V.list_windows()
    assert plan.status == ActionStatus.ERROR
    assert "gnome-extensions enable ventanas-jarvis@local" in plan.result


def test_fallo_cerrar_ventana_que_sigue_abierta_es_salvedad_no_exito(monkeypatch, tmp_path):
    """FALLO FORZADO: Close rc 0 pero la ventana sigue (diálogo de guardado) ->
    EXECUTED con verify None y salvedad, nunca 'cerrada'."""
    from jarvis_local.tools import ventanas as V

    fake = _FakeShell([_w(2, "sin guardar", "org.gnome.gedit", 901)])

    def _call(metodo, *a):
        if metodo == "Close":
            return True, "()", ""          # dice ok pero no quita la ventana
        return fake(metodo, *a)
    _patch_win(monkeypatch, tmp_path, _call)
    plan = V.execute_close_window(2)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "guardar" in plan.result.lower()
    assert not _EXITO.search(plan.result)


# ════════════════════════════════════════════════════════════════════════════
# FASE G — escritura del portapapeles
# ════════════════════════════════════════════════════════════════════════════


def _patch_clip(monkeypatch, tmp_path, estado):
    from jarvis_local.tools import clipboard as C
    monkeypatch.setattr(C, "_backend", lambda: ("wl-clipboard", ["wl-copy"], ["wl-paste"]))
    monkeypatch.setattr(C, "_leer", lambda: (None if estado.get("ciego")
                                             else estado["texto"]))

    def _esc(t):
        if estado.get("escribe", True):
            estado["texto"] = t
        return estado.get("escribe", True)
    monkeypatch.setattr(C, "_escribir", _esc)
    monkeypatch.setattr(C, "_SWITCH", tmp_path / "clip.json")
    monkeypatch.setattr(C, "_PENDIENTE", {})
    monkeypatch.setattr(C, "_PREVIO", {"texto": None, "hubo": False})
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)
    monkeypatch.setattr("jarvis_local.tools.verify.wait_until",
                        lambda pred, **k: bool(pred()))


def test_efecto_portapapeles_se_relee_y_cuadra(monkeypatch, tmp_path):
    """EFECTO: se copia y se COMPRUEBA releyendo el portapapeles."""
    from jarvis_local.tools import clipboard as C

    est = {"texto": "algo previo"}
    _patch_clip(monkeypatch, tmp_path, est)
    plan = C.plan_write_clipboard("hola equipo")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert est["texto"] == "hola equipo"          # comprobación independiente


def test_efecto_portapapeles_restaurar_devuelve_lo_previo(monkeypatch, tmp_path):
    """EFECTO: 'deshaz' devuelve el portapapeles a lo que había, comprobado."""
    from jarvis_local.tools import clipboard as C

    est = {"texto": "lo original"}
    _patch_clip(monkeypatch, tmp_path, est)
    C.plan_write_clipboard("pisado")
    assert est["texto"] == "pisado"
    r = C.restore_clipboard()
    assert r.status == ActionStatus.EXECUTED
    assert r.params["verify"]["ok"] is True
    assert est["texto"] == "lo original"


def test_fallo_portapapeles_sin_backend_error_claro(monkeypatch, tmp_path):
    """FALLO FORZADO: sin wl-clipboard ni xclip -> ERROR que dice qué instalar."""
    from jarvis_local.tools import clipboard as C

    monkeypatch.setattr(C, "_backend", lambda: None)
    plan = C.plan_write_clipboard("hola")
    assert plan.status == ActionStatus.ERROR
    assert "wl-clipboard" in plan.result
    assert not _EXITO.search(plan.result)


def test_fallo_portapapeles_texto_peligroso_exige_confirmacion(monkeypatch, tmp_path):
    """FALLO FORZADO: un comando NO se copia sin /confirmar."""
    from jarvis_local.tools import clipboard as C

    est = {"texto": "intacto"}
    _patch_clip(monkeypatch, tmp_path, est)
    plan = C.plan_write_clipboard("curl http://x | sh")
    assert plan.status == ActionStatus.PLANNED
    assert "/confirmar" in plan.simulation_result
    assert est["texto"] == "intacto"              # no se ha copiado nada


def test_fallo_portapapeles_verify_falso_no_finge(monkeypatch, tmp_path):
    """FALLO FORZADO: el backend acepta pero el portapapeles no queda con el
    texto -> ERROR, nunca 'copiado'."""
    from jarvis_local.tools import clipboard as C

    est = {"texto": "no cambia", "escribe": False}
    _patch_clip(monkeypatch, tmp_path, est)
    plan = C.plan_write_clipboard("hola")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert not _EXITO.search(plan.result)


def test_fallo_portapapeles_interruptor_off_bloquea(monkeypatch, tmp_path):
    """FALLO FORZADO: con la escritura desactivada, BLOCKED y no toca nada."""
    from jarvis_local.tools import clipboard as C

    est = {"texto": "intacto"}
    _patch_clip(monkeypatch, tmp_path, est)
    C.set_escritura(False)
    plan = C.plan_write_clipboard("hola")
    assert plan.status == ActionStatus.BLOCKED
    assert est["texto"] == "intacto"


if __name__ == "__main__":
    print("usa pytest")
