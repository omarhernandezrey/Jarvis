import QtQuick
import QtQuick.Controls.Basic
import "."

// Consola conversacional. `Conversation` es el ConversationModel (contexto).
// Autoscroll anclado al final que se libera al desplazarse hacia arriba y
// ofrece volver al final.
Item {
    id: root
    property real measure: 560

    ListView {
        id: list
        anchors.fill: parent
        model: Conversation
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

        onContentYChanged: {
            // si el usuario sube, se libera el anclaje; al volver al fondo, engancha
            if (!movingVertically && !flickingVertically)
                return
            stick = atYEnd
        }
        onMovementEnded: stick = atYEnd

        // barra sutil
        ScrollBar.vertical: ScrollBar { active: true; policy: ScrollBar.AsNeeded }
    }

    // estado vacío: identidad a 40 px, callada. Se desvanece con el primer turno.
    Column {
        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
        spacing: Design.sp(3)
        opacity: list.count === 0 ? 1.0 : 0.0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: Design.durSlow } }
        Text {
            text: "JARVIS"
            color: Design.textMeta
            font.family: Design.fontSans
            font.pixelSize: Design.fsDisplay
        }
        Text {
            text: "consola conversacional — escribe abajo o mantén el micrófono"
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsSmall
        }
    }

    // píldora "volver al final"
    Rectangle {
        visible: !list.stick && list.contentHeight > list.height
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter
                  bottomMargin: Design.sp(3) }
        width: backText.implicitWidth + Design.sp(6)
        height: backText.implicitHeight + Design.sp(3)
        radius: height / 2
        color: Design.surfaceColor
        border.width: 1
        border.color: Design.hairline
        Text {
            id: backText
            anchors.centerIn: parent
            text: "volver al final ↓"
            color: Design.textSecondary
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
        }
        TapHandler {
            onTapped: { list.stick = true; list.positionViewAtEnd() }
        }
    }
}
