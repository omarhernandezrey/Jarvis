#version 440

// ─────────────────────────────────────────────────────────────────────────────
//  NÚCLEO JARVIS — campo de interferencia + volumen SDF + especular anisótropo.
//
//  No es un arc-reactor ni anillos concéntricos ni un ecualizador circular.
//  Dos retículas radiales contrarrotantes cuyo patrón de moiré ES la
//  visualización: el DATO real (energy/flux/bandas) modula la FASE de las
//  retículas, no su amplitud. Sin dato real, todo queda en su estado base.
//
//  Fase 7: paralaje del volumen, onda de choque de estado, rim iluminado con
//  fleco cromático, anillo de forma de onda con el audio real, respiración de
//  la geometría, dither anti-banding.
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
    vec4  tintDeep;    // azul profundo del limbo / atmósfera (Fase 6)
    vec4  tintHot;     // cian casi-blanco: SÓLO highlight cercano al centro
    float spin;        // 0..1 velocidad de giro por estado (personalidad)
    float pointerX;    // -1..1 posición del ratón (paralaje del volumen)
    float pointerY;
    float transPhase;  // 1→0 tras un cambio de estado (onda de choque)
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
    // (8) RESPIRACIÓN DE LA GEOMETRÍA: el radio base inhala/exhala muy poco,
    // sobre todo en reposo (con energía alta casi no se nota).
    float baseR = 0.60 + 0.012 * sin(tm * 0.8) * (1.0 - 0.6 * energy);
    return length(p) - baseR - disp;
}
vec3 calcNormal(vec3 p) {
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
    if (rad > 1.10) { fragColor = vec4(0.0); return; }
    float ang = atan(uv.y, uv.x);
    float tm = reduced > 0.5 ? 0.0 : time;

    // (1) PARALAJE — el volumen interior se desplaza contra la cáscara según
    //     el ratón: el orbe deja de leerse como disco y se lee como esfera.
    vec2 par = vec2(pointerX, -pointerY) * 0.06;

    vec3 col = vec3(0.0);
    float alpha = 0.0;
    float em = 0.22 + 0.78 * emission;

    // ── CAMPO DE INTERFERENCIA — dos retículas radiales contrarrotantes ──
    float ph  = energy * 6.2831 + flux * 3.5 + (bandLow - bandHigh) * 2.4;
    float rot = dashed > 0.5 ? 0.0 : tm * mix(0.35, 1.35, spin);
    float s1 = sin(rad * 34.0 - rot * 1.6 + ang * 7.0 + ph);
    float s2 = sin(rad * 37.0 + rot * 2.0 - ang * 7.0 - ph * 0.6);
    float arm1 = smoothstep(0.34, 0.92, s1);
    float arm2 = smoothstep(0.34, 0.92, s2);
    float field = max(arm1, arm2) * 0.62 + arm1 * arm2 * 0.95;
    float ring = smoothstep(1.02, 0.58, rad) * smoothstep(0.18, 0.46, rad);
    ring *= mix(0.35, 1.0, ringOpen);
    if (fragmented > 0.5) ring *= step(0.34, fract(ang * (5.0 / 6.2831) + 0.5 + tm * 0.05));
    if (dashed > 0.5)     ring *= step(0.5, fract(rad * 26.0)) * 0.6;
    float emanate = smoothstep(1.0, 0.12, rad);

    // profundidad cromática: azul profundo en el limbo → tinte de estado →
    // highlight sólo cerca del centro y con energía.
    vec3 depthCol = mix(tintDeep.rgb, tint.rgb, smoothstep(0.98, 0.30, rad));
    depthCol = mix(depthCol, tintHot.rgb,
                   smoothstep(0.26, 0.02, rad) * (0.30 + 0.50 * energy));
    col   += depthCol * field * ring * emanate * (0.5 + 1.3 * emission) * (0.45 + 0.9 * energy);
    alpha += field * ring * (0.30 + 0.70 * emission);

    // halo central suave
    float halo = smoothstep(0.60, 0.0, rad);
    col += mix(tint.rgb, tintDeep.rgb, 0.25) * halo * halo * (0.05 + 0.28 * energy) * emission;

    // ── CAMPO DE ENERGÍA — dos arcos orbitales lentos fuera del cuerpo ──
    float orb1 = smoothstep(0.020, 0.0, abs(rad - 0.855))
               * (0.55 + 0.45 * sin(ang * 3.0 + tm * 0.5 * mix(0.4, 1.2, spin)));
    float orb2 = smoothstep(0.016, 0.0, abs(rad - 0.945))
               * (0.55 + 0.45 * sin(ang * 2.0 - tm * 0.33));
    vec3 fieldRingCol = mix(tintDeep.rgb, tint.rgb, 0.62);
    col   += fieldRingCol * (orb1 * 0.24 + orb2 * 0.15) * (0.45 + 0.8 * emission);
    alpha  = max(alpha, (orb1 * 0.20 + orb2 * 0.13) * (0.4 + 0.5 * emission));

    // ── (4) ANILLO DE FORMA DE ONDA — sólo con audio real (listening/speaking)
    float bandSum = bandLow + bandMid + bandHigh;
    if (bandSum > 0.02) {
        float wv = sin(ang * 7.0  + tm * 2.1) * bandMid
                 + sin(ang * 13.0 - tm * 1.4) * bandHigh
                 + sin(ang * 4.0  + tm * 0.8) * bandLow;
        float wring = smoothstep(0.045, 0.0, abs(rad - (0.80 + 0.055 * wv)));
        col   += mix(tint.rgb, tintHot.rgb, 0.25) * wring * bandSum * (0.6 + 0.5 * emission);
        alpha  = max(alpha, wring * bandSum * 0.55);
    }

    // ── (2) ONDA DE CHOQUE — un frente sale del centro tras un cambio de estado
    if (transPhase > 0.001) {
        float wr = (1.0 - transPhase) * 1.15;
        float shock = smoothstep(0.055, 0.0, abs(rad - wr)) * transPhase;
        col   += mix(tint.rgb, tintHot.rgb, 0.5) * shock * (0.5 + 0.6 * emission);
        alpha  = max(alpha, shock * 0.45 * (0.4 + 0.6 * emission));
    }

    // ── (3) BORDE + (5) FLECO CROMÁTICO — anillo de energía en el limbo,
    //     más brillante en el arco superior-izquierdo (luz coherente), con
    //     un ligero desdoble R/B como el borde de un campo de energía.
    float rimLit = 0.35 + 0.85 * (0.5 + 0.5 *
                   dot(normalize(uv + 1e-4), normalize(vec2(-0.45, 0.78))));
    float caOff = 0.013;
    float rimR = smoothstep(0.05, 0.0, abs((rad + caOff) - 0.76)) * rimLit;
    float rimG = smoothstep(0.05, 0.0, abs( rad          - 0.76)) * rimLit;
    float rimB = smoothstep(0.05, 0.0, abs((rad - caOff) - 0.76)) * rimLit;
    vec3  rc = mix(tint.rgb, tintHot.rgb, 0.32);
    float rimK = (0.42 + 0.7 * emission) * (0.7 + 0.5 * energy);
    col.r += rc.r * rimR * rimK;
    col.g += rc.g * rimG * rimK;
    col.b += rc.b * rimB * rimK;
    alpha  = max(alpha, rimG * (0.45 + 0.4 * emission));

    // ── VOLUMEN INTERIOR (raymarch) — ES LUZ, no un objeto opaco ──
    if (rad < 0.78 && compact < 0.5) {
        // paralaje: mover el origen del rayo en sentido contrario al ratón
        vec3 ro = vec3((uv - par * 1.7) * 1.18, 2.0);
        vec3 rd = vec3(0.0, 0.0, -1.0);
        float t = 1.2;
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
            // la luz sigue un poco al ratón (paralaje del sombreado)
            vec3 L = normalize(vec3(0.16 + par.x * 0.6, 0.90, 0.55 - par.y * 0.5));
            float diff = max(dot(n, L), 0.0);
            float fres = pow(1.0 - max(dot(n, v), 0.0), 2.3);
            float thick = clamp((0.62 - length(p)) * 3.2, 0.0, 1.0);

            vec3 hlf = normalize(L + v);
            float ndh = max(dot(n, hlf), 0.0);
            vec3 tang = normalize(cross(n, vec3(0.0, 1.0, 0.0)) + vec3(1e-4));
            float tdh = dot(tang, hlf);
            float aniso = pow(ndh, 36.0) * exp(-tdh * tdh * 5.0);
            float sweep = pow(0.5 + 0.5 * sin(ang * 2.0 - tm * 0.7), 7.0);

            vec3 plasmaCol = mix(tintDeep.rgb, tint.rgb, 0.7);
            vec3 glow = plasmaCol * (0.14 + 0.7 * energy) * (0.45 + 0.55 * thick);
            glow += mix(tint.rgb, tintHot.rgb, 0.4) * fres * (0.45 + 0.95 * energy);
            glow += vec3(1.0) * aniso * sweep * (0.38 + 0.6 * energy);
            glow += tint.rgb * diff * 0.10;
            glow += mix(tintHot.rgb, vec3(1.0), 0.5)
                    * smoothstep(0.10, 0.0, length(p)) * (0.30 + 0.55 * energy);
            glow *= em;

            col += glow;
            alpha = max(alpha, clamp(fres * 0.9 + thick * 0.55 + 0.15 * emission, 0.0, 1.0));
        }
    }

    // insignia: punto de luz interior en vez del volumen
    if (compact > 0.5) {
        float d = smoothstep(0.40, 0.0, rad);
        col   += mix(tint.rgb, tintHot.rgb, 0.45) * d * (0.30 + 0.9 * emission) * (0.6 + energy);
        alpha  = max(alpha, d * (0.45 + 0.55 * emission));
    }

    // (7) DITHER anti-banding: rompe el escalonado de los degradados suaves.
    float dth = fract(sin(dot(qt_TexCoord0 * vec2(443.0, 731.0), vec2(1.0, 1.0))) * 4375.85) - 0.5;
    col += dth * (1.0 / 255.0);

    float mask = smoothstep(1.05, 0.96, rad);
    fragColor = vec4(col, clamp(alpha, 0.0, 1.0) * mask) * qt_Opacity;
}
