import QtQuick
import QtQuick.Controls.Basic
import "."

// Consola conversacional. `Conversation` es el ConversationModel (contexto).
// Autoscroll anclado al final que se libera al desplazarse hacia arriba y
// ofrece volver al final.
Item {
    id: root
    property real measure: 560
    // ¿hay al menos un turno? (para el scrim localizado de Main en fondo transp.)
    readonly property bool hasContent: list.count > 0

    // ── CABECERA DE CONSOLA ───────────────────────────────────────────────
    // Barra técnica, sin fondo: rótulo en mayúsculas + contador de líneas +
    // reloj de sesión, una regla punteada debajo, punto que late con el núcleo.
    Item {
        id: header
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Design.sp(6)
        visible: root.hasContent
        opacity: visible ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: Design.durSlow } }

        Row {
            anchors { left: parent.left; leftMargin: Design.sp(0.5)
                      verticalCenter: parent.verticalCenter }
            spacing: Design.sp(1.5)
            Rectangle {   // testigo de canal
                width: 6; height: 6
                anchors.verticalCenter: parent.verticalCenter
                color: Design.ok
                opacity: Math.min(1.0, 0.35 + 0.35 * Design.breath()
                                  + 0.5 * Math.min(1.0, Design.coreEnergy * 1.6))
                scale: 0.85 + 0.2 * Design.breath()
            }
            Text {
                text: "JARVIS // CONSOLA"
                color: Design.consoleHeader
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                font.letterSpacing: Design.trkLabel
                style: Text.Outline; styleColor: Design.textEdge
            }
            Text {
                text: "· " + list.count + " LÍN"
                color: Design.stateWash(Design.chatMeta, 0.4)
                font.family: Design.fontMono
                font.pixelSize: Design.fsMicro
                font.letterSpacing: 0.8
                opacity: 0.7
                style: Text.Outline; styleColor: Design.textEdge
            }
        }
        Text {
            id: clock
            anchors { right: parent.right; rightMargin: Design.sp(0.5)
                      verticalCenter: parent.verticalCenter }
            color: Design.chatMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMicro
            font.letterSpacing: 0.8
            style: Text.Outline; styleColor: Design.textEdge
            text: "T " + Qt.formatDateTime(new Date(), "hh:mm:ss")
            Timer {
                interval: 1000; repeat: true
                running: header.visible
                onTriggered: clock.text = "T " + Qt.formatDateTime(new Date(), "hh:mm:ss")
            }
        }
        // regla punteada bajo la cabecera
        Row {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            spacing: 4
            Repeater {
                model: Math.max(1, Math.floor(header.width / 7))
                delegate: Rectangle {
                    width: 3; height: 1
                    color: Design.stateWash(Design.consoleHeader, 0.5)
                    opacity: 0.18 + 0.14 * Design.breath()
                }
            }
        }
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                  top: root.hasContent ? header.bottom : parent.top
                  topMargin: root.hasContent ? Design.sp(2) : 0 }
        model: ConversationModel        // context property (ver app.py bind_context)
        clip: true
        spacing: Design.sp(4)
        cacheBuffer: 800
        boundsBehavior: Flickable.StopAtBounds

        property bool stick: true

        delegate: Turn {
            required property var model
            width: ListView.view.width - Design.sp(2)
            channel: model.channel
            body: model.body
            timestamp: model.timestamp
            meta: model.meta
            streaming: model.streaming
            kind: model.kind
            measure: Math.min(root.measure, width - Design.sp(20))
            onImplicitHeightChanged: if (list.stick) list.positionViewAtEnd()
        }

        onCountChanged: if (stick) Qt.callLater(positionViewAtEnd)

        // un turno nuevo no aparece de golpe: sube su opacidad — parte de la
        // misma reacción del sistema (misma curva que el cross-fade del
        // núcleo), no un pop.
        add: Transition {
            NumberAnimation { property: "opacity"; from: 0.0; to: 1.0
                duration: Design.durBase; easing.type: Design.easeType
                easing.bezierCurve: Design.easeCurve }
        }
        displaced: Transition {
            NumberAnimation { property: "y"; duration: Design.durBase
                easing.type: Design.easeType; easing.bezierCurve: Design.easeCurve }
        }

        onContentYChanged: {
            // si el usuario sube, se libera el anclaje; al volver al fondo, engancha
            if (!movingVertically && !flickingVertically)
                return
            stick = atYEnd
        }
        onMovementEnded: stick = atYEnd

        // barra sutil: sólo visible al desplazar/arrastrar
        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            active: list.movingVertically || list.draggingVertically || pressed
            contentItem: Rectangle {
                implicitWidth: 3
                radius: 1.5
                color: Design.hairline
                opacity: parent.active ? 0.9 : 0.0
                Behavior on opacity { NumberAnimation { duration: Design.durFast } }
            }
        }
    }

    // estado vacío: identidad a 40 px, callada. Se desvanece con el primer turno.
    Column {
        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
        spacing: Design.sp(3)
        opacity: list.count === 0 ? 1.0 : 0.0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: Design.durSlow } }
        Text {
            text: "JARVIS ❯ _"
            color: Design.chatJarvis
            font.family: Design.fontMono
            font.pixelSize: Design.fsLarge
            font.letterSpacing: 2
            style: Text.Outline; styleColor: Design.textEdge
        }
        Text {
            text: "consola conversacional — escribe abajo o mantén el micrófono"
            color: Design.chatMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsSmall
            style: Text.Outline; styleColor: Design.textEdge
        }
    }

    // "volver al final" — sin fondo: sólo el texto con contorno y un marco fino
    Item {
        visible: !list.stick && list.contentHeight > list.height
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter
                  bottomMargin: Design.sp(3) }
        width: backText.implicitWidth + Design.sp(5)
        height: backText.implicitHeight + Design.sp(2.5)
        HoloFrame { anchors.fill: parent; accent: Design.chatPrompt; bracketLen: 5 }
        Text {
            id: backText
            anchors.centerIn: parent
            text: "▼ VOLVER AL FINAL"
            color: Design.chatPrompt
            font.family: Design.fontMono
            font.pixelSize: Design.fsMicro
            font.letterSpacing: 1.0
            style: Text.Outline; styleColor: Design.textEdge
        }
        TapHandler {
            onTapped: { list.stick = true; list.positionViewAtEnd() }
        }
    }
}
