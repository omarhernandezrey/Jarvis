import QtQuick
import "."

// Un turno de la consola: canaleta izquierda (etiqueta de canal + regla
// vertical alineada al primer renglón) y cuerpo a la derecha. Sin burbujas.
Item {
    id: turn
    property string channel: "user"
    property string body: ""
    property string timestamp: ""
    property string meta: ""
    property bool streaming: false
    property string kind: "chat"
    property real measure: 520

    readonly property color _accent: kind === "error" ? Design.alert
        : channel === "user" ? Design.textSecondary : Design.cyan

    implicitHeight: col.implicitHeight + Design.sp(4)

    // canaleta: etiqueta + regla vertical
    Text {
        id: chLabel
        x: 0
        y: 0
        width: Design.sp(16)
        text: channel === "user" ? "USER" : "JARVIS"
        color: turn._accent
        font.family: Design.fontMono
        font.pixelSize: Design.fsMeta
        font.bold: true
        font.letterSpacing: 0.8
        style: Text.Outline; styleColor: Design.textEdge
    }
    Rectangle {
        x: Design.sp(16)
        y: 2
        width: 1
        height: turn.implicitHeight - Design.sp(4)
        color: turn._accent
        opacity: kind === "error" ? 0.9 : 0.6
    }

    Column {
        id: col
        x: Design.sp(19)
        width: turn.measure
        spacing: Design.sp(1)

        Row {
            spacing: Design.sp(2)
            // mientras se genera y aún no hay texto: aviso de que está trabajando
            // (el modelo en CPU puede tardar); desaparece al llegar el 1er token
            Text {
                visible: turn.streaming && !turn.body.length
                text: "procesando… (modelo en CPU)"
                color: Design.textMeta
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                style: Text.Outline; styleColor: Design.textEdge
            }
            MarkdownBody {
                id: md
                visible: turn.body.length > 0
                raw: turn.body
                measure: turn.measure
            }
            // cursor de bloque mientras se genera; al terminar, desaparece
            Text {
                visible: turn.streaming
                text: "▌"
                color: Design.cyan
                font.family: Design.fontMono
                font.pixelSize: Design.fsBody
                // latido del cursor: con easing (InOutSine), no lineal — un
                // parpadeo lineal se lee como máquina.
                SequentialAnimation on opacity {
                    running: turn.streaming
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.18; duration: Design.blinkHalf
                        easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: Design.blinkHalf
                        easing.type: Easing.InOutSine }
                }
            }
        }

        // metadatos: color terciario, tamaño 12, sin competir con el mensaje
        Text {
            visible: !turn.streaming && (turn.timestamp.length || turn.meta.length)
            text: turn.timestamp + (turn.meta.length ? "   " + turn.meta : "")
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            style: Text.Outline; styleColor: Design.textEdge
        }
    }
}
