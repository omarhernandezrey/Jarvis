import QtQuick
import "."

// Un dato del HUD: etiqueta pequeña + valor grande + regla de 1px. Sin
// recuadro. Si el dato está ausente, el valor es "—" en color de metadato.
Item {
    id: cell
    property string label: ""
    property string value: ""
    property bool absent: false
    property color accent: Design.textPrimary
    property bool vertical: false      // Fase 6: banda superior vs. regla lateral
    // punto de presencia antes del valor: NO es un LED estático — su opacidad
    // respira con `Design.coreEnergy` (dato real que ya mueve el núcleo).
    property bool pulse: false

    implicitWidth: Math.max(labelText.implicitWidth, valueText.implicitWidth)
                   + Design.sp(7)
    implicitHeight: vertical ? Design.sp(13) : Design.sp(16)

    // regla de 1px iluminada por el núcleo: abajo en horizontal, a la izquierda
    // en vertical
    Hairline {
        vertical: cell.vertical
        width: cell.vertical ? 1 : parent.width
        height: cell.vertical ? parent.height : 1
        anchors.left: parent.left
        anchors.bottom: cell.vertical ? undefined : parent.bottom
        anchors.top: cell.vertical ? parent.top : undefined
    }

    Column {
        anchors.left: parent.left
        anchors.leftMargin: cell.vertical ? Design.sp(2) : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        Text {
            id: labelText
            text: cell.label
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            font.weight: Design.wLabel
            font.letterSpacing: Design.trkLabel
            style: Text.Outline; styleColor: Design.textEdge   // borde óptico, no blur
        }
        Row {
            spacing: Design.sp(1.5)
            Rectangle {
                visible: cell.pulse && !cell.absent
                width: 6; height: 6; radius: 3
                anchors.verticalCenter: valueText.verticalCenter
                color: cell.accent
                // respira con la energía real del núcleo, nunca a 0 del todo
                opacity: 0.4 + 0.6 * Math.min(1.0, 0.3 + Design.coreEnergy * 1.6)
            }
            Text {
                id: valueText
                text: cell.absent ? "—" : cell.value
                color: cell.absent ? Design.textDisabled : cell.accent
                font.family: Design.fontMono          // dígitos ya tabulares (mono)
                font.pixelSize: cell.vertical ? Design.fsBody : Design.fsLarge
                font.weight: cell.vertical ? Design.wLabel : Design.wValue
                style: Text.Outline; styleColor: Design.textEdge
            }
        }
    }
}
