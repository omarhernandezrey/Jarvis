import QtQuick
import "."

// Un dato del HUD como WIDGET moderno: vidrio oscuro translúcido, esquina
// redondeada, barra de acento a la izquierda en el color de firma del dato,
// etiqueta arriba (susurra) + valor abajo (domina, en el color vivo). El
// orbe se queda en azul/cian; aquí manda el color.
Item {
    id: cell
    property string label: ""
    property string value: ""
    property bool absent: false
    property color accent: Design.sky              // color de FIRMA (barra + borde)
    property color valueColor: accent              // color del VALOR (estado)
    property bool vertical: false      // banda superior vs. regla lateral
    // punto de presencia: su opacidad respira con Design.coreEnergy (dato real).
    property bool pulse: false

    readonly property color _accent: absent ? Design.textDisabled : accent
    readonly property color _value:  absent ? Design.textDisabled : valueColor

    implicitWidth: Math.max(labelText.implicitWidth, valueText.implicitWidth)
                   + Design.sp(vertical ? 6 : 9)
    implicitHeight: vertical ? Design.sp(13) : Design.sp(17)

    // ── superficie del widget ──────────────────────────────────────────────
    Rectangle {
        id: surface
        anchors.fill: parent
        radius: Design.widgetRadius
        color: Design.widgetFill
        border.width: 1
        border.color: cell.absent ? Design.widgetStroke
                                  : Design.widgetEdge(cell._accent)
        Behavior on border.color { ColorAnimation { duration: Design.durBase } }

        // brillo de vidrio en el borde superior
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right
                      leftMargin: parent.radius; rightMargin: parent.radius
                      topMargin: 1 }
            height: 1
            color: Qt.rgba(1, 1, 1, 0.10)
        }
    }

    // barra de acento a la izquierda — el color de firma del dato
    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom
                  topMargin: Design.sp(1); bottomMargin: Design.sp(1) }
        width: 2.5
        radius: 1.5
        color: cell._accent
        opacity: cell.absent ? 0.35 : 0.95
        Behavior on color { ColorAnimation { duration: Design.durBase } }
    }

    Column {
        anchors.left: parent.left
        anchors.leftMargin: Design.sp(2.5)
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        Text {
            id: labelText
            text: cell.label.toUpperCase()
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            font.weight: Design.wLabel
            font.letterSpacing: Design.trkLabel
            style: Text.Outline; styleColor: Design.textEdge
        }
        Row {
            spacing: Design.sp(1.5)
            Rectangle {
                visible: cell.pulse && !cell.absent
                width: 6; height: 6; radius: 3
                anchors.verticalCenter: valueText.verticalCenter
                color: cell._accent
                opacity: 0.4 + 0.6 * Math.min(1.0, 0.3 + Design.coreEnergy * 1.6)
            }
            Text {
                id: valueText
                text: cell.absent ? "—" : cell.value
                color: cell._value
                font.family: Design.fontMono
                font.pixelSize: cell.vertical ? Design.fsBody : Design.fsTitle
                font.weight: Design.wValue
                style: Text.Outline; styleColor: Design.textEdge
                Behavior on color { ColorAnimation { duration: Design.durBase } }
            }
        }
    }
}
