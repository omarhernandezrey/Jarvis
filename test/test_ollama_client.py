"""
Tests de conexion a Ollama - Fase 1
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.ollama_client.client import OllamaClient


def test_client_creation():
    client = OllamaClient()
    assert client.host == "http://localhost:11434"
    assert client.timeout == 600


def test_client_custom_params():
    client = OllamaClient(host="http://localhost:9999", timeout=30)
    assert client.host == "http://localhost:9999"
    assert client.timeout == 30


def test_is_running():
    client = OllamaClient()
    running = client.is_running()
    if running:
        print("  [INFO] Ollama esta corriendo - test de conexion OK")
    else:
        print("  [INFO] Ollama NO esta corriendo - test omitido (esperado si no se ha iniciado)")
        return
    models = client.list_models()
    assert isinstance(models, list)


def test_list_models_requires_running():
    client = OllamaClient()
    if not client.is_running():
        print("  [INFO] Ollama no esta corriendo - test de modelos omitido")
        return
    models = client.list_models()
    assert isinstance(models, list)
    print(f"  Modelos instalados: {len(models)}")


if __name__ == "__main__":
    test_client_creation()
    test_client_custom_params()
    test_is_running()
    test_list_models_requires_running()
    print("OK: Tests de cliente Ollama completados.")
