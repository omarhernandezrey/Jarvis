#version 330 core
// FASE C — anillos HUD y espectro real como SDF, en un pase APARTE a
// resolución completa (para que el trazo quede nítido pese al raymarch
// del orbe ir a media resolución) — `fwidth()` da antialiasing correcto
// a cualquier tamaño de pantalla, no un ancho de línea fijo en píxeles.
in vec2 vUv;
out vec4 fragColor;

uniform float u_time;
uniform float u_stateMult;
uniform vec2  u_resolution;
uniform vec2  u_lightUv;
uniform float u_lightRadius;   // radio del orbe, en unidades de "centered" (ver scene.frag)
uniform vec3  u_tint;
uniform int   u_hasSpectrum;
uniform float u_spectrum[64];
uniform int   u_spectrumCount;

const float TAU = 6.2831853;

float ringLine(float d, float radius, float width) {
    float aa = max(fwidth(d), 1e-5);
    return smoothstep(width + aa, width - aa, abs(d - radius));
}

void main() {
    vec2 centered = vUv - u_lightUv;
    centered.x *= u_resolution.x / u_resolution.y;
    float d = length(centered);
    float r = max(u_lightRadius, 1e-4);
    float ang = atan(centered.y, centered.x);

    vec3 col = vec3(0.0);
    float a = 0.0;

    float ring1 = ringLine(d, r * 1.35, 0.0022);
    float ring2 = ringLine(d, r * 1.55, 0.0015);
    col += u_tint * (ring1 * 0.85 + ring2 * 0.5);
    a += ring1 * 0.85 + ring2 * 0.5;

    // marcas alrededor del anillo externo
    float tickPhase = fract(ang / TAU * 48.0);
    float ticks = step(0.85, tickPhase) * ringLine(d, r * 1.55, 0.012);
    col += u_tint * ticks * 0.55;
    a += ticks * 0.55;

    // barrido rotatorio (más rápido en PROCESANDO)
    float sweepAngle = mod(u_time * 0.7 * u_stateMult, TAU);
    float angDiff = abs(mod(ang - sweepAngle + 3.14159265, TAU) - 3.14159265);
    float sweep = smoothstep(0.22, 0.0, angDiff) * ringLine(d, r * 1.45, 0.07);
    col += u_tint * sweep * 0.6;
    a += sweep * 0.6;

    // espectro real (barras radiales) — sólo si hay datos reales, nunca
    // una forma inventada cuando no los hay.
    if (u_hasSpectrum == 1 && u_spectrumCount > 0) {
        float na = (ang + 3.14159265) / TAU;
        int idx = clamp(int(na * float(u_spectrumCount)), 0, u_spectrumCount - 1);
        float amp = clamp(u_spectrum[idx], 0.0, 1.0);
        float barR0 = r * 1.68;
        float barR1 = barR0 + amp * r * 0.55;
        float bar = step(barR0, d) * step(d, barR1);
        col += u_tint * bar * 0.9;
        a += bar * 0.9;
    }

    fragColor = vec4(col, clamp(a, 0.0, 1.0));
}
