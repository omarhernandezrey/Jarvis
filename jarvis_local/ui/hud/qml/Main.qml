import QtQuick
import QtQuick.Window
import "."

// FASE 4 — núcleo + consola conversacional. La barra de comando definitiva y el
// responsive llegan en fases 5 y 6. `Vm` / `Conversation` / `Chat` son
// contexto. Teclas 1–6: inspección de estados (no es UI final).
Window {
    id: win
    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 560
    visible: true
    color: Design.bgVoid
    title: "J.A.R.V.I.S"

    property real pointerX: 0
    property real pointerY: 0

    Item {
        id: rootItem
        anchors.fill: parent
        focus: true

        // Plano 0 — fondo absoluto (paralaje 2 px)
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
            id: hudRule
            anchors { left: parent.left; right: parent.right; top: hudBand.bottom
                      topMargin: Design.sp(3) }
            height: 1
            color: Design.hairline
        }

        // ── zona de contenido: núcleo | conversación ──────────────────────
        Item {
            id: contentRow
            anchors { left: parent.left; right: parent.right
                      top: hudRule.bottom; bottom: parent.bottom
                      margins: Design.sp(5) }

            Item {
                id: coreZone
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: Math.max(320, Math.min(parent.width * 0.42, parent.height))

                Core {
                    id: core
                    anchors.centerIn: parent
                    width: Math.min(coreZone.width, coreZone.height) * 0.92
                    height: width
                    coreState: Vm ? Vm.state : "idle"
                    audioLevel: Vm ? Vm.audio.level : 0
                    spectrum: Vm ? Vm.audio.spectrum : []
                    tokensPerSecond: (Vm && Vm.metrics.tokensPerSecond !== undefined)
                                     ? Vm.metrics.tokensPerSecond : 0
                    pointer: Qt.point(win.pointerX, win.pointerY)
                    loopRunning: win.active     // Fase 7 endurece esto
                }

                Row {
                    anchors { left: parent.left; bottom: parent.bottom }
                    spacing: Design.sp(2)
                    Rectangle {
                        width: 1; height: stLabel.height
                        color: stLabel.text === "alert" ? Design.alert
                            : stLabel.text === "offline" ? Design.textMeta : Design.cyan
                    }
                    Text {
                        id: stLabel
                        text: Vm ? Vm.state : "idle"
                        color: Design.textSecondary
                        font.family: Design.fontMono
                        font.pixelSize: Design.fsSmall
                    }
                }
            }

            Rectangle {
                id: zoneRule
                anchors { left: coreZone.right; top: parent.top; bottom: parent.bottom
                          leftMargin: Design.sp(4) }
                width: 1
                color: Design.hairline
            }

            Item {
                id: convZone
                anchors { left: zoneRule.right; right: parent.right
                          top: parent.top; bottom: parent.bottom
                          leftMargin: Design.sp(5) }

                Conversation {
                    id: convo
                    anchors { left: parent.left; right: parent.right; top: parent.top
                              bottom: cmdBar.top; bottomMargin: Design.sp(3) }
                    measure: 560
                }

                CommandBar {
                    id: cmdBar
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                }
            }
        }

        Keys.onPressed: (e) => {
            const map = { "1": "idle", "2": "listening", "3": "thinking",
                          "4": "speaking", "5": "alert", "6": "offline" }
            if (map[e.text] !== undefined && Vm) Vm.set_state(map[e.text])
        }
    }

    Component.onCompleted: win.requestActivate()
}
