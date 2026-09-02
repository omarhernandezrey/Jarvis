import QtQuick
import "."

// Lectura de estado del núcleo como INSTRUMENTO PRINCIPAL (Fase 13). Sin fondo:
// retícula (corchetes + chispa de perímetro), la palabra de estado, y bajo
// ella una ESCALA GRADUADA (marcas tipo regla) por la que corre el relleno de
// energía real. "STANDBY", "LISTENING", "PROCESSING", "EXECUTING", "SPEAKING",
// "SYSTEM ALERT", "OFFLINE".
Item {
    id: root
    property string coreState: "idle"

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

    implicitWidth: col.implicitWidth + Design.sp(8)
    implicitHeight: col.implicitHeight + Design.sp(6)

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
        extraLift: root._kick + 0.08
        scan: true
        bracketLen: 10
    }

    Column {
        id: col
        anchors.centerIn: parent
        spacing: 2
        Row {
            spacing: Design.sp(1.5)
            Text {
                text: "MODO"
                color: Design.textMeta
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                font.weight: Design.wLabel
                font.letterSpacing: Design.trkLabel
                style: Text.Outline; styleColor: Design.textEdge
            }
            Text {
                text: "//"
                color: Design.stateWash(Design.textDisabled, 0.6)
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                opacity: 0.5 + 0.3 * Design.breath()
            }
        }
        Row {
            id: valueRow
            spacing: Design.sp(2)
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
                width: 5; height: 5
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
                font.pixelSize: Design.fsStatus
                font.weight: Design.wStatus
                font.letterSpacing: Design.trkStatus
                style: Text.Outline; styleColor: Design.textEdge
                Behavior on color { ColorAnimation {
                    duration: Design.stateXfade; easing.type: Design.easeType
                    easing.bezierCurve: Design.easeCurve } }
            }
        }
    }

    // ── ESCALA GRADUADA + relleno de energía real ──
    Item {
        id: scale
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                  leftMargin: Design.sp(2.5); rightMargin: Design.sp(2.5)
                  bottomMargin: Design.sp(1.75) }
        height: 5

        // marcas de la regla
        Row {
            anchors.fill: parent
            Repeater {
                model: 21
                delegate: Item {
                    required property int index
                    width: scale.width / 21
                    height: scale.height
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: 1
                        height: (index % 5 === 0) ? scale.height : scale.height * 0.5
                        color: Qt.rgba(root._accent.r, root._accent.g, root._accent.b, 0.22)
                    }
                }
            }
        }
        // aguja / relleno: sigue Design.coreEnergy; en reposo LATE con breath()
        Rectangle {
            anchors.bottom: parent.bottom
            width: 2
            height: scale.height
            color: root._accent
            opacity: 0.55 + 0.35 * Design.breath()
            x: (parent.width - width) * Math.max(0.03 + 0.06 * Design.pulse,
                                                 Math.min(1.0, Design.coreEnergy))
        }
    }
}
