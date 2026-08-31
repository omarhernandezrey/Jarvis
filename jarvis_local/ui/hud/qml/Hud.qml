import QtQuick
import "."

// Banda densa de telemetría. Todo dato viene de `Vm.metrics` (muestreo real
// cada 2 s en services.py). Sin tarjetas: cada celda es etiqueta + valor +
// regla. `vertical` reorganiza la banda como columna lateral (Fase 6).
Item {
    id: hud
    property var m: Vm ? Vm.metrics : ({})
    property bool vertical: false

    implicitHeight: vertical ? content.implicitHeight : Design.sp(15)
    implicitWidth: vertical ? Design.sp(40) : content.implicitWidth

    function _has(v) { return v !== undefined && v !== null }
    function _pct(v) { return _has(v) ? Math.round(v) + "%" : "" }

    readonly property var cells: [
        {
            label: "SISTEMA",
            absent: !_has(m.online),
            value: m.online ? "EN LÍNEA" : "SIN CONEXIÓN",
            accent: m.online ? Design.ok : Design.alert
        },
        {
            label: "MODELO",
            absent: !_has(m.model),
            value: m.model || "",
            accent: Design.textPrimary
        },
        {
            label: "CPU",
            absent: !_has(m.cpu),
            value: _pct(m.cpu),
            accent: _has(m.cpu) && m.cpu > 85 ? Design.warn : Design.textPrimary
        },
        {
            label: "RAM",
            absent: !_has(m.ram),
            value: _pct(m.ram),
            accent: _has(m.ram) && m.ram > 90 ? Design.warn : Design.textPrimary
        },
        {
            label: "LATENCIA",
            absent: !_has(m.latencyMs),
            value: _has(m.latencyMs) ? m.latencyMs + " ms" : "",
            accent: Design.textPrimary
        },
        {
            label: "TOKENS/S",
            absent: !_has(m.tokensPerSecond),
            value: _has(m.tokensPerSecond) ? m.tokensPerSecond.toFixed(1) : "",
            accent: Design.cyan
        },
        {
            label: "VOZ",
            absent: !_has(m.voice),
            value: m.voice ? ((m.voice.tts ? "LISTA" : "OFF")
                   + (m.voice.mic === "available" ? "" :
                      m.voice.mic === "denied" ? " · sin permiso" : " · sin mic")) : "",
            accent: m.voice && m.voice.tts ? Design.ok : Design.textSecondary
        },
        {
            label: "MEMORIA",
            absent: !_has(m.memory),
            value: m.memory ? ((m.memory.auto_recall ? "ACTIVA" : "INACTIVA")
                   + (_has(m.memory.count) ? " · " + m.memory.count : "")) : "",
            accent: m.memory && m.memory.auto_recall ? Design.ok : Design.textSecondary
        },
        {
            label: "HERRAMIENTAS",
            absent: !(m.tools && _has(m.tools.count)),
            value: m.tools && _has(m.tools.count)
                   ? (m.tools.count + (m.tools.agent ? "" : " · parser")) : "",
            accent: Design.textPrimary
        }
    ]

    Flow {
        id: content
        anchors.fill: parent
        flow: hud.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: hud.vertical ? Design.sp(2) : Design.sp(7)
        Repeater {
            model: hud.cells
            delegate: HudCell {
                required property var modelData
                label: modelData.label
                value: modelData.value
                absent: modelData.absent
                accent: modelData.accent
                vertical: hud.vertical
            }
        }
    }
}
