"""
Tests básicos para la interfaz web.
Verifican que el módulo se importa correctamente.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _html() -> str:
    """El HTML tal cual se sirve (la única diferencia es el token)."""
    from jarvis_local.ui import server
    return server.HTML


def _bloque_css(html: str, selector: str) -> str:
    """Devuelve el cuerpo `{...}` de la regla CSS para `selector`."""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", html, re.S)
    assert m is not None, f"no hay regla CSS para {selector!r}"
    return m.group(1)


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


# ── H3: seleccionar y copiar la conversación ──────────────────────────────
# Antes el `body` entero era `user-select: none`, así que no había forma de
# llevarse ni una palabra de lo que JARVIS respondía: ni arrastrando el ratón,
# ni con Ctrl+A, ni con botón derecho -> Copiar.

def test_la_pagina_no_bloquea_la_seleccion_entera():
    """Regresión: un `user-select: none` global deja la consola inútil."""
    html = _html()
    cuerpo = _bloque_css(html, "body")
    assert "user-select" not in cuerpo, \
        "`body` vuelve a bloquear la selección de texto en toda la página"
    assert re.search(r"\buser-select:\s*none", html) is not None, \
        "el cromo ya no se protege: arrastrar sobre el orbe deja rastro azul"


def test_la_conversacion_se_puede_seleccionar():
    html = _html()
    cuerpo = _bloque_css(html, ".chat-area, .chat-area .msg-bubble, "
                               ".chat-area .msg-time,\n  .chat-area .msg-avatar")
    assert "user-select: text" in cuerpo
    # y el cursor lo delata: sobre una burbuja el ratón es de texto, no de flecha
    assert "cursor: text" in _bloque_css(html, ".chat-area .msg-bubble")


def test_cada_mensaje_tiene_boton_de_copiar():
    html = _html()
    # el mensaje de bienvenida (HTML estático) y los que llegan por JS
    assert 'class="msg-copy"' in html
    assert "copiarTurno(" in html
    assert "actions.appendChild(copyBtn)" in html, \
        "los mensajes nuevos se crean sin su botón de copiar"


def test_hay_boton_de_copiar_toda_la_conversacion():
    html = _html()
    assert 'id="copyAllBtn"' in html
    assert "copiarConversacion()" in html
    # rol y hora en el texto copiado, como en el HUD ("USER ❯ ...")
    assert "TÚ" in html and "JARVIS" in html and "❯" in html


def test_el_portapapeles_tiene_fallback_sin_contexto_seguro():
    """En http://localhost no hay `navigator.clipboard`; si no hay fallback,
    el botón copiaría sólo en https."""
    html = _html()
    assert "navigator.clipboard" in html
    assert "execCommand('copy')" in html


if __name__ == "__main__":
    test_server_import()
    test_server_has_main()
    test_server_port_defined()
    test_server_auth_token()
    print("OK: Todos los tests de server pasaron.")
