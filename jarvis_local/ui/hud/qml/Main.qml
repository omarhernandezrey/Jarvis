import QtQuick
import QtQuick.Window
import "."

// FASE 2 — el núcleo montado sobre los planos de profundidad. HUD, conversación
// y barra de comando llegan en fases siguientes. `Vm` es el ViewModel
// (contexto). Las teclas 1–6 recorren los estados para inspección; no forman
// parte de la interfaz final.
Window {
    id: win
    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 560
    visible: true
    color: Design.bgVoid
    title: "J.A.R.V.I.S"

    // puntero normalizado -1..1 para el paralaje
    property real pointerX: 0
    property real pointerY: 0

    Item {
        id: rootItem
        anchors.fill: parent
        focus: true

    // Plano 0 — fondo absoluto (paralaje 2 px).
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        x: win.pointerX * 2
        y: win.pointerY * 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: Design.bgAbyss }
            GradientStop { position: 1.0; color: Design.bgVoid }
        }
    }
    // halo de luz único, arriba-centro
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Design.glow(Design.azure, 0.10) }
            GradientStop { position: 0.4; color: "transparent" }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        onPositionChanged: (m) => {
            win.pointerX = (m.x / win.width - 0.5) * 2
            win.pointerY = (m.y / win.height - 0.5) * 2
        }
        onExited: { win.pointerX = 0; win.pointerY = 0 }
    }

    Hud {
        id: hudBand
        anchors { top: parent.top; left: parent.left; right: parent.right
                  margins: Design.sp(5) }
    }
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: hudBand.bottom
                  topMargin: Design.sp(3) }
        height: 1
        color: Design.hairline
    }

    Core {
        id: core
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.52
        height: width
        coreState: Vm ? Vm.state : "idle"
        audioLevel: Vm ? Vm.audio.level : 0
        spectrum: Vm ? Vm.audio.spectrum : []
        tokensPerSecond: (Vm && Vm.metrics.tokensPerSecond !== undefined) ? Vm.metrics.tokensPerSecond : 0
        pointer: Qt.point(win.pointerX, win.pointerY)
        loopRunning: win.active          // Fase 7 endurece esto (0 fps sin foco)
    }

    // etiqueta de estado — en la regla lateral, no en versalitas flotantes
    Row {
        anchors { left: parent.left; bottom: parent.bottom; margins: Design.sp(6) }
        spacing: Design.sp(2)
        Rectangle { width: 1; height: label.height
                    color: label.text === "alert" ? Design.alert
                    : label.text === "offline" ? Design.textMeta : Design.cyan }
        Text {
            id: label
            text: Vm ? Vm.state : "idle"
            color: Design.textSecondary
            font.family: Design.fontMono
            font.pixelSize: Design.fsSmall
        }
    }

    Keys.onPressed: (e) => {
        const map = { "1": "idle", "2": "listening", "3": "thinking",
                      "4": "speaking", "5": "alert", "6": "offline" }
        if (map[e.text] !== undefined) Vm.set_state(map[e.text])
    }
    }

    Component.onCompleted: win.requestActivate()
}
