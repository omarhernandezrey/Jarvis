import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  HOLOFRAME — marco holográfico compartido por todo el HUD.
//
//  No es una tarjeta: es una proyección del núcleo. Fondo con gradiente teñido
//  por el ESTADO, borde de 1px, corchetes de mira en las 4 esquinas y brillo
//  de vidrio. Su intensidad RESPIRA de forma visible con el latido del orbe
//  (`Design.breath()`), se lava hacia el color del estado (`Design.stateWash`),
//  destella con el frente de reacción (`Design.waveAt` + `waveGlow`) y —si
//  `scan` está activo— una chispa recorre su perímetro.
//
//  El llamador fija el tamaño (normalmente `anchors.fill: parent`).
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: holo

    property color accent: Design.sky
    property real  radius: Design.widgetRadius
    property bool  fillSurface: true       // pinta el fondo con gradiente
    property bool  showBorder: true        // borde de 1px
    property real  extraLift: 0.0          // suma puntual (p. ej. foco del campo)
    property bool  scan: false             // chispa que recorre el perímetro

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

    // realce total 0..1: energía del HUD × RESPIRACIÓN visible, + el frente de
    // reacción cuando cruza, + el destello global del cambio de estado, + un
    // micro-shimmer que sólo aparece con actividad real y a la cadencia del
    // estado.
    readonly property real _glowK: Math.min(1.0,
        holo.lift * Design.breath()
        + 0.85 * _wave
        + 0.30 * Design.waveGlow
        + 0.08 * Math.sin(Design.tick * 4.0 * Design.stateCadence() + _mid.x * 0.012)
                * Math.min(1.0, Design.coreEnergy * 2.5))

    // se calcula UNA vez por fotograma y lo comparten los 8 brazos de corchete
    readonly property real _bracketOpacity: 0.24 + 0.70 * _glowK

    // ── fondo: gradiente teñido por el estado ──
    Rectangle {
        anchors.fill: parent
        visible: holo.fillSurface
        radius: holo.radius
        gradient: Gradient {
            GradientStop { position: 0.0
                color: Design.mix(Design.holoTop, holo._wc, 0.10 + 0.14 * holo._glowK) }
            GradientStop { position: 1.0
                color: Design.mix(Design.holoBot, holo._wc, 0.05 + 0.08 * holo._glowK) }
        }
    }

    // ── borde teñido por el estado y la luz del núcleo ──
    Rectangle {
        anchors.fill: parent
        visible: holo.showBorder
        radius: holo.radius
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(holo._wc.r, holo._wc.g, holo._wc.b,
                              0.18 + 0.62 * holo._glowK)
    }

    // ── brillo de vidrio en el borde superior ──
    Rectangle {
        anchors { top: parent.top; left: parent.left; right: parent.right
                  leftMargin: holo.radius; rightMargin: holo.radius; topMargin: 1 }
        height: 1
        color: Qt.rgba(1, 1, 1, 0.04 + 0.20 * holo._glowK)
    }

    // ── corchetes de mira en las 4 esquinas ──
    Repeater {
        model: 4
        delegate: Item {
            id: corner
            required property int index
            readonly property bool rightSide:  index === 1 || index === 2
            readonly property bool bottomSide: index >= 2
            readonly property real arm: Design.bracketLen
            width: arm
            height: arm
            x: rightSide  ? holo.width  - Design.bracketInset - arm : Design.bracketInset
            y: bottomSide ? holo.height - Design.bracketInset - arm : Design.bracketInset

            Rectangle {   // brazo horizontal
                width: corner.arm; height: 1.5
                x: 0
                y: corner.bottomSide ? corner.arm - 1.5 : 0
                color: holo._wc
                opacity: holo._bracketOpacity
            }
            Rectangle {   // brazo vertical
                width: 1.5; height: corner.arm
                x: corner.rightSide ? corner.arm - 1.5 : 0
                y: 0
                color: holo._wc
                opacity: holo._bracketOpacity
            }
        }
    }

    // ── chispa que recorre el perímetro (sólo si `scan`) ──
    // Posición parametrizada por el reloj global; sin timer propio. Dos
    // rectángulos apilados = falso glow (halo tenue + núcleo brillante).
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
            width: 16; height: 16; radius: 8
            color: holo._wc
            opacity: 0.16 + 0.14 * holo._glowK
        }
        Rectangle {
            anchors.centerIn: parent
            width: 5; height: 5; radius: 2.5
            color: holo._wc
            opacity: 0.75
        }
    }
}
