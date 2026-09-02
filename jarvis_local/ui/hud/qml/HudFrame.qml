import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  HUDFRAME — el borde de la ventana ES parte de la entidad (Fase 13).
//
//  SIN perímetro cerrado (eso leería como marco/panel). Sólo señales de
//  cabina: 4 corchetes de mira en las esquinas + 4 ticks en el punto medio de
//  cada borde. Teñidos por el color del ESTADO, respirando con el latido del
//  orbe y destellando en cada cambio de estado. La ventana sigue 100 %
//  transparente. Deja libre la canaleta de redimensionado.
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: frame
    anchors.fill: parent

    property int inset: Design.windowShadowGutter + Design.sp(1)

    readonly property color _wc: Design.stateWash(Design.cyan, 0.9)
    readonly property real _cx: width / 2
    readonly property real _cy: height / 2
    readonly property real _wave: Design.waveAt(_cx, _cy)
    readonly property real _k: Math.min(1.0,
        (0.28 + 0.42 * Design.lightLevel(_cx, _cy)) * Design.breath()
        + 0.55 * Design.waveGlow + 0.35 * _wave)

    readonly property real _arm: Math.max(14, Math.min(30, width * 0.05))

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
            opacity: 0.22 + 0.72 * frame._k

            Rectangle {
                width: c.width; height: 1.5
                x: 0; y: c.bottomSide ? c.height - 1.5 : 0
                color: frame._wc
            }
            Rectangle {
                width: 1.5; height: c.height
                x: c.rightSide ? c.width - 1.5 : 0; y: 0
                color: frame._wc
            }
        }
    }

    // ── ticks en el punto medio de cada borde ──
    Repeater {
        model: 4
        delegate: Rectangle {
            required property int index
            readonly property bool horiz: index < 2       // 0 arriba · 1 abajo
            width:  horiz ? 12 : 1.5
            height: horiz ? 1.5 : 12
            x: index === 0 || index === 1 ? frame._cx - width / 2
             : index === 2 ? frame.inset - 3
             : frame.width - frame.inset + 3 - width
            y: index === 0 ? frame.inset - 3
             : index === 1 ? frame.height - frame.inset + 3 - height
             : frame._cy - height / 2
            color: frame._wc
            opacity: 0.18 + 0.55 * frame._k
        }
    }
}
