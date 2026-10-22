#version 330 core
in vec2 vUv;
out vec4 fragColor;

uniform float u_time;
uniform float u_energy;
uniform float u_activity;
uniform float u_neutronKick;
uniform vec3  u_tint;
uniform vec3  u_tint2;
uniform vec3  u_accent;
uniform float u_stateMult;
uniform float u_hover;
uniform int   u_steps;
uniform sampler3D u_noise3d;
uniform sampler2D u_filaments;

const float EDGE = 0.717;
const float TAU = 6.28318530718;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float ringBand(vec2 p, float radius, float aspect, float angle, float width) {
    float ca = cos(angle);
    float sa = sin(angle);
    vec2 q = mat2(ca, -sa, sa, ca) * p;
    q.y /= aspect;
    float d = abs(length(q) - radius);
    float aa = max(fwidth(d), 1e-4);
    return smoothstep(width + aa, width - aa, d);
}

mat2 rot2(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat2(c, -s, s, c);
}

vec2 neutronPos(float fi, float tt, float rush) {
    float h1 = hash12(vec2(fi, 3.1));
    float h2 = hash12(vec2(fi, 7.7));
    float h3 = hash12(vec2(fi, 11.3));
    float h4 = hash12(vec2(fi, 17.9));
    float dir = h4 > 0.5 ? 1.0 : -1.0;
    float omega = (2.50 + 3.50 * h1) * rush;
    float ang = tt * omega * dir + h2 * TAU;
    // radio siempre LEJOS del núcleo: los neutrones golpean la red de
    // filamentos, no se esconden en el brillo central. El radio sube y
    // baja a otra frecuencia, así que rayan el orbe en espirales cerradas.
    float radPhase = tt * (1.20 + 2.40 * h3) * rush * (0.60 + 0.40 * h1)
                   + h4 * TAU;
    float rad = EDGE * (0.32 + 0.42 * (0.5 + 0.5 * sin(radPhase)));
    float squash = 0.50 + 0.35 * h3;
    vec2 p = vec2(cos(ang) * rad, sin(ang) * rad * squash);
    p += EDGE * (0.02 + 0.04 * min(rush, 3.0)) * vec2(
        sin(tt * omega * 2.30 + h2 * TAU),
        cos(tt * omega * 1.90 + h1 * TAU)
    );
    float plen = length(p);
    if (plen > EDGE * 0.92) {
        p *= (EDGE * 0.92) / max(plen, 1e-5);
    }
    return rot2(h2 * TAU + tt * (0.16 + 0.10 * h1) * dir) * p;
}

