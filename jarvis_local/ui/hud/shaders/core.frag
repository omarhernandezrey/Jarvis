#version 440

// ─────────────────────────────────────────────────────────────────────────────
//  NÚCLEO JARVIS — ENTIDAD viva. Campo de interferencia + cuerpo SDF amorfo
//  (lóbulos migrantes) + volumen con filamentos de datos + pupila que sigue al
//  ratón + motas orbitales + fulguraciones de energía. El DATO real
//  (energy/flux/bandas) modula fase, temperatura de color y actividad.
//
//  Fase 8: cuerpo orgánico (no esfera perfecta), pupila que MIRA, filamentos
//  de datos en la superficie, 10 motas orbitales, fulguraciones en picos,
//  oclusión suave del campo, temperatura de color con energía, AA adaptativo
//  (fwidth), flare del rim en el cambio de estado.
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
    float aa = fwidth(rad) * 1.4;            // (5) AA adaptativo

    vec2 par = vec2(pointerX, -pointerY) * 0.06;     // paralaje

    vec3 col = vec3(0.0);
    float alpha = 0.0;
    float em = 0.22 + 0.78 * emission;

    // (7) TEMPERATURA DE COLOR — el cuerpo se CALIENTA al trabajar y se enfría
    // en reposo. Estado base = tinte del estado; sube hacia tintHot con energía.
    vec3 warmTint = mix(mix(tint.rgb, tintDeep.rgb, 0.35 * (1.0 - energy)),
                        tintHot.rgb, 0.22 * energy);

    // ── CAMPO DE INTERFERENCIA ──
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
    // (4) OCLUSIÓN — el campo se atenúa donde el cuerpo está delante (centro):
    //     el orbe se lee como núcleo sólido con el campo envolviéndolo.
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

    // ── CAMPO DE ENERGÍA — dos arcos orbitales lentos ──
    float orb1 = smoothstep(0.020 + aa, 0.0, abs(rad - 0.855))
               * (0.55 + 0.45 * sin(ang * 3.0 + tm * 0.5 * mix(0.4, 1.2, spin)));
    float orb2 = smoothstep(0.016 + aa, 0.0, abs(rad - 0.945))
               * (0.55 + 0.45 * sin(ang * 2.0 - tm * 0.33));
    vec3 fieldRingCol = mix(tintDeep.rgb, warmTint, 0.62);
    col   += fieldRingCol * (orb1 * 0.24 + orb2 * 0.15) * (0.45 + 0.8 * emission);
    alpha  = max(alpha, (orb1 * 0.20 + orb2 * 0.13) * (0.4 + 0.5 * emission));

    // ── MOTAS ORBITALES — puntos diminutos girando en el campo. Vida. ──
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
        col   += mix(warmTint, tintHot.rgb, 0.55) * mote * (0.45 + 0.75 * energy) * em;
        alpha  = max(alpha, mote * 0.6 * em);
    }

    // ── FULGURACIONES — en picos de energía real, lenguas que salen del limbo
    if (max(energy, flux) > 0.30) {
        float k = clamp(max(energy, flux), 0.0, 1.0);
        float tongue = pow(0.5 + 0.5 * sin(ang * 5.0 + tm * 1.7), 14.0);
        float prom = smoothstep(0.024 + aa, 0.0,
                        abs(rad - (0.78 + 0.20 * tongue * k)))
                   * smoothstep(1.02, 0.78, rad) * tongue * k;
        col   += mix(warmTint, tintHot.rgb, 0.45) * prom * (0.6 + 0.6 * emission);
        alpha  = max(alpha, prom * 0.5);
    }

    // ── ONDA DE CHOQUE tras un cambio de estado ──
    if (transPhase > 0.001) {
        float wr = (1.0 - transPhase) * 1.15;
        float shock = smoothstep(0.055, 0.0, abs(rad - wr)) * transPhase;
        col   += mix(warmTint, tintHot.rgb, 0.5) * shock * (0.5 + 0.6 * emission);
        alpha  = max(alpha, shock * 0.45 * (0.4 + 0.6 * emission));
    }

    // ── ANILLO DE FORMA DE ONDA — sólo con audio real ──
    float bandSum = bandLow + bandMid + bandHigh;
    if (bandSum > 0.02) {
        float wv = sin(ang * 7.0  + tm * 2.1) * bandMid
                 + sin(ang * 13.0 - tm * 1.4) * bandHigh
                 + sin(ang * 4.0  + tm * 0.8) * bandLow;
        float wring = smoothstep(0.045 + aa, 0.0, abs(rad - (0.80 + 0.055 * wv)));
        col   += mix(warmTint, tintHot.rgb, 0.25) * wring * bandSum * (0.6 + 0.5 * emission);
        alpha  = max(alpha, wring * bandSum * 0.55);
    }

    // ── BORDE + FLECO CROMÁTICO + FLARE de transición ──
    float rimLit = 0.35 + 0.85 * (0.5 + 0.5 *
                   dot(normalize(uv + 1e-4), normalize(vec2(-0.45, 0.78))));
    float caOff = 0.013;
    float rw = 0.05 + aa;
    float rimR = smoothstep(rw, 0.0, abs((rad + caOff) - 0.76)) * rimLit;
    float rimG = smoothstep(rw, 0.0, abs( rad          - 0.76)) * rimLit;
    float rimB = smoothstep(rw, 0.0, abs((rad - caOff) - 0.76)) * rimLit;
    vec3  rc = mix(warmTint, tintHot.rgb, 0.32);
    float rimK = (0.42 + 0.7 * emission) * (0.7 + 0.5 * energy)
               * (1.0 + 2.4 * pow(transPhase, 1.6));      // (6) flare
    col.r += rc.r * rimR * rimK;
    col.g += rc.g * rimG * rimK;
    col.b += rc.b * rimB * rimK;
    alpha  = max(alpha, rimG * (0.45 + 0.4 * emission));

    // ── VOLUMEN INTERIOR (raymarch) — tejido vivo, no objeto opaco ──
    if (rad < 0.80 && compact < 0.5) {
        vec3 ro = vec3((uv - par * 1.7) * 1.18, 2.0);
        vec3 rd = vec3(0.0, 0.0, -1.0);
        float t = 1.15;
        float hit = 0.0;
        for (int i = 0; i < 22; i++) {
            vec3 p = ro + rd * t;
            float d = mapSDF(p);
            if (d < 0.002) { hit = 1.0; break; }
            t += max(d * 0.9, 0.006);
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
            glow *= em;

            col += glow;
            alpha = max(alpha, clamp(fres * 0.9 + thick * 0.55 + 0.15 * emission, 0.0, 1.0));
        }
    }

    // ── PUPILA que MIRA — un vacío que absorbe en el centro (deriva hacia el
    //    ratón: el orbe te sigue), rodeado de un iris encendido. Lo que lo
    //    hace parecer VIVO y alienígena.
    if (compact < 0.5) {
        vec2 pc = par * 3.4;                       // la pupila mira al ratón
        float rp = length(uv - pc);
        float pupil = smoothstep(0.10, 0.045, rp);
        float iris  = smoothstep(0.045, 0.085, rp) * smoothstep(0.20, 0.11, rp);
        col *= (1.0 - pupil * (0.85 + 0.1 * emission));   // absorbe la luz
        col += mix(tintHot.rgb, vec3(1.0), 0.35) * iris * (0.35 + 0.9 * energy) * em;
        alpha = max(alpha, iris * 0.75 * em + pupil * 0.55 * (0.4 + 0.6 * emission));
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
