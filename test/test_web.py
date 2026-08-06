"""
Tests de herramientas web - Fase 4
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.tools.web import _is_safe_url, build_url


def test_build_url_http():
    """URL con http se mantiene."""
    assert build_url("http://example.com") == "http://example.com"


def test_build_url_https():
    """URL con https se mantiene."""
    assert build_url("https://example.com") == "https://example.com"


def test_build_url_sin_esquema():
    """URL sin esquema añade https."""
    assert build_url("example.com") == "https://example.com"


def test_build_url_nombre_sin_dominio():
    """Nombre sin dominio añade https://www..com."""
    assert build_url("google") == "https://www.google.com"


def test_build_url_con_espacios():
    """Nombre con espacios se procesa."""
    assert build_url("mi sitio") == "https://www.misitio.com"


def test_is_safe_url_http():
    """URL http es segura."""
    assert _is_safe_url("http://example.com") is True


def test_is_safe_url_https():
    """URL https es segura."""
    assert _is_safe_url("https://example.com") is True


def test_is_safe_url_javascript():
    """URL javascript no es segura."""
    assert _is_safe_url("javascript:alert(1)") is False


def test_is_safe_url_data():
    """URL data no es segura."""
    assert _is_safe_url("data:text/html,<h1>hola</h1>") is False


def test_is_safe_url_file():
    """URL file no es segura."""
    assert _is_safe_url("file:///etc/passwd") is False


def test_build_url_javascript_blocked():
    """URL javascript se bloquea y devuelve fallback."""
    url = build_url("javascript:alert(1)")
    assert url == "https://www.google.com"


def test_build_url_data_blocked():
    """URL data se bloquea y devuelve fallback."""
    url = build_url("data:text/html,<h1>hola</h1>")
    assert url == "https://www.google.com"


if __name__ == "__main__":
    test_build_url_http()
    test_build_url_https()
    test_build_url_sin_esquema()
    test_build_url_nombre_sin_dominio()
    test_build_url_con_espacios()
    test_is_safe_url_http()
    test_is_safe_url_https()
    test_is_safe_url_javascript()
    test_is_safe_url_data()
    test_is_safe_url_file()
    test_build_url_javascript_blocked()
    test_build_url_data_blocked()
    print("OK: Todos los tests de web pasaron.")
