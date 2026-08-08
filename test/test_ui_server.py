"""
Tests básicos para la interfaz web.
Verifican que el módulo se importa correctamente.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_server_import():
    """Verifica que el módulo de servidor se puede importar."""
    import importlib
    spec = importlib.util.find_spec("jarvis_local.ui.server")
    assert spec is not None


def test_server_has_main():
    """Verifica que el módulo tiene función main."""
    from jarvis_local.ui import server
    assert hasattr(server, 'main')


def test_server_port_defined():
    """Verifica que el puerto está definido."""
    from jarvis_local.ui import server
    assert hasattr(server, 'PORT')
    assert isinstance(server.PORT, int)


def test_server_auth_token():
    """Verifica que el token de autenticación existe."""
    from jarvis_local.ui import server
    assert hasattr(server, '_AUTH_TOKEN')
    assert isinstance(server._AUTH_TOKEN, str)
    assert len(server._AUTH_TOKEN) > 0


if __name__ == "__main__":
    test_server_import()
    test_server_has_main()
    test_server_port_defined()
    test_server_auth_token()
    print("OK: Todos los tests de server pasaron.")
