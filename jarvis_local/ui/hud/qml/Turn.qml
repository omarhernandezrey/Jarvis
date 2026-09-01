import QtQuick
import "."

// Un turno de la consola estilo TERMINAL: prompt de canal a la izquierda
// (`USER ❯` / `JARVIS ❯`), regla vertical y cuerpo monoespaciado con colores
// ANSI vivos. Sin burbujas.
Item {
    id: turn
    property string channel: "user"
    property string body: ""
    property string timestamp: ""
    property string meta: ""
    property bool streaming: false
    property string kind: "chat"
    property real measure: 520

    // color del canal: rojo error · verde brillante usuario · cian JARVIS
    readonly property color _accent: kind === "error" ? Design.alert
        : channel === "user" ? Design.chatUser : Design.chatPrompt
    // color del cuerpo del mensaje
    readonly property color _bodyColor: kind === "error" ? Design.alert
        : channel === "user" ? Design.chatUser : Design.chatJarvis

    implicitHeight: col.implicitHeight + Design.sp(4)

    // prompt del canal
    Text {
        id: chLabel
        x: 0
        y: 0
        width: Design.sp(17)
        text: (channel === "user" ? "USER" : "JARVIS") + " ❯"
        color: turn._accent
        font.family: Design.fontMono
        font.pixelSize: Design.fsMeta
        font.bold: true
        font.letterSpacing: 0.6
        style: Text.Outline; styleColor: Design.textEdge
    }
    Rectangle {
        x: Design.sp(17)
        y: 2
        width: 1
        height: turn.implicitHeight - Design.sp(4)
        color: turn._accent
        opacity: kind === "error" ? 0.95 : 0.7
    }

    Column {
        id: col
        x: Design.sp(20)
        width: turn.measure
        spacing: Design.sp(1)

        Row {
            spacing: Design.sp(2)
            // mientras se genera y aún no hay texto: aviso de que está trabajando
            Text {
                visible: turn.streaming && !turn.body.length
                text: "procesando… (modelo en CPU)"
                color: Design.warn
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                style: Text.Outline; styleColor: Design.textEdge
            }
            MarkdownBody {
                id: md
                visible: turn.body.length > 0
                raw: turn.body
                measure: turn.measure
                textColor: turn._bodyColor
            }
            // cursor de bloque estilo terminal
            Text {
                visible: turn.streaming
                text: "▌"
                color: Design.chatUser
                font.family: Design.fontMono
                font.pixelSize: Design.fsBody
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

        // metadatos: verde apagado, sin competir con el mensaje
        Text {
            visible: !turn.streaming && (turn.timestamp.length || turn.meta.length)
            text: turn.timestamp + (turn.meta.length ? "   " + turn.meta : "")
            color: Design.chatMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            style: Text.Outline; styleColor: Design.textEdge
        }
    }
}
