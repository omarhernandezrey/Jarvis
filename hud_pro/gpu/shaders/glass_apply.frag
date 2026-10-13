#version 330 core
// Blit sin remapeo del vidrio ya desenfocado (ver `glass_blur.frag`) de
// vuelta sobre su rect real en `scene` — el upsample de 1/4 res a la
// resolución del panel es el filtro bilineal de hardware del propio
// sampler, sin pasada de upsample aparte. Shader propio (no reusar
// `blit.frag`, el del orbe): ver el comentario de `bg_composite.frag`
// sobre por qué compartir programas de compositing entre usos con
// uniforms distintos deja valores del frame/uso anterior colados.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_glass;

void main() {
    fragColor = vec4(texture(u_glass, vUv).rgb, 1.0);
}
