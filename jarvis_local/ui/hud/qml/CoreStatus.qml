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

    readonly property var _map: ({
        idle:      ["STANDBY",      Design.textSecondary],
        listening: ["LISTENING",    Design.cyan],
        thinking:  ["PROCESSING",   Design.azure],
        executing: ["EXECUTING",    Design.cyan],
        speaking:  ["SPEAKING",     Design.cyan],
        alert:     ["SYSTEM ALERT", Design.alert],
        offline:   ["OFFLINE",      Design.textMeta]
    })
    readonly property var _entry: _map[coreState] || _map.idle
    readonly property string _label: _entry[0]
    readonly property color  _accent: _entry[1]

    implicitWidth: col.implicitWidth
    implicitHeight: col.implicitHeight

    Column {
        id: col
        spacing: 2
        Text {
            text: "ESTADO"
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            font.letterSpacing: 1.5
        }
        Row {
            spacing: Design.sp(2)
            Rectangle {
                id: dot
                width: 5; height: 5; radius: 2.5
                anchors.verticalCenter: parent.verticalCenter
                color: root._accent
                opacity: 0.45 + 0.55 * Math.min(1.0, Design.coreEnergy * 1.4)
            }
            Text {
                text: root._label
                color: root._accent
                font.family: Design.fontMono
                font.pixelSize: Design.fsTitle
                font.bold: true
                font.letterSpacing: 1.5
            }
        }
    }
}
