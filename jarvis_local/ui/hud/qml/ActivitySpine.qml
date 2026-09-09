import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  ACTIVITY SPINE (Fase I · I1) — la columna izquierda deja de estar vacía.
//
//  Tira vertical fina, mismo lenguaje que el resto del HUD (sin panel, sólo
//  retícula + líneas). De arriba a abajo:
//    · RELOJ de sesión (hh:mm:ss), grande.
//    · ESTADO del núcleo: palabra + acento del estado.
//    · ESPINA: historial reciente de la ENERGÍA del núcleo (Design.coreEnergy)
//      como barras horizontales apiladas — la más reciente arriba. Se muestrea
//      del reloj global (Design.tick), sin timer propio.
//
//  El llamador fija tamaño y posición.
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: spine

    property string coreState: "idle"
    property var metrics: ({})

    function _mm(k, unit) {
        var v = spine.metrics ? spine.metrics[k] : undefined
        if (v === undefined || v === null) return "—"
        return (typeof v === "number" ? Math.round(v) : v) + (unit || "")
    }

    readonly property var _map: ({
        idle:      ["STANDBY",   Design.sky],
        listening: ["LISTENING", Design.cyan],
        thinking:  ["PROCESSING", Design.mix(Design.cyan, Design.azure, 0.35)],
        executing: ["EXECUTING", Design.warn],
        speaking:  ["SPEAKING",  Design.cyan],
        alert:     ["ALERT",     Design.alert],
        offline:   ["OFFLINE",   Design.textDisabled]
    })
    readonly property var _entry: _map[coreState] || _map.idle
    readonly property color _accent: _entry[1]

    // ── muestreo de la energía del núcleo (ring buffer, sin timer) ──────────
    property var _hist: []
    property int _cap: 44
    property real _lastSample: -1
    onXChanged: _mid()
    function _mid() {}                       // (placeholder; HoloFrame remapea solo)
    Connections {
        target: Design
        function onTickChanged() {
            // ~7 muestras/seg — suficiente para que la espina "corra"
            if (Design.tick - spine._lastSample < 0.14) return
            spine._lastSample = Design.tick
            var h = spine._hist.slice()
            h.push(Math.max(0.0, Math.min(1.0, Design.coreEnergy)))
            if (h.length > spine._cap) h.shift()
            spine._hist = h
        }
    }

    HoloFrame {
        anchors.fill: parent
        accent: spine._accent
        bracketLen: 8
        scan: false
    }

    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top
                  leftMargin: Design.sp(2); rightMargin: Design.sp(2)
                  topMargin: Design.sp(2.5) }
        spacing: Design.sp(2.5)

        // ── RELOJ ──
        Column {
            spacing: 1
            Text {
                text: "SESIÓN"
                color: Design.textMeta
                font.family: Design.fontMono
                font.pixelSize: Design.fsMicro
                font.letterSpacing: Design.trkLabel
                style: Text.Outline; styleColor: Design.textEdge
            }
            Text {
                id: clock
                color: Design.litText(Design.textSecondary,
                                      spine.x + spine.width / 2, spine.y + 40)
                font.family: Design.fontMono
                font.pixelSize: Design.fsBody
                font.letterSpacing: 1.5
                style: Text.Outline; styleColor: Design.textEdge
                text: Qt.formatDateTime(new Date(), "hh:mm:ss")
                Timer {
                    interval: 1000; repeat: true; running: spine.visible
                    onTriggered: clock.text = Qt.formatDateTime(new Date(), "hh:mm:ss")
                }
            }
        }

        Rectangle {   // regla
            width: parent.width; height: 1
            color: Design.stateWash(Design.hairline, 0.7)
            opacity: 0.35 + 0.25 * Design.breath()
        }

        // ── ESTADO ──
        Column {
            spacing: 1
            Text {
                text: "MODO"
                color: Design.textMeta
                font.family: Design.fontMono
                font.pixelSize: Design.fsMicro
                font.letterSpacing: Design.trkLabel
                style: Text.Outline; styleColor: Design.textEdge
            }
            Row {
                spacing: Design.sp(1.25)
                Rectangle {
                    width: 5; height: 5; radius: 1
                    anchors.verticalCenter: parent.verticalCenter
                    color: spine._accent
                    opacity: 0.5 + 0.5 * Math.min(1.0, Design.coreEnergy * 1.4)
                    Behavior on color { ColorAnimation { duration: Design.stateXfade } }
                }
                Text {
                    text: spine._entry[0]
                    color: spine._accent
                    font.family: Design.fontMono
                    font.pixelSize: Design.fsSmall
                    font.weight: Design.wStatus
                    font.letterSpacing: Design.trkStatus
                    style: Text.Outline; styleColor: Design.textEdge
                    Behavior on color { ColorAnimation { duration: Design.stateXfade } }
                }
            }
        }

        Rectangle {   // regla
            width: parent.width; height: 1
            color: Design.stateWash(Design.hairline, 0.7)
            opacity: 0.35 + 0.25 * Design.breath()
        }

        // ── TELEMETRÍA en vivo (compacta) ──
        Column {
            width: parent.width
            spacing: 2
            Repeater {
                model: [["CPU", "cpu", "%"], ["RAM", "ram", "%"],
                        ["LAT", "latencyMs", " ms"], ["T/S", "tokensPerSecond", ""]]
                delegate: Row {
                    required property var modelData
                    width: parent.width
                    Text {
                        width: Design.sp(9)
                        text: modelData[0]
                        color: Design.textMeta
                        font.family: Design.fontMono
                        font.pixelSize: Design.fsMicro
                        font.letterSpacing: Design.trkLabel
                        style: Text.Outline; styleColor: Design.textEdge
                    }
                    Text {
                        text: spine._mm(modelData[1], modelData[2])
                        color: Design.litText(Design.textSecondary,
                                              spine.x + spine.width / 2, spine.y + 120)
                        font.family: Design.fontMono
                        font.pixelSize: Design.fsSmall
                        font.weight: Design.wValue
                        style: Text.Outline; styleColor: Design.textEdge
                    }
                }
            }
        }

        Rectangle {   // regla
            width: parent.width; height: 1
            color: Design.stateWash(Design.hairline, 0.7)
            opacity: 0.35 + 0.25 * Design.breath()
        }

        Text {
            text: "ESPINA · ENERGÍA"
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMicro
            font.letterSpacing: Design.trkLabel
            style: Text.Outline; styleColor: Design.textEdge
        }
    }

    // ── ESPINA: historial de energía como barras horizontales apiladas ──
    Column {
        id: bars
        anchors { left: parent.left; right: parent.right
                  leftMargin: Design.sp(2); rightMargin: Design.sp(2)
                  top: col.bottom; topMargin: Design.sp(1.5)
                  bottom: parent.bottom; bottomMargin: Design.sp(3) }
        spacing: 2
        // más reciente arriba: se recorre el buffer al revés
        Repeater {
            model: spine._cap
            delegate: Item {
                required property int index
                width: bars.width
                height: Math.max(2, (bars.height - (spine._cap - 1) * 2) / spine._cap)
                readonly property int _i: spine._hist.length - 1 - index
                readonly property real v: (_i >= 0 && _i < spine._hist.length)
                                          ? spine._hist[_i] : 0.0
                readonly property bool _fresh: index < 3
                // pista tenue de fondo
                Rectangle {
                    anchors.fill: parent
                    color: Design.stateWash(Design.hairline, 0.5)
                    opacity: 0.10
                }
                // barra de energía
                Rectangle {
                    height: parent.height
                    width: Math.max(1, parent.width * (0.06 + 0.94 * parent.v))
                    color: Design.mix(spine._accent, Design.coreHot,
                                      Math.min(0.5, parent.v * 0.6))
                    opacity: (parent._fresh ? 0.95 : 0.62) - 0.25 * (index / spine._cap)
                }
            }
        }
    }
}
