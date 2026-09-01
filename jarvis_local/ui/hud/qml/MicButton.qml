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

    // icono vectorial trazado (sin emojis). Todo el dibujo queda DENTRO de los
    // límites del Canvas: antes el arco superior de la cápsula se salía por
    // arriba (y negativa) y el recorte lo escondía → "micrófono cortado arriba".
    Canvas {
        id: ico
        anchors.centerIn: parent
        width: Design.sp(5.5); height: Design.sp(7)
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            ctx.strokeStyle = mic._c; ctx.fillStyle = mic._c
            ctx.lineWidth = 1.5; ctx.lineCap = "round"; ctx.lineJoin = "round"
            var w = width, h = height, cx = w / 2
            var r = w * 0.22                    // radio de la cápsula
            var capTop = r + 1.5               // el arco sube r → borde en y≈1.5
            var capBot = h * 0.46
            // cápsula (píldora vertical)
            ctx.beginPath()
            ctx.moveTo(cx - r, capTop)
            ctx.arc(cx, capTop, r, Math.PI, 0, false)
            ctx.lineTo(cx + r, capBot)
            ctx.arc(cx, capBot, r, 0, Math.PI, false)
            ctx.closePath()
            if (mic.micState === "listening") ctx.fill(); else ctx.stroke()
            // soporte en U bajo la cápsula
            var br = w * 0.40
            ctx.beginPath()
            ctx.arc(cx, capBot, br, 0.16 * Math.PI, 0.84 * Math.PI, false)
            ctx.stroke()
            // tallo + base
            var footY = h - 2
            ctx.beginPath()
            ctx.moveTo(cx, capBot + br); ctx.lineTo(cx, footY)
            ctx.moveTo(cx - w * 0.20, footY); ctx.lineTo(cx + w * 0.20, footY)
            ctx.stroke()
            if (mic.micState === "denied") {           // barra diagonal
                ctx.beginPath()
                ctx.moveTo(w * 0.12, h * 0.10); ctx.lineTo(w * 0.88, h * 0.90)
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
