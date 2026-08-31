pragma Singleton
import QtQuick

// ─────────────────────────────────────────────────────────────────────────────
//  DESIGN — fuente única de verdad del sistema de diseño de la vista JARVIS.
//
//  Regla dura (ver brief, Fase 1.2): NINGÚN color, radio, duración, tamaño de
//  fuente o valor de espaciado se escribe fuera de este archivo. Todo lo demás
//  referencia `Design.*`. Si algo no está aquí, se añade aquí, no en el sitio
//  de uso.
//
//  La profundidad se construye con luz (gradientes desde `lightOrigin`), no con
//  box-shadow. El glow es escaso: solo lo emiten el núcleo y el estado activo.
// ─────────────────────────────────────────────────────────────────────────────
QtObject {
    id: d

    // ── COLOR ────────────────────────────────────────────────────────────────
    // Planos de profundidad (luminancia y saturación decrecientes hacia el fondo).
    readonly property color bgVoid:   "#04070D"   // fondo absoluto (plano más atrás)
    readonly property color bgAbyss:  "#070C16"   // plano de fondo / campo lejano

    // Superficie translúcida con desenfoque. `surfaceColor` ya lleva su alpha
    // (0.72); `surfaceBlur` es el radio de blur para el MultiEffect que la pinta.
    readonly property color surfaceColor: Qt.rgba(0x0B / 255, 0x12 / 255, 0x20 / 255, 0.72)
    readonly property real  surfaceBlur:  32

    // Líneas de 1px entre bloques. NUNCA recuadros: la etiqueta de un bloque va
    // en su regla lateral, no flotando encima.
    readonly property color hairline: Qt.rgba(0.62, 0.71, 0.82, 0.14)

    // Actividad. `cyan` = primaria (estado activo), `azure` = secundaria/profundidad.
    readonly property color cyan:  "#4DE8FF"
    readonly property color azure: "#2B7FFF"

    // Semáforo de salud de subsistemas.
    readonly property color ok:    "#35E08A"   // online
    readonly property color warn:  "#FFC857"   // degradado
    readonly property color alert: "#FF4D5E"   // fallo

    // Texto: primario / secundario / metadato.
    readonly property color textPrimary:   "#C9D6E4"
    readonly property color textSecondary: "#7E8FA3"
    readonly property color textMeta:      "#4A5A6E"

    // Blanco puro: reservado al punto de luz del núcleo de partículas. No usar
    // para texto ni bordes.
    readonly property color emitCore: "#FFFFFF"

    // Fuente de luz única y coherente: arriba-centro. Coordenadas normalizadas
    // (0..1) sobre el área que se esté iluminando. Todos los gradientes de
    // profundidad parten de aquí.
    readonly property point lightOrigin: Qt.point(0.5, -0.15)

    // Helper: un color de emisión con alpha, para halos y glow. `base` debería
    // ser SIEMPRE `cyan` o `azure` (nada más emite).
    function glow(base, alpha) { return Qt.rgba(base.r, base.g, base.b, alpha) }
    // Helper: mezcla lineal de dos colores (t = 0..1). Para interpolar estado.
    function mix(a, b, t) {
        return Qt.rgba(a.r + (b.r - a.r) * t,
                       a.g + (b.g - a.g) * t,
                       a.b + (b.b - a.b) * t,
                       a.a + (b.a - a.a) * t)
    }

    // ── TIPOGRAFÍA ───────────────────────────────────────────────────────────
    // Verificadas con `fc-list` en la máquina objetivo:
    //   mono → "JetBrainsMono Nerd Font" (instalada)
    //   sans → "Ubuntu" (instalada). "Inter" NO está instalada; Ubuntu es el
    //          sustituto acordado. La lista de respaldo cubre el resto de casos.
    readonly property string fontMono: "JetBrainsMono Nerd Font"
    readonly property string fontSans: "Ubuntu"

    // Escala tipográfica: jerarquía real, nunca todo igual.
    //   meta 12 · small 13 · body 15 · title 18 · large 24 · display 40
    readonly property int fsMeta:    12
    readonly property int fsSmall:   13
    readonly property int fsBody:    15
    readonly property int fsTitle:   18
    readonly property int fsLarge:   24
    readonly property int fsDisplay: 40

    // ── ESPACIADO ────────────────────────────────────────────────────────────
    // Todo múltiplo de 4. Usar `Design.sp(n)` en vez de literales.
    readonly property int unit: 4
    function sp(n) { return n * d.unit }

    // ── RADIOS ───────────────────────────────────────────────────────────────
    // No hay un radio único para todo: 2px en HUD, 10px en superficies.
    readonly property int radiusHud:     2
    readonly property int radiusSurface: 10

    // ── MOTION ───────────────────────────────────────────────────────────────
    readonly property int durFast: 140
    readonly property int durBase: 220
    readonly property int durSlow: 320

    // easing cubic-bezier(.2,.8,.2,1) — formato spline de QML: pares de control
    // + punto final (1,1). Se aplica como:
    //   easing.type: Design.easeType; easing.bezierCurve: Design.easeCurve
    readonly property int easeType: Easing.BezierSpline
    readonly property var easeCurve: [0.2, 0.8, 0.2, 1.0, 1.0, 1.0]

    // Interpolación estándar entre estados del núcleo (brief, Fase 2): 220 ms,
    // nunca corte seco.
    readonly property int stateXfade: durBase
}
