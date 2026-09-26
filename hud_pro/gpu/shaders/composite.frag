#version 330 core
// Composición final: escena + bloom + destello, aberración cromática en
// los bordes, tone mapping ACES, grano de película y viñeta.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_scene;    // resolución completa
uniform sampler2D u_bloom;    // 1/4 (o el nivel final del dual-Kawase)
uniform sampler2D u_streak;   // 1/4
uniform float u_time;
uniform float u_bloomStrength;
uniform float u_streakStrength;
uniform float u_aberration;   // 0..~3 px en la esquina
uniform float u_grain;        // 0..~0.05
uniform float u_vignette;     // 0..~0.5
uniform vec2  u_texel;        // 1.0 / resolución de pantalla

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// ACES (ajuste de Narkowicz, de dominio público) — curva estándar, no una
// invención propia.
vec3 aces(vec3 x) {
    const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

void main() {
    vec2 c = vUv - 0.5;
    float r = length(c) * 1.41421;

    // Aberración cromática SÓLO en el canal que de verdad se desplaza (R y
    // B); G se muestrea sin desplazar. Guardia (misma lección que el orbe
    // raster / el núcleo QML): si el píxel de origen YA era azul/cian
    // (b>=g), el resultado no puede volcarse a verde por el desplazamiento
    // — evita reproducir aquí el residuo verde que costó una sesión entera
    // de diagnóstico en el HUD legado.
    vec2 off = c * r * u_aberration * u_texel;
    float rr = texture(u_scene, vUv + off).r;
    vec4  gg = texture(u_scene, vUv);
    float bb = texture(u_scene, vUv - off).b;
    vec3 scene = vec3(rr, gg.g, bb);
    if (gg.b >= gg.g) scene.b = max(scene.b, scene.g);

    vec3 bloom = texture(u_bloom, vUv).rgb * u_bloomStrength;
    vec3 streak = texture(u_streak, vUv).rgb * u_streakStrength;

    vec3 col = scene + bloom + streak;
    col = aces(col);

    // viñeta
    col *= mix(1.0, 1.0 - u_vignette, smoothstep(0.35, 1.05, r));

    // grano temporal, escalado a la luminancia (menos visible en negros puros)
    float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
    float g = (hash21(gl_FragCoord.xy + u_time * 137.0) - 0.5) * u_grain;
    col += g * (0.35 + 0.65 * lum);

    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
