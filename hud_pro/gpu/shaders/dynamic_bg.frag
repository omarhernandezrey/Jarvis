#version 330 core
// Capa DINÁMICA del fondo: niebla, reflejo del orbe, onda de escaneo,
// radar y líneas de datos — todo lo que de verdad se mueve frame a
// frame. Se renderiza a RESOLUCIÓN REDUCIDA (0.35-0.75 según calidad,
// ver `QualitySettings.bg_dynamic_scale`) y se compone sobre el fondo
// estático con upsample bilineal de hardware — nunca a resolución
// completa. Niebla: 1-2 muestras de la textura de ruido 3D, nunca fbm
// por píxel. Reflejo: mancha gaussiana deformada, no una reflexión real.
in vec2 vUv;
out vec4 fragColor;

uniform float u_time;
uniform float u_energy;
uniform vec2  u_resolution;   // resolución REDUCIDA de este pase
uniform vec3  u_tint;
uniform float u_stateMult;
uniform float u_scanAge;
uniform vec2  u_lightUv;
uniform sampler3D u_noise3d;

void main() {
    vec2 uv = vUv;
    vec2 centered = uv - 0.5;
    centered.x *= u_resolution.x / u_resolution.y;

    vec3 col = vec3(0.0);
    float alpha = 0.0;

    // niebla: salida temprana si la máscara radial ya la apaga en esta
    // región (evita la segunda muestra de ruido, más cara, donde no hace
    // falta).
    float fogMask = smoothstep(1.0, 0.15, length(centered)) * (0.18 + 0.5 * u_energy);
    if (fogMask > 0.004) {
        vec3 noiseCoord = vec3(centered * 0.8, u_time * 0.02);
        float fogBase = texture(u_noise3d, noiseCoord).r;
        float fogDetail = texture(u_noise3d, noiseCoord * 2.3 + vec3(0.3, 0.1, u_time * 0.015)).g;
        float fog = (fogBase * 0.7 + fogDetail * 0.3) * fogMask;
        col += u_tint * fog;
        alpha += fog;
    }

    const float horizon = 0.56;
    if (uv.y < horizon) {
        float fade = smoothstep(horizon, horizon - 0.42, uv.y);
        // reflejo del orbe: mancha gaussiana deformada (achatada en Y),
        // NO un cálculo de reflexión real — mucho más barato y, a esta
        // escala reducida, indistinguible.
        vec2 d = vec2(centered.x - (u_lightUv.x - 0.5), (horizon - uv.y) * 1.6);
        float blob = exp(-dot(d, d) * 10.0);
        col += u_tint * blob * 0.35 * fade * (0.4 + 0.6 * u_energy);
        alpha += blob * fade;
    }

    float r = length(centered - (u_lightUv - 0.5));

    // onda de escaneo (analítica, sin loop).
    if (u_scanAge < 1.4) {
        float ringR = u_scanAge * 1.6;
        float ring = smoothstep(0.05, 0.0, abs(r - ringR)) * (1.0 - u_scanAge / 1.4);
        col += u_tint * ring * 0.8;
        alpha += ring;
    }

    // radar (analítico, sin loop).
    float ang = atan(centered.y, centered.x);
    float sweep = fract((ang - u_time * 0.4 * u_stateMult) / 6.2831853);
    float radarMask = smoothstep(1.0, 0.0, length(centered) * 1.6);
    float radar = smoothstep(0.12, 0.0, sweep) * radarMask * 0.05;
    col += u_tint * radar;
    alpha += radar;

    // líneas de datos verticales (analíticas, sin loop).
    float sideMask = smoothstep(0.32, 0.5, abs(centered.x));
    float lines = step(0.97, fract(uv.y * 26.0 - u_time * 0.6)) * sideMask * 0.05;
    col += u_tint * lines;
    alpha += lines;

    fragColor = vec4(col, clamp(alpha, 0.0, 1.0));
}
