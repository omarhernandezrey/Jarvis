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
    property color tint: "#2B7FFF"
    property bool live: true          // false → todo el pipeline se congela
    property bool bypass: false       // ruta de degradación (§7): sólo el shader

    // ¿corren las etapas de bloom?  no si está congelado o degradado
    readonly property bool _pipeOn: live && !bypass

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
    }
    ShaderEffectSource {
        id: coreTex
        anchors.fill: parent
        sourceItem: core
        hideSource: !bloom.bypass       // en bypass el núcleo se ve directo
        live: bloom._pipeOn
        smooth: true
    }

    // 2) extracción de altas luces
    ShaderEffect {
        id: extract
        anchors.fill: parent
        visible: false
        property var source: coreTex
        // umbral más alto → sólo florece lo REALMENTE brillante (menos halo
        // general que difumina la lectura del núcleo).
        property real threshold: 0.54
        property real knee: 0.22
        fragmentShader: Qt.resolvedUrl("../shaders/bloom_extract.frag.qsb")
    }
    ShaderEffectSource {
        id: extractTex
        anchors.fill: parent
        sourceItem: extract
        hideSource: true
        live: bloom._pipeOn
        smooth: true
    }

    // 3) bloom en dos pasadas (radios distintos)
    MultiEffect {
        id: b0
        anchors.fill: parent
        visible: false
        source: extractTex
        blurEnabled: true
        blur: 1.0
        blurMax: 20
        blurMultiplier: 0.7
    }
    ShaderEffectSource {
        id: b0Tex; anchors.fill: parent; sourceItem: b0
        hideSource: true; live: bloom._pipeOn; smooth: true
    }
    MultiEffect {
        id: b1
        anchors.fill: parent
        visible: false
        source: extractTex
        blurEnabled: true
        blur: 1.0
        blurMax: 48
        blurMultiplier: 1.7
    }
    ShaderEffectSource {
        id: b1Tex; anchors.fill: parent; sourceItem: b1
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
