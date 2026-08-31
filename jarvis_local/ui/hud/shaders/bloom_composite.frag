#version 440

// Composición aditiva: núcleo original + dos pasadas de bloom (radios distintos).

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4  qt_Matrix;
    float qt_Opacity;
    float k0;   // peso del bloom estrecho
    float k1;   // peso del bloom ancho
};
layout(binding = 1) uniform sampler2D source;   // núcleo (nítido)
layout(binding = 2) uniform sampler2D bloom0;   // blur estrecho
layout(binding = 3) uniform sampler2D bloom1;   // blur ancho

void main() {
    vec4 c  = texture(source, qt_TexCoord0);
    vec3 b0 = texture(bloom0, qt_TexCoord0).rgb;
    vec3 b1 = texture(bloom1, qt_TexCoord0).rgb;
    vec3 rgb = c.rgb + b0 * k0 + b1 * k1;
    float bloomA = max(b0.r, max(b0.g, b0.b)) * k0 + max(b1.r, max(b1.g, b1.b)) * k1;
    float a = clamp(max(c.a, bloomA), 0.0, 1.0);
    fragColor = vec4(rgb, a) * qt_Opacity;
}
