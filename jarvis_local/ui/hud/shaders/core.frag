#version 440

// ─────────────────────────────────────────────────────────────────────────────
//  NÚCLEO JARVIS — ENTIDAD viva (Fase 9 · "obra maestra").
//
//  Campo de interferencia + cuerpo SDF amorfo (lóbulos migrantes) + PLASMA
//  VOLUMÉTRICO interior con paralaje por capas (mover el ratón revela un
//  ADENTRO con profundidad, no una cáscara) + IRIS alienígena de hojas que
//  dilata con la energía y sigue al ratón, con un reflejo vivo en la pupila +
//  PIEL CELULAR bioluminiscente que late con el audio + CORONA magnética
//  (arcos que salen del limbo y regresan) + satélite compañero que proyecta
//  sombra + iridiscencia de película fina en el borde + deriva onírica de
//  color en reposo (batido de minutos, nunca se repite). Todo modulado por el
//  DATO real (energy/flux/bandas). Sin uniforms nuevos.
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
// FBM corto (2 octavas) para el plasma interior. Barato a propósito.
float fbm2(vec3 p) {
    return vnoise(p) * 0.65 + vnoise(p * 2.03 + 11.0) * 0.35;
}
// iridiscencia (película fina): fase → color que se desliza suavemente
vec3 irid(float t) {
    return 0.5 + 0.5 * cos(6.2831 * (t + vec3(0.0, 0.33, 0.67)));
}
// Voronoi 2D barato: (distancia a la célula más cercana, id de la célula)
vec2 voro(vec2 x) {
    vec2 n = floor(x), f = fract(x);
    float md = 8.0;
    vec2  mid = vec2(0.0);
    for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
        vec2 g = vec2(float(i), float(j));
        vec2 o = vec2(hash(vec3(n + g, 1.0)), hash(vec3(n + g, 7.0)));
        vec2 r = g + o - f;
        float d = dot(r, r);
        if (d < md) { md = d; mid = n + g + o; }
    }
    return vec2(sqrt(md), hash(vec3(mid, 3.0)));
}

// lóbulos migrantes: el cuerpo NO es una esfera perfecta — dos bultos lentos
// que se desplazan por la superficie. Barato (sin pow, sin ruido extra).
float lobes(vec3 p, float tm) {
    vec3 np = normalize(p + 1e-4);
    vec3 d1 = normalize(vec3(sin(tm * 0.11), 0.55, cos(tm * 0.13)));
    vec3 d2 = normalize(vec3(cos(tm * 0.17) + 0.3, -0.35, sin(tm * 0.09)));
    float a = max(dot(np, d1), 0.0);
    float b = max(dot(np, d2), 0.0);
    return a * a * 0.7 + b * b * b * 0.45;
}

