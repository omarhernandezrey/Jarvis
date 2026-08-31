import QtQuick
import "."

// Ventana aislada del núcleo para validar la dirección visual (addendum).
// Incluye el pipeline completo: bloom (dentro de Core) + atmósfera global.
// La conduce scripts/core_preview.py.
Rectangle {
    id: root
    width: 760
    height: 760
    color: Design.bgVoid
    property string coreState: "idle"

    property real tick: 0
    FrameAnimation { running: true; onTriggered: root.tick += frameTime }

    layer.enabled: true
    layer.effect: Atmosphere { time: Math.floor(root.tick * 24) / 24 }

    Core {
        anchors.centerIn: parent
        width: 560
        height: 560
        coreState: root.coreState
        audioLevel: (coreState === "listening" || coreState === "speaking") ? 0.55 : 0
        tokensPerSecond: coreState === "thinking" ? 12 : 0
        time: root.tick
        loopRunning: true
    }

    Text {
        anchors { left: parent.left; bottom: parent.bottom; margins: Design.sp(4) }
        text: root.coreState
        color: Design.textSecondary
        font.family: Design.fontMono
        font.pixelSize: Design.fsSmall
    }
    Text {
        anchors { right: parent.right; bottom: parent.bottom; margins: Design.sp(4) }
        text: "1–6 estados · ESC salir"
        color: Design.textMeta
        font.family: Design.fontMono
        font.pixelSize: Design.fsMeta
    }

    focus: true
    Keys.onPressed: (e) => {
        const m = {"1":"idle","2":"listening","3":"thinking",
                   "4":"speaking","5":"alert","6":"offline"}
        if (m[e.text] !== undefined) root.coreState = m[e.text]
        if (e.key === Qt.Key_Escape) Qt.quit()
    }
}
