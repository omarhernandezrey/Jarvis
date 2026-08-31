#version 440

// Extracción de altas luces: conserva sólo lo que supera `threshold`.
// Entrada: la textura del núcleo (layer del CoreShader). Salida: alimenta el
// blur de bloom.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;
    float qt_Opacity;
    float threshold;   // 0..1
    float knee;        // suavizado del umbral
};
layout(binding = 1) uniform sampler2D source;

void main() {
    vec4 c = texture(source, qt_TexCoord0);
    float b = max(c.r, max(c.g, c.b));
    float w = smoothstep(threshold, threshold + max(knee, 1e-4), b);
    fragColor = vec4(c.rgb * w, c.a * w) * qt_Opacity;
}
