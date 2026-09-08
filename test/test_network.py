"""PLAN_EJECUCION FASE F · F2 — red y WiFi (nmcli).

nmcli se simula. Se comprueban: lectura sin preguntar, conectar solo a redes
GUARDADAS con VERIFY real, confirmación para desconectar/apagar, el guardia
E1·c (transacción de paquetes), y que NUNCA hay una contraseña en los
parámetros ni en el resultado.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import network as N

_EXITO = re.compile(r"operaci[oó]n completada|hecho,?\s*se[nñ]or", re.I)
_SECRETO = "MiClaveWifiSuperSecreta2024"


def _cp(out="", rc=0, err=""):
    return subprocess.CompletedProcess([], rc, out, err)


class FakeNmcli:
    """Simula `_nmcli(*args)`. `estado` guarda conexiones activas/guardadas y
    el radio."""

    def __init__(self, guardadas=None, activas=None, radio="enabled",
                 wifi_hw=True, wifi_scan=""):
        self.guardadas = dict(guardadas or {})          # nombre -> tipo
        self.activas = set(activas or [])               # nombres activados
        self.radio = radio
        self.wifi_hw = wifi_hw
        self.wifi_scan = wifi_scan
        self.up_falla = False

    def __call__(self, *a):
        if a[:2] == ("-t", "-f") and "WIFI-HW" in a:
            return _cp("enabled" if self.wifi_hw else "missing")
        if a[:2] == ("-t", "-f") and a[2] == "WIFI":
            return _cp(self.radio)
        if a[:2] == ("-t", "-f") and a[2] == "DEVICE,TYPE,STATE,CONNECTION":
            return _cp("enp1s0:ethernet:connected:netplan-enp1s0\nlo:loopback:connected:lo\n")
        if a[:2] == ("-t", "-f") and a[2] == "IP4.ADDRESS":
            return _cp("IP4.ADDRESS[1]:192.168.1.45/24\n")
        if a[:2] == ("-t", "-f") and a[2] == "NAME,TYPE" and "show" in a:
            return _cp("".join(f"{n}:{t}\n" for n, t in self.guardadas.items()))
        if a[:2] == ("-t", "-f") and a[2].startswith("NAME,STATE"):
            return _cp("".join(f"{n}:activated\n" for n in self.activas))
        if a[:2] == ("-t", "-f") and a[2].startswith("NAME,DEVICE"):
            return _cp("".join(f"{n}:wlan0:802-11-wireless\n" for n in self.activas))
        if a[:2] == ("-t", "-f") and "IN-USE,SSID,SIGNAL,SECURITY" in " ".join(a):
            return _cp(self.wifi_scan)
        if a[0] == "connection" and a[1] == "up":
            if self.up_falla:
                return _cp(rc=4, err="Error: Connection activation failed.")
            self.activas.add(a[2])
            return _cp()
        if a[0] == "connection" and a[1] == "down":
            self.activas.discard(a[2])
            return _cp()
        if a[0] == "radio" and a[1] == "wifi":
            self.radio = "enabled" if a[2] == "on" else "disabled"
            return _cp()
        return _cp()


@pytest.fixture
def _nm(monkeypatch):
    from jarvis_local.safety import permisos
    fake = FakeNmcli()
    monkeypatch.setattr(N, "_hay_nmcli", lambda: True)
    monkeypatch.setattr(N, "_nmcli", fake)
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: False)
    return fake


# --- lectura -----------------------------------------------------------


def test_net_status(_nm):
    plan = N.net_status()
    assert plan.status == ActionStatus.EXECUTED
    assert "enp1s0" in plan.result and "192.168.1.45" in plan.result


def test_wifi_list_sin_hardware(_nm):
    _nm.wifi_hw = False
    plan = N.wifi_list()
    assert "no tiene wifi" in plan.result.lower()


def test_sin_nmcli_error_claro(monkeypatch):
    monkeypatch.setattr(N, "_hay_nmcli", lambda: False)
    plan = N.net_status()
    assert plan.status == ActionStatus.ERROR
    assert "nmcli" in plan.result and "network-manager" in plan.result


# --- conectar: solo redes guardadas, con VERIFY ----------------------


def test_conectar_a_red_no_guardada_se_bloquea(_nm):
    _nm.guardadas = {"CasaWifi": "802-11-wireless"}
    plan = N.wifi_connect("OficinaAjena")
    assert plan.status == ActionStatus.BLOCKED
    assert "no tengo guardada" in plan.result.lower()
    assert "CasaWifi" in plan.result             # dice cuáles sí


def test_conectar_ok_verifica_activated(_nm):
    _nm.guardadas = {"CasaWifi": "802-11-wireless"}
    plan = N.wifi_connect("CasaWifi")
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert "CasaWifi" in _nm.activas


def test_conectar_rc_no_cero_es_error_no_finge(_nm):
    _nm.guardadas = {"CasaWifi": "802-11-wireless"}
    _nm.up_falla = True
    plan = N.wifi_connect("CasaWifi")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False
    assert not _EXITO.search(plan.result)


def test_conectar_nunca_lleva_la_contrasena_en_params_ni_resultado(_nm):
    _nm.guardadas = {"CasaWifi": "802-11-wireless"}
    plan = N.wifi_connect("CasaWifi")
    todo = repr(plan.params) + " " + (plan.result or "") + " " + (plan.simulation_result or "")
    assert _SECRETO not in todo
    assert "psk" not in todo.lower() and "password" not in todo.lower()


# --- confirmación: apagar WiFi / desconectar -----------------------


def test_apagar_wifi_pide_confirmacion(_nm):
    plan = N.plan_wifi_radio(encender=False)
    assert plan.status == ActionStatus.PLANNED
    assert "/confirmar" in plan.simulation_result and "/cancelar" in plan.simulation_result


def test_desconectar_sin_objetivo_elige_el_wifi_activo(_nm):
    _nm.activas = {"CasaWifi"}
    plan = N.plan_disconnect()
    assert plan.status == ActionStatus.PLANNED
    assert plan.params["objetivo"] == "CasaWifi"
    assert "sin esa conexión" in plan.simulation_result or "sin conexión" in plan.simulation_result.lower()


def test_execute_wifi_radio_verifica(_nm):
    plan = N.execute_wifi_radio(encender=False)
    assert plan.status == ActionStatus.EXECUTED
    assert plan.params["verify"]["ok"] is True
    assert _nm.radio == "disabled"


def test_execute_disconnect_que_no_desconecta_es_error(_nm):
    _nm.activas = {"CasaWifi"}
    orig = _nm.__call__

    def _no_baja(*a):
        if a[0] == "connection" and a[1] == "down":
            return _cp(rc=1, err="not active")   # no la quita de activas
        return orig(*a)
    _nm.__call__ = _no_baja
    # FakeNmcli.__call__ es de clase; se llama vía instancia -> parcheamos _nmcli
    import jarvis_local.tools.network as _N
    _N._nmcli = _no_baja

    plan = N.execute_disconnect("CasaWifi")
    assert plan.status == ActionStatus.ERROR
    assert plan.params["verify"]["ok"] is False


# --- guardia E1·c: transacción de paquetes ------------------------


def test_no_toca_la_red_con_instalacion_en_curso(_nm, monkeypatch):
    from jarvis_local.safety import permisos
    monkeypatch.setattr(permisos, "transaccion_de_paquetes_en_curso", lambda: True)
    _nm.guardadas = {"CasaWifi": "802-11-wireless"}
    for plan in (N.wifi_connect("CasaWifi"), N.plan_wifi_radio(False),
                 N.plan_disconnect("CasaWifi"), N.execute_wifi_radio(True)):
        assert plan.status == ActionStatus.BLOCKED
        assert "instalación" in plan.result or "actualización" in plan.result


# --- capa 0 redacta la clave de WiFi (verificación pedida en F2) ---


def test_capa0_redacta_psk_de_wifi():
    from jarvis_local.safety.secrets import redact_secrets
    red, n = redact_secrets(f"802-11-wireless-security.psk: {_SECRETO}")
    assert n == 1 and _SECRETO not in red and "[REDACTED]" in red
    red2, n2 = redact_secrets(f"psk={_SECRETO}")
    assert n2 == 1 and _SECRETO not in red2


if __name__ == "__main__":
    print("usa pytest")
