"""
Tests de configuracion - Fase 1
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jarvis_local.config as cfg_module


def test_default_config():
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()
    assert cfg["ollama"]["host"] == "http://localhost:11434"
    assert cfg["ollama"]["model"] == "llama3.2:3b"
    assert cfg["jarvis"]["name"] == "JARVIS"
    assert cfg["jarvis"]["max_history"] == 20


def test_config_caching():
    cfg_module._config_cache = None
    cfg1 = cfg_module.get_config()
    cfg2 = cfg_module.get_config()
    assert cfg1 is cfg2


def test_reload_config():
    cfg_module._config_cache = None
    cfg1 = cfg_module.get_config()
    cfg2 = cfg_module.reload_config()
    assert cfg1 == cfg2


def test_config_has_required_keys():
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()
    assert "ollama" in cfg
    assert "jarvis" in cfg
    assert "logging" in cfg
    assert "host" in cfg["ollama"]
    assert "model" in cfg["ollama"]


# ── PLAN_EJECUCION FASE C · C5: num_ctx ajustado a lo que se ocupa de verdad ──
def test_num_ctx_cubre_una_sesion_de_chat_completa():
    """Medido en sesión real (BANCO_PRUEBAS_BASELINE §13): cada intercambio
    (usuario + respuesta) del chat ronda ~110 tokens. Con max_history turnos,
    una sesión llena de system prompt + historial no debe superar num_ctx: si
    lo hace, context-shift descarta los turnos más viejos a mitad de sesión e
    invalida el prefijo cacheado de C4. Deja margen (no ajustado al límite)
    para memoria manual + recuerdo automático."""
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()
    ollama_cfg, jarvis_cfg = cfg["ollama"], cfg["jarvis"]

    tokens_por_turno_medido = 110  # BANCO_PRUEBAS_BASELINE §13, medido con Ollama vivo
    margen_system_y_memoria = 800  # system prompt + memoria manual + recuerdo automático
    presupuesto_sesion_llena = (
        jarvis_cfg["max_history"] * tokens_por_turno_medido + margen_system_y_memoria)

    assert ollama_cfg["num_ctx"] >= presupuesto_sesion_llena, (
        f"num_ctx={ollama_cfg['num_ctx']} no cubre una sesión llena de "
        f"max_history={jarvis_cfg['max_history']} turnos "
        f"(~{presupuesto_sesion_llena} tokens estimados)")


def test_agent_num_ctx_cubre_el_uso_medido_con_margen():
    """Medido en C3 (test_puerta_herramientas.py, desglose_prefill): los
    prompts del agente (system + 3-4 esquemas del top-K + history[-6:] +
    mensaje) rondan 800-1100 tokens. agent_num_ctx no necesita el mismo
    tamaño que el chat: el historial que usa está acotado."""
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()["ollama"]
    assert cfg["agent_num_ctx"] >= 1100 * 1.3  # medido + margen


def test_keep_alive_explicito_y_no_trivial():
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()["ollama"]
    assert cfg.get("keep_alive"), "keep_alive debe estar seteado explícitamente"


def test_un_solo_modelo_residente_para_chat_y_agente():
    """agent_model y model deben ser el mismo: si difirieran, Ollama tendría
    que mantener DOS modelos de 3B cargados (o desalojar uno para el otro en
    cada cambio de ruta), justo lo que 'un solo modelo residente' pide evitar."""
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()["ollama"]
    assert cfg["agent_model"] == cfg["model"]


if __name__ == "__main__":
    test_default_config()
    test_config_caching()
    test_reload_config()
    test_config_has_required_keys()
    print("OK: Todos los tests de configuracion pasaron.")
