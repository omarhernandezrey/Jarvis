#version 330 core
// FASE C — orbe raymarched: esfera de plasma real (SDF + textura de
// ruido 3D, 2 muestras — nunca fbm de varias octavas), con salida
// temprana por densidad acumulada y por distancia. Se dibuja en un FBO
// PROPIO, pequeño (sólo el cuadro alrededor del orbe, ver
// `HoloStage._ensure_orb_fbo`) y a MEDIA resolución de ese cuadro — así
// el límite de pasos (24 high / 40 ultra) sólo cuesta donde el orbe
// realmente está, nunca en el resto de la pantalla.
in vec2 vUv;
out vec4 fragColor;

uniform float u_time;
uniform float u_energy;
uniform vec3  u_tint;
uniform float u_stateMult;   // más rápido/eléctrico en PROCESANDO
uniform float u_hover;       // 0/1 → +20% de brillo
uniform int   u_steps;       // 24 high / 40 ultra (piso de calidad)
uniform sampler3D u_noise3d;

const int MAX_STEPS = 40;

float sdSphere(vec3 p, float r) { return length(p) - r; }

void main() {
    vec2 uv = (vUv - 0.5) * 2.0;
    if (length(uv) > 1.05) { fragColor = vec4(0.0); return; }

    vec3 ro = vec3(0.0, 0.0, 2.2);
    vec3 rd = normalize(vec3(uv, -1.6));

    // sphere-tracing normal MIENTRAS el rayo está fuera (saltos grandes,
    // según la distancia real al SDF); al entrar cambia a paso FIJO y
    // pequeño para acumular densidad volumétrica (plasma) atravesando el
    // interior — un rayo por el centro cruza ~2 unidades (~el presupuesto
    // de pasos completo, sale antes por densidad); uno que roza el borde
    // cruza mucho menos y acumula menos: así el relleno se ve sólido y
    // más brillante al centro, no un simple contorno hueco.
    float t = 0.6;
    float density = 0.0;
    vec3 glow = vec3(0.0);
    for (int i = 0; i < MAX_STEPS; i++) {
        if (i >= u_steps) break;
        vec3 p = ro + rd * t;
        float d = sdSphere(p, 1.0);
        if (d < 0.0) {
            // Antes `p` se rotaba como bloque rigido (mat2 rot(spin)) antes
            // de muestrear el ruido 3D: todo el campo de plasma giraba
            // junto, como un disco — "se ve como una rocola", reportado en
            // uso real sobre la maquina real (GPU, no el fallback offscreen
            // que usa orb.py). Sin esa rotacion compartida, cada octava solo
            // deriva en Z a su propia velocidad (ya existia, con signos
            // opuestos) -- turbulencia organica, no un remolino rigido.
            float n1 = texture(u_noise3d, p * 1.4 + vec3(0.0, 0.0, u_time * 0.05 * u_stateMult)).r;
            float n2 = texture(u_noise3d, p * 3.2 - vec3(0.0, 0.0, u_time * 0.09 * u_stateMult)).g;
            float plasma = n1 * 0.6 + n2 * 0.4 + 0.35;
            float amount = plasma * (0.5 + 0.5 * u_energy);
            density += amount * 0.11;
            glow += u_tint * amount * 0.03;
            if (density > 1.1) break;  // salida temprana por densidad acumulada
            t += 0.09;
        } else {
            if (d > 4.0) break;  // salida temprana por distancia (fuera de la esfera)
            t += max(d, 0.05);
        }
    }

    float rim = smoothstep(0.78, 1.0, length(uv));
    vec3 col = u_tint * (0.28 + 0.85 * density) + u_tint * rim * 0.55 + glow;
    col *= (1.0 + 0.2 * u_hover);

    float circleMask = smoothstep(1.05, 0.9, length(uv));
    float alpha = clamp(density * 0.9 + rim * 0.5, 0.0, 1.0) * circleMask;
    fragColor = vec4(col, alpha);
}
