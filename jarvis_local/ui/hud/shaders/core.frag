#version 440

// ─────────────────────────────────────────────────────────────────────────────
//  NÚCLEO JARVIS — TRES FRECUENCIAS (Fase I · I2).
//
//  LEY DE COLOR (dura): todo lo que este shader emite sale de la rampa
//  azul/cian/casi-blanco (`tint`/`tintDeep`/`tintHot`). Rojo, ámbar o verde
//  sólo aparecen si esos uniforms los traen (estados `alert`/`offline`, los
//  fija Core.qml) — el shader nunca inventa un color fuera de esos tres.
//
//  Reemplaza el cuerpo de las Fases 8-9 (piel celular Voronoi + iris
//  alienígena + raymarch volumétrico): esas rutas se salían de la rampa en
//  esta GPU (ver docs/PLAN_EJECUCION.md · I2) y costaban la mayor parte del
//  presupuesto de GPU sin que nadie las hubiera verificado en vivo. Se
//  borran, no se comentan.
//
//  Estructura (las tres frecuencias del brief):
//    1. CUERPO — absorción: el centro es DENSO/OSCURO, el brillo crece
//       monótonamente hacia el limbo. Así se lee como esfera, no como disco
//       ni como bombilla.
//    2. BORDE — fresnel nítido (~2px) con una dispersión cromática pequeña,
//       acotada a esa misma banda (nunca un canal aislado sin base: siempre
//       hay un fresnel acromático debajo).
//    3. MICRODETALLE — 2ª octava de ruido, amplitud creciente hacia el
//       limbo.
//  Encima: el patrón de interferencia (Fase 6, ya en rampa), un barrido
//  especular cada 7 s, arcos orbitales, corona magnética / anillo de audio
//  (impulsados por datos REALES: energy/flux/bandas), onda de choque al
//  cambiar de estado, y un satélite. Todo tinta desde warmTint/tintDeep/
//  tintHot — nunca un color propio.
//
//  Compilar:  pyside6-qsb --qt6 -o core.frag.qsb core.frag
// ─────────────────────────────────────────────────────────────────────────────

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;
    float qt_Opacity;
    float time;
    float energy;
    float flux;
    float ringOpen;
    float emission;
    float bandLow;
    float bandMid;
    float bandHigh;
    float fragmented;
    float dashed;
    float aspect;
    float reduced;
    float compact;
    vec4  tint;
    vec4  tintDeep;
    vec4  tintHot;
    float spin;
    float pointerX;
    float pointerY;
    float transPhase;
};

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

