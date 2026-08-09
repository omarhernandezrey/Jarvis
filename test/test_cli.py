"""
Tests de CLI - Funciones extraídas de main()
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

from jarvis_local.cli import handle_apps, handle_archivos, handle_terminal, init_jarvis, parse_args


def test_parse_args_simple():
    """Verifica que parse_args divide correctamente."""
    result = parse_args("listar /home")
    assert result == ["listar", "/home"]


def test_parse_args_with_quotes():
    """Verifica que parse_args maneja comillas."""
    result = parse_args('crear-archivo test.txt "hola mundo"')
    assert result == ["crear-archivo", "test.txt", "hola mundo"]


def test_handle_archivos_no_args(capsys):
    """Verifica que handle_archivos muestra uso sin argumentos."""
    handle_archivos([])
    captured = capsys.readouterr()
    assert "Uso" in captured.out


def test_handle_archivos_listar(capsys):
    """Verifica que handle_archivos listar funciona."""
    with patch("jarvis_local.cli.list_files") as mock:
        plan = MagicMock()
        plan.__str__ = lambda s: "archivo1.txt\narchivo2.txt"
        mock.return_value = plan
        handle_archivos(["listar", "."])
        captured = capsys.readouterr()
        assert "archivo" in captured.out.lower()


def test_handle_apps_no_args(capsys):
    """Verifica que handle_apps muestra uso sin argumentos."""
    handle_apps([])
    captured = capsys.readouterr()
    assert "Uso" in captured.out


def test_handle_apps_listar(capsys):
    """Verifica que handle_apps listar funciona."""
    with patch("jarvis_local.cli.list_apps") as mock:
        plan = MagicMock()
        plan.__str__ = lambda s: "chrome: instalado\nvscode: instalado"
        mock.return_value = plan
        handle_apps(["listar"])
        captured = capsys.readouterr()
        assert "chrome" in captured.out.lower() or "instalado" in captured.out.lower()


def test_handle_terminal_no_args(capsys):
    """Verifica que handle_terminal muestra uso sin argumentos."""
    handle_terminal([])
    captured = capsys.readouterr()
    assert "Uso" in captured.out


def test_handle_terminal_plan(capsys):
    """Verifica que handle_terminal plan funciona."""
    with patch("jarvis_local.cli.plan_command") as mock:
        mock.return_value = MagicMock(status=MagicMock(value="planned"), __str__=lambda s: "Plan creado")
        handle_terminal(["plan", "ls -la"])
        captured = capsys.readouterr()
        assert "Plan" in captured.out or "plan" in captured.out.lower()


if __name__ == "__main__":
    test_parse_args_simple()
    test_parse_args_with_quotes()
    test_handle_archivos_no_args()
    test_handle_archivos_listar()
    test_handle_apps_no_args()
    test_handle_apps_listar()
    test_handle_terminal_no_args()
    test_handle_terminal_plan()
    print("OK: Todos los tests de CLI pasaron.")
