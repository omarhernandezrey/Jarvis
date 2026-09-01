#version 440

// ─────────────────────────────────────────────────────────────────────────────
//  NÚCLEO JARVIS — campo de interferencia + volumen SDF + especular anisótropo.
//
//  No es un arc-reactor ni anillos concéntricos ni un ecualizador circular.
//  Dos retículas radiales contrarrotantes cuyo patrón de moiré ES la
//  visualización: el DATO real (energy/flux/bandas) modula la FASE de las
//  retículas, no su amplitud. Sin dato real, todo queda en su estado base.
//
//  Compilar:  pyside6-qsb --qt6 -o core.frag.qsb core.frag
// ─────────────────────────────────────────────────────────────────────────────

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;
    float qt_Opacity;
    // --- alimentados por Core.qml desde el ViewModel (datos reales) ---
    float time;        // segundos acumulados (FrameAnimation global)
    float energy;      // 0..1  agregado real (RMS mic / envolvente TTS / tok·s)
    float flux;        // 0..1  ritmo (derivada de energy / tokens por segundo)
    float ringOpen;    // 0..1  apertura del campo por estado
    float emission;    // 0..1  cuánto emite el estado (alert/offline = 0)
    float bandLow;     // 0..1  tercio grave del espectro
    float bandMid;     // 0..1  tercio medio
    float bandHigh;    // 0..1  tercio agudo
    float fragmented;  // 0/1   ALERT: rompe el campo
    float dashed;      // 0/1   OFFLINE: campo discontinuo, inerte
    float aspect;      // ancho/alto del recuadro
    float reduced;     // 0/1   prefers-reduced-motion: congela el movimiento
    float compact;     // 0/1   modo insignia (Fase 6): sin volumen interior
    vec4  tint;        // color del estado (rgb; a sin usar)
};

// ---- ruido de valor 3D (para el desplazamiento de la superficie) ----
float hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float vnoise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash(i + vec3(0,0,0)), hash(i + vec3(1,0,0)), f.x),
                   mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
               mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
                   mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}

// ---- SDF: esfera con superficie viva (no un círculo) ----
float mapSDF(vec3 p) {
    float tm = reduced > 0.5 ? 0.0 : time;
    float d1 = vnoise(p * 3.0 + vec3(0.0, tm * 0.13, 0.0)) - 0.5;
    float d2 = vnoise(p * 6.5 - tm * 0.09) - 0.5;
    float disp = (d1 + d2 * 0.45) * 0.10 * (0.45 + 0.9 * energy);
    return length(p) - 0.60 - disp;
}
vec3 calcNormal(vec3 p) {
    // normal por tetraedro: 4 evaluaciones del SDF en vez de 6
    const vec2 k = vec2(1.0, -1.0);
    const float h = 0.002;
    return normalize(k.xyy * mapSDF(p + k.xyy * h) +
                     k.yyx * mapSDF(p + k.yyx * h) +
                     k.yxy * mapSDF(p + k.yxy * h) +
                     k.xxx * mapSDF(p + k.xxx * h));
}

