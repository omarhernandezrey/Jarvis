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
    // (6) BLOOM BICOLOR: el bloom estrecho tira a cian-caliente; el ancho, a
    // azul profundo. El glow gana la misma rampa que el cuerpo, no un tinte
    // plano.
    b0 *= vec3(1.00, 1.04, 1.10);
    b1 *= vec3(0.72, 0.86, 1.16);
    vec3 rgb = c.rgb + b0 * k0 + b1 * k1;
    // tonemap MUY suave: sólo recorta el blanco quemado; deja que el centro
    // nítido del núcleo conserve su intensidad (antes 0.55 lo aplanaba).
    rgb = rgb / (1.0 + rgb * 0.34);
    float bloomA = max(b0.r, max(b0.g, b0.b)) * k0 + max(b1.r, max(b1.g, b1.b)) * k1;
    float a = clamp(max(c.a, bloomA), 0.0, 1.0);
    // difuminar los bordes del propio recuadro: sin arista visible del layer
    // (se apaga tanto color como alpha para que no quede ni un gris de fondo)
    vec2 e = abs(qt_TexCoord0 - 0.5) * 2.0;
    float edge = 1.0 - smoothstep(0.55, 0.98, dot(e, e));
    rgb *= edge;
    a *= edge;
    fragColor = vec4(rgb, a) * qt_Opacity;
}
