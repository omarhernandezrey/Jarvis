#version 330 core
// Triángulo de pantalla completa compartido por todas las pasadas del
// pipeline (scene, extract, kawase, streak, composite): sin VBO de
// geometría, las 3 esquinas salen del propio índice de vértice.
out vec2 vUv;

void main() {
    vec2 pos = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vUv = pos;
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
