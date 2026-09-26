#version 330 core
// Blit de pantalla completa sin remapeo ni discard — a diferencia de
// `blit.frag` (que recorta al cuadro del orbe vía u_lightUv/u_lightRadius/
// u_margin), este pase sólo copia la textura de entrada. Uso exclusivo:
// componer el fondo estático/dinámico en `_render_scene`. Compartir
// `blit.frag` para esto causaba un artefacto rectangular: su programa
// retiene entre frames los uniforms u_lightUv/u_lightRadius/u_margin del
// último compositing del orbe, y como el fondo nunca los fija, se colaba
// el discard del orbe sobre el fondo.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;

void main() {
    fragColor = texture(u_source, vUv);
}
