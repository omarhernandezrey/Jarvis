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
    readonly property color surfaceColor: Qt.rgba(0x0A / 255, 0x11 / 255, 0x1E / 255, 0.82)
    readonly property real  surfaceBlur:  32

    // Líneas de 1px entre bloques. NUNCA recuadros: la etiqueta de un bloque va
    // en su regla lateral, no flotando encima. Sobre ventana transparente el
    // 0.14 era invisible; 0.26 se lee sin gritar.
    readonly property color hairline: Qt.rgba(0.66, 0.75, 0.86, 0.26)

    // Contorno de 1px para TEXTO sobre fondo transparente (style: Text.Outline).
    // No es blur: es un borde nítido que separa el glifo del escritorio.
    readonly property color textEdge: Qt.rgba(0.02, 0.04, 0.07, 0.72)

    // Actividad. `cyan` = primaria (estado activo), `azure` = secundaria/profundidad.
    readonly property color cyan:  "#4DE8FF"
    readonly property color azure: "#2B7FFF"

    // Semáforo de salud de subsistemas.
    readonly property color ok:    "#35E08A"   // online
    readonly property color warn:  "#FFC857"   // degradado
    readonly property color alert: "#FF4D5E"   // fallo

    // Texto: primario / secundario / metadato. Subidos para contraste sobre
    // escritorio real (la ventana es transparente, no hay panel detrás).
    readonly property color textPrimary:   "#E3ECF5"
    readonly property color textSecondary: "#9DB0C4"
    readonly property color textMeta:      "#7386A0"

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

    // ── ILUMINACIÓN GLOBAL (addendum §4) ────────────────────────────────────
    // El núcleo es la ÚNICA fuente de luz del sistema y esa luz está viva.
    // Lo alimenta Core.qml (posición en coords de escena, energía real, color
    // del estado). Cada hairline / borde / panel deriva su color y opacidad de
    // aquí: nada tiene un color fijo.
    property point corePos: Qt.point(0, 0)
    property real  coreEnergy: 0.0          // 0..1 dato real (RMS mic / tok·s / TTS)
    property color coreTint: azure          // color del estado actual
    property real  lightRadius: 720         // px: alcance de la luz (lo fija Main)

    // nivel de luz 0..1 en un punto de escena (sx, sy)
    function lightLevel(sx, sy) {
        var dx = sx - corePos.x, dy = sy - corePos.y
        var dn = Math.sqrt(dx * dx + dy * dy) / Math.max(1.0, lightRadius)
        var f = 1.0 / (1.0 + dn * dn * 2.6)          // caída suave
        return Math.min(1.0, (0.20 + 0.80 * f) * (0.88 + 0.40 * coreEnergy))
    }
    // color de una hairline/borde en ese punto: la base, teñida hacia el núcleo
    // y con la opacidad modulada por la luz (cerca = brilla, lejos = se apaga).
    function litHairline(sx, sy) {
        var l = lightLevel(sx, sy)
        var t = Math.min(0.65, l * 0.55 + coreEnergy * 0.20)
        var c = mix(hairline, coreTint, t)
        return Qt.rgba(c.r, c.g, c.b, hairline.a * (0.62 + 0.95 * l))
    }
    // un color base que "respira" con el núcleo (para texto secundario/metadato)
    function litText(base, sx, sy) {
        var l = lightLevel(sx, sy)
        var t = Math.max(0.0, Math.min(0.45, (l - 0.5) * 0.6 + coreEnergy * 0.35))
        return mix(base, mix(base, coreTint, 0.4), t)
    }

    // ── ARRANQUE (addendum §5) ──────────────────────────────────────────────
    // Un frente de luz que sale del núcleo y va revelando la interfaz por
    // DISTANCIA. `bootReveal` 0→1 lo anima Main una sola vez (≤900 ms). Con
    // valor 1 todo está revelado (estado normal).
    property real bootReveal: 1.0
    property real bootReach: 2000       // px que alcanza el frente en bootReveal=1

    // 0..1 cuánto ha llegado el frente a un punto de escena (1 = revelado)
    function reveal(sx, sy) {
        if (bootReveal >= 1.0) return 1.0
        var dx = sx - corePos.x, dy = sy - corePos.y
        var d = Math.sqrt(dx * dx + dy * dy)
        var front = bootReveal * bootReach
        var edge = 200.0
        return Math.max(0.0, Math.min(1.0, (front - d) / edge + 0.5))
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
    // No hay un radio único para todo: 2px en HUD, 10px en superficies,
    // 12px en la propia ventana (sin marco del SO).
    readonly property int radiusHud:     2
    readonly property int radiusSurface: 10
    readonly property int radiusWindow:  12

    // Canaleta para la sombra proyectada de la ventana sin marco.
    readonly property int windowShadowGutter: 22

    // ── MOTION ───────────────────────────────────────────────────────────────
    // Una sola escala temporal, sin literales sueltos por los .qml. De rápido a
    // lento según la INTENCIÓN del movimiento, no al azar:
    //   durMicro  micro-reacción (acuse, hover)        ~120 ms
    //   durFast   feedback inmediato                    140 ms
    //   durBase   transición normal (entrada de chat…)  220 ms
    //   durSlow   transición amplia                     320 ms
    //   stateXfade cambio de ESTADO del sistema         380 ms  (deliberado)
    //   durHold   sostener un aviso ("copiado")        1400 ms
    //   durBoot   secuencia de arranque                1100 ms
    readonly property int durMicro: 120
    readonly property int durFast: 140
    readonly property int durBase: 220
    readonly property int durSlow: 320
    readonly property int stateXfade: 380
    readonly property int durHold: 1400
    readonly property int durBoot: 1100

    // Latido del cursor de streaming: regular pero con easing (no lineal, que
    // se lee como máquina). Un ciclo = 2 * este valor.
    readonly property int blinkHalf: 520
    // Pulso del anillo del micro mientras escucha.
    readonly property int micPulse: 1200

    // easing cubic-bezier(.2,.8,.2,1) — formato spline de QML: pares de control
    // + punto final (1,1). Se aplica como:
    //   easing.type: Design.easeType; easing.bezierCurve: Design.easeCurve
    readonly property int easeType: Easing.BezierSpline
    readonly property var easeCurve: [0.2, 0.8, 0.2, 1.0, 1.0, 1.0]

    // ── ATENCIÓN ─────────────────────────────────────────────────────────────
    // Ping 0..1 cuando el usuario "despierta" a JARVIS (foco en la barra de
    // comando). Lo dispara CommandBar con una SequentialAnimation (sube a 1 y
    // decae a 0 en ~700 ms, OutCubic). El núcleo lo suma a su energía de
    // reposo: una subida breve = "acaba de prestar atención". No es un estado
    // nuevo ni un dato inventado — es un evento de interacción real.
    property real attention: 0.0
}
