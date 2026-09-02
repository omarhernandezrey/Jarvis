import QtQuick
import "."

// Lectura de estado del núcleo. Mismo lenguaje holográfico que HudCell
// (HoloFrame: gradiente + corchetes de mira + borde que respira) pero el valor
// es la palabra de estado: "STANDBY", "LISTENING", "PROCESSING", "EXECUTING",
// "SPEAKING", "SYSTEM ALERT", "OFFLINE". Bajo la palabra, una BASE de energía
// cuya longitud sigue `Design.coreEnergy` — el mismo dato real (RMS de voz /
// tokens·s / pulso de ejecución) que mueve el orbe, aquí cuantificado.
Item {
    id: root
    property string coreState: "idle"

    // La palabra de estado SÍ usa color vivo (no es el orbe): cian para los
    // modos de IA, naranja para "operando el sistema", rojo para fallo.
    readonly property var _map: ({
        idle:      ["STANDBY",      Design.sky],
        listening: ["LISTENING",    Design.cyan],
        thinking:  ["PROCESSING",   Design.mix(Design.cyan, Design.azure, 0.35)],
        executing: ["EXECUTING",    Design.warn],
        speaking:  ["SPEAKING",     Design.cyan],
        alert:     ["SYSTEM ALERT", Design.alert],
        offline:   ["OFFLINE",      Design.textDisabled]
    })
    readonly property var _entry: _map[coreState] || _map.idle
    readonly property string _label: _entry[0]
    readonly property color  _accent: _entry[1]

    implicitWidth: col.implicitWidth + Design.sp(6)
    implicitHeight: col.implicitHeight + Design.sp(4)

    // El cambio de estado es UNA reacción del sistema: núcleo y lectura
    // transicionan juntos (Design.stateXfade), nunca en desfase.
    onCoreStateChanged: { ackFlash.restart(); liftKick.restart() }
    property real _kick: 0
    NumberAnimation {
        id: liftKick
        target: root; property: "_kick"
        from: 0.35; to: 0.0; duration: Design.durSlow; easing.type: Easing.OutCubic
    }

    HoloFrame {
        anchors.fill: parent
        accent: root._accent
        radius: Design.widgetRadius
        extraLift: root._kick + 0.08
    }

    Column {
        id: col
        anchors.centerIn: parent
        spacing: 2
        Text {
            text: "ESTADO"
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            font.weight: Design.wLabel
            font.letterSpacing: Design.trkLabel
            style: Text.Outline; styleColor: Design.textEdge
        }
        Row {
            id: valueRow
            spacing: Design.sp(2)
            // acuse breve del cambio de estado: una caída de opacidad y vuelta
            // (un solo pulso, no un parpadeo).
            SequentialAnimation {
                id: ackFlash
                NumberAnimation { target: valueRow; property: "opacity"
                    to: 0.5; duration: Design.durMicro; easing.type: Design.easeType
                    easing.bezierCurve: Design.easeCurve }
                NumberAnimation { target: valueRow; property: "opacity"
                    to: 1.0; duration: Design.stateXfade; easing.type: Design.easeType
                    easing.bezierCurve: Design.easeCurve }
            }
            Rectangle {
                id: dot
                width: 5; height: 5; radius: 2.5
                anchors.verticalCenter: parent.verticalCenter
                color: root._accent
                opacity: 0.45 + 0.55 * Math.min(1.0, Design.coreEnergy * 1.4)
                Behavior on color { ColorAnimation {
                    duration: Design.stateXfade; easing.type: Design.easeType
                    easing.bezierCurve: Design.easeCurve } }
            }
            Text {
                text: root._label
                color: root._accent
                font.family: Design.fontMono
                font.pixelSize: Design.fsStatus    // lectura primaria: 26
                font.weight: Design.wStatus
                font.letterSpacing: Design.trkStatus
                style: Text.Outline; styleColor: Design.textEdge
                Behavior on color { ColorAnimation {
                    duration: Design.stateXfade; easing.type: Design.easeType
                    easing.bezierCurve: Design.easeCurve } }
            }
        }
    }

    // ── BASE DE ENERGÍA — la longitud sigue Design.coreEnergy (dato real) ──
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                  leftMargin: Design.sp(2.5); rightMargin: Design.sp(2.5)
                  bottomMargin: Design.sp(1.5) }
        height: 1.5
        color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.16)
        Rectangle {
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width: parent.width * Math.min(1.0, Math.max(0.015, Design.coreEnergy))
            color: root._accent
            opacity: 0.85
        }
    }
}
