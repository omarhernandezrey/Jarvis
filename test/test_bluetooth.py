"""PLAN_EJECUCION FASE F · F3 — Bluetooth (bluetoothctl).

bluetoothctl se simula. Se comprueban: detección en runtime, que solo se
tocan dispositivos YA EMPAREJADOS, y el VERIFY real (`Connected:` de
`bluetoothctl info`) con sus tres desenlaces.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.intent.parser import parse_intent
from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import bluetooth as BT

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or", re.I)


def _cp(out="", rc=0, err=""):
    return subprocess.CompletedProcess([], rc, out, err)


class FakeBt:
    """Simula `_bt(*args)`. `paired` = {MAC: nombre}; `connected` = set de MAC."""

    def __init__(self, paired=None, connected=None, powered=True,
                 controlador=True, connect_falla=False, info_ilegible=False):
        self.paired = dict(paired or {})
        self.connected = set(connected or [])
        self.powered = powered
        self.controlador = controlador
        self.connect_falla = connect_falla
        self.info_ilegible = info_ilegible

    def __call__(self, *a):
        if a == ("show",):
            if not self.controlador:
                return _cp("No default controller available", rc=1)
            return _cp(f"Controller B8:86:87:BE:8D:70 (public)\n"
                       f"\tName: test\n\tPowered: {'yes' if self.powered else 'no'}\n")
        if a[:2] == ("devices", "Paired"):
            return _cp("".join(f"Device {m} {n}\n" for m, n in self.paired.items()))
        if a[:2] == ("devices", "Connected"):
            return _cp("".join(f"Device {m} {self.paired.get(m, m)}\n"
                               for m in self.connected))
        if a[0] == "info":
            mac = a[1]
            if self.info_ilegible:
                return _cp(f"Device {mac} (public)\n\tName: x\n")
            estado = "yes" if mac in self.connected else "no"
            return _cp(f"Device {mac} (public)\n\tName: x\n\tConnected: {estado}\n")
        if a[0] == "connect":
            if self.connect_falla:
                return _cp("Failed to connect: org.bluez.Error.Failed", rc=1)
            self.connected.add(a[1])
            return _cp("Connection successful\n")
        if a[0] == "disconnect":
            self.connected.discard(a[1])
            return _cp("Successful disconnected\n")
        return _cp()


@pytest.fixture
def _bt(monkeypatch):
    fake = FakeBt(paired={"AA:AA:AA:AA:AA:01": "Sony WH-1000XM4"})
    monkeypatch.setattr(BT, "_hay_bluetoothctl", lambda: True)
    monkeypatch.setattr(BT, "_bt", fake)
    monkeypatch.setattr("jarvis_local.tools.verify.grace", lambda *a, **k: None)
    return fake


# --- detección en runtime -------------------------------------------

def test_sin_bluetoothctl_error_claro(monkeypatch):
    monkeypatch.setattr(BT, "_hay_bluetoothctl", lambda: False)
    plan = BT.bt_status()
    assert plan.status == ActionStatus.ERROR
    assert "bluetoothctl" in plan.result and "apt install" in plan.result


def test_sin_controlador_lo_dice(_bt):
    _bt.controlador = False
    plan = BT.bt_list()
    assert plan.status == ActionStatus.ERROR
    assert "controlador" in plan.result.lower()


# --- lectura -------------------------------------------------------

def test_estado_resume_emparejados_y_conectados(_bt):
    _bt.connected = {"AA:AA:AA:AA:AA:01"}
    plan = BT.bt_status()
    assert plan.status == ActionStatus.EXECUTED
    assert "1 emparejado" in plan.result and "1 conectado" in plan.result


def test_listar_sin_emparejados_guia_a_configuracion(_bt):
    _bt.paired = {}
    plan = BT.bt_list()
    assert plan.status == ActionStatus.EXECUTED
    assert "Configuración" in plan.result and "PIN" in plan.result


def test_listar_marca_los_conectados(_bt):
    _bt.paired["AA:AA:AA:AA:AA:02"] = "JBL Flip 5"
    _bt.connected = {"AA:AA:AA:AA:AA:02"}
    plan = BT.bt_list()
    lineas = plan.result.splitlines()
    assert any(ln.strip().startswith("* JBL Flip 5") for ln in lineas)
    assert any(ln.strip().startswith("Sony WH-1000XM4") for ln in lineas)


# --- conectar: solo emparejados, con VERIFY ----------------------

def test_conectar_a_no_emparejado_se_bloquea(_bt):
    plan = BT.bt_connect("Bose QC")
    assert plan.status == ActionStatus.BLOCKED
    assert "Sony WH-1000XM4" in plan.result          # dice cuáles sí


def test_conectar_ok_verifica_connected_yes(_bt):
    plan = BT.bt_connect("Sony")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "AA:AA:AA:AA:AA:01" in _bt.connected


def test_conectar_rc_no_cero_es_error_no_finge(_bt):
    _bt.connect_falla = True
    plan = BT.bt_connect("Sony")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert not _EXITO.search(plan.result)


def test_conectar_sin_poder_releer_estado_da_salvedad(_bt):
    _bt.info_ilegible = True
    plan = BT.bt_connect("Sony")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is None
    assert "no pude" in plan.result.lower()


def test_conectar_sin_objetivo_con_un_solo_emparejado(_bt):
    plan = BT.bt_connect("")
    assert plan.status == ActionStatus.EXECUTED
    assert "AA:AA:AA:AA:AA:01" in _bt.connected


def test_conectar_varias_coincidencias_pide_exacto(_bt):
    _bt.paired = {"AA:AA:AA:AA:AA:01": "Sony WH-1000XM4",
                  "AA:AA:AA:AA:AA:02": "Sony WF-1000XM5"}
    plan = BT.bt_connect("Sony")
    assert plan.status == ActionStatus.BLOCKED
    assert "exacto" in plan.result.lower() or "MAC" in plan.result


# --- desconectar: con VERIFY -----------------------------------

def test_desconectar_ok_verifica(_bt):
    _bt.connected = {"AA:AA:AA:AA:AA:01"}
    plan = BT.bt_disconnect("Sony")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert not _bt.connected


def test_desconectar_que_no_desconecta_es_error(_bt):
    _bt.connected = {"AA:AA:AA:AA:AA:01"}
    orig = FakeBt.__call__

    def _no_baja(self, *a):
        if a and a[0] == "disconnect":
            return _cp("Failed", rc=1)              # no lo quita de connected
        return orig(self, *a)
    import jarvis_local.tools.bluetooth as _B
    _B._bt = lambda *a: _no_baja(_bt, *a)

    plan = BT.bt_disconnect("Sony")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False


def test_desconectar_sin_nada_conectado_se_bloquea(_bt):
    plan = BT.bt_disconnect("")
    assert plan.status == ActionStatus.BLOCKED


# --- parser --------------------------------------------------

def test_parser_enruta_bluetooth():
    assert parse_intent("estado del bluetooth").tool == "bt_status"
    assert parse_intent("lista los dispositivos bluetooth").tool == "bt_list"
    r = parse_intent("conéctate al altavoz JBL Flip por bluetooth")
    assert r.tool == "bt_connect" and "JBL Flip" in r.arguments["objetivo"]
    assert parse_intent("desconecta los cascos").tool == "bt_disconnect"
    # emparejar un nuevo: fuera de alcance, se explica (no se finge)
    assert parse_intent("empareja unos auriculares nuevos").kind == "ambiguous"
    # el volumen no se ve afectado
    assert parse_intent("sube el volumen").tool == "volume_up"


if __name__ == "__main__":
    print("usa pytest")
