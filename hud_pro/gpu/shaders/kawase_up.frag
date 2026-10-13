#version 330 core
// Dual-Kawase blur — paso de expansión (8 muestras, pesos 1/2/1 en anillo).
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;
uniform vec2 u_halfpixel;  // 0.5 / resolución del FBO de origen (el nivel chico)

void main() {
    vec2 uv = vUv;
    vec3 sum = texture(u_source, uv + vec2(-u_halfpixel.x * 2.0, 0.0)).rgb;
    sum += texture(u_source, uv + vec2(-u_halfpixel.x, u_halfpixel.y)).rgb * 2.0;
    sum += texture(u_source, uv + vec2(0.0, u_halfpixel.y * 2.0)).rgb;
    sum += texture(u_source, uv + vec2(u_halfpixel.x, u_halfpixel.y)).rgb * 2.0;
    sum += texture(u_source, uv + vec2(u_halfpixel.x * 2.0, 0.0)).rgb;
    sum += texture(u_source, uv + vec2(u_halfpixel.x, -u_halfpixel.y)).rgb * 2.0;
    sum += texture(u_source, uv + vec2(0.0, -u_halfpixel.y * 2.0)).rgb;
    sum += texture(u_source, uv + vec2(-u_halfpixel.x, -u_halfpixel.y)).rgb * 2.0;
    fragColor = vec4(sum / 12.0, 1.0);
}
