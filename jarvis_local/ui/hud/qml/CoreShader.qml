import QtQuick

// Envoltorio GPU del núcleo. Todo el dibujo vive en `../shaders/core.frag.qsb`
// (campo de interferencia + volumen SDF + especular anisótropo). Este archivo
// solo expone los uniforms; el cerebro (máquina de estados, datos reales) está
// en Core.qml. `layer.*` da MSAA y permite congelar el render sin foco.
ShaderEffect {
    id: fx

    property real time: 0
    property real energy: 0            // 0..1 agregado real
    property real flux: 0             // 0..1 ritmo
    property real ringOpen: 0
    property real emission: 0.45
    property real bandLow: 0
    property real bandMid: 0
    property real bandHigh: 0
    property real fragmented: 0        // 0/1
    property real dashed: 0            // 0/1
    property real aspect: width / Math.max(1, height)
    property real reduced: 0           // 0/1
    property real compact: 0           // 0/1
    property color tint: "#2B7FFF"

    fragmentShader: Qt.resolvedUrl("../shaders/core.frag.qsb")
    blending: true

    layer.enabled: true
    layer.samples: 4          // silueta/anillos más limpios (antes 2 = aristas)
    layer.smooth: true
    // sin foco / minimizada: el layer no se re-renderiza (0 trabajo de GPU)
    layer.live: true
}
