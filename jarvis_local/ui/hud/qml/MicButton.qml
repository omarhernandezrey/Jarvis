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
        : hover.hovered ? Design.emitCore : Design.textPrimary

    // En reposo NO hay recuadro: sólo el icono. Al pasar el ratón o al
    // escuchar aparecen los corchetes de mira (mismo lenguaje que el HUD).
    Rectangle {
        anchors.fill: parent
        radius: Design.radiusHud
        color: micState === "listening" ? Design.glow(Design.cyan, 0.12)
             : hover.hovered && micState !== "denied" ? Qt.rgba(1, 1, 1, 0.05)
             : "transparent"
        Behavior on color { ColorAnimation { duration: Design.durFast } }
    }
    HoloFrame {
        anchors.fill: parent
        radius: Design.radiusHud
        fillSurface: false
        showBorder: false
        scan: mic.micState === "listening"
        accent: mic.micState === "denied" ? Design.alert : Design.cyan
        opacity: (mic.micState === "listening"
                  || (hover.hovered && mic.micState !== "denied")) ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: Design.durFast } }
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
            var w = width, h = height, cx = w / 2
            var r = w * 0.22                    // radio de la cápsula
            var capTop = r + 1.5
            var capBot = h * 0.46
            var br = w * 0.40
            var footY = h - 2
            // trazo del icono en dos pasadas: contorno oscuro (borde óptico
            // sobre escritorio) + trazo de color. Sin blur.
            function paint(col, lw, fillCap) {
                ctx.strokeStyle = col; ctx.fillStyle = col
                ctx.lineWidth = lw; ctx.lineCap = "round"; ctx.lineJoin = "round"
                ctx.beginPath()
                ctx.moveTo(cx - r, capTop)
                ctx.arc(cx, capTop, r, Math.PI, 0, false)
                ctx.lineTo(cx + r, capBot)
                ctx.arc(cx, capBot, r, 0, Math.PI, false)
                ctx.closePath()
                if (fillCap) ctx.fill(); else ctx.stroke()
                ctx.beginPath()
                ctx.arc(cx, capBot, br, 0.16 * Math.PI, 0.84 * Math.PI, false)
                ctx.moveTo(cx, capBot + br); ctx.lineTo(cx, footY)
                ctx.moveTo(cx - w * 0.20, footY); ctx.lineTo(cx + w * 0.20, footY)
                ctx.stroke()
                if (mic.micState === "denied") {
                    ctx.beginPath()
                    ctx.moveTo(w * 0.12, h * 0.10); ctx.lineTo(w * 0.88, h * 0.90)
                    ctx.stroke()
                }
            }
            var listening = mic.micState === "listening"
            paint("" + Design.textEdge, 4.0, listening)
            paint("" + mic._c, 1.8, listening)
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
            NumberAnimation { from: 0.5; to: 0.0; duration: Design.micPulse
                easing.type: Easing.OutCubic }
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