float mapSDF(vec3 p) {
    float tm = reduced > 0.5 ? 0.0 : time;
    float d1 = vnoise(p * 3.0 + vec3(0.0, tm * 0.13, 0.0)) - 0.5;
    float d2 = vnoise(p * 6.5 - tm * 0.09) - 0.5;
    float disp = (d1 + d2 * 0.45) * 0.085 * (0.45 + 0.9 * energy);
    float lb   = lobes(p, tm) * 0.065 * (0.55 + 0.55 * energy);
    // respiración de la geometría (irregular: sin + sin lento desfasado)
    float br = 0.012 * sin(tm * 0.8) + 0.006 * sin(tm * 0.37 + 1.4);
    float baseR = 0.58 + br * (1.0 - 0.6 * energy);
    return length(p) - baseR - disp - lb;
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
    if (rad > 1.12) { fragColor = vec4(0.0); return; }
    float ang = atan(uv.y, uv.x);
    float tm = reduced > 0.5 ? 0.0 : time;
    float aa = fwidth(rad) * 1.4;            // AA adaptativo

    vec2 par = vec2(pointerX, -pointerY) * 0.06;     // paralaje

    vec3 col = vec3(0.0);
    float alpha = 0.0;
    float em = 0.22 + 0.78 * emission;
    float bandSum = bandLow + bandMid + bandHigh;

    // ── DERIVA ONÍRICA ──  En reposo, el color y la estructura evolucionan
    // lentísimamente con un batido largo (minutos): nunca se repite, nunca
    // está muerto. Se desvanece cuando hay trabajo real.
    float dream = 0.5 + 0.5 * sin(tm * 0.037) * sin(tm * 0.019 + 1.7);
    float rest  = 1.0 - clamp(energy * 1.6, 0.0, 1.0);

    // ── TEMPERATURA DE COLOR ──  El cuerpo se calienta al trabajar y se
    // enfría en reposo; además, en reposo respira color por la rampa.
    vec3 warmTint = mix(mix(tint.rgb, tintDeep.rgb, 0.35 * (1.0 - energy)),
                        tintHot.rgb, 0.22 * energy);
    warmTint = mix(warmTint, mix(tintDeep.rgb, tint.rgb, 0.65), 0.14 * dream * rest);

    // ── CAMPO DE INTERFERENCIA ──
    float ph  = energy * 6.2831 + flux * 3.5 + (bandLow - bandHigh) * 2.4;
    float rot = dashed > 0.5 ? 0.0 : tm * mix(0.35, 1.35, spin) + dream * 0.5 * rest;
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
    // OCLUSIÓN — el campo se atenúa donde el cuerpo está delante: el orbe se
    // lee como núcleo sólido con el campo envolviéndolo.
    float occ = smoothstep(0.55, 0.14, rad);
    field *= mix(1.0, 0.30, occ);

    vec3 depthCol = mix(tintDeep.rgb, warmTint, smoothstep(0.98, 0.30, rad));
    depthCol = mix(depthCol, tintHot.rgb,
                   smoothstep(0.26, 0.02, rad) * (0.30 + 0.50 * energy));
    col   += depthCol * field * ring * emanate * (0.5 + 1.3 * emission) * (0.45 + 0.9 * energy);
    alpha += field * ring * (0.30 + 0.70 * emission);

    // halo central suave
    float halo = smoothstep(0.60, 0.0, rad);
    col += mix(warmTint, tintDeep.rgb, 0.25) * halo * halo * (0.05 + 0.28 * energy) * emission;

    // ── ARCOS ORBITALES lentos ──
    float orb1 = smoothstep(0.020 + aa, 0.0, abs(rad - 0.855))
               * (0.55 + 0.45 * sin(ang * 3.0 + tm * 0.5 * mix(0.4, 1.2, spin)));
    float orb2 = smoothstep(0.016 + aa, 0.0, abs(rad - 0.945))
               * (0.55 + 0.45 * sin(ang * 2.0 - tm * 0.33));
    vec3 fieldRingCol = mix(tintDeep.rgb, warmTint, 0.62);
    col   += fieldRingCol * (orb1 * 0.24 + orb2 * 0.15) * (0.45 + 0.8 * emission);
    alpha  = max(alpha, (orb1 * 0.20 + orb2 * 0.13) * (0.4 + 0.5 * emission));

    // ── MOTAS ORBITALES + NACIMIENTO DE ESTRELLA ──  Puntos girando en el
    // campo; rara vez uno fulgura y se estira antes de apagarse.
    for (int m = 0; m < 10; m++) {
        float fm = float(m);
        float sd = fract(sin(fm * 127.1) * 43758.5453);
        float orbR = 0.60 + 0.36 * fract(sin(fm * 71.7) * 1234.5);
        float sp = (0.25 + 0.9 * sd) * mix(0.4, 1.7, spin) * (0.45 + 0.7 * energy);
        float aOff = sd * 6.2831;
        float ecc = 0.62 + 0.5 * fract(sin(fm * 13.3) * 99.0);
        vec2 mp = vec2(cos(tm * sp + aOff) * orbR * ecc, sin(tm * sp + aOff) * orbR);
        float rm = fm * 0.63;
        mp = mat2(cos(rm), -sin(rm), sin(rm), cos(rm)) * mp;
        float dpt = length(uv - mp);
        float mote = smoothstep(0.016 + aa, 0.0, dpt);
        float birth = smoothstep(0.90, 1.0, fract(sin(fm * 19.7) * 91.3 + tm * 0.07));
        float streak = smoothstep(0.10 + aa, 0.0, dpt) * birth;
        col   += mix(warmTint, tintHot.rgb, 0.55) * mote * (0.45 + 0.75 * energy) * em;
        col   += vec3(1.0) * streak * 0.7 * em;
        alpha  = max(alpha, max(mote, streak * 0.8) * 0.6 * em);
    }

    // ── CORONA MAGNÉTICA ──  Arcos que salen del limbo y regresan, impulsados
    // por energía / flux / bandas REALES. Sustituye a las lenguas rectas.
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

    // ── SATÉLITE COMPAÑERO ──  Un cuerpo coherente en órbita inclinada.
    // Proyecta una sombra tenue sobre el campo al pasar por delante. Sistema,
    // no chispa.
    {
        float satSp = mix(0.10, 0.34, spin);
        float satA  = tm * satSp + 1.0;
        vec2 satP = mat2(0.87, -0.50, 0.50, 0.87)
                  * vec2(cos(satA) * 0.92, sin(satA) * 0.34);
        float satD = length(uv - satP);
        float satFront = 0.5 + 0.5 * sin(satA);           // ~1 = por delante
        float sat = smoothstep(0.044 + aa, 0.0, satD);
        float satGlow = smoothstep(0.17, 0.0, satD);
        col   += mix(warmTint, tintHot.rgb, 0.7) * (sat * 0.9 + satGlow * 0.16)
               * (0.5 + 0.6 * energy) * em;
        alpha  = max(alpha, sat * 0.8 * em);
        float shadow = smoothstep(0.24, 0.03, satD) * satFront
                     * 0.20 * (0.4 + 0.6 * emission);
        col *= (1.0 - shadow);
    }

    // ── BORDE ──  Fleco cromático + IRIDISCENCIA de película fina + FLARE de
    // transición. El color del borde se desliza con el ángulo y el ratón.
    float rimLit = 0.35 + 0.85 * (0.5 + 0.5 *
                   dot(normalize(uv + 1e-4), normalize(vec2(-0.45, 0.78))));
    float caOff = 0.013;
    float rw = 0.05 + aa;
    float rimR = smoothstep(rw, 0.0, abs((rad + caOff) - 0.76)) * rimLit;
    float rimG = smoothstep(rw, 0.0, abs( rad          - 0.76)) * rimLit;
    float rimB = smoothstep(rw, 0.0, abs((rad - caOff) - 0.76)) * rimLit;
    vec3  rc = mix(warmTint, tintHot.rgb, 0.32);
    float rimK = (0.42 + 0.7 * emission) * (0.7 + 0.5 * energy)
               * (1.0 + 2.4 * pow(transPhase, 1.6));      // flare
    col.r += rc.r * rimR * rimK;
    col.g += rc.g * rimG * rimK;
    col.b += rc.b * rimB * rimK;
    vec3 sheen = irid(rad * 2.4 + ang * 0.12 + (par.x + par.y) * 2.6 + tm * 0.02);
    col += sheen * rimG * (0.16 + 0.28 * energy) * (0.5 + 0.7 * emission);
    alpha  = max(alpha, rimG * (0.45 + 0.4 * emission));

    // ── VOLUMEN INTERIOR (raymarch) — tejido vivo, no objeto opaco ──
    if (rad < 0.80 && compact < 0.5) {
        vec3 ro = vec3((uv - par * 1.7) * 1.18, 2.0);
        vec3 rd = vec3(0.0, 0.0, -1.0);
        float t = 1.15;
        float hit = 0.0;
        for (int i = 0; i < 18; i++) {
            vec3 p = ro + rd * t;
            float d = mapSDF(p);
            if (d < 0.002) { hit = 1.0; break; }
            t += max(d * 0.9, 0.007);
            if (t > 2.9) break;
        }
        if (hit > 0.5) {
            vec3 p = ro + rd * t;
            vec3 n = calcNormal(p);
            vec3 vv = -rd;
            vec3 L = normalize(vec3(0.16 + par.x * 0.6, 0.90, 0.55 - par.y * 0.5));
            float diff = max(dot(n, L), 0.0);
            float fres = pow(1.0 - max(dot(n, vv), 0.0), 2.3);
            float thick = clamp((0.62 - length(p)) * 3.2, 0.0, 1.0);

            vec3 hlf = normalize(L + vv);
            float ndh = max(dot(n, hlf), 0.0);
            vec3 tang = normalize(cross(n, vec3(0.0, 1.0, 0.0)) + vec3(1e-4));
            float tdh = dot(tang, hlf);
            float aniso = pow(ndh, 36.0) * exp(-tdh * tdh * 5.0);
            float sweep = pow(0.5 + 0.5 * sin(ang * 2.0 - tm * 0.7), 7.0);

            // FILAMENTOS DE DATOS: líneas finas que corren por la superficie
            // siguiendo el flujo del normal. Lectura de "procesando".
            float flow = fract(n.y * 4.5 + n.x * 2.5 - n.z * 1.5
                               - tm * 1.4 * mix(0.5, 1.6, spin));
            float fil = smoothstep(0.055, 0.0, abs(flow - 0.5))
                      * smoothstep(0.85, 0.25, fres);

            vec3 plasmaCol = mix(tintDeep.rgb, warmTint, 0.7);
            vec3 glow = plasmaCol * (0.14 + 0.7 * energy) * (0.45 + 0.55 * thick);
            glow += mix(warmTint, tintHot.rgb, 0.4) * fres * (0.42 + 0.9 * energy);
            glow += vec3(1.0) * aniso * sweep * (0.36 + 0.6 * energy);
            glow += warmTint * diff * 0.10;
            glow += mix(tintHot.rgb, vec3(1.0), 0.6) * fil * (0.25 + 0.7 * energy);

            // PLASMA VOLUMÉTRICO — tras tocar la superficie avanzamos DENTRO
            // del cuerpo acumulando densidad con warp de dominio. Cada capa se
            // desplaza con el ratón → hay un ADENTRO con profundidad 3D real,
            // no una cáscara pintada.
            if (reduced < 0.5) {
                vec3 pv = p;
                float dens = 0.0;
                for (int kk = 0; kk < 4; kk++) {
                    pv += rd * 0.10;
                    vec3 q = pv * 3.3 + vec3(par * (1.6 + float(kk) * 0.8), 0.0)
                           + vec3(0.0, tm * 0.18, tm * 0.05);
                    float dn = fbm2(q + vnoise(q * 0.7) * 0.9);
                    dens += smoothstep(0.55, 0.87, dn) * (1.0 - float(kk) * 0.18);
                }
                dens *= thick;
                vec3 pcB = mix(warmTint, tintHot.rgb, 0.65);
                vec3 plasma = mix(mix(tintDeep.rgb, warmTint, 0.5), pcB,
                                  clamp(dens * 0.8, 0.0, 1.0));
                glow += plasma * dens * (0.22 + 0.9 * energy);

                // PIEL CELULAR bioluminiscente — ommatidios que laten con el
                // audio REAL. Ondas de luz recorren las células.
                vec2 skinUV = vec2(atan(n.z, n.x) * 1.9, n.y * 3.2)
                            + vec2(tm * 0.05, 0.0);
                vec2 vc = voro(skinUV * 4.0);
                float cellIn = smoothstep(0.05, 0.17, vc.x);
                float cpulse = 0.5 + 0.5 * sin(vc.y * 42.0 - tm * 3.0 + bandMid * 12.0);
                float cellLit = cellIn * cpulse * (0.10 + 0.9 * (bandLow + bandHigh));
                glow += mix(warmTint, tintHot.rgb, 0.5) * cellLit * 0.6;
            }

            glow *= em;
            col += glow;
            alpha = max(alpha, clamp(fres * 0.9 + thick * 0.55 + 0.15 * emission, 0.0, 1.0));
        }
    }

    // ── IRIS ALIENÍGENA ──  No un círculo: hojas que dilatan con la energía
    // (se abre al escuchar/hablar, se cierra al pensar) y siguen al ratón,
    // con fibras radiales y un reflejo vivo en la pupila. Es lo que lo hace
    // parecer un ser y no un gráfico.
    if (compact < 0.5) {
        vec2 pc = par * 3.4;                       // el iris mira al ratón
        vec2 pv = uv - pc;
        float rp = length(pv);
        float pang = atan(pv.y, pv.x);
        float dil = mix(0.052, 0.135, clamp(energy * 1.1, 0.0, 1.0));
        float bl  = 0.5 + 0.5 * cos(pang * 6.0 + tm * 0.25);      // hojas
        float edge = dil * (0.86 + 0.14 * bl);
        float pupil = smoothstep(edge + aa, edge - 0.02, rp);
        float iris  = smoothstep(edge, edge + 0.05, rp)
                    * smoothstep(edge + 0.15, edge + 0.05, rp);
        float fib   = smoothstep(0.006, 0.0, abs(fract(pang * 6.0 / 3.14159) - 0.5));
        col *= (1.0 - pupil * (0.88 + 0.1 * emission));           // absorbe la luz
        vec3 irisCol = mix(tintHot.rgb, vec3(1.0), 0.30);
        col += irisCol * iris * (0.40 + 0.95 * energy) * em;
        col += irisCol * iris * fib * 0.35 * em;
        float spec = smoothstep(0.020, 0.0, length(pv - vec2(-0.018, 0.020)));
        col += vec3(1.0) * spec * pupil * (0.45 + 0.55 * emission);
        alpha = max(alpha, iris * 0.8 * em + pupil * 0.6 * (0.4 + 0.6 * emission));
    }

    // insignia: punto de luz interior en vez del volumen
    if (compact > 0.5) {
        float d = smoothstep(0.40, 0.0, rad);
        col   += mix(warmTint, tintHot.rgb, 0.45) * d * (0.30 + 0.9 * emission) * (0.6 + energy);
        alpha  = max(alpha, d * (0.45 + 0.55 * emission));
    }

    // DITHER anti-banding
    float dth = fract(sin(dot(qt_TexCoord0 * vec2(443.0, 731.0), vec2(1.0, 1.0))) * 4375.85) - 0.5;
    col += dth * (1.0 / 255.0);

    float mask = smoothstep(1.05, 0.96, rad);
    fragColor = vec4(col, clamp(alpha, 0.0, 1.0) * mask) * qt_Opacity;
}
