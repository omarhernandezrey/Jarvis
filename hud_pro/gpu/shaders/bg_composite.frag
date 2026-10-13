#version 330 core
// Funde estático + dinámico en UN solo pase de pantalla completa — antes
// eran dos blits separados (`passthrough.frag` dos veces, con un toggle
// de blend GL en medio); ese segundo draw call + bind de FBO + cambio de
// estado de blend costaba más, en esta GPU, de lo que ahorraba renderizar
// la capa dinámica a resolución reducida. Aquí el mezclado por alpha lo
// hace el propio shader (`mix`), sin blending de hardware — un solo draw.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_static;
uniform sampler2D u_dynamic;  // resolución reducida — el sampler ya hace el upsample bilineal

void main() {
    vec3 base = texture(u_static, vUv).rgb;
    vec4 dyn = texture(u_dynamic, vUv);
    fragColor = vec4(mix(base, dyn.rgb, dyn.a), 1.0);
}
