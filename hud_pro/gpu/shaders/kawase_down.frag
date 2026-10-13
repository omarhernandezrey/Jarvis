#version 330 core
// Dual-Kawase blur — paso de reducción (Bjørge, ARM, técnica pública de
// dominio general: 5 muestras por nivel, mucho más barato que un blur
// gaussiano de radio grande y sin el anillado de un box blur simple).
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;
uniform vec2 u_halfpixel;  // 0.5 / resolución del FBO de origen

void main() {
    vec2 uv = vUv;
    vec3 sum = texture(u_source, uv).rgb * 4.0;
    sum += texture(u_source, uv - u_halfpixel).rgb;
    sum += texture(u_source, uv + u_halfpixel).rgb;
    sum += texture(u_source, uv + vec2(u_halfpixel.x, -u_halfpixel.y)).rgb;
    sum += texture(u_source, uv - vec2(u_halfpixel.x, -u_halfpixel.y)).rgb;
    fragColor = vec4(sum / 8.0, 1.0);
}
