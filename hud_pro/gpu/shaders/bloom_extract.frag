#version 330 core
// Extracción de brillos (primer paso del bloom dual-Kawase): igual regla
// que el orbe raster (hud_pro/orb.py) y el núcleo QML original — un umbral
// con "knee" suave, nunca el cuerpo entero.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;
uniform float u_threshold;  // 0..1
uniform float u_knee;       // suavizado del umbral

void main() {
    vec3 c = texture(u_source, vUv).rgb;
    float b = max(c.r, max(c.g, c.b));
    float w = smoothstep(u_threshold, u_threshold + max(u_knee, 1e-4), b);
    fragColor = vec4(c * w, 1.0);
}
