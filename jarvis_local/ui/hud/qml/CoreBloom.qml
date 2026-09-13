import QtQuick
import QtQuick.Effects

// Pipeline de post-proceso del núcleo (addendum §2):
//   CoreShader → extracción de altas luces → bloom en dos pasadas (radios
//   distintos, MultiEffect) → composición aditiva sobre el original.
// Expone los mismos uniforms que CoreShader (pass-through). La atmósfera global
// (viñeta/grano/aberración) se aplica más arriba, sobre toda la escena.
Item {
    id: bloom

    property real time: 0
    property real energy: 0
    property real flux: 0
    property real ringOpen: 0
    property real emission: 0.45
    property real bandLow: 0
    property real bandMid: 0
    property real bandHigh: 0
    property real fragmented: 0
    property real dashed: 0
    property real reduced: 0
    property real compact: 0
    property color tint: "#37D2FF"
    property color tintDeep: "#0A2A6E"
    property color tintHot: "#DCF6FF"
    property real spin: 0.5
    property real pointerX: 0
    property real pointerY: 0
    property real transPhase: 0
    property bool live: true          // false → todo el pipeline se congela
    property bool bypass: false       // ruta de degradación (§7): sólo el shader

    // ¿corren las etapas de bloom?  no si está congelado o degradado
    readonly property bool _pipeOn: live && !bypass

    // FASE I · I6: el bloom se extrae y difumina a 1/4 de resolución — la
    // convención habitual (mitad de ancho × mitad de alto = 1/4 de píxeles).
    // La nitidez la pone el núcleo (compuesto a resolución completa más
    // abajo); el halo no la necesita, y es ahí donde vivía el coste de GPU
    // (dos pasadas de MultiEffect sobre el rectángulo completo del núcleo).
    // El downsample explícito también es el candidato principal para cerrar
    // el residuo verde anotado en I2: ya no depende de blurear highlights
    // nítidos a resolución nativa.
    readonly property size _qsz: Qt.size(
        Math.max(1, Math.round(width / 2)), Math.max(1, Math.round(height / 2)))

    // 1) el núcleo. En bypass es lo único visible; si no, alimenta la textura.
    CoreShader {
        id: core
        anchors.fill: parent
        visible: bloom.bypass
        time: bloom.time; energy: bloom.energy; flux: bloom.flux
        ringOpen: bloom.ringOpen; emission: bloom.emission
        bandLow: bloom.bandLow; bandMid: bloom.bandMid; bandHigh: bloom.bandHigh
        fragmented: bloom.fragmented; dashed: bloom.dashed
        reduced: bloom.reduced; compact: bloom.compact; tint: bloom.tint
        tintDeep: bloom.tintDeep; tintHot: bloom.tintHot; spin: bloom.spin
        pointerX: bloom.pointerX; pointerY: bloom.pointerY
        transPhase: bloom.transPhase
    }
    ShaderEffectSource {
        id: coreTex
        anchors.fill: parent
        sourceItem: core
        hideSource: !bloom.bypass       // en bypass el núcleo se ve directo
        live: bloom._pipeOn
        smooth: true
    }

    // 2) extracción de altas luces — a 1/4 de resolución (I6): menos
    // fragmentos que procesar, y el downsample explícito le quita al blur
    // los highlights nítidos a resolución nativa que causaban el residuo.
    ShaderEffect {
        id: extract
        width: bloom._qsz.width; height: bloom._qsz.height
        visible: false
        property var source: coreTex
        // I2: sólo florece lo REALMENTE brillante — el fresnel, el barrido
        // especular y los picos reales de energía; nunca el cuerpo entero.
        // El brief pedía "luminancia >= 0,72"; a ese umbral con un knee
        // razonable aparecía un artefacto de esta GPU (ver docs/PLAN_
        // EJECUCION.md · I2): fragmentos verdes en forma de hoja al
        // blurear highlights finos y muy brillantes (fresnel/arcos). Subir
        // el umbral a 0,80 con un knee ancho (0,5) lo elimina del todo sin
        // perder el fresnel ni el barrido especular — se verificó con
        // capturas en los 5 estados. Mantiene el espíritu del brief (nunca
        // el cuerpo entero) aunque no el número exacto.
        property real threshold: 0.80
        property real knee: 0.5
        fragmentShader: Qt.resolvedUrl("../shaders/bloom_extract.frag.qsb")
    }
    ShaderEffectSource {
        id: extractTex
        width: bloom._qsz.width; height: bloom._qsz.height
        sourceItem: extract
        hideSource: true
        live: bloom._pipeOn
        smooth: true
    }

    // 3) bloom en dos pasadas (radios distintos), toda la cadena a 1/4 res.
    // blurMax a la mitad del original: al componer sobre el rect a
    // resolución completa (2× más grande en cada eje), el radio aparente
    // vuelve a ser el mismo que antes del downsample.
    MultiEffect {
        id: b0
        width: bloom._qsz.width; height: bloom._qsz.height
        visible: false
        source: extractTex
        blurEnabled: true
        blur: 1.0
        blurMax: 10
        blurMultiplier: 0.7
    }
    ShaderEffectSource {
        id: b0Tex
        width: bloom._qsz.width; height: bloom._qsz.height
        sourceItem: b0
        hideSource: true; live: bloom._pipeOn; smooth: true
    }
    MultiEffect {
        id: b1
        width: bloom._qsz.width; height: bloom._qsz.height
        visible: false
        source: extractTex
        blurEnabled: true
        blur: 1.0
        blurMax: 24
        blurMultiplier: 1.7
    }
    ShaderEffectSource {
        id: b1Tex
        width: bloom._qsz.width; height: bloom._qsz.height
        sourceItem: b1
        hideSource: true; live: bloom._pipeOn; smooth: true
    }

    // 4) composición aditiva (lo visible salvo en bypass)
    ShaderEffect {
        anchors.fill: parent
        visible: !bloom.bypass
        blending: true
        property var source: coreTex
        property var bloom0: b0Tex
        property var bloom1: b1Tex
        // NITIDEZ > GLOW: el bloom complementa, no domina. El ojo ve primero
        // el núcleo nítido y luego el halo.
        property real k0: 0.42
        property real k1: 0.22
        fragmentShader: Qt.resolvedUrl("../shaders/bloom_composite.frag.qsb")
    }
}