void main() {
    vec2 uv = (vUv - 0.5) * 2.0;
    float sd = length(uv);
    if (sd > 1.05) {
        fragColor = vec4(0.0);
        return;
    }

    float t = max(u_time, 0.0);
    float energy = clamp(u_energy, 0.0, 1.0);
    float activity = clamp(u_activity, 0.0, 1.6);
    float stateMult = clamp(u_stateMult, 0.2, 4.0);
    // la red nunca está quieta: respira en reposo y se agita con voz,
    // tecleo, respuestas y generación (actividad real del sistema)
    float speed = (0.90 + 0.35 * stateMult)
                * (0.75 + 0.45 * energy + 0.55 * activity);

    // esfera de vidrio: interior sólido con borde suave
    float body = smoothstep(EDGE + 0.006, EDGE - 0.045, sd);
    float edgeFade = smoothstep(EDGE, EDGE * 0.78, sd);

    // --- advección orgánica: la red fluye, no sólo rota ---
    vec2 np = uv * 0.58;
    vec2 driftA = vec2(0.026, -0.018) * t * speed;
    vec2 driftB = vec2(-0.016, 0.022) * t * speed;
    float wn1 = texture(u_noise3d, vec3(np + driftA, t * 0.19 * speed)).r - 0.5;
    float wn2 = texture(u_noise3d, vec3(np * 1.7 + 0.31 + driftB, -t * 0.15 * speed)).g - 0.5;
    float wn3 = texture(u_noise3d, vec3(np * 2.6 - 0.17 + driftB * 0.6, t * 0.27 * speed)).g - 0.5;
    vec2 warp = (vec2(wn1, wn2) + vec2(wn3, -wn3) * 0.45)
              * (0.060 + 0.030 * energy + 0.035 * activity) * edgeFade;

    // --- dos redes (3ª en calidad alta): respiran, giran y se mecen ---
    float breathe = 1.0 + (0.040 + 0.025 * energy + 0.030 * activity)
                  * sin(t * 1.05 * stateMult + 0.6);
    float angA = 0.28 * sin(t * 0.37 * stateMult) + t * 0.05 * speed;
    vec2 uvA = rot2(angA) * uv * breathe;
    vec4 texA = texture(u_filaments, uvA * 0.5 + 0.5 + warp, -0.35);

    float angB = -0.24 + 0.20 * sin(t * 0.29 * stateMult + 1.9) - t * 0.035 * speed;
    vec2 uvB = rot2(angB) * uv * (0.86 * breathe);
    vec4 texB = texture(u_filaments, uvB * 0.5 + 0.5 - warp * 0.80, -0.30);

    vec4 texC = vec4(0.0);
    if (u_steps >= 32) {
        float angC = 0.80 + 0.18 * sin(t * 0.23 + 0.9) + t * 0.028 * speed;
        vec2 uvC = rot2(angC) * uv * 1.14;
        texC = texture(u_filaments, uvC * 0.5 + 0.5 + warp * 1.30, -0.25);
    }

    float vein = max(texA.r, max(texB.g * 0.85, texC.g * 0.45)) * body;
    float cloud = max(texA.b, max(texB.b * 0.85, texC.b * 0.60)) * body;
    vein = smoothstep(0.10, 0.52, vein);
    cloud = smoothstep(0.08, 0.72, cloud);
    float thinVein = smoothstep(0.62, 0.94, vein);

    // --- cuerpo: vidrio índigo profundo, coherente con el HUD oscuro ---
    float radial = smoothstep(0.02, EDGE, sd);
    vec3 deepBody = mix(u_tint2 * 0.20, u_tint * 0.14, radial)
                  + vec3(0.003, 0.010, 0.030);
    deepBody += mix(u_tint, u_accent, 0.55) * smoothstep(0.34, EDGE, sd) * 0.07;
    deepBody *= 0.95 + 0.10 * (wn1 + 0.5);
    vec3 bodyCol = deepBody;

    // --- filamentos luminosos: la red es la que vive ---
    vec3 inkCol = u_tint2 * 0.05 + vec3(0.001, 0.004, 0.014);
    bodyCol = mix(bodyCol, inkCol, clamp(vein * 0.30, 0.0, 0.45));
    float coreCloud = smoothstep(0.52, 0.03, sd);
    bodyCol += mix(u_tint2, u_tint, 0.40) * cloud * coreCloud
             * (0.12 + 0.14 * energy);

    float fil = smoothstep(0.10, 0.50, vein);
    float filCore = smoothstep(0.52, 0.92, vein);
    vec3 filCol = mix(u_tint, u_accent, 0.55);
    float patch = 0.70 + 0.30 * smoothstep(0.15, 0.75, cloud);
    bodyCol += filCol * fil * patch * (0.20 + 0.28 * energy + 0.38 * activity);
    bodyCol += mix(u_accent, vec3(1.0), 0.55) * filCore
             * (0.13 + 0.32 * energy + 0.28 * activity);

    // núcleo: halo oscuro + corazón blanco que late con la voz
    float darkCore = exp(-sd * sd * 24.0);
    bodyCol = mix(bodyCol, inkCol * 0.55, darkCore * 0.60);
    float beat = 0.55 + 0.45 * sin(t * (1.9 + 2.4 * energy + 1.4 * activity) + 0.4);
    float nucleus = exp(-sd * sd * 120.0);
    vec3 hot = mix(u_accent, vec3(1.0), 0.60);
    bodyCol += hot * exp(-sd * sd * 18.0) * activity * 0.06;
    bodyCol += hot * nucleus
             * (0.30 + 0.45 * energy + 0.40 * activity) * (0.55 + 0.45 * beat);
    bodyCol += vec3(1.0) * exp(-sd * sd * 520.0)
             * (0.40 + 0.45 * energy + 0.30 * activity);

    // nodos vivos: chispas que se encienden y apagan sobre los filamentos
    float nodeNoise = texture(u_noise3d, vec3(uv * 2.2 + warp, t * 0.11)).r;
    float nodes = smoothstep(0.58, 0.78, nodeNoise) * thinVein;
    bodyCol += hot * nodes * (0.08 + 0.30 * energy + 0.35 * activity)
             * (0.55 + 0.45 * sin(t * 1.6));

    // --- pulsos que recorren las venas (energía + actividad del sistema) ---
    float runA = pow(0.5 + 0.5 * sin(sd * 18.0
                 - t * (1.6 + 3.0 * energy + 1.8 * activity) - wn1 * 3.0), 6.0);
    float runB = pow(0.5 + 0.5 * sin(sd * 10.0
                 + t * (1.0 + 2.0 * energy + 1.2 * activity) + wn2 * 2.0), 8.0);
    float veinsPulse = (runA * 0.75 + runB * 0.45) * thinVein;
    bodyCol += mix(u_tint, vec3(1.0), 0.50) * veinsPulse
             * (0.06 + 0.42 * energy + 0.38 * activity);

    // --- ondas de potencia: la energía late hacia el borde ---
    float waveMask = smoothstep(EDGE, 0.10, sd) * smoothstep(0.02, 0.10, sd) * body;
    float waveA = 0.5 + 0.5 * sin(sd * 17.0
                - t * (2.0 + 2.6 * energy + 1.5 * activity) + wn1 * 2.5);
    float waveB = 0.5 + 0.5 * sin(sd * 11.0
                + t * (1.2 + 1.6 * energy + 1.0 * activity) + wn2 * 2.0);
    bodyCol += filCol * (waveA + waveB * 0.55) * waveMask
             * (0.02 + 0.06 * energy + 0.10 * activity);

    // brillo de vidrio arriba-izquierda + sombreado volumétrico
    vec2 hp = uv - vec2(-0.24, -0.30);
    float highlight = exp(-dot(hp, hp) * 7.0);
    bodyCol += vec3(0.07, 0.09, 0.11) * highlight * body;
    float shade = clamp(dot(normalize(vec3(uv, 0.85)), normalize(vec3(-0.45, 0.55, 0.90))), 0.0, 1.0);
    bodyCol *= 0.85 + 0.22 * shade;

    // --- órbitas internas: arcos finos que giran con una cuenta de luz ---
    float ringAngleA = -0.52 + t * 0.14;
    float ringAngleB = 1.12 - t * 0.10;
    float ringAngleC = 0.34 + t * 0.07;
    float bandA = ringBand(uv, 0.590, 0.40, ringAngleA, 0.008);
    float bandAGlow = ringBand(uv, 0.590, 0.40, ringAngleA, 0.045);
    float bandB = ringBand(uv, 0.452, 0.56, ringAngleB, 0.011);
    float bandC = ringBand(uv, 0.300, 0.26, ringAngleC, 0.007);
    float bandMask = smoothstep(EDGE, EDGE - 0.09, sd) * smoothstep(0.015, 0.08, sd);
    float bands = (bandA * 0.26 + bandAGlow * 0.06 + bandB * 0.14 + bandC * 0.22) * bandMask;
    bodyCol = mix(bodyCol, inkCol * 1.15, clamp(bands * 0.35, 0.0, 0.30));

    // electrones: una estela recorre cada órbita (no un aro dibujado)
    vec2 qA = rot2(ringAngleA) * uv;
    qA.y /= 0.40;
    vec2 qB = rot2(ringAngleB) * uv;
    qB.y /= 0.56;
    float phiA = atan(qA.y, qA.x + 1e-5);
    float phiB = atan(qB.y, qB.x + 1e-5);
    float trailA = pow(0.5 + 0.5 * cos(phiA - t * 1.0), 12.0);
    float trailB = pow(0.5 + 0.5 * cos(phiB + t * 0.8), 14.0);
    float orbitLine = (bandA * (0.10 + 0.55 * trailA)
                     + bandB * (0.08 + 0.45 * trailB)
                     + bandC * 0.10) * bandMask;
    bodyCol += mix(u_accent, vec3(1.0), 0.35) * orbitLine
             * (0.60 + 0.55 * energy + 0.45 * activity);

    // --- neutrones: proyectiles de luz que cruzan el plasma a toda
    // velocidad y dejan estela; la interacción real (teclas, envío,
    // respuesta, voz) los acelera sin piedad. ---
    float heat = clamp(activity + 0.85 * u_neutronKick, 0.0, 1.8);
    float neutronRush = (0.70 + 0.55 * stateMult)
                      * (0.62 + 0.55 * energy + 1.05 * heat);
    float tailSpan = 0.050 + 0.045 * min(heat, 1.2) + 0.010 * energy;
    float sparkShadow = 0.0;
    vec3 sparkEmission = vec3(0.0);
    if (body > 0.01) {
        for (int i = 0; i < 10; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.1));
            float h2 = hash12(vec2(fi, 7.7));
            float h3 = hash12(vec2(fi, 11.3));
            vec2 head = neutronPos(fi, t, neutronRush);
            vec2 mid = neutronPos(fi, t - tailSpan * 0.5, neutronRush);
            vec2 tail = neutronPos(fi, t - tailSpan, neutronRush);

            float headSize = 0.018 + 0.010 * h2 + 0.003 * heat;
            float trailWidth = 0.0035 + 0.0025 * h3 + 0.0015 * heat;
            vec2 hd = uv - head;
            float hd2 = dot(hd, hd);
            float hlen = sqrt(hd2);
            float bead = 1.0 - smoothstep(headSize * 0.52, headSize * 0.95, hlen);
            float headGlow = exp(-hd2 / (headSize * headSize * 4.0));
            float shell = exp(-hd2 / (headSize * headSize * 3.0))
                        * (1.0 - exp(-hd2 / (headSize * headSize * 1.8)));
            float halo = exp(-hd2 / (headSize * headSize * 14.0));

            vec2 pa1 = uv - mid;
            vec2 ba1 = head - mid;
            float t1 = clamp(dot(pa1, ba1) / max(dot(ba1, ba1), 1e-7), 0.0, 1.0);
            vec2 o1 = pa1 - ba1 * t1;
            float w1 = 0.40 + 0.60 * t1;

            vec2 pa2 = uv - tail;
            vec2 ba2 = mid - tail;
            float t2 = clamp(dot(pa2, ba2) / max(dot(ba2, ba2), 1e-7), 0.0, 1.0);
            vec2 o2 = pa2 - ba2 * t2;
            float w2 = 0.08 + 0.36 * t2;

            float trailGlow = exp(-dot(o1, o1) / (trailWidth * trailWidth)) * w1
                            + exp(-dot(o2, o2) / (trailWidth * trailWidth)) * w2;
            float trailCore = exp(-dot(o1, o1) / (trailWidth * trailWidth * 0.16)) * w1
                            + exp(-dot(o2, o2) / (trailWidth * trailWidth * 0.16)) * w2;
            float trailShadow = exp(-dot(o1, o1) / (trailWidth * trailWidth * 4.0)) * w1
                              + exp(-dot(o2, o2) / (trailWidth * trailWidth * 4.0)) * w2;

            float flicker = 0.82 + 0.18 * sin(t * (4.0 + 3.0 * h3) + h1 * TAU);
            sparkShadow += (exp(-hd2 / (headSize * headSize * 2.5)) * 2.5
                          + trailShadow * 0.12) * flicker;
            sparkEmission += vec3(1.0) * (bead * 2.30 + headGlow * 0.45 + trailCore * 0.45) * flicker
                           + mix(u_tint, vec3(1.0), 0.18) * (shell * 0.85) * flicker
                           + mix(u_tint, u_accent, 0.35) * trailGlow * 0.28 * flicker
                           + mix(u_tint, u_accent, 0.55) * halo * 0.025 * flicker;
        }
    }
    float sparkMask = body * (0.72 + 0.28 * cloud);
    bodyCol = mix(bodyCol, vec3(0.0), clamp(sparkShadow * 0.55, 0.0, 0.78));
    bodyCol += sparkEmission * sparkMask
             * (0.95 + 0.35 * energy + 0.50 * heat);

    // --- borde de vidrio + halo de la esfera ---
    float rimThin = smoothstep(EDGE - 0.016, EDGE - 0.006, sd)
                  * (1.0 - smoothstep(EDGE - 0.002, EDGE + 0.010, sd));
    float rimWide = smoothstep(EDGE - 0.060, EDGE - 0.010, sd)
                  * (1.0 - smoothstep(EDGE - 0.002, EDGE + 0.020, sd));
    float halo = exp(-max(sd - EDGE, 0.0) * 30.0);
    float haloFar = exp(-max(sd - EDGE, 0.0) * 9.0);

    vec3 col = bodyCol * body;
    col += mix(u_tint, vec3(1.0), 0.35)
         * (rimThin * (0.38 + 0.05 * activity) + rimWide * 0.07);
    col += u_tint * halo * (0.08 + 0.04 * energy + 0.05 * min(activity, 1.0));
    col += u_tint2 * haloFar * 0.030;
    col *= (1.0 + 0.16 * u_hover);

    float alpha = clamp(body * 0.91 + rimThin * 0.38 + rimWide * 0.08
                      + halo * 0.06, 0.0, 1.0);
    fragColor = vec4(col, alpha);
}