void main() {
    vec2 uv = (qt_TexCoord0 - 0.5) * 2.0;
    uv.x *= aspect;
    float rad = length(uv);
    if (rad > 1.12) { fragColor = vec4(0.0); return; }
    float ang = atan(uv.y, uv.x);
    float tm = reduced > 0.5 ? 0.0 : time;
    float aa = fwidth(rad) * 1.4;            // ~1px en unidades de `rad`

    vec2 par = vec2(pointerX, -pointerY) * 0.06;     // paralaje (reservado)

    vec3 col = vec3(0.0);
    float alpha = 0.0;
    float em = 0.22 + 0.78 * emission;
    float bandSum = bandLow + bandMid + bandHigh;

    // ── DERIVA ONÍRICA + TEMPERATURA DE COLOR ── (Fase 6, en rampa)
    float dream = 0.5 + 0.5 * sin(tm * 0.037) * sin(tm * 0.019 + 1.7);
    float rest  = 1.0 - clamp(energy * 1.6, 0.0, 1.0);
    vec3 warmTint = mix(mix(tint.rgb, tintDeep.rgb, 0.35 * (1.0 - energy)),
                        tintHot.rgb, 0.22 * energy);
    warmTint = mix(warmTint, mix(tintDeep.rgb, tint.rgb, 0.65), 0.14 * dream * rest);

    // insignia: modo compacto (reservado, sin uso hoy) — un punto de luz,
    // nada de las tres frecuencias.
    if (compact > 0.5) {
        float d = smoothstep(0.40, 0.0, rad);
        col   = mix(warmTint, tintHot.rgb, 0.45) * d * (0.30 + 0.9 * emission) * (0.6 + energy);
        alpha = d * (0.45 + 0.55 * emission);
        fragColor = vec4(col, clamp(alpha, 0.0, 1.0)) * qt_Opacity;
        return;
    }

    // ══ FRECUENCIA 1 — CUERPO: absorción. El centro es denso/oscuro; el
    //    brillo sube monótono hacia el limbo. Antes el centro era el punto
    //    más brillante ("bombilla"); ahora es al revés ("volumen"). ══
    float bodyMask = smoothstep(0.98, 0.0, rad);
    float absorb   = smoothstep(0.0, 0.85, rad);              // 0 centro -> 1 limbo
    vec3  body     = mix(tintDeep.rgb * 0.5, warmTint, absorb);
    body = mix(body, warmTint, 0.18 * energy);                // "más lleno" con energía real
    col   += body * bodyMask * (0.34 + 0.5 * emission) * (0.6 + 0.5 * energy);
    alpha  = bodyMask * (0.55 + 0.35 * emission);

    // ── CAMPO DE INTERFERENCIA (Fase 6) — el patrón visible ──
    float ph  = energy * 6.2831 + flux * 3.5 + (bandLow - bandHigh) * 2.4;
    float rot = dashed > 0.5 ? 0.0 : tm * mix(0.35, 1.35, spin) + dream * 0.5 * rest;
    float s1 = sin(rad * 34.0 - rot * 1.6 + ang * 7.0 + ph);
    float s2 = sin(rad * 37.0 + rot * 2.0 - ang * 7.0 - ph * 0.6);
    float arm1 = smoothstep(0.34, 0.92, s1);
    float arm2 = smoothstep(0.34, 0.92, s2);
    float field = max(arm1, arm2) * 0.62 + arm1 * arm2 * 0.95;
    float fieldRing = smoothstep(1.02, 0.58, rad) * smoothstep(0.18, 0.46, rad);
    fieldRing *= mix(0.35, 1.0, ringOpen);
    if (fragmented > 0.5) fieldRing *= step(0.34, fract(ang * (5.0 / 6.2831) + 0.5 + tm * 0.05));
    if (dashed > 0.5)     fieldRing *= step(0.5, fract(rad * 26.0)) * 0.6;
    float emanate = smoothstep(1.0, 0.12, rad);
    col   += mix(tintDeep.rgb, warmTint, 0.6) * field * fieldRing * emanate
             * (0.4 + 0.9 * emission) * (0.4 + 0.8 * energy);
    alpha  = max(alpha, field * fieldRing * (0.25 + 0.6 * emission));

    // ══ FRECUENCIA 3 — MICRODETALLE: 2ª octava de ruido, amplitud creciente
    //    hacia el limbo. Textura de superficie, no forma. ══
    vec3 np = vec3(uv * 6.0 + rot * 0.15, tm * 0.05);
    float micro = vnoise(np) * 0.6 + vnoise(np * 2.13 + 11.0) * 0.4;
    micro = (micro - 0.5) * 2.0;                              // -1..1
    float microAmp = smoothstep(0.15, 0.95, rad) * 0.10;      // 0 centro -> 10% limbo
    col *= (1.0 + micro * microAmp);
    col += warmTint * (micro * 0.5 + 0.5) * microAmp * 0.35 * bodyMask;

    // ══ FRECUENCIA 2 — BORDE: fresnel nítido (~2px) + dispersión cromática
    //    ACOTADA A ESTA BANDA. Nunca un canal aislado: siempre hay un
    //    fresnel acromático de base y la dispersión sólo lo desplaza un
    //    poco, nunca lo sustituye. ══
    float limbR = 0.86;
    float rw = max(aa, 0.0035) * 1.6;                         // ancho ≈ 2px
    float rim = smoothstep(rw, 0.0, abs(rad - limbR));
    vec3  rimCol = mix(tint.rgb, tintHot.rgb, 0.55);
    float rimK = (0.55 + 0.9 * emission) * (0.7 + 0.6 * energy)
               * (1.0 + 2.2 * pow(transPhase, 1.6));          // flare en transición
    col   += rimCol * rim * rimK;
    alpha  = max(alpha, rim * (0.5 + 0.4 * emission));
    float caOff = 0.0035;
    float rimShiftR = smoothstep(rw, 0.0, abs((rad + caOff) - limbR)) - rim;
    float rimShiftB = smoothstep(rw, 0.0, abs((rad - caOff) - limbR)) - rim;
    col.r += rimCol.r * rimShiftR * rimK * 0.4;
    col.b += rimCol.b * rimShiftB * rimK * 0.4;

    // ── BARRIDO ESPECULAR — cada 7 s, un fulgor recorre el limbo una vez ──
    float cyc = fract(tm / 7.0);
    float sweepAng = cyc * 6.2831853;
    float da0 = abs(mod(ang - sweepAng + 3.14159265, 6.2831853) - 3.14159265);
    float spec = smoothstep(0.30, 0.0, da0) * rim;
    col   += mix(tintHot.rgb, vec3(1.0), 0.5) * spec * (0.7 + 0.5 * emission);
    alpha  = max(alpha, spec * 0.7);

    // ── ARCOS ORBITALES lentos (Fase 6) ──
    float orb1 = smoothstep(0.020 + aa, 0.0, abs(rad - 0.855))
               * (0.55 + 0.45 * sin(ang * 3.0 + tm * 0.5 * mix(0.4, 1.2, spin)));
    float orb2 = smoothstep(0.016 + aa, 0.0, abs(rad - 0.945))
               * (0.55 + 0.45 * sin(ang * 2.0 - tm * 0.33));
    vec3 fieldRingCol = mix(tintDeep.rgb, warmTint, 0.62);
    col   += fieldRingCol * (orb1 * 0.22 + orb2 * 0.14) * (0.45 + 0.8 * emission);
    alpha  = max(alpha, (orb1 * 0.18 + orb2 * 0.12) * (0.4 + 0.5 * emission));

    // ── CORONA MAGNÉTICA — impulsada por energía/flux/bandas REALES ──
    {
        float k = clamp(max(max(energy, flux), bandSum * 0.6), 0.0, 1.0);
        if (k > 0.05) {
            float corona = 0.0;
            for (int a = 0; a < 4; a++) {
                float fa = float(a);
                float base = fa * 1.5708 + tm * (0.05 + 0.03 * fa)
                           + 4.0 * hash(vec3(fa, 2.0, 0.0));
                float da = abs(mod(ang - base + 3.14159, 6.28318) - 3.14159);
                float span = 0.42 + 0.24 * sin(tm * 0.7 + fa);
                float loop = smoothstep(span, 0.0, da);
                float h = 0.80 + (0.28 + 0.12 * sin(tm * 1.9 + fa * 2.0)) * k * loop;
                float arc = smoothstep(0.028 + aa, 0.0, abs(rad - h)) * loop
                          * smoothstep(1.12, 0.80, rad);
                corona += arc;
            }
            vec3 cc = mix(warmTint, tintHot.rgb, 0.5);
            col   += cc * corona * k * (0.5 + 0.7 * emission);
            alpha  = max(alpha, corona * k * 0.5);
        }
    }

    // ── ONDA DE CHOQUE tras un cambio de estado ──
    if (transPhase > 0.001) {
        float wr = (1.0 - transPhase) * 1.15;
        float shock = smoothstep(0.055, 0.0, abs(rad - wr)) * transPhase;
        col   += mix(warmTint, tintHot.rgb, 0.5) * shock * (0.5 + 0.6 * emission);
        alpha  = max(alpha, shock * 0.45 * (0.4 + 0.6 * emission));
    }

    // ── ANILLO DE FORMA DE ONDA — sólo con audio real ──
    if (bandSum > 0.02) {
        float wv = sin(ang * 7.0  + tm * 2.1) * bandMid
                 + sin(ang * 13.0 - tm * 1.4) * bandHigh
                 + sin(ang * 4.0  + tm * 0.8) * bandLow;
        float wring = smoothstep(0.045 + aa, 0.0, abs(rad - (0.80 + 0.055 * wv)));
        col   += mix(warmTint, tintHot.rgb, 0.25) * wring * bandSum * (0.6 + 0.5 * emission);
        alpha  = max(alpha, wring * bandSum * 0.55);
    }

    // ── SATÉLITE COMPAÑERO ──
    {
        float satSp = mix(0.10, 0.34, spin);
        float satA  = tm * satSp + 1.0;
        vec2 satP = mat2(0.87, -0.50, 0.50, 0.87)
                  * vec2(cos(satA) * 0.92, sin(satA) * 0.34);
        float satD = length(uv - satP);
        float satFront = 0.5 + 0.5 * sin(satA);
        float sat = smoothstep(0.044 + aa, 0.0, satD);
        float satGlow = smoothstep(0.17, 0.0, satD);
        col   += mix(warmTint, tintHot.rgb, 0.7) * (sat * 0.9 + satGlow * 0.16)
               * (0.5 + 0.6 * energy) * em;
        alpha  = max(alpha, sat * 0.8 * em);
        float shadow = smoothstep(0.24, 0.03, satD) * satFront
                     * 0.20 * (0.4 + 0.6 * emission);
        col *= (1.0 - shadow);
    }

    // DITHER anti-banding
    float dth = fract(sin(dot(qt_TexCoord0 * vec2(443.0, 731.0), vec2(1.0, 1.0))) * 4375.85) - 0.5;
    col += dth * (1.0 / 255.0);

    // Tonemap suave: mantiene `col` en un rango predecible para que el
    // umbral de bloom (luminancia >= 0,72) signifique algo estable, en vez
    // de perseguir acumulados HDR sin techo.
    col = col / (1.0 + max(max(col.r, col.g), col.b) * 0.22);

    float mask = smoothstep(1.05, 0.96, rad);
    fragColor = vec4(col, clamp(alpha, 0.0, 1.0) * mask) * qt_Opacity;
}
