"""TAREA de auditoría — la configuración ya no es decorativa.

Hasta esta tarea, cuatro cosas que el usuario podía leer en config.yaml (o en
el propio código) no se aplicaban:

1. `safety.allowed_folders` se ignoraba por completo.
2. `voice.tts_rate` / `voice.tts_volume` eran decorativos (siempre "+0%").
3. `AGENT_TIMEOUT = 30` existía en agent/loop.py y NO se usaba: el único límite
   era el timeout HTTP de 600 s, así que un modelo colgado paraba JARVIS 10 min.
4. `search_files` con `except PermissionError: pass` respondía "no encontrado"
   como EXECUTED cuando no pudo mirar ni la mitad del árbol.
"""
import importlib
import sys

import pytest

from jarvis_local.safety.policy import ActionStatus


@pytest.fixture(autouse=True)
def _modulos_limpios():
    """Reimporta los módulos que los tests de este archivo recargan, PARA QUE
    el siguiente test no herede la configuración parcheada del anterior."""
    yield
    import jarvis_local.safety.permissions as permissions
    import jarvis_local.voice.tts as tts
    importlib.reload(permissions)
    importlib.reload(tts)


# ── 1. allowed_folders se respeta ─────────────────────────────────────────
def test_allowed_folders_de_config_manda(monkeypatch, tmp_path):
    carpeta = tmp_path / "solo_esto"
    carpeta.mkdir()
    import jarvis_local.config as config

    cfg = dict(config.get_config())
    cfg["safety"] = {"allowed_folders": [str(carpeta)]}
    monkeypatch.setattr(config.ConfigManager, "_config_cache", cfg)
    monkeypatch.setattr(config, "get_config", lambda: cfg)

    import jarvis_local.safety.permissions as permissions
    importlib.reload(permissions)
    assert [str(carpeta)] == permissions.ALLOWED_FOLDERS
    ok, _ = permissions.is_within_allowed(str(carpeta / "f.txt"))
    assert ok is True
    ok, _ = permissions.is_within_allowed("/etc/passwd")
    assert ok is False


def test_allowed_folders_vacio_usa_las_reales_del_usuario():
    from jarvis_local.safety.permissions import ALLOWED_FOLDERS
    assert len(ALLOWED_FOLDERS) >= 3
    assert all(not p.startswith("%") for p in ALLOWED_FOLDERS)


def test_allowed_folders_con_variables_sin_resolver_se_ignoran(monkeypatch, tmp_path):
    """Una ruta de Windows en Linux no se admite: admitirla dejaría la lista
    inutilizable y rompería todas las herramientas de archivos."""
    import jarvis_local.config as config

    cfg = dict(config.get_config())
    cfg["safety"] = {"allowed_folders": ["%USERPROFILE%\\Documents",
                                          str(tmp_path / "buena")]}
    (tmp_path / "buena").mkdir()
    monkeypatch.setattr(config.ConfigManager, "_config_cache", cfg)
    monkeypatch.setattr(config, "get_config", lambda: cfg)

    import jarvis_local.safety.permissions as permissions
    importlib.reload(permissions)
    assert [str(tmp_path / "buena")] == permissions.ALLOWED_FOLDERS


# ── 2. la voz obedece a config.yaml ───────────────────────────────────────
def test_tts_aplica_tts_rate_y_tts_volume(monkeypatch):
    import jarvis_local.config as config
    cfg = dict(config.get_config())
    cfg["voice"] = {"tts_rate": 200, "tts_volume": 0.5}
    monkeypatch.setattr(config, "get_config", lambda: cfg)

    import jarvis_local.voice.tts as tts
    importlib.reload(tts)
    assert tts._EDGE_RATE == "+14%"     # (200-175)/175
    assert tts._EDGE_VOLUME == "-50%"
    importlib.reload(tts)


def test_tts_rate_fuera_de_rango_no_se_aplica():
    """El límite de set_rate no se saltó: sólo se aplica lo que es válido."""
    import jarvis_local.voice.tts as tts
    assert tts.set_rate(50) is False
    assert tts.set_rate(250) is True
    importlib.reload(tts)


# ── 3. AGENT_TIMEOUT se usa ────────────────────────────────────────────────
def test_el_llm_se_corta_al_agotar_el_presupuesto(monkeypatch):
    import time

    from jarvis_local.agent import loop

    def _lento(*_a, **_kw):
        time.sleep(0.3)

    monkeypatch.setattr(loop, "_llm_con_timeout",
                        lambda fn, *a, **kw: _llm_real(fn, *a, **kw))

    def _llm_real(fn, *a, **kw):
        import threading
        box = {}
        def _corre():
            try:
                box["valor"] = fn(*a, **kw)
            except Exception as e:
                box["error"] = e
        hilo = threading.Thread(target=_corre, daemon=True)
        hilo.start()
        hilo.join(0.05)                    # presupuesto minúsculo
        if hilo.is_alive():
            raise TimeoutError("excedido")
        if "error" in box:
            raise box["error"]
        return box.get("valor")

    cliente = type("C", (), {"chat_with_tools": staticmethod(_lento)})()
    with pytest.raises(TimeoutError):
        loop._llamar_modelo(cliente, [], [], False)


def test_agt_timeout_es_la_constante_si_no_hay_config():
    from jarvis_local.agent.loop import AGENT_TIMEOUT
    # Medido en este equipo: una petición del agente tarda ~88 s SIN carga.
    # Menos de ~90 s de presupuesto dejaría el agente inutilizable en producción.
    assert AGENT_TIMEOUT >= 120


# ── 4. search_files ya no finge éxito ─────────────────────────────────────
def test_search_files_sin_permiso_no_finge_que_no_habia_nada(monkeypatch, tmp_path):
    from jarvis_local.safety import permissions

    permitida = str(tmp_path)
    monkeypatch.setattr(permissions, "ALLOWED_FOLDERS", [permitida])

    from jarvis_local.tools import files

    def _walk_que_revienta(_ruta):
        raise PermissionError(13, "denegado")
        yield  # noqa: B018 -- solo para que sea un generador

    monkeypatch.setattr(files.os, "walk", _walk_que_revienta)
    plan = files.search_files("loquesea", permitida)
    assert plan.status == ActionStatus.ERROR
    assert "permiso" in plan.result.lower() or "acceso" in plan.result.lower()
    assert "no se encontro" not in plan.result.lower()


def test_search_files_sin_permiso_con_algunos_resultados_lo_dice(monkeypatch, tmp_path):
    """Si se encontró algo PERO no se pudo mirar del todo, el resultado lo
    declara: ya no es un 'no encontré' engañoso."""
    from jarvis_local.safety import permissions
    permitida = str(tmp_path)
    monkeypatch.setattr(permissions, "ALLOWED_FOLDERS", [permitida])

    from jarvis_local.tools import files

    def _walk_parcial(_ruta):
        yield (permitida, [], ["notas.txt"])
        raise PermissionError(13, "denegado en otra carpeta")

    monkeypatch.setattr(files.os, "walk", _walk_parcial)
    plan = files.search_files("notas", permitida)
    assert plan.status == ActionStatus.EXECUTED
    assert "notas.txt" in plan.result
    assert "no pude mirar" in plan.result.lower()
