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


@pytest.fixture(scope="module")
def motor():
    """Motor QML para crear componentes sueltos (Turn.qml, MarkdownBody.qml).

    Se apaga DENTRO de la sesión, no al salir del intérprete: si los objetos
    Qt siguen vivos cuando Python se está cerrando, PySide6 los destruye en
    orden arbitrario y se despide con **SIGSEGV (exit 139)**. Así la CI queda
    en rojo con todos los tests en verde -- exactamente lo que pasó.
    """
    m = QQmlEngine()
    m.addImportPath(str(_QML))
    yield m
    m.collectGarbage()
    m.deleteLater()
    _app.processEvents()


@pytest.fixture
def cargar(motor):
    """Crea un componente QML suelto y lo destruye al acabar el test.

    Se retiene el `QQmlComponent` mientras el objeto vive: Qt lo crea como
    hijo del componente, y si éste se recolecta antes, el objeto desaparece
    (`RuntimeError: Internal C++ object ... already deleted`).
    """
    creados = []

    def _cargar(nombre: str, props: dict | None = None):
        comp = QQmlComponent(motor)
        comp.loadUrl(_QML.joinpath(nombre).as_uri())
        if comp.isError():
            comp.deleteLater()
            raise AssertionError("error QML: "
                                 + " | ".join(e.toString() for e in comp.errors()))
        obj = comp.createWithInitialProperties(props or {})
        if obj is None:
            comp.deleteLater()
            raise AssertionError(f"{nombre} no se pudo instanciar")
        creados.append((obj, comp))
        _app.processEvents()
        return obj

    yield _cargar

    for obj, comp in creados:
        obj.deleteLater()
        comp.deleteLater()
    _app.processEvents()


@pytest.fixture(autouse=True)
def portapapeles_limpio():
    """Aísla el portapapeles del sistema entre tests... y lo vacía al salir.

    Dejar datos propios en el portapapeles hasta el final del proceso es una
    de las formas de que Qt se despida mal al apagarse: `QClipboard` es propiedad
    de `QGuiApplication`, y el intérprete no garantiza el orden de destrucción.
    """
    _vaciar_portapapeles()
    yield
    _vaciar_portapapeles()
    QGuiApplication.clipboard().clear(QClipboard.Mode.Clipboard)
    _app.processEvents()


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
def test_el_cuerpo_del_turno_se_selecciona_con_el_raton(cargar):
    """Regresión: `Text` no admite selección; sólo `TextEdit`/`TextInput`.

    Si alguien vuelve a `Text` por recuperar el borde óptico (`style`), el
    usuario pierde la selección sin que nada más del HUD lo delate.
    """
    mdb = cargar("MarkdownBody.qml", {"raw": "respuesta **con** markdown"})
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


def test_boton_copiar_turno_pone_el_mensaje_en_el_portapapeles(cargar):
    _vaciar_portapapeles()
    turn = cargar("Turn.qml", {"body": "respuesta **con** markdown"})

    boton = turn.findChild(QQuickItem, "copiarTurno")
    assert boton is not None, "Turn.qml no expone el botón de copiar"
    assert boton.property("visible") is True

    assert QMetaObject.invokeMethod(turn, "copiar") is True
    _app.processEvents()
    # se copia el mensaje tal cual (markdown incluido), sin rótulo ni hora
    assert _portapapeles() == "respuesta **con** markdown"


def test_boton_copiar_no_aparece_en_turno_sin_cuerpo(cargar):
    """Un turno vacío no ofrece "copiar": no tendría sentido."""
    turn = cargar("Turn.qml", {"body": ""})
    boton = turn.findChild(QQuickItem, "copiarTurno")
    assert boton is not None
    assert boton.property("visible") is False


def test_copiar_toda_la_conversacion_desde_la_cabecera(motor):
    """Pulso el botón real de la cabecera de la consola y leo el portapapeles.

    Se carga `Conversation.qml` SUELTO (no la ventana entera): basta con
    exponerle su modelo y un `Vm` mínimo por contexto. Crear la ventana
    completa arrastra el runtime del HUD (hilos de métricas, shaders) y eso,
    al apagarse, es lo que hacía caer la CI con SIGSEGV.
    """
    modelo = ConversationModel()
    motor.rootContext().setContextProperty("ConversationModel", modelo)
    motor.rootContext().setContextProperty("Vm", {"metrics": {}})
    try:
        modelo.add_user("hola")
        modelo.begin_assistant()
        modelo.append_token("buenas")
        modelo.end_assistant("", "10 ms", "chat")

        consola = None
        comp = QQmlComponent(motor)
        comp.loadUrl(_QML.joinpath("Conversation.qml").as_uri())
        if comp.isError():
            raise AssertionError("error QML: "
                                 + " | ".join(e.toString() for e in comp.errors()))
        consola = comp.create()
        _app.processEvents()
        try:
            boton = consola.findChild(QQuickItem, "copiarConversacion")
            assert boton is not None, "la cabecera no tiene botón de copiar todo"
            cabecera = boton.parent()   # la función `copiarTodo` vive en el header
            assert QMetaObject.invokeMethod(cabecera, "copiarTodo") is True
            _app.processEvents()

            copiado = _portapapeles()
            assert copiado == modelo.texto_completo()
            assert "USER ❯ hola" in copiado
            assert "JARVIS ❯ buenas" in copiado
        finally:
            if consola is not None:
                consola.deleteLater()
            comp.deleteLater()
            _app.processEvents()
    finally:
        # el modelo se quita del contexto ANTES de que nadie lo destruya
        motor.rootContext().setContextProperty("ConversationModel", None)
        modelo.deleteLater()
        _app.processEvents()
