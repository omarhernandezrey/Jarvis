#version 330 core
// Polvo bokeh: ~300 point sprites en 3 capas de profundidad, deriva
// analítica en el propio shader (nunca actualizado por CPU cada frame) —
// point sprites instanciados vía VBO, no un bucle por píxel.
layout(location = 0) in vec4 aData;  // x0, y0 (0..1), capa (0..2), fase (0..1)

uniform float u_time;

out float vAlpha;
out float vLayer;

void main() {
    float layer = aData.z;      // 0 = fondo (lento, chico), 2 = frente (rápido, grande)
    float speed = mix(0.010, 0.045, layer / 2.0);
    vec2 pos = aData.xy;
    pos.x = fract(pos.x + u_time * speed + aData.w);
    pos.y = fract(pos.y + u_time * speed * 0.4);
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
    gl_PointSize = mix(2.0, 6.0, layer / 2.0);
    vAlpha = mix(0.08, 0.30, layer / 2.0);
    vLayer = layer;
}
