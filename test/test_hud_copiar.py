"""H3 — Seleccionar y copiar la conversación del HUD (Qt Quick).

Cubre tres cosas que el usuario pidió y que antes no existían:

1. Seleccionar con el ratón el cuerpo de cada turno (`MarkdownBody.qml` hacía
   el render con `Text`, que en QML NO admite selección).
2. Botón "copiar" por turno (`Turn.qml`).
3. Botón "copiar todo" en la cabecera de la consola (`Conversation.qml` +
   `ConversationModel.texto_completo()`), que arma el texto plano.

Los tests NO se limitan a mirar el .qml: crean los componentes de verdad,
pulsan el botón y leen el portapapeles real del sistema (bajo `offscreen` Qt
lo mantiene en el proceso y se puede leer), así que un botón que deje de
copiar rompe el test.
"""
import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtQuick")

from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject  # noqa: E402
from PySide6.QtGui import QClipboard, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from jarvis_local.ui.hud.conversation_model import (  # noqa: E402
    ConversationModel,
    conversacion_a_texto,
)

_RAIZ = pathlib.Path(__file__).resolve().parents[1]
_QML = _RAIZ / "jarvis_local" / "ui" / "hud" / "qml"

_app = QGuiApplication.instance() or QGuiApplication([])

# Qt destruye el objeto recién creado si el QQmlComponent que lo parió se
# recolecta antes: hay que retener motor y componente mientras se usa.
_RETENIDOS: list = []


def _cargar(nombre: str, props: dict | None = None):
    motor = QQmlEngine()
    motor.addImportPath(str(_QML))
    comp = QQmlComponent(motor)
    comp.loadUrl(_QML.joinpath(nombre).as_uri())
    if comp.isError():
        raise AssertionError("error QML: "
                             + " | ".join(e.toString() for e in comp.errors()))
    obj = comp.createWithInitialProperties(props or {})
    _app.processEvents()
    _RETENIDOS.extend([motor, comp, obj])
    return obj


def _portapapeles() -> str:
    return QGuiApplication.clipboard().text(QClipboard.Mode.Clipboard)


def _vaciar_portapapeles() -> None:
    QGuiApplication.clipboard().setText("", QClipboard.Mode.Clipboard)


# ── serialización a texto plano (puro, sin Qt) ────────────────────────────
def test_conversacion_a_texto_etiqueta_canal_y_omite_turnos_vacios():
    """Formato `[hh:mm:ss] CANAL ❯ cuerpo`; un turno sin texto no deja rastro.

    Importa el caso del turno de JARVIS recién abierto (streaming, aún sin
    token): sin este filtro, "copiar todo" pegaba líneas en blanco.
    """
    turnos = [
        {"channel": "user", "text": "hola", "ts": "12:00:00"},
        {"channel": "jarvis", "text": "   ", "ts": "12:00:01"},
        {"channel": "jarvis", "text": "buenas", "ts": "12:00:02"},
    ]
    assert conversacion_a_texto(turnos) == (
        "[12:00:00] USER ❯ hola\n[12:00:02] JARVIS ❯ buenas"
    )


def test_conversacion_a_texto_sin_turnos_es_vacio():
    assert conversacion_a_texto([]) == ""
    # turno sin marca de tiempo: se copia igual, sin el prefijo
    assert conversacion_a_texto([{"channel": "user", "text": "hola"}]) == "USER ❯ hola"


# ── el modelo expone la conversión ────────────────────────────────────────
def test_modelo_expone_texto_completo():
    cm = ConversationModel()
    assert cm.texto_completo() == ""
    cm.add_user("hola")
    cm.begin_assistant()
    cm.append_token("res")
    cm.append_token("puesta")
    cm.end_assistant("", "10 ms", "chat")
    texto = cm.texto_completo()
    assert "USER ❯ hola" in texto
    assert "JARVIS ❯ respuesta" in texto
    # durante el streaming (turno aún vacío) no se cuela ninguna línea en blanco
    lineas = texto.splitlines()
    assert [x for x in lineas if x.strip()] == lineas


# ── QML: selección con el ratón y botones ─────────────────────────────────
def test_el_cuerpo_del_turno_se_selecciona_con_el_raton():
    """Regresión: `Text` no admite selección; sólo `TextEdit`/`TextInput`.

    Si alguien vuelve a `Text` por recuperar el borde óptico (`style`), el
    usuario pierde la selección sin que nada más del HUD lo delate.
    """
    mdb = _cargar("MarkdownBody.qml", {"raw": "respuesta **con** markdown"})
    repeater = next(o for o in mdb.findChildren(QQuickItem)
                    if o.metaObject().className() == "QQuickRepeater")
    seg = QMetaObject.invokeMethod(repeater, "itemAt",
                                   Q_RETURN_ARG("QQuickItem*"), Q_ARG("int", 0))
    assert seg is not None, "el Repeater no creó ningún segmento"

    editores = [o for o in seg.findChildren(QQuickItem)
                if "QQuickTextEdit" in o.metaObject().className()]
    prosa = next(o for o in editores if o.property("readOnly"))
    assert prosa.property("selectByMouse") is True, \
        "el cuerpo del turno no se puede seleccionar con el ratón"
    assert prosa.property("persistentSelection") is True
    assert prosa.property("cursorVisible") is False
    assert "markdown" in prosa.property("text")


def test_boton_copiar_turno_pone_el_mensaje_en_el_portapapeles():
    _vaciar_portapapeles()
    turn = _cargar("Turn.qml", {"body": "respuesta **con** markdown"})

    boton = turn.findChild(QQuickItem, "copiarTurno")
    assert boton is not None, "Turn.qml no expone el botón de copiar"
    assert boton.property("visible") is True

    assert QMetaObject.invokeMethod(turn, "copiar") is True
    _app.processEvents()
    # se copia el mensaje tal cual (markdown incluido), sin rótulo ni hora
    assert _portapapeles() == "respuesta **con** markdown"


def test_boton_copiar_no_aparece_en_turno_sin_cuerpo():
    """Un turno vacío no ofrece "copiar": no tendría sentido."""
    turn = _cargar("Turn.qml", {"body": ""})
    boton = turn.findChild(QQuickItem, "copiarTurno")
    assert boton is not None
    assert boton.property("visible") is False


def test_copiar_toda_la_conversacion_desde_la_cabecera():
    """Pulso el botón real de la cabecera de la consola y leo el portapapeles."""
    from jarvis_local.ui.hud.app import create_engine
    from jarvis_local.ui.hud.viewmodel import ViewModel

    _vaciar_portapapeles()
    motor = create_engine(_app, ViewModel())
    try:
        win = motor.rootObjects()[0]
        rt = motor._runtime        # noqa: SLF001
        rt.conversation.add_user("hola")
        rt.conversation.begin_assistant()
        rt.conversation.append_token("buenas")
        rt.conversation.end_assistant("", "10 ms", "chat")
        _app.processEvents()

        boton = win.findChild(QQuickItem, "copiarConversacion")
        assert boton is not None, "la cabecera no tiene botón de copiar todo"
        cabecera = boton.parent()      # la función `copiarTodo` vive en el header
        assert QMetaObject.invokeMethod(cabecera, "copiarTodo") is True
        _app.processEvents()

        copiado = _portapapeles()
        assert copiado == rt.conversation.texto_completo()
        assert "USER ❯ hola" in copiado
        assert "JARVIS ❯ buenas" in copiado
    finally:
        motor._runtime.shutdown()      # noqa: SLF001
        motor.deleteLater()
