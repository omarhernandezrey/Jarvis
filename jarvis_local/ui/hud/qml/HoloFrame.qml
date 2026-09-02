import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  HOLOFRAME — retícula técnica compartida por todo el HUD (Fase 13).
//
//  SIN FONDO. La ventana es 100 % transparente y estos elementos también: no
//  hay panel, no hay vidrio, no hay sombra. Sólo líneas — corchetes de mira en
//  las esquinas (con codo), un borde-hairline opcional muy tenue, y —si `scan`
//  está activo— una chispa recorriendo el perímetro. Todo se tiñe hacia el
//  color del ESTADO, respira con el latido del orbe (`Design.breath()`) y
//  destella con el frente de reacción.
//
//  El llamador fija el tamaño (normalmente `anchors.fill: parent`).
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: holo

    property color accent: Design.sky
    property real  radius: 0               // técnico = esquinas vivas
    property bool  showBorder: true        // hairline de 1px MUY tenue
    property bool  scan: false             // chispa que recorre el perímetro
    property real  extraLift: 0.0          // suma puntual (p. ej. foco del campo)
    property real  bracketLen: Design.bracketLen

    // posición de escena → nivel de energía del HUD aquí
    property point _mid: Qt.point(0, 0)
    function _remap() { _mid = mapToItem(null, width / 2, height / 2) }
    onWidthChanged: _remap()
    onHeightChanged: _remap()
    onXChanged: _remap()
    onYChanged: _remap()
    Component.onCompleted: _remap()
    Connections { target: Design; function onCorePosChanged() { holo._remap() } }

    readonly property real lift:
        Math.min(1.0, Design.hudLift(_mid.x, _mid.y) + extraLift)

    // color: la firma del acento LAVADA fuerte hacia el color del estado.
    readonly property color _wc: Design.stateWash(holo.accent, 0.75)
    readonly property real _wave: Design.waveAt(_mid.x, _mid.y)

    // realce 0..1: energía × respiración visible + frente de reacción + destello
    // global + micro-shimmer sólo con actividad real, a la cadencia del estado.
    readonly property real _glowK: Math.min(1.0,
        holo.lift * Design.breath()
        + 0.85 * _wave
        + 0.30 * Design.waveGlow
        + 0.08 * Math.sin(Design.tick * 4.0 * Design.stateCadence() + _mid.x * 0.012)
                * Math.min(1.0, Design.coreEnergy * 2.5))

    readonly property real _bracketOpacity: 0.22 + 0.72 * _glowK

    // ── borde-hairline (MUY tenue, sin relleno) ──
    Rectangle {
        anchors.fill: parent
        visible: holo.showBorder
        radius: holo.radius
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(holo._wc.r, holo._wc.g, holo._wc.b,
                              0.06 + 0.20 * holo._glowK)
    }

    // ── corchetes de mira en las 4 esquinas (con codo) ──
    Repeater {
        model: 4
        delegate: Item {
            id: corner
            required property int index
            readonly property bool rightSide:  index === 1 || index === 2
            readonly property bool bottomSide: index >= 2
            readonly property real arm: holo.bracketLen
            width: arm
            height: arm
            x: rightSide  ? holo.width  - Design.bracketInset - arm : Design.bracketInset
            y: bottomSide ? holo.height - Design.bracketInset - arm : Design.bracketInset
            opacity: holo._bracketOpacity

            Rectangle {   // brazo horizontal
                width: corner.arm; height: 1
                x: 0
                y: corner.bottomSide ? corner.arm - 1 : 0
                color: holo._wc
            }
            Rectangle {   // brazo vertical
                width: 1; height: corner.arm
                x: corner.rightSide ? corner.arm - 1 : 0
                y: 0
                color: holo._wc
            }
        }
    }

    // ── chispa que recorre el perímetro (sólo si `scan`) ──
    function _perim(u) {
        var w = width, h = height
        var d = ((u % 1.0) + 1.0) % 1.0 * (2 * (w + h))
        if (d < w) return Qt.point(d, 0)
        d -= w; if (d < h) return Qt.point(w, d)
        d -= h; if (d < w) return Qt.point(w - d, h)
        d -= w; return Qt.point(0, h - d)
    }
    Item {
        id: spark
        visible: holo.scan
        readonly property point p: holo._perim(Design.tick * 0.16)
        x: p.x; y: p.y
        Rectangle {
            anchors.centerIn: parent
            width: 14; height: 14; radius: 7
            color: holo._wc
            opacity: 0.12 + 0.14 * holo._glowK
        }
        Rectangle {
            anchors.centerIn: parent
            width: 4; height: 4; radius: 2
            color: holo._wc
            opacity: 0.8
        }
    }
}
