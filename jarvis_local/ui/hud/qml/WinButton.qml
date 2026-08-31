import QtQuick
import "."

// Control de ventana trazado a 1.5px (sin emojis, sin relleno). min · max ·
// restore · close.
Item {
    id: btn
    property string kind: "close"
    signal activated()

    implicitWidth: Design.sp(7)
    implicitHeight: Design.sp(7)

    HoverHandler { id: hov }
    TapHandler { onTapped: btn.activated() }

    Canvas {
        id: ico
        anchors.centerIn: parent
        width: Design.sp(3.5)
        height: Design.sp(3.5)
        onPaint: {
            var c = getContext("2d")
            c.reset()
            c.strokeStyle = hov.hovered
                ? (btn.kind === "close" ? "" + Design.alert : "" + Design.cyan)
                : "" + Design.textSecondary
            c.lineWidth = 1.5
            c.lineCap = "round"
            c.lineJoin = "round"
            var w = width, h = height
            if (btn.kind === "min") {
                c.beginPath(); c.moveTo(1, h - 1.5); c.lineTo(w - 1, h - 1.5); c.stroke()
            } else if (btn.kind === "max") {
                c.strokeRect(1.25, 1.25, w - 2.5, h - 2.5)
            } else if (btn.kind === "restore") {
                c.strokeRect(1.25, 3.25, w - 5, h - 5)
                c.beginPath()
                c.moveTo(4.25, 3.25); c.lineTo(4.25, 1.25); c.lineTo(w - 1.25, 1.25)
                c.lineTo(w - 1.25, h - 4.25); c.lineTo(w - 4.25, h - 4.25); c.stroke()
            } else { // close
                c.beginPath()
                c.moveTo(1, 1); c.lineTo(w - 1, h - 1)
                c.moveTo(w - 1, 1); c.lineTo(1, h - 1); c.stroke()
            }
        }
        Connections {
            target: hov
            function onHoveredChanged() { ico.requestPaint() }
        }
        onWidthChanged: requestPaint()
    }
}
