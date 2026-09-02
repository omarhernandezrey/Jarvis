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

    // etiquetas en minúscula: la etiqueta susurra, el valor (24 px) domina.
    // La lista es configurable: Fase 4 la parte en dos clústeres flotantes
    // (identidad arriba · métricas en vivo abajo).
    property var keys: ["sistema", "modelo", "cpu", "ram", "latencia",
                        "tokens/s", "voz", "memoria", "herramientas"]

    // Fila de widgets. `Row.implicitWidth` = suma real (sin la circularidad
    // que tenía `Flow` bindeado a su propio ancho → se colapsaba en columna).
    implicitHeight: content.implicitHeight
    implicitWidth: content.implicitWidth

    function _has(v) { return v !== undefined && v !== null }

    // código de índice técnico por clave (anotación tipo HUD de cabina)
    function _tag(key) {
        return ({ "sistema": "SYS", "modelo": "MDL", "voz": "VOX", "memoria": "MEM",
                  "herramientas": "TLS", "cpu": "CPU", "ram": "RAM",
                  "latencia": "LAT", "tokens/s": "T/S" })[key] || ""
    }

    // Umbral → color vivo (verde bien · ámbar medio · rojo mal).
    function _grade(v, warnAt, badAt) {
        if (v === undefined || v === null) return Design.sky
        if (v >= badAt)  return Design.alert
        if (v >= warnAt) return Design.warn
        return Design.ok
    }

    // [absent, value, SIGNATURE, VALUE] — cada widget tiene un color de firma
    // vivo permanente (barra + borde); el color del VALOR sigue el estado.
    function cell(key) {
        var mm = hud.m || {}
        switch (key) {
        case "sistema": {
            var on = !!mm.online
            return [!_has(mm.online), on ? "EN LÍNEA" : "SIN CONEXIÓN",
                    on ? Design.ok : Design.alert, on ? Design.ok : Design.alert]
        }
        case "modelo":
            return [!_has(mm.model), mm.model || "", Design.sky, Design.sky]
        case "cpu":
            return [!_has(mm.cpu), _has(mm.cpu) ? Math.round(mm.cpu) + "%" : "",
                    Design.sky, _grade(mm.cpu, 70, 90)]
        case "ram":
            return [!_has(mm.ram), _has(mm.ram) ? Math.round(mm.ram) + "%" : "",
                    Design.sky, _grade(mm.ram, 75, 92)]
        case "latencia":
            return [!_has(mm.latencyMs), _has(mm.latencyMs) ? mm.latencyMs + " ms" : "",
                    Design.amber, _grade(mm.latencyMs, 1500, 8000)]
        case "tokens/s":
            return [!_has(mm.tokensPerSecond),
                    _has(mm.tokensPerSecond) ? mm.tokensPerSecond.toFixed(1) : "",
                    Design.acidLime, Design.acidLime]
        case "voz": {
            var vt = mm.voice ? !!mm.voice.tts : false
            var mic = mm.voice ? mm.voice.mic : "absent"
            var vv = vt ? Design.ok
                   : mic === "denied" ? Design.alert : Design.textDisabled
            return [!_has(mm.voice),
                    mm.voice ? ((vt ? "LISTA" : "OFF")
                        + (mic === "available" ? "" : mic === "denied"
                           ? " · SIN PERMISO" : " · SIN MIC")) : "",
                    Design.magenta, vv]
        }
        case "memoria": {
            var ar = mm.memory ? !!mm.memory.auto_recall : false
            return [!_has(mm.memory),
                    mm.memory ? ((ar ? "ACTIVA" : "INACTIVA")
                        + (_has(mm.memory.count) ? " · " + mm.memory.count : "")) : "",
                    Design.violet, ar ? Design.violet : Design.textDisabled]
        }
        case "herramientas":
            return [!(mm.tools && _has(mm.tools.count)),
                    mm.tools && _has(mm.tools.count)
                        ? (mm.tools.count + (mm.tools.agent ? "" : " · PARSER")) : "",
                    Design.amber, Design.amber]
        }
        return [true, "", Design.sky, Design.sky]
    }

    Row {
        id: content
        anchors.verticalCenter: parent.verticalCenter
        spacing: Design.sp(2.5)
        Repeater {
            model: hud.keys
            delegate: HudCell {
                required property string modelData
                required property int index
                property var c: hud.cell(modelData)   // re-evalúa al cambiar hud.m
                label: modelData
                tag: hud._tag(modelData)
                absent: c[0]
                value: c[1]
                accent: c[2]
                valueColor: c[3]
                vertical: hud.vertical
                ordinal: index                        // entrada escalonada
                // "SYSTEM ONLINE" no es un LED fijo: late con el núcleo
                pulse: modelData === "sistema" && !c[0]
                       && hud.m !== undefined && hud.m.online === true
            }
        }
    }
}
