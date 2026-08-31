import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  CORE — el elemento que define el producto.
//
//  El dibujo está en GPU (CoreShader → core.frag). Aquí vive el cerebro: la
//  máquina de estados (cross-fade de 220 ms, nunca corte seco) y la traducción
//  de datos REALES del ViewModel a uniforms (energy/flux/bandas). Un ÚNICO
//  FrameAnimation global (`objectName: coreLoop`) mueve el tiempo; sin foco se
//  detiene y el layer del shader se congela (0 trabajo de GPU).
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: root

    // API pública (la fija Main.qml)
    property string coreState: "idle"
    property real   audioLevel: 0.0
    property var    spectrum: []
    property real   tokensPerSecond: 0.0
    property bool   loopRunning: true
    property bool   compact: false
    property bool   reducedMotion: false
    property point  pointer: Qt.point(0, 0)   // paralaje (reservado para Fase 4 del addendum)

    implicitWidth: 340
    implicitHeight: 340

    readonly property bool loopActive: loopRunning
        && (!reducedMotion || coreState === "listening" || coreState === "speaking")

    // ── parámetros por estado (interpolados) ──────────────────────────────
    property color pTint: Design.azure
    property real  pRingOpen: 0.0
    property real  pEmission: 0.45
    property real  pFragmented: 0.0
    property real  pDashed: 0.0
    property real  pConverge: 0.0        // 0 campo abierto · 1 concentrado (thinking)

    Behavior on pRingOpen   { CoreNum {} }
    Behavior on pEmission    { CoreNum {} }
    Behavior on pConverge    { CoreNum {} }
    Behavior on pFragmented  { CoreNum {} }
    Behavior on pDashed      { CoreNum {} }
    Behavior on pTint {
        ColorAnimation {
            duration: Design.stateXfade
            easing.type: Design.easeType
            easing.bezierCurve: Design.easeCurve
        }
    }
    component CoreNum: NumberAnimation {
        duration: Design.stateXfade
        easing.type: Design.easeType
        easing.bezierCurve: Design.easeCurve
    }

    state: root.coreState
    states: [
        State { name: "idle";      PropertyChanges { target: root
            pTint: Design.azure; pRingOpen: 0.35; pEmission: 0.42
            pFragmented: 0; pDashed: 0; pConverge: 0 } },
        State { name: "listening"; PropertyChanges { target: root
            pTint: Design.cyan; pRingOpen: 1.0; pEmission: 0.9
            pFragmented: 0; pDashed: 0; pConverge: 0 } },
        State { name: "thinking";  PropertyChanges { target: root
            pTint: Design.mix(Design.azure, Design.cyan, 0.5); pRingOpen: 0.62
            pEmission: 0.75; pFragmented: 0; pDashed: 0; pConverge: 1 } },
        State { name: "speaking";  PropertyChanges { target: root
            pTint: Design.cyan; pRingOpen: 0.7; pEmission: 1.0
            pFragmented: 0; pDashed: 0; pConverge: 0 } },
        State { name: "alert";     PropertyChanges { target: root
            pTint: Design.alert; pRingOpen: 0.3; pEmission: 0.0
            pFragmented: 1; pDashed: 0; pConverge: 0 } },
        State { name: "offline";   PropertyChanges { target: root
            pTint: Design.textMeta; pRingOpen: 0.0; pEmission: 0.0
            pFragmented: 0; pDashed: 1; pConverge: 0 } }
    ]

    // ── datos reales → energía del shader ─────────────────────────────────
    property real _t: 0
    property real _energy: 0
    property real _flux: 0
    property real _bLow: 0
    property real _bMid: 0
    property real _bHigh: 0

    function _targetEnergy() {
        if (coreState === "listening" || coreState === "speaking")
            return audioLevel                                  // RMS real
        if (coreState === "thinking")
            return Math.max(0, Math.min(1, tokensPerSecond / 18))
        if (coreState === "alert" || coreState === "offline")
            return 0.0
        // idle: respiración subliminal, deliberada — no aleatoria
        return 0.05 + 0.035 * (0.5 + 0.5 * Math.sin(_t * 0.5))
    }
    function _bands() {
        var s = spectrum
        if (!s || !s.length) return [0, 0, 0]
        var n = s.length, a = 0, b = 0, c = 0, ka = 0, kb = 0, kc = 0
        for (var i = 0; i < n; i++) {
            var f = i / n
            if (f < 0.33) { a += s[i]; ka++ }
            else if (f < 0.66) { b += s[i]; kb++ }
            else { c += s[i]; kc++ }
        }
        return [ka ? a / ka : 0, kb ? b / kb : 0, kc ? c / kc : 0]
    }

    FrameAnimation {
        objectName: "coreLoop"          // único bucle; hud_perfcheck lo cuenta
        running: root.loopActive
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)
            root._t += (root.reducedMotion ? 0 : dt)
            var e = root._targetEnergy()
            var k = Math.min(1, dt * 9)
            var prev = root._energy
            root._energy += (e - prev) * k
            root._flux += (Math.min(1, Math.abs(e - prev) * 7
                           + (root.coreState === "thinking"
                              ? root.tokensPerSecond / 40 : 0)) - root._flux) * 0.15
            var bands = root._bands()
            root._bLow  += (bands[0] - root._bLow) * k
            root._bMid  += (bands[1] - root._bMid) * k
            root._bHigh += (bands[2] - root._bHigh) * k
        }
    }

    CoreShader {
        id: shader
        anchors.fill: parent
        time: root._t
        energy: root._energy
        flux: root._flux
        ringOpen: root.pRingOpen * (1.0 - 0.35 * root.pConverge)
        emission: root.pEmission
        bandLow: root._bLow
        bandMid: root._bMid
        bandHigh: root._bHigh
        fragmented: root.pFragmented
        dashed: root.pDashed
        reduced: root.reducedMotion ? 1 : 0
        compact: root.compact ? 1 : 0
        tint: root.pTint
        layer.live: root.loopActive
    }
}
