#version 330 core
// FASE D — vidrio esmerilado de los paneles: desenfoque barato (5 muestras
// en cruz, sin dual-Kawase completo — el panel ya es una región pequeña y
// el destino está a 1/4 de su propia resolución, así que el ahorro real
// viene de CUÁNTOS píxeles se tocan, no de más pasadas) de la región del
// panel dentro de `scene`, escrito a una FBO pequeña propia (1/4 del
// tamaño del panel). `HoloStage._render_glass` sólo llama a este shader
// a 20Hz — el fondo detrás de un panel cambia despacio, no hace falta
// recalcularlo cada frame.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;   // la FBO "scene" completa (pre-tonemap)
uniform vec2 u_rectMin;       // esquina del panel dentro de u_source, UV bottom-up
uniform vec2 u_rectSize;      // tamaño del panel, UV bottom-up
uniform vec2 u_texel;         // 1 / resolución de u_source

void main() {
    vec2 srcUv = u_rectMin + vUv * u_rectSize;
    vec2 o = u_texel * 3.0;
    vec3 col = texture(u_source, srcUv).rgb * 0.40;
    col += texture(u_source, srcUv + vec2(o.x, 0.0)).rgb * 0.15;
    col += texture(u_source, srcUv - vec2(o.x, 0.0)).rgb * 0.15;
    col += texture(u_source, srcUv + vec2(0.0, o.y)).rgb * 0.15;
    col += texture(u_source, srcUv - vec2(0.0, o.y)).rgb * 0.15;
    fragColor = vec4(col, 1.0);
}
