#version 330 core
// Capa ESTÁTICA del fondo: gradiente base + retícula hexagonal del suelo
// (sin animar, sin depender del estado) + viñeta. Se renderiza a una
// textura UNA sola vez por resize/cambio de calidad (ver
// `HoloStage._ensure_static_bg`) — el resto de los frames la reutilizan
// con una sola lectura de textura (`blit.frag`), nunca recalculando el
// SDF del hexágono. El color de estado y el movimiento viven en
// `dynamic_bg.frag`, no aquí.
in vec2 vUv;
out vec4 fragColor;

uniform vec2 u_resolution;

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

    // suelo: sólo bajo el horizonte (salida temprana por región).
    const float horizon = 0.56;
    if (uv.y < horizon) {
        float depth = (horizon - uv.y) + 0.02;
        float persp = 1.0 / depth;
        vec2 ground = vec2(centered.x * persp, persp * 0.6);
        vec4 cell = hexCell(ground * 3.2);
        float edge = hexEdgeDist(cell.xy);
        float lineGlow = smoothstep(0.5, 0.46, edge) - smoothstep(0.46, 0.40, edge);
        float fade = smoothstep(horizon, horizon - 0.42, uv.y);
        col += vec3(0.30, 0.55, 0.75) * lineGlow * fade * 0.35;
    }

    // viñeta radial suave — oscurece hacia los bordes.
    float vig = smoothstep(0.15, 1.05, length(centered));
    col *= mix(1.0, 0.55, vig);

    fragColor = vec4(col, 1.0);
}
