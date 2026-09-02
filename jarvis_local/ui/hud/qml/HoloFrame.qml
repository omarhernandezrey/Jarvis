import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  HOLOFRAME — marco holográfico compartido por todo el HUD (Fase 10).
//
//  No es una tarjeta: es una proyección del núcleo. Fondo con gradiente
//  (iluminado desde arriba), borde de 1px teñido por el acento, corchetes de
//  mira en las 4 esquinas, y un brillo de vidrio arriba. Su intensidad RESPIRA
//  con `Design.hudLift` en su posición de escena: cerca del núcleo trabajando
//  brilla, en reposo se asienta — el mismo dato real que mueve el orbe.
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

    // ── vida del marco (Fase 11) ──
    // color: la firma del acento LAVADA hacia el color del estado actual.
    readonly property color _wc: Design.stateWash(holo.accent, 0.55)
    // realce total 0..1: energía del HUD × respiración de reposo, + el frente
    // de reacción cuando cruza, + un micro-shimmer que SÓLO aparece con
    // actividad real (coreEnergy) y a la cadencia del estado.
    readonly property real _wave: Design.waveAt(_mid.x, _mid.y)
    readonly property real _glowK: Math.min(1.0,
        holo.lift * (0.86 + 0.14 * Design.pulse)
        + 0.55 * _wave
        + 0.06 * Math.sin(Design.tick * 4.0 * Design.stateCadence() + _mid.x * 0.012)
                * Math.min(1.0, Design.coreEnergy * 2.5))
    // se calcula UNA vez por fotograma y lo comparten los 8 brazos de corchete
    // (antes: 8 bindings iguales re-evaluados por instancia y fotograma).
    readonly property real _bracketOpacity: 0.28 + 0.62 * _glowK

    // ── fondo con gradiente (luz desde arriba) ──
    Rectangle {
        anchors.fill: parent
        visible: holo.fillSurface
        radius: holo.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Design.holoTop }
            GradientStop { position: 1.0; color: Design.holoBot }
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
                              0.20 + 0.48 * holo._glowK)
    }

    // ── brillo de vidrio en el borde superior ──
    Rectangle {
        anchors { top: parent.top; left: parent.left; right: parent.right
                  leftMargin: holo.radius; rightMargin: holo.radius; topMargin: 1 }
        height: 1
        color: Qt.rgba(1, 1, 1, 0.05 + 0.14 * holo._glowK)
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
}
