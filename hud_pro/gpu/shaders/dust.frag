#version 330 core
// Sprite bokeh: círculo suave vía gl_PointCoord — sin textura, un solo
// smoothstep por fragmento (el sprite mismo es de pocos píxeles).
in float vAlpha;
in float vLayer;
out vec4 fragColor;

uniform vec3 u_tint;

void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c) * 2.0;
    float a = smoothstep(1.0, 0.0, d) * vAlpha;
    fragColor = vec4(u_tint * (0.6 + 0.4 * vLayer / 2.0), a);
}
