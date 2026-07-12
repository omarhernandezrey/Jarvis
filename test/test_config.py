"""
Tests de configuracion - Fase 1
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import jarvis_local.config as cfg_module


def test_default_config():
    cfg_module._config_cache = None
    cfg = cfg_module.get_config()
    assert cfg["ollama"]["host"] == "http://localhost:11434"
    assert cfg["ollama"]["model"] == "qwen2.5:3b"
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


if __name__ == "__main__":
    test_default_config()
    test_config_caching()
    test_reload_config()
    test_config_has_required_keys()
    print("OK: Todos los tests de configuracion pasaron.")
