#version 440

// Atmósfera global: viñeta + grano temporal + aberración cromática (≤ unos px
// hacia los bordes). Es lo que separa una imagen renderizada de un dibujo.
// Se aplica como `layer.effect` de toda la escena; `source` es la escena.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;
    float qt_Opacity;
    float time;         // reloj cuantizado (~24 fps); 0 congela el grano
    float grainAmt;     // 0..~0.06
    float vignette;     // 0..~0.5
    float aberration;   // px máximos en la esquina
    float cornerRadius; // px — esquinas de la ventana sin marco (0 = recta)
    vec2  texel;        // 1.0 / resolución
};
layout(binding = 1) uniform sampler2D source;

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 c = uv - 0.5;
    float r = length(c) * 1.41421;                 // 0 centro · 1 esquina

    // aberración cromática que crece hacia el borde
    vec2 off = c * r * aberration;
    float rr = texture(source, uv + off * texel).r;
    vec4  gg = texture(source, uv);
    float bb = texture(source, uv - off * texel).b;
    vec3 col = vec3(rr, gg.g, bb);

    // viñeta
    col *= mix(1.0, 1.0 - vignette, smoothstep(0.30, 1.0, r));

    // grano temporal (por píxel de pantalla, varía con el tiempo)
    float g = (hash21(gl_FragCoord.xy + time * 411.0 + 0.5) - 0.5) * grainAmt;
    col += g;

    // esquinas redondeadas de la ventana sin marco (SDF de caja redondeada)
    float a = gg.a;
    if (cornerRadius > 0.5) {
        vec2 res = 1.0 / texel;
        vec2 p = (uv - 0.5) * res;
        vec2 q = abs(p) - (res * 0.5 - cornerRadius);
        float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - cornerRadius;
        a *= 1.0 - smoothstep(-1.0, 1.0, d);
    }

    fragColor = vec4(col, a) * qt_Opacity;
}
