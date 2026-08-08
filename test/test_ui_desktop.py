"""
Tests básicos para la interfaz de escritorio.
Verifican que el módulo se importa correctamente.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_desktop_import():
    """Verifica que el módulo de escritorio se puede importar."""
    import importlib
    spec = importlib.util.find_spec("jarvis_local.ui.desktop")
    assert spec is not None


def test_desktop_has_main():
    """Verifica que el módulo tiene función main."""
    from jarvis_local.ui import desktop
    assert hasattr(desktop, 'main')


def test_desktop_colors_defined():
    """Verifica que la paleta de colores está definida."""
    from jarvis_local.ui import desktop
    assert hasattr(desktop, 'C')
    assert isinstance(desktop.C, dict)
    assert "bg" in desktop.C
    assert "primary" in desktop.C


if __name__ == "__main__":
    test_desktop_import()
    test_desktop_has_main()
    test_desktop_colors_defined()
    print("OK: Todos los tests de desktop pasaron.")
