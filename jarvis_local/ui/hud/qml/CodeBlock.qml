import QtQuick
import "."
import "hl.js" as HL

// Bloque de código: mono, fondo apenas más claro que el panel, resaltado
// ligero y botón de copiar. `lang` es solo informativo (etiqueta en la regla).
Item {
    id: block
    property string code: ""
    property string lang: ""
    property real contentWidth: 480

    implicitWidth: contentWidth
    implicitHeight: bg.height

    property point _c: Qt.point(0, 0)
    function _remap() { _c = mapToItem(null, width / 2, height / 2) }
    onWidthChanged: _remap()
    onHeightChanged: _remap()
    onXChanged: _remap()
    onYChanged: _remap()
    Component.onCompleted: _remap()
    Connections { target: Design; function onCorePosChanged() { block._remap() } }

    // superficie que RECIBE luz: gradiente de un solo lado orientado al núcleo
    Rectangle {
        id: bg
        width: parent.width
        height: body.implicitHeight + Design.sp(6)
        radius: Design.radiusHud
        border.width: 1
        border.color: Design.litHairline(block._c.x, block._c.y)

        readonly property color _base: Qt.rgba(1, 1, 1, 0.03)
        readonly property real _dx: Design.corePos.x - block._c.x
        readonly property real _dy: Design.corePos.y - block._c.y
        readonly property bool _h: Math.abs(_dx) >= Math.abs(_dy)
        readonly property bool _litAt0: _h ? _dx < 0 : _dy < 0
        readonly property color _lit: Design.mix(_base,
            Qt.rgba(Design.coreTint.r, Design.coreTint.g, Design.coreTint.b, 0.07),
            Math.min(1.0, Design.lightLevel(block._c.x, block._c.y)))
        gradient: Gradient {
            orientation: bg._h ? Gradient.Horizontal : Gradient.Vertical
            GradientStop { position: 0.0; color: bg._litAt0 ? bg._lit : bg._base }
            GradientStop { position: 1.0; color: bg._litAt0 ? bg._base : bg._lit }
        }
    }

    Text {
        id: langLabel
        anchors { left: bg.left; leftMargin: Design.sp(2); top: bg.top; topMargin: 2 }
        text: block.lang
        color: Design.textMeta
        font.family: Design.fontMono
        font.pixelSize: Design.fsMeta
    }
    Text {
        id: copyBtn
        anchors { right: bg.right; rightMargin: Design.sp(2); top: bg.top; topMargin: 2 }
        text: copyState.copied ? "copiado" : "copiar"
        color: hover.hovered ? Design.cyan : Design.textMeta
        font.family: Design.fontMono
        font.pixelSize: Design.fsMeta
        QtObject { id: copyState; property bool copied: false }
        HoverHandler { id: hover }
        TapHandler {
            onTapped: {
                clip.text = block.code
                clip.selectAll()
                clip.copy()
                clip.deselect()
                copyState.copied = true
                resetAnim.restart()
            }
        }
        // sin Timer suelto: una animación de una pasada (addendum §7)
        SequentialAnimation {
            id: resetAnim
            PauseAnimation { duration: Design.durHold }
            ScriptAction { script: copyState.copied = false }
        }
    }
    TextEdit { id: clip; visible: false }

    Text {
        id: body
        anchors {
            left: bg.left; right: bg.right; top: bg.top
            leftMargin: Design.sp(3); rightMargin: Design.sp(3)
            topMargin: Design.sp(4)
        }
        textFormat: Text.RichText
        font.family: Design.fontMono
        font.pixelSize: Design.fsSmall
        color: Design.textPrimary
        lineHeight: 1.45
        wrapMode: Text.NoWrap
        text: "<pre style='margin:0'>" + HL.highlight(block.code, {
            kw: "" + Design.cyan, str: "" + Design.ok, com: "" + Design.textMeta,
            num: "" + Design.warn, txt: "" + Design.textPrimary
        }) + "</pre>"
    }
}
