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
        }
        Text {
            id: valueText
            text: cell.absent ? "—" : cell.value
            color: cell.absent ? Design.textMeta : cell.accent
            font.family: Design.fontMono          // dígitos ya tabulares (mono)
            font.pixelSize: cell.vertical ? Design.fsBody : Design.fsLarge
        }
    }
}
