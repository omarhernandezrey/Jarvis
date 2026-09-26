#version 330 core
// Compone el FBO pequeño del orbe (FASE C, raymarch a media resolución
// de su propio cuadro) sobre la escena completa. En vez de acotar el
// dibujo con `glViewport`/recortar píxeles a mano (con el riesgo de
// invertir el eje Y entre el espacio de la FBO y el de pantalla), este
// pase es de pantalla completa y barato (una lectura de textura por
// píxel) — recalcula en qué parte de la escena cae el cuadro del orbe
// con el MISMO sistema `centered`/corrección de aspecto que ya usan
// `scene.frag`/`rings.frag`, y descarta fuera de él.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;
uniform vec2  u_lightUv;
uniform float u_lightRadius;
uniform vec2  u_resolution;
uniform float u_margin;

void main() {
    vec2 centered = vUv - u_lightUv;
    centered.x *= u_resolution.x / u_resolution.y;
    vec2 local = centered / (u_lightRadius * u_margin) * 0.5 + 0.5;
    if (local.x < 0.0 || local.x > 1.0 || local.y < 0.0 || local.y > 1.0) {
        discard;
    }
    fragColor = texture(u_source, local);
}
