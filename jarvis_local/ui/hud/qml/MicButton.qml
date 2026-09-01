import QtQuick
import QtQuick.Controls.Basic
import "."

// Micrófono con tres estados reales: inactive · listening · denied.
Item {
    id: mic
    property string micState: "inactive"
    signal toggled()

    implicitWidth: Design.sp(10)
    implicitHeight: Design.sp(10)

    readonly property color _c: micState === "denied" ? Design.alert
        : micState === "listening" ? Design.cyan
        : hover.hovered ? Design.textPrimary : Design.textSecondary

    // En reposo NO hay recuadro: sólo el icono (antes su propio contenedor lo
    // apretaba). El recuadro aparece al pasar el ratón o al escuchar.
    Rectangle {
        anchors.fill: parent
        radius: Design.radiusHud
        color: micState === "listening" ? Design.glow(Design.cyan, 0.12)
             : hover.hovered && micState !== "denied" ? Qt.rgba(1, 1, 1, 0.05)
             : "transparent"
        border.width: 1
        border.color: micState === "listening" ? Design.glow(Design.cyan, 0.5)
             : hover.hovered && micState !== "denied" ? Design.hairline
             : "transparent"
        Behavior on border.color { ColorAnimation { duration: Design.durFast } }
        Behavior on color { ColorAnimation { duration: Design.durFast } }
    }

    // icono vectorial trazado (sin emojis)
    Canvas {
        id: ico
        anchors.centerIn: parent
        width: Design.sp(4.5); height: Design.sp(5.5)
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            ctx.strokeStyle = mic._c; ctx.fillStyle = mic._c
            ctx.lineWidth = 1.5; ctx.lineCap = "round"
            var w = width, h = height, cx = w / 2
            // cápsula
            ctx.beginPath()
            ctx.moveTo(cx - w * 0.28, h * 0.12)
            ctx.arc(cx, h * 0.12, w * 0.28, Math.PI, 0)
            ctx.lineTo(cx + w * 0.28, h * 0.42)
            ctx.arc(cx, h * 0.42, w * 0.28, 0, Math.PI)
            ctx.closePath()
            if (mic.micState === "listening") ctx.fill(); else ctx.stroke()
            // arco inferior + pie
            ctx.beginPath()
            ctx.arc(cx, h * 0.42, w * 0.42, 0.15 * Math.PI, 0.85 * Math.PI)
            ctx.moveTo(cx, h * 0.42 + w * 0.42); ctx.lineTo(cx, h * 0.9)
            ctx.moveTo(cx - w * 0.22, h * 0.9); ctx.lineTo(cx + w * 0.22, h * 0.9)
            ctx.stroke()
            if (mic.micState === "denied") {           // barra diagonal
                ctx.beginPath()
                ctx.moveTo(w * 0.05, h * 0.05); ctx.lineTo(w * 0.95, h * 0.95)
                ctx.stroke()
            }
        }
        Connections {
            target: mic
            function onMicStateChanged() { ico.requestPaint() }
        }
        Connections {
            target: hover
            function onHoveredChanged() { ico.requestPaint() }
        }
    }

    // pulso sutil mientras escucha (animación, no timer)
    Rectangle {
        anchors.fill: parent
        radius: Design.radiusHud
        color: "transparent"
        border.color: Design.cyan
        border.width: 1
        visible: mic.micState === "listening"
        SequentialAnimation on opacity {
            running: mic.micState === "listening"
            loops: Animation.Infinite
            NumberAnimation { from: 0.5; to: 0.0; duration: 1100 }
        }
    }

    HoverHandler { id: hover; enabled: mic.micState !== "denied" }
    TapHandler {
        enabled: mic.micState !== "denied"
        onTapped: mic.toggled()
    }

    ToolTip {
        visible: hover.hovered && mic.micState === "denied"
        text: "Micrófono sin permiso"
    }
}
