import QtQuick
import "."

// Lectura de estado del núcleo. Mismo lenguaje visual que HudCell (etiqueta
// susurra / valor domina) pero el valor es la palabra de estado, no un dato
// numérico: "STANDBY", "LISTENING", "PROCESSING", "EXECUTING", "SPEAKING",
// "SYSTEM ALERT", "OFFLINE". El punto de presencia no es una animación
// inventada: su opacidad sigue `Design.coreEnergy`, el mismo dato real
// (RMS de voz / tokens·s / pulso de ejecución) que ya mueve el núcleo.
Item {
    id: root
    property string coreState: "idle"

    // Colores = misma rampa que el núcleo por estado (azul profundo → cian).
    readonly property var _map: ({
        idle:      ["STANDBY",      Design.mix(Design.azure, Design.textSecondary, 0.45)],
        listening: ["LISTENING",    Design.cyan],
        thinking:  ["PROCESSING",   Design.mix(Design.azure, Design.cyan, 0.45)],
        executing: ["EXECUTING",    Design.mix(Design.cyan, Design.azure, 0.35)],
        speaking:  ["SPEAKING",     Design.cyan],
        alert:     ["SYSTEM ALERT", Design.alert],
        offline:   ["OFFLINE",      Design.textDisabled]
    })
    readonly property var _entry: _map[coreState] || _map.idle
    readonly property string _label: _entry[0]
    readonly property color  _accent: _entry[1]

    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight

    // El cambio de estado es UNA reacción del sistema: el color del núcleo
    // hace cross-fade de 220 ms (Design.stateXfade); aquí igual, para que
    // núcleo y lectura de estado transicionen juntos y no en desfase.
    onCoreStateChanged: ackFlash.restart()

    Column {
        id: col
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
            // acuse breve del cambio de estado: una caída de opacidad de
            // ~90 ms y vuelta (no un parpadeo repetido, un solo pulso).
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
}
