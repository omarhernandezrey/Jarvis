#version 330 core
in vec2 vUv;
out vec4 fragColor;

uniform float u_orbFlow;
uniform float u_energy;
uniform float u_activity;
uniform float u_neutronKick;
uniform float u_neutronFlow;
uniform float u_neutronMotion;
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

vec2 neutronPos(float fi, float tt) {
    float h1 = hash12(vec2(fi, 3.1));
    float h2 = hash12(vec2(fi, 7.7));
    float h3 = hash12(vec2(fi, 11.3));
    float h4 = hash12(vec2(fi, 17.9));
    float dir = h4 > 0.5 ? 1.0 : -1.0;
    float omega = 2.50 + 3.50 * h1;
    // reparto angular casi uniforme (ángulo áureo) para que, cuando la
    // fase se congela en reposo, no queden amontonados en un lado.
    float ang = tt * omega * dir + fi * 2.399963 + h2 * 0.60;
    // radio siempre LEJOS del núcleo: los neutrones golpean la red de
    // filamentos, no se esconden en el brillo central. El radio sube y
    // baja a otra frecuencia, así que rayan el orbe en espirales cerradas.
    float radPhase = tt * (1.20 + 2.40 * h3) * (0.60 + 0.40 * h1)
                   + h4 * TAU;
    float rad = EDGE * (0.32 + 0.42 * (0.5 + 0.5 * sin(radPhase)));
    float squash = 0.50 + 0.35 * h3;
    vec2 p = vec2(cos(ang) * rad, sin(ang) * rad * squash);
    p += EDGE * (0.02 + 0.04 * clamp(u_neutronMotion, 0.0, 1.0)) * vec2(
        sin(tt * omega * 2.30 + h2 * TAU),
        cos(tt * omega * 1.90 + h1 * TAU)
    );
    // nervio: un temblor de alta frecuencia que sólo aparece con el pulso
    // de interacción — el neutrón se sobresalta en vez de sólo acelerar.
    p += EDGE * 0.05 * clamp(u_neutronKick, 0.0, 1.0) * vec2(
        sin(tt * (5.3 + 3.0 * h3) + h1 * TAU),
        cos(tt * (4.7 + 2.0 * h4) + h2 * TAU)
    );
    float plen = length(p);
    if (plen > EDGE * 0.92) {
        p *= (EDGE * 0.92) / max(plen, 1e-5);
    }
    return rot2(h2 * 0.90 + tt * (0.16 + 0.10 * h1) * dir) * p;
}

