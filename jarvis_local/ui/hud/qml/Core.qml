import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  CORE — el elemento que define el producto.
//
//  Envuelve CoreField (el lienzo + el bucle) con la máquina de estados. Cada
//  estado cambia geometría, ritmo y color; las transiciones se interpolan en
//  220 ms (nunca corte seco). El paralaje se calcula aquí desde el puntero y
//  se pasa al campo.
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: root

    // API pública
    property string coreState: "idle"
    property real   audioLevel: 0.0
    property var    spectrum: []
    property real   tokensPerSecond: 0.0
    property bool   loopRunning: true

    // paralaje: puntero normalizado -1..1 (lo alimenta MouseArea del padre)
    property point pointer: Qt.point(0, 0)

    implicitWidth: 340
    implicitHeight: 340

    CoreField {
        id: field
        anchors.fill: parent
        coreState: root.coreState
        audioLevel: root.audioLevel
        spectrum: root.spectrum
        tokensPerSecond: root.tokensPerSecond
        loopRunning: root.loopRunning
        parallax: Qt.point(root.pointer.x, root.pointer.y)

        // valores por defecto = IDLE; las transiciones interpolan al cambiar
        tint: Design.azure
        ringOpen: 0.0
        spinRate: 6.0
        converge: 0.0
        emission: 0.45
        concentric: 0.0
        radialWave: 0.0
        fragmented: false
        dashed: false

        Behavior on ringOpen   { CoreNum {} }
        Behavior on spinRate   { CoreNum {} }
        Behavior on converge   { CoreNum {} }
        Behavior on emission   { CoreNum {} }
        Behavior on concentric { CoreNum {} }
        Behavior on radialWave { CoreNum {} }
        Behavior on tint {
            ColorAnimation {
                duration: Design.stateXfade
                easing.type: Design.easeType
                easing.bezierCurve: Design.easeCurve
            }
        }
    }

    // reutilizable: la curva de interpolación estándar entre estados
    component CoreNum: NumberAnimation {
        duration: Design.stateXfade
        easing.type: Design.easeType
        easing.bezierCurve: Design.easeCurve
    }

    state: root.coreState
    states: [
        State {
            name: "idle"
            PropertyChanges {
                target: field; tint: Design.azure; ringOpen: 0.0; spinRate: 6.0
                converge: 0.0; emission: 0.45; concentric: 0.0; radialWave: 0.0
                fragmented: false; dashed: false
            }
        },
        State {
            name: "listening"
            PropertyChanges {
                target: field; tint: Design.cyan; ringOpen: 1.0; spinRate: 10.0
                converge: 0.0; emission: 0.85; concentric: 0.0; radialWave: 0.0
                fragmented: false; dashed: false
            }
        },
        State {
            name: "thinking"
            PropertyChanges {
                target: field; tint: Design.mix(Design.azure, Design.cyan, 0.5)
                ringOpen: 0.5; spinRate: 24.0; converge: 1.0; emission: 0.7
                concentric: 1.0; radialWave: 0.0; fragmented: false; dashed: false
            }
        },
        State {
            name: "speaking"
            PropertyChanges {
                target: field; tint: Design.cyan; ringOpen: 0.62; spinRate: 12.0
                converge: 0.0; emission: 1.0; concentric: 0.0; radialWave: 1.0
                fragmented: false; dashed: false
            }
        },
        State {
            name: "alert"
            PropertyChanges {
                target: field; tint: Design.alert; ringOpen: 0.3; spinRate: 0.0
                converge: 0.0; emission: 0.0; concentric: 0.0; radialWave: 0.0
                fragmented: true; dashed: false
            }
        },
        State {
            name: "offline"
            PropertyChanges {
                target: field; tint: Design.textMeta; ringOpen: 0.0; spinRate: 0.0
                converge: 0.0; emission: 0.0; concentric: 0.0; radialWave: 0.0
                fragmented: false; dashed: true
            }
        }
    ]
}
