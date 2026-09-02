import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  HUDFRAME — el borde de la ventana ES parte de la entidad (Fase 12).
//
//  Cuatro corchetes de mira grandes en las esquinas de la ventana + una línea
//  interior de 1px muy tenue. Todo teñido por el color del ESTADO, respirando
//  de forma visible con el latido del orbe y con un destello en cada cambio de
//  estado. No es un fondo ni un panel: es una retícula emisiva sobre la
//  ventana transparente. Deja libre la canaleta de redimensionado.
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: frame
    anchors.fill: parent

    property int inset: Design.windowShadowGutter + Design.sp(1)

    readonly property color _wc: Design.stateWash(Design.cyan, 0.9)
    readonly property real _cx: width / 2
    readonly property real _cy: height / 2
    readonly property real _wave: Design.waveAt(_cx, _cy)
    // muy visible: respiración amplia + destello del cambio de estado.
    readonly property real _k: Math.min(1.0,
        (0.30 + 0.45 * Design.lightLevel(_cx, _cy)) * Design.breath()
        + 0.55 * Design.waveGlow + 0.35 * _wave)

    readonly property real _arm: Math.max(14, Math.min(30, width * 0.055))

    // ── línea interior de 1px (perímetro) ──
    Rectangle {
        anchors.fill: parent
        anchors.margins: frame.inset
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(frame._wc.r, frame._wc.g, frame._wc.b, 0.05 + 0.14 * frame._k)
        radius: Design.radiusWindow
    }

    // ── 4 corchetes de esquina ──
    Repeater {
        model: 4
        delegate: Item {
            id: c
            required property int index
            readonly property bool rightSide:  index === 1 || index === 2
            readonly property bool bottomSide: index >= 2
            x: rightSide  ? frame.width  - frame.inset - frame._arm : frame.inset
            y: bottomSide ? frame.height - frame.inset - frame._arm : frame.inset
            width: frame._arm; height: frame._arm
            opacity: 0.30 + 0.70 * frame._k

            Rectangle {
                width: c.width; height: 2
                x: 0; y: c.bottomSide ? c.height - 2 : 0
                color: frame._wc
            }
            Rectangle {
                width: 2; height: c.height
                x: c.rightSide ? c.width - 2 : 0; y: 0
                color: frame._wc
            }
        }
    }
}