void main() {
    vec2 uv = (vUv - 0.5) * 2.0;
    float sd = length(uv);
    if (sd > 1.05) {
        fragColor = vec4(0.0);
        return;
    }

    float t = max(u_orbFlow, 0.0);
    float energy = clamp(u_energy, 0.0, 1.0);
    float activity = clamp(u_activity, 0.0, 1.6);
    float stateMult = clamp(u_stateMult, 0.2, 4.0);
    // el reloj interno late despacio en reposo (la red y el núcleo
    // respiran, nunca se ven muertos) y se dispara cuando Jarvis
    // interactúa de verdad: al teclear/enviar, escuchar, hablar o pensar,
    // este tiempo se acelera y todo se agita con fuerza.
    float speed = (0.90 + 0.35 * stateMult)
                * (0.75 + 0.45 * energy + 0.55 * activity);
    // pulso crudo de interacción (tecla, envío, respuesta, cambio de
    // estado): úsalo para que el átomo reaccione AL INSTANTE, no sólo
    // más rápido con el tiempo — un organismo vivo responde al toque.
    float kick = clamp(u_neutronKick, 0.0, 1.0);

    // nube de rayos-X: el borde ya no es un vidrio nítido, se difumina como
    // el halo de un escaneo (referencia: "rotation atom with filaments").
    float body = smoothstep(EDGE + 0.070, EDGE - 0.150, sd);
    float edgeFade = smoothstep(EDGE, EDGE * 0.70, sd);

    // --- advección orgánica: la red fluye, no sólo rota ---
    vec2 np = uv * 0.58;
    vec2 driftA = vec2(0.026, -0.018) * t * speed;
    vec2 driftB = vec2(-0.016, 0.022) * t * speed;
    float wn1 = texture(u_noise3d, vec3(np + driftA, t * 0.19 * speed)).r - 0.5;
    float wn2 = texture(u_noise3d, vec3(np * 1.7 + 0.31 + driftB, -t * 0.15 * speed)).g - 0.5;
    float wn3 = texture(u_noise3d, vec3(np * 2.6 - 0.17 + driftB * 0.6, t * 0.27 * speed)).g - 0.5;
    vec2 warp = (vec2(wn1, wn2) + vec2(wn3, -wn3) * 0.45)
              * (0.060 + 0.030 * energy + 0.035 * activity + 0.085 * kick) * edgeFade;

    // --- dos redes (3ª en calidad alta): giran de verdad, como un átomo
    // que rota en 3D, no sólo se mecen. `squashY` finge el tumbo del eje
    // (se achata hacia un anillo de canto, como en el video de referencia). ---
    float squashY = 0.74 + 0.26 * cos(t * 0.045 * speed + 0.4);
    float breathe = 1.0 + (0.030 + 0.020 * energy + 0.022 * activity)
                  * sin(t * 1.05 * stateMult + 0.6);
    float angA = t * 0.16 * speed + 0.12 * sin(t * 0.37 * stateMult);
    vec2 uvA = rot2(angA) * (uv * vec2(1.0, squashY)) * breathe;
    vec4 texA = texture(u_filaments, uvA * 0.5 + 0.5 + warp, -0.35);

    float angB = -t * 0.12 * speed + 0.10 * sin(t * 0.29 * stateMult + 1.9);
    vec2 uvB = rot2(angB) * (uv * vec2(1.0, squashY)) * (0.86 * breathe);
    vec4 texB = texture(u_filaments, uvB * 0.5 + 0.5 - warp * 0.80, -0.30);

    vec4 texC = vec4(0.0);
    if (u_steps >= 32) {
        float angC = t * 0.095 * speed + 0.08 * sin(t * 0.23 + 0.9);
        vec2 uvC = rot2(angC) * (uv * vec2(1.0, squashY)) * 1.14;
        texC = texture(u_filaments, uvC * 0.5 + 0.5 + warp * 1.30, -0.25);
    }

    float vein = max(texA.r, max(texB.g * 0.85, texC.g * 0.45)) * body;
    float cloud = max(texA.b, max(texB.b * 0.85, texC.b * 0.60)) * body;
    vein = smoothstep(0.10, 0.52, vein);
    cloud = smoothstep(0.08, 0.72, cloud);
    float thinVein = smoothstep(0.62, 0.94, vein);

    // --- cuerpo: vidrio índigo profundo, mucho más contenido — el brillo
    // ambiental ya no compite con la mancha oscura del núcleo ---
    float radial = smoothstep(0.02, EDGE, sd);
    vec3 deepBody = mix(u_tint2 * 0.13, u_tint * 0.09, radial)
                  + vec3(0.002, 0.007, 0.020);
    deepBody += mix(u_tint, u_accent, 0.55) * smoothstep(0.34, EDGE, sd) * 0.045;
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
    vec3 filCol = mix(u_tint, u_accent, 0.42);
    float patch = 0.70 + 0.30 * smoothstep(0.15, 0.75, cloud);
    bodyCol += filCol * fil * patch * (0.12 + 0.18 * energy + 0.26 * activity);
    bodyCol += mix(u_accent, vec3(1.0), 0.30) * filCore
             * (0.07 + 0.20 * energy + 0.18 * activity);

    // núcleo: mancha de tinta ancha y densa al centro (átomo de rayos-X),
    // no un foco de luz. "Respira" con el latido (su radio se expande y
    // contrae, no sólo su brillo) y se CONTRAE de golpe ante un pulso de
    // interacción real — un flinch, como algo vivo que reacciona al
    // toque. `hot` sólo aporta un acento sutil, jamás un pico blanco puro.
    vec3 inkDeep = mix(inkCol, u_tint2, 0.45) * 0.55;
    float heartbeat = sin(t * (1.9 + 2.4 * energy + 1.4 * activity) + 0.4);
    float beat = 0.55 + 0.45 * heartbeat;
    float breathR = 1.0 + 0.11 * heartbeat - 0.18 * kick;
    float breathR2 = max(breathR * breathR, 0.22);
    float darkCore = exp(-sd * sd * 5.0 / breathR2);
    bodyCol = mix(bodyCol, inkDeep, darkCore * (0.74 + 0.20 * activity + 0.12 * beat));
    float nucleusDensity = exp(-sd * sd * 22.0 / breathR2);
    bodyCol = mix(bodyCol, inkDeep * 0.45, nucleusDensity
                * (0.58 + 0.24 * activity + 0.16 * energy) * (0.6 + 0.4 * beat));
    vec3 hot = mix(u_tint2, u_accent, 0.5);
    bodyCol += hot * exp(-sd * sd * 70.0) * (1.0 - nucleusDensity * 0.6)
             * (0.05 + 0.10 * energy + 0.12 * activity) * (0.5 + 0.5 * beat);

    // onda de choque: un anillo que viaja desde el centro hacia afuera en
    // cada pulso de interacción real (voz, tecla, envío, cambio de
    // estado) — "vivo" es reaccionar al instante, no sólo acelerarse.
    float ringPhase = sd * 13.0 - t * 5.0;
    float shockRing = exp(-pow(fract(ringPhase * 0.5 + 0.5) - 0.5, 2.0) * 50.0)
                     * kick * body;
    bodyCol += mix(u_tint2, u_accent, 0.45) * shockRing * 0.40;

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

    // --- neutrones: en reposo quedan suspendidos; cuando Jarvis
    // interactúa de verdad (teclas, envío, respuesta, voz) la fase avanza
    // y cruzan el plasma a toda velocidad dejando estela. ---
    float heat = clamp(activity + 0.85 * u_neutronKick, 0.0, 1.8);
    float neutronFlow = max(u_neutronFlow, 0.0);
    float neutronMotion = clamp(u_neutronMotion, 0.0, 1.0);
    float tailSpan = (0.065 + 0.060 * min(heat, 1.2) + 0.012 * energy)
                   * neutronMotion;
    float sparkShadow = 0.0;
    vec3 sparkEmission = vec3(0.0);
    if (body > 0.01) {
        for (int i = 0; i < 10; i++) {
            float fi = float(i);
            float h1 = hash12(vec2(fi, 3.1));
            float h2 = hash12(vec2(fi, 7.7));
            float h3 = hash12(vec2(fi, 11.3));
            vec2 head = neutronPos(fi, neutronFlow);
            vec2 mid = neutronPos(fi, neutronFlow - tailSpan * 0.5);
            vec2 tail = neutronPos(fi, neutronFlow - tailSpan);

            float headSize = 0.024 + 0.012 * h2 + 0.004 * heat
                           + 0.005 * neutronMotion;
            float trailWidth = 0.0050 + 0.0030 * h3 + 0.0018 * heat
                             + 0.0018 * neutronMotion;
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

            float trailGlow = (exp(-dot(o1, o1) / (trailWidth * trailWidth)) * w1
                             + exp(-dot(o2, o2) / (trailWidth * trailWidth)) * w2)
                             * neutronMotion;
            float trailCore = (exp(-dot(o1, o1) / (trailWidth * trailWidth * 0.16)) * w1
                             + exp(-dot(o2, o2) / (trailWidth * trailWidth * 0.16)) * w2)
                             * neutronMotion;
            float trailShadow = (exp(-dot(o1, o1) / (trailWidth * trailWidth * 4.0)) * w1
                               + exp(-dot(o2, o2) / (trailWidth * trailWidth * 4.0)) * w2)
                               * neutronMotion;

            float flicker = mix(1.0, 0.82 + 0.18 * sin(t * (4.0 + 3.0 * h3) + h1 * TAU),
                                neutronMotion);
            // gota de tinta, no chispa blanca: el nodo oscurece su zona
            // (sparkShadow) y sólo asoma un acento índigo tenue, con una
            // cola translúcida en vez de un rastro brillante.
            sparkShadow += (exp(-hd2 / (headSize * headSize * 1.6)) * 3.6
                          + trailShadow * 0.22) * flicker;
            float alive = 0.82 + 0.28 * neutronMotion;
            vec3 inkBead = mix(inkCol, u_tint2, 0.5) * 0.6;
            sparkEmission += (inkBead * (bead * 1.10 + headGlow * 0.22 + trailCore * 0.30) * flicker
                            + mix(u_tint, vec3(1.0), 0.12) * (shell * 0.40) * flicker
                            + mix(u_tint, u_accent, 0.30) * trailGlow * 0.20 * flicker
                            + mix(u_tint, u_accent, 0.45) * halo * 0.015 * flicker) * alive;
        }
    }
    float sparkMask = body * (0.72 + 0.28 * cloud);
    bodyCol = mix(bodyCol, vec3(0.0), clamp(sparkShadow * 0.70, 0.0, 0.85));
    bodyCol += sparkEmission * sparkMask
             * (0.55 + 0.25 * energy + 0.35 * heat);

    // pase final: por más que el resto del shader sume brillo (nubes,
    // pulsos, chispas), el centro del átomo tiene que seguir leyendo como
    // una mancha de tinta ancha y densa — se atenúa la luminancia ahí en
    // vez de pelear término a término contra cada fuente de luz. El borde
    // de la mancha se perturba con el mismo ruido que ya mueve la red,
    // para que no sea un círculo perfecto.
    float inkMask = smoothstep(0.46, 0.04, sd + 0.07 * (wn1 + wn2));
    bodyCol *= mix(1.0, 0.18, inkMask * (0.85 + 0.15 * beat));

    // --- halo difuso de rayos-X, no un filo de vidrio nítido ---
    float rimThin = smoothstep(EDGE - 0.040, EDGE - 0.010, sd)
                  * (1.0 - smoothstep(EDGE - 0.010, EDGE + 0.050, sd));
    float rimWide = smoothstep(EDGE - 0.140, EDGE - 0.020, sd)
                  * (1.0 - smoothstep(EDGE - 0.010, EDGE + 0.090, sd));
    float halo = exp(-max(sd - EDGE, 0.0) * 10.0);
    float haloFar = exp(-max(sd - EDGE, 0.0) * 3.0);

    vec3 col = bodyCol * body;
    col += mix(u_tint, vec3(1.0), 0.22)
         * (rimThin * (0.20 + 0.04 * activity) + rimWide * 0.08);
    col += u_tint * halo * (0.06 + 0.03 * energy + 0.04 * min(activity, 1.0));
    col += u_tint2 * haloFar * 0.045;
    col *= (1.0 + 0.16 * u_hover);

    float alpha = clamp(body * 0.91 + rimThin * 0.38 + rimWide * 0.08
                      + halo * 0.06, 0.0, 1.0);
    fragColor = vec4(col, alpha);
}
