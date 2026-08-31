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

    Rectangle {
        id: bg
        width: parent.width
        height: body.implicitHeight + Design.sp(6)
        color: Qt.rgba(1, 1, 1, 0.03)
        radius: Design.radiusHud
        border.width: 1
        border.color: Design.hairline
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
                resetTimer.restart()
            }
        }
    }
    Timer { id: resetTimer; interval: 1400; onTriggered: copyState.copied = false }
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
