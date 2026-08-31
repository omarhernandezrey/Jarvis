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

    // 1) el núcleo, oculto: sólo alimenta la textura
    CoreShader {
        id: core
        anchors.fill: parent
        visible: false
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
        hideSource: true
        live: bloom.live
        smooth: true
    }

    // 2) extracción de altas luces
    ShaderEffect {
        id: extract
        anchors.fill: parent
        visible: false
        property var source: coreTex
        property real threshold: 0.42
        property real knee: 0.28
        fragmentShader: Qt.resolvedUrl("../shaders/bloom_extract.frag.qsb")
    }
    ShaderEffectSource {
        id: extractTex
        anchors.fill: parent
        sourceItem: extract
        hideSource: true
        live: bloom.live
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
        hideSource: true; live: bloom.live; smooth: true
    }
    MultiEffect {
        id: b1
        anchors.fill: parent
        visible: false
        source: extractTex
        blurEnabled: true
        blur: 1.0
        blurMax: 64
        blurMultiplier: 2.2
    }
    ShaderEffectSource {
        id: b1Tex; anchors.fill: parent; sourceItem: b1
        hideSource: true; live: bloom.live; smooth: true
    }

    // 4) composición aditiva (lo único visible)
    ShaderEffect {
        anchors.fill: parent
        blending: true
        property var source: coreTex
        property var bloom0: b0Tex
        property var bloom1: b1Tex
        property real k0: 0.95
        property real k1: 0.7
        fragmentShader: Qt.resolvedUrl("../shaders/bloom_composite.frag.qsb")
    }
}