void main() {
    vec2 uv = (qt_TexCoord0 - 0.5) * 2.0;
    uv.x *= aspect;
    float rad = length(uv);
    // fuera del disco del núcleo no hay nada que calcular (≈45% del quad)
    if (rad > 1.06) { fragColor = vec4(0.0); return; }
    float ang = atan(uv.y, uv.x);          // frecuencias angulares ENTERAS → sin costura
    float tm = reduced > 0.5 ? 0.0 : time;

    vec3 col = vec3(0.0);
    float alpha = 0.0;
    float em = 0.22 + 0.78 * emission;                 // suelo de emisión visible

    // ── 1) CAMPO DE INTERFERENCIA — dos espirales radiales contrarrotantes ──
    // Su superposición (moiré) ES la visualización: el DATO modula la FASE.
    float ph  = energy * 6.2831 + flux * 3.5 + (bandLow - bandHigh) * 2.4;
    float rot = dashed > 0.5 ? 0.0 : tm;               // OFFLINE: inmóvil
    float s1 = sin(rad * 34.0 - rot * 1.6 + ang * 7.0 + ph);
    float s2 = sin(rad * 37.0 + rot * 2.0 - ang * 7.0 - ph * 0.6);
    // umbral más cerrado → brazos/nodos MÁS definidos (menos difusos)
    float arm1 = smoothstep(0.34, 0.92, s1);
    float arm2 = smoothstep(0.34, 0.92, s2);
    float field = max(arm1, arm2) * 0.62 + arm1 * arm2 * 0.95;  // brazos + nodos
    float ring = smoothstep(1.02, 0.58, rad) * smoothstep(0.18, 0.46, rad);
    ring *= mix(0.35, 1.0, ringOpen);
    if (fragmented > 0.5) ring *= step(0.34, fract(ang * (5.0 / 6.2831) + 0.5 + tm * 0.05));
    if (dashed > 0.5)     ring *= step(0.5, fract(rad * 26.0)) * 0.6;
    float emanate = smoothstep(1.0, 0.12, rad);        // más brillo cerca del núcleo
    vec3 fieldCol = mix(tint.rgb, vec3(1.0), 0.15 * energy);
    col   += fieldCol * field * ring * emanate * (0.5 + 1.3 * emission) * (0.45 + 0.9 * energy);
    alpha += field * ring * (0.30 + 0.70 * emission);

    // halo central suave (independiente del SDF): vende la emisión. Peso
    // REDUCIDO: antes lavaba el campo de interferencia; ahora sólo lo insinúa.
    float halo = smoothstep(0.60, 0.0, rad);
    col += tint.rgb * halo * halo * (0.05 + 0.30 * energy) * emission;

    // ── BORDE DEFINIDO — anillo de energía fino en el limbo del orbe ──
    // Da una silueta legible (ORBE vs ALREDEDOR) sin un círculo blanco
    // artificial: usa el tinte, se integra con el campo, y aporta a alpha
    // para que sea un borde real, no un brillo.
    float rim = smoothstep(0.05, 0.0, abs(rad - 0.76));
    vec3  rimCol = mix(tint.rgb, vec3(1.0), 0.30);
    col   += rimCol * rim * (0.42 + 0.7 * emission) * (0.7 + 0.5 * energy);
    alpha  = max(alpha, rim * (0.45 + 0.4 * emission));

    // ── 2) VOLUMEN INTERIOR (raymarch) — ES LUZ, no un objeto opaco ──
    if (rad < 0.74 && compact < 0.5) {
        vec3 ro = vec3(uv * 1.18, 2.0);
        vec3 rd = vec3(0.0, 0.0, -1.0);
        float t = 1.2;                        // arranca cerca de la esfera (r≈0.6, ro.z=2)
        float hit = 0.0;
        for (int i = 0; i < 20; i++) {
            vec3 p = ro + rd * t;
            float d = mapSDF(p);
            if (d < 0.002) { hit = 1.0; break; }
            t += max(d * 0.9, 0.006);
            if (t > 2.9) break;
        }
        if (hit > 0.5) {
            vec3 p = ro + rd * t;
            vec3 n = calcNormal(p);
            vec3 v = -rd;
            vec3 L = normalize(vec3(0.16, 0.90, 0.55));      // luz coherente arriba-centro
            float diff = max(dot(n, L), 0.0);
            float fres = pow(1.0 - max(dot(n, v), 0.0), 2.3);
            float thick = clamp((0.62 - length(p)) * 3.2, 0.0, 1.0);  // grosor del volumen

            // ── 3) BARRIDO ESPECULAR ANISÓTROPO (no glow uniforme) ──
            vec3 hlf = normalize(L + v);
            float ndh = max(dot(n, hlf), 0.0);
            vec3 tang = normalize(cross(n, vec3(0.0, 1.0, 0.0)) + vec3(1e-4));
            float tdh = dot(tang, hlf);
            float aniso = pow(ndh, 36.0) * exp(-tdh * tdh * 5.0);
            float sweep = pow(0.5 + 0.5 * sin(ang * 2.0 - tm * 0.7), 7.0);

            vec3 glow = tint.rgb * (0.14 + 0.7 * energy) * (0.45 + 0.55 * thick);   // plasma interno
            glow += mix(tint.rgb, vec3(1.0), 0.35) * fres * (0.55 + 1.1 * energy);   // borde encendido
            glow += vec3(1.0) * aniso * sweep * (0.45 + 0.7 * energy);               // material que barre
            glow += tint.rgb * diff * 0.10;
            glow += mix(tint.rgb, vec3(1.0), 0.6)
                    * smoothstep(0.11, 0.0, length(p)) * (0.28 + 0.5 * energy);      // centro caliente
            glow *= em;

            col += glow;                                       // ADITIVO: emite
            alpha = max(alpha, clamp(fres * 0.9 + thick * 0.55 + 0.15 * emission, 0.0, 1.0));
        }
    }

    // insignia: punto de luz interior en vez del volumen
    if (compact > 0.5) {
        float d = smoothstep(0.40, 0.0, rad);
        col   += mix(tint.rgb, vec3(1.0), 0.4) * d * (0.30 + 0.9 * emission) * (0.6 + energy);
        alpha  = max(alpha, d * (0.45 + 0.55 * emission));
    }

    float mask = smoothstep(1.05, 0.96, rad);
    fragColor = vec4(col, clamp(alpha, 0.0, 1.0) * mask) * qt_Opacity;
}
