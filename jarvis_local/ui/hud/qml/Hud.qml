import QtQuick
import "."

// Banda densa de telemetría. Todo dato viene de `Vm.metrics` (muestreo real en
// services.py). Sin tarjetas: cada celda es etiqueta + valor + regla. El
// modelo del Repeater es una lista de CLAVES constante: los delegados persisten
// y sólo re-evalúan sus bindings cuando cambia `m` (sin churn de delegados).
Item {
    id: hud
    property var m: Vm ? Vm.metrics : ({})
    property bool vertical: false

    readonly property var keys: ["SISTEMA", "MODELO", "CPU", "RAM", "LATENCIA",
                                 "TOKENS/S", "VOZ", "MEMORIA", "HERRAMIENTAS"]

    implicitHeight: vertical ? content.implicitHeight : Design.sp(15)
    implicitWidth: vertical ? Design.sp(40) : content.implicitWidth

    function _has(v) { return v !== undefined && v !== null }

    // (absent, value, accent) para una clave dada, a partir de `m`
    function cell(key) {
        var mm = hud.m || {}
        switch (key) {
        case "SISTEMA":
            return [!_has(mm.online), mm.online ? "EN LÍNEA" : "SIN CONEXIÓN",
                    mm.online ? Design.ok : Design.alert]
        case "MODELO":
            return [!_has(mm.model), mm.model || "", Design.textPrimary]
        case "CPU":
            return [!_has(mm.cpu), _has(mm.cpu) ? Math.round(mm.cpu) + "%" : "",
                    _has(mm.cpu) && mm.cpu > 85 ? Design.warn : Design.textPrimary]
        case "RAM":
            return [!_has(mm.ram), _has(mm.ram) ? Math.round(mm.ram) + "%" : "",
                    _has(mm.ram) && mm.ram > 90 ? Design.warn : Design.textPrimary]
        case "LATENCIA":
            return [!_has(mm.latencyMs), _has(mm.latencyMs) ? mm.latencyMs + " ms" : "",
                    Design.textPrimary]
        case "TOKENS/S":
            return [!_has(mm.tokensPerSecond),
                    _has(mm.tokensPerSecond) ? mm.tokensPerSecond.toFixed(1) : "",
                    Design.cyan]
        case "VOZ":
            return [!_has(mm.voice),
                    mm.voice ? ((mm.voice.tts ? "LISTA" : "OFF")
                        + (mm.voice.mic === "available" ? ""
                           : mm.voice.mic === "denied" ? " · sin permiso" : " · sin mic")) : "",
                    mm.voice && mm.voice.tts ? Design.ok : Design.textSecondary]
        case "MEMORIA":
            return [!_has(mm.memory),
                    mm.memory ? ((mm.memory.auto_recall ? "ACTIVA" : "INACTIVA")
                        + (_has(mm.memory.count) ? " · " + mm.memory.count : "")) : "",
                    mm.memory && mm.memory.auto_recall ? Design.ok : Design.textSecondary]
        case "HERRAMIENTAS":
            return [!(mm.tools && _has(mm.tools.count)),
                    mm.tools && _has(mm.tools.count)
                        ? (mm.tools.count + (mm.tools.agent ? "" : " · parser")) : "",
                    Design.textPrimary]
        }
        return [true, "", Design.textPrimary]
    }

    Flow {
        id: content
        anchors.fill: parent
        flow: hud.vertical ? Flow.TopToBottom : Flow.LeftToRight
        spacing: hud.vertical ? Design.sp(2) : Design.sp(7)
        Repeater {
            model: hud.keys
            delegate: HudCell {
                required property string modelData
                property var c: hud.cell(modelData)   // re-evalúa al cambiar hud.m
                label: modelData
                absent: c[0]
                value: c[1]
                accent: c[2]
                vertical: hud.vertical
            }
        }
    }
}
