#version 330 core
// Destello anamórfico: blur MUY alargado en horizontal sobre lo brillante
// ya extraído (bloom_extract). 12 muestras a lo largo de X, peso gaussiano
// aproximado — nunca en vertical, así se lee como un lente anamórfico, no
// como más bloom.
in vec2 vUv;
out vec4 fragColor;

uniform sampler2D u_source;   // salida de bloom_extract, misma resolución 1/4
uniform float u_texelX;       // 1.0 / ancho del FBO de origen
uniform float u_stretch;      // longitud del destello en texeles

void main() {
    float weights[6] = float[6](0.22, 0.18, 0.13, 0.09, 0.05, 0.02);
    vec3 sum = texture(u_source, vUv).rgb * 0.24;
    for (int i = 1; i <= 6; i++) {
        float off = float(i) * u_stretch * u_texelX;
        float w = weights[i - 1];
        sum += texture(u_source, vUv + vec2(off, 0.0)).rgb * w;
        sum += texture(u_source, vUv - vec2(off, 0.0)).rgb * w;
    }
    fragColor = vec4(sum, 1.0);
}
