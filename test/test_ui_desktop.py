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


def test_mic_available_returns_bool():
    """_mic_available() nunca debe fallar ni devolver un tipo raro, aunque
    no haya microfono conectado."""
    from jarvis_local.ui.desktop import _mic_available
    assert isinstance(_mic_available(), bool)


def test_read_cpu_mem_shape():
    """_read_cpu_mem() debe devolver (float, float) o (None, None) --
    nunca datos inventados si psutil no esta disponible."""
    from jarvis_local.ui.desktop import _read_cpu_mem
    cpu, mem = _read_cpu_mem()
    assert (cpu is None and mem is None) or (
        isinstance(cpu, (int, float)) and isinstance(mem, (int, float)))
    if cpu is not None:
        assert 0 <= cpu <= 100
        assert 0 <= mem <= 100


def test_count_tools_matches_registry():
    """La franja de estado debe mostrar la cantidad real de herramientas
    registradas, no un numero inventado."""
    from jarvis_local.agent.registry import TOOLS
    from jarvis_local.ui.desktop import _count_tools
    assert _count_tools() == len(TOOLS)
    assert _count_tools() > 0


def test_state_color_has_error_state():
    """El estado de ALERTA debe existir en el mapa de colores del nucleo
    (antes un error no cambiaba nada visualmente)."""
    import inspect

    from jarvis_local.ui import desktop
    src = inspect.getsource(desktop.JarvisDesktop._state_color)
    assert '"error"' in src


if __name__ == "__main__":
    test_desktop_import()
    test_desktop_has_main()
    test_desktop_colors_defined()
    test_mic_available_returns_bool()
    test_read_cpu_mem_shape()
    test_count_tools_matches_registry()
    test_state_color_has_error_state()
    print("OK: Todos los tests de desktop pasaron.")
