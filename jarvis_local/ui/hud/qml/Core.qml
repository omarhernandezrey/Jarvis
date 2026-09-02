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
    property bool   degraded: false           // §7: sin bloom, sólo el shader
    property point  pointer: Qt.point(0, 0)   // paralaje (reservado)
    property real   bootIgnite: 1.0           // 0→1: el núcleo se enciende desde un punto

    implicitWidth: 340
    implicitHeight: 340

    // arranque: pop-in desde un punto con un leve rebasamiento
    scale: {
        if (bootIgnite >= 1.0) return 1.0
        var b = bootIgnite
        var over = 1.0 + 0.10 * Math.sin(b * Math.PI)      // rebasa y vuelve
        return (0.06 + 0.94 * (b * b * (3.0 - 2.0 * b))) * over
    }
    opacity: Math.min(1.0, bootIgnite * 3.0)

    readonly property bool loopActive: loopRunning
        && (!reducedMotion || coreState === "listening" || coreState === "speaking")

    // ── iluminación global (addendum §4): el núcleo publica su luz ──────────
    // Cada hairline/borde/panel del sistema deriva su color de aquí.
    function _publishPos() {
        Design.corePos = mapToItem(null, width / 2, height / 2)
    }
    onXChanged: _publishPos()
    onYChanged: _publishPos()
    onWidthChanged: _publishPos()
    onHeightChanged: _publishPos()
    Component.onCompleted: _publishPos()
    Binding { target: Design; property: "coreEnergy";    value: root._energy }
    Binding { target: Design; property: "coreTint";      value: root.pTint }
    Binding { target: Design; property: "pulse";         value: root._pulse }
    Binding { target: Design; property: "coreStateName"; value: root.coreState }

    // ── onda de choque en el cambio de estado (Fase 7) ────────────────────
    // Un frente sale del centro y se disipa en ~650 ms. Es una REACCIÓN, no
    // un bucle: se dispara una vez por transición.
    property real _transPhase: 0
    onCoreStateChanged: { transAnim.restart(); hudWave.restart() }
    SequentialAnimation {
        id: transAnim
        PropertyAction { target: root; property: "_transPhase"; value: 1.0 }
        NumberAnimation { target: root; property: "_transPhase"
            to: 0.0; duration: 650; easing.type: Easing.OutCubic }
    }
    // frente de reacción que recorre el HUD (Fase 11): mismo disparo que la
    // onda de choque del shader, pero para la interfaz.
    SequentialAnimation {
        id: hudWave
        PropertyAction { target: Design; property: "waveFront"; value: 0.0 }
        NumberAnimation { target: Design; property: "waveFront"
            to: 1.0; duration: Design.stateXfade * 3.6; easing.type: Easing.OutCubic }
    }

    // ── parámetros por estado (interpolados) ──────────────────────────────
    //  Fase 6: cada estado tiene TINTE (rampa azul→cian), TINTE PROFUNDO del
    //  limbo, y VELOCIDAD DE GIRO (spin) propia. El casi-blanco NO es un
    //  estado — es un highlight que pinta el shader en el punto del centro.
    property color pTint:      Design.mix(Design.azure, Design.coreDeep, 0.35)
    property color pTintDeep:  Design.coreDeep
    property real  pSpin:      0.30
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
    Behavior on pSpin        { CoreNum {} }
    Behavior on pTint     { CoreCol {} }
    Behavior on pTintDeep { CoreCol {} }
    component CoreNum: NumberAnimation {
        duration: Design.stateXfade
        easing.type: Design.easeType
        easing.bezierCurve: Design.easeCurve
    }
    component CoreCol: ColorAnimation {
        duration: Design.stateXfade
        easing.type: Design.easeType
        easing.bezierCurve: Design.easeCurve
    }

    state: root.coreState
    states: [
        // IDLE — azul eléctrico profundo, giro lentísimo: "está aquí, esperando"
        State { name: "idle";      PropertyChanges { target: root
            pTint: Design.mix(Design.azure, Design.coreDeep, 0.35)
            pTintDeep: Design.coreDeep; pSpin: 0.30
            pRingOpen: 0.35; pEmission: 0.42
            pFragmented: 0; pDashed: 0; pConverge: 0 } },
        // LISTENING — cian eléctrico, giro sensible
        State { name: "listening"; PropertyChanges { target: root
            pTint: Design.cyan
            pTintDeep: Design.mix(Design.azure, Design.coreDeep, 0.3); pSpin: 0.85
            pRingOpen: 1.0; pEmission: 0.9
            pFragmented: 0; pDashed: 0; pConverge: 0 } },
        // THINKING — cian + azul, giro concentrado, campo convergido
        State { name: "thinking";  PropertyChanges { target: root
            pTint: Design.mix(Design.azure, Design.cyan, 0.45)
            pTintDeep: Design.coreDeep; pSpin: 0.55
            pRingOpen: 0.62; pEmission: 0.75
            pFragmented: 0; pDashed: 0; pConverge: 1 } },
        // SPEAKING — cian; el shader añade los highlights blancos del centro
        State { name: "speaking";  PropertyChanges { target: root
            pTint: Design.cyan
            pTintDeep: Design.mix(Design.azure, Design.coreDeep, 0.25); pSpin: 0.70
            pRingOpen: 0.7; pEmission: 1.0
            pFragmented: 0; pDashed: 0; pConverge: 0 } },
        // EXECUTING — cian FRÍO tirando a azul (instrumento), giro rápido y
        // preciso, campo semiabierto. Distinto de speaking por color, geometría
        // y ritmo. No toca dashed/fragmented (reservados a offline/alert).
        State { name: "executing"; PropertyChanges { target: root
            pTint: Design.mix(Design.cyan, Design.azure, 0.35)
            pTintDeep: Design.mix(Design.coreDeep, Design.azure, 0.4); pSpin: 1.15
            pRingOpen: 0.46; pEmission: 0.92
            pFragmented: 0; pDashed: 0; pConverge: 0.4 } },
        State { name: "alert";     PropertyChanges { target: root
            pTint: Design.alert
            pTintDeep: Design.mix(Design.alert, Design.coreDeep, 0.5); pSpin: 0.4
            pRingOpen: 0.3; pEmission: 0.0
            pFragmented: 1; pDashed: 0; pConverge: 0 } },
        State { name: "offline";   PropertyChanges { target: root
            pTint: Design.textDisabled
            pTintDeep: Qt.rgba(0.04, 0.08, 0.14, 1.0); pSpin: 0.0
            pRingOpen: 0.0; pEmission: 0.0
            pFragmented: 0; pDashed: 1; pConverge: 0 } }
    ]

    // ── datos reales → energía del shader ─────────────────────────────────
    property real _t: 0
    property real _energy: 0
    property real _flux: 0
    property real _bLow: 0
    property real _bMid: 0
    property real _bHigh: 0
    property real _pulse: 0.5      // latido compartido del HUD (respiración + corazón)

    function _targetEnergy() {
        if (coreState === "listening" || coreState === "speaking")
            return audioLevel                                  // RMS real
        if (coreState === "thinking")
            return Math.max(0, Math.min(1, tokensPerSecond / 18))
        if (coreState === "executing")
            // sin dato de progreso real (la herramienta ya corrió, síncrona):
            // un pulso de trabajo más rápido que la respiración de idle, para
            // no fingir una métrica que no existe.
            return 0.35 + 0.15 * (0.5 + 0.5 * Math.sin(_t * 3.2))
        if (coreState === "alert" || coreState === "offline")
            return 0.0
        // idle: PRESENCIA. Dos capas:
        //  · respiración — suma de dos senos lentos inconmensurables (batido
        //    ~30 s, no se repite de forma obvia). Amplitud mínima.
        //  · latido digital — cada ~5.2 s un "lub-dub" muy sutil (dos golpes
        //    exponenciales seguidos y luego silencio). Señal de vida, no
        //    parpadeo. Sólo en reposo.
        var breathe = 0.014 * Math.sin(_t * 0.42)
                    + 0.009 * Math.sin(_t * 0.23 + 1.3)
        var hp = _t / 5.2 - Math.floor(_t / 5.2)          // fase 0..1 del latido
        var beat = 0.028 * Math.exp(-hp * 26.0)
                 + 0.018 * Math.exp(-Math.pow(hp - 0.16, 2.0) * 90.0)
        return 0.050 + breathe + beat + 0.10 * Design.attention
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

    // El único FrameAnimation vive en Main.qml y alimenta `time`; aquí sólo se
    // suaviza la traducción datos-reales → uniforms en cada avance de reloj.
    property real time: 0
    property real _prevT: 0
    onTimeChanged: {
        var dt = Math.min(Math.max(time - _prevT, 0.0), 0.05)
        _prevT = time
        if (dt <= 0) return
        root._t += (root.reducedMotion ? 0 : dt)

        // latido compartido del HUD: respiración lenta con amplitud modulada
        // (no se repite de forma obvia) + un golpe cardiaco cada ~5,2 s.
        // Siempre activo, no depende del estado: la interfaz nunca se "muere".
        var _br = 0.5 + 0.5 * Math.sin(root._t * 0.42)
                        * (0.72 + 0.28 * Math.sin(root._t * 0.17 + 0.6))
        var _hb = root._t / 5.2 - Math.floor(root._t / 5.2)
        var _beat = Math.exp(-_hb * 20.0) * 0.7
                  + Math.exp(-Math.pow(_hb - 0.15, 2.0) * 130.0) * 0.5
        root._pulse = Math.max(0.0, Math.min(1.0, 0.30 + 0.55 * _br + 0.14 * _beat))

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

    CoreBloom {
        id: shader
        // margen para que el bloom pueda extenderse más allá del orbe
        anchors.fill: parent
        anchors.margins: -Math.round(Math.min(parent.width, parent.height) * 0.13)
        // durante el encendido, un destello que sube y baja
        readonly property real _ignitePulse: root.bootIgnite < 1.0
            ? Math.sin(root.bootIgnite * Math.PI) : 0.0
        time: root._t
        energy: Math.max(root._energy, 0.15 + 0.8 * _ignitePulse)
        flux: root._flux
        ringOpen: root.pRingOpen * (1.0 - 0.35 * root.pConverge)
        emission: root.pEmission + 0.45 * _ignitePulse
        bandLow: root._bLow
        bandMid: root._bMid
        bandHigh: root._bHigh
        fragmented: root.pFragmented
        dashed: root.pDashed
        reduced: root.reducedMotion ? 1 : 0
        compact: root.compact ? 1 : 0
        tint: root.pTint
        tintDeep: root.pTintDeep
        tintHot: Design.coreHot           // highlight constante (misma rampa)
        spin: root.pSpin
        pointerX: root.pointer.x
        pointerY: root.pointer.y
        transPhase: root._transPhase
        live: root.loopActive
        bypass: root.degraded
    }
}
