#version 330 core
// FASE A — escena de prueba del motor GPU: un resplandor radial simple,
// teñido por estado y animado por tiempo/energía real. No es el orbe
// final (eso es la FASE C, con raymarching) ni el fondo cinematográfico
// (FASE B) — es sólo la pieza mínima para probar el pipeline completo
// (bloom, destello, aberración, tono ACES, grano, viñeta) de punta a
// punta antes de construir el contenido real encima.
in vec2 vUv;
out vec4 fragColor;

uniform float u_time;
uniform float u_energy;   // 0..1, nivel real de audio o síntesis de reposo
uniform vec2  u_resolution;
uniform vec3  u_tint;     // color del estado (azul/cian; rojo sólo en error)

void main() {
    vec2 uv = (vUv - 0.5);
    uv.x *= u_resolution.x / u_resolution.y;

    float pulse = 0.5 + 0.5 * sin(u_time * 1.3);
    float r = length(uv);
    float glow = smoothstep(0.42, 0.0, r) * (0.55 + 0.45 * pulse) * (0.5 + 0.5 * u_energy);

    vec3 col = u_tint * glow;
    // fondo casi negro, muy ligeramente azulado (deja sitio a la FASE B)
    col += vec3(0.01, 0.015, 0.03);

    fragColor = vec4(col, 1.0);
}
