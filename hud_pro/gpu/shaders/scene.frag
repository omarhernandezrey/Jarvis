#version 330 core
// FASE B — fondo cinematográfico: niebla azul profunda (densidad real de
// `u_energy`, forma de `u_noise3d`), suelo hexagonal analítico (SDF, sin
// texturas), onda de escaneo al cambiar de estado o al detectar un pico
// de energía real mientras escucha, barrido de radar y líneas de datos
// verticales. El orbe en sí (FASE C) se dibuja en pases aparte —
// `orb.frag` (raymarch) y `rings.frag` (SDF) — compuestos encima de este
// fondo, no aquí. Todo el "peso" de este archivo (niebla, hexágonos) es
// matemática analítica evaluada unas pocas veces por píxel — nunca un
// bucle de fbm.
in vec2 vUv;
out vec4 fragColor;

uniform float u_time;
uniform float u_energy;       // 0..1, nivel real de audio o síntesis de reposo
uniform vec2  u_resolution;
uniform vec3  u_tint;         // color del estado (azul/cian; rojo sólo en error)
uniform float u_stateMult;    // >1 durante PROCESANDO: fondo más rápido/eléctrico
uniform float u_scanAge;      // segundos desde el último disparo (grande = inactivo)
uniform vec2  u_lightUv;      // posición real del orbe en pantalla (0..1)
uniform sampler3D u_noise3d;  // RG8 64³ tileable — R forma gruesa, G detalle

// ── suelo hexagonal (SDF, célula más cercana por lattice — técnica
// pública estándar de rejillas hexagonales, no un asset ni un código
// copiado de un proyecto concreto) ─────────────────────────────────────
vec4 hexCell(vec2 uv) {
    vec2 r = vec2(1.0, 1.7320508);
    vec2 h = r * 0.5;
    vec2 a = mod(uv, r) - h;
    vec2 b = mod(uv - h, r) - h;
    vec2 gv = dot(a, a) < dot(b, b) ? a : b;
    return vec4(gv, uv - gv);
}

float hexEdgeDist(vec2 gv) {
    vec2 p = abs(gv);
    return max(dot(p, normalize(vec2(1.0, 1.7320508))), p.x);
}

void main() {
    vec2 uv = vUv;
    vec2 centered = uv - 0.5;
    centered.x *= u_resolution.x / u_resolution.y;

    vec3 col = vec3(0.01, 0.015, 0.03);

    // ── suelo: proyección en perspectiva simple bajo el horizonte ──────
    const float horizon = 0.56;
    if (uv.y < horizon) {
        float depth = (horizon - uv.y) + 0.02;
        float persp = 1.0 / depth;
        vec2 ground = vec2(centered.x * persp, persp * 0.6 + u_time * 0.05 * u_stateMult);
        vec4 cell = hexCell(ground * 3.2);
        float edge = hexEdgeDist(cell.xy);
        float lineGlow = smoothstep(0.5, 0.46, edge) - smoothstep(0.46, 0.40, edge);
        float fade = smoothstep(horizon, horizon - 0.42, uv.y);
        vec3 floorTint = mix(u_tint, vec3(0.55, 0.85, 1.0), 0.35);
        col += floorTint * lineGlow * fade * (0.35 + 0.5 * u_energy);

        // reflejo difuso del orbe en el piso: mismo resplandor central,
        // espejado verticalmente respecto al horizonte, muy atenuado
        float reflDist = length(vec2(centered.x, (horizon - uv.y)) - vec2(u_lightUv.x - 0.5, 0.0));
        col += u_tint * smoothstep(0.5, 0.0, reflDist) * 0.10 * fade * (0.4 + 0.6 * u_energy);
    }

    // ── niebla volumétrica: densidad de ruido 3D real (2 muestras con
    // distinto offset/escala, nunca fbm por píxel) modulada por la
    // energía real de audio/síntesis de reposo ────────────────────────
    vec3 noiseCoord = vec3(centered * 0.8, u_time * 0.02);
    float fogBase = texture(u_noise3d, noiseCoord).r;
    float fogDetail = texture(u_noise3d, noiseCoord * 2.3 + vec3(0.3, 0.1, u_time * 0.015)).g;
    float fog = fogBase * 0.7 + fogDetail * 0.3;
    float fogMask = smoothstep(1.0, 0.15, length(centered)) * (0.18 + 0.5 * u_energy);
    col += u_tint * fog * fogMask;

    // distancia al centro del orbe real — FASE C lo dibuja en su propio
    // pase (`orb.frag` + `rings.frag`); aquí sólo hace falta para la onda
    // de escaneo, que sigue viviendo en el fondo.
    float r = length(centered - (u_lightUv - 0.5));

    // ── onda de escaneo: anillo expansivo desde el orbe al cambiar de
    // estado o al detectar un pico de energía real mientras escucha ───
    if (u_scanAge < 1.4) {
        float ringR = u_scanAge * 1.6;
        float ring = smoothstep(0.05, 0.0, abs(r - ringR)) * (1.0 - u_scanAge / 1.4);
        col += u_tint * ring * 0.8;
    }

    // ── barrido de radar (tenue) ────────────────────────────────────────
    float ang = atan(centered.y, centered.x);
    float sweep = fract((ang - u_time * 0.4 * u_stateMult) / 6.2831853);
    float radarMask = smoothstep(1.0, 0.0, length(centered) * 1.6);
    col += u_tint * smoothstep(0.12, 0.0, sweep) * radarMask * 0.05;

    // ── líneas de datos verticales a los lados (sutiles) ────────────────
    float sideMask = smoothstep(0.32, 0.5, abs(centered.x));
    float lines = step(0.97, fract(uv.y * 26.0 - u_time * 0.6)) * sideMask;
    col += u_tint * lines * 0.05;

    // techo defensivo: esta FBO es RGBA16F (rango HDR real para el bloom)
    // pero medio-flotante desborda a Infinito por encima de ~65504 — con
    // varias capas sumándose sin tope (niebla + piso + reflejo + brillo +
    // barrido + líneas) un píxel donde coincidan varias podría acercarse;
    // nunca hace falta más que esto para que el umbral de bloom (0.72)
    // siga funcionando iguales.
    col = clamp(col, 0.0, 8.0);

    fragColor = vec4(col, 1.0);
}
