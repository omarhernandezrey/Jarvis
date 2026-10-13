#version 330 core
// Rayos de dios (crepuscular rays) — blur radial en espacio de pantalla
// desde la posición real del orbe, sobre el mismo buffer de brillos ya
// extraído para el bloom (se reutiliza, no se vuelve a extraer). Técnica
// pública estándar ("volumetric light scattering as post-process",
// Mitchell/Sousa — GPU Gems 3): acumula muestras hacia la fuente con
// decaimiento geométrico. 32–48 muestras según calidad (nunca menos).
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;   // brillos ya extraídos (bloom_extract), 1/4 res
uniform vec2  u_lightUv;      // posición real del orbe, 0..1
uniform int   u_numSamples;   // 32..48 según calidad
uniform float u_density;
uniform float u_decay;
uniform float u_exposure;

const int MAX_SAMPLES = 48;

void main() {
    vec2 deltaUv = (vUv - u_lightUv) * (u_density / float(u_numSamples));
    vec2 sampleUv = vUv;
    float illum = 1.0;
    vec3 acc = vec3(0.0);
    for (int i = 0; i < MAX_SAMPLES; i++) {
        if (i >= u_numSamples) break;
        sampleUv -= deltaUv;
        acc += texture(u_source, sampleUv).rgb * illum;
        illum *= u_decay;
    }
    fragColor = vec4(acc * u_exposure / float(u_numSamples), 1.0);
}
