import QtQuick

// Atmósfera global (addendum §2): viñeta + grano temporal + aberración
// cromática hacia los bordes. Se usa como `layer.effect` de toda la escena;
// Qt inyecta la textura de la escena en `source`.
ShaderEffect {
    id: atmo
    property var source                       // lo inyecta layer.effect
    property real time: 0                     // reloj cuantizado; 0 congela el grano
    property real grainAmt: 0.026
    property real vignette: 0.30
    property real aberration: 1.2             // px máximos en la esquina
    property real cornerRadius: 0             // px — esquinas de la ventana sin marco
    property vector2d texel: Qt.vector2d(1.0 / Math.max(1, width),
                                         1.0 / Math.max(1, height))
    fragmentShader: Qt.resolvedUrl("../shaders/atmosphere.frag.qsb")
}
