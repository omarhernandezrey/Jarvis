import QtQuick
import QtQuick.Window
import QtQuick.Effects
import "."

// Composición del HUD (Fase 4).
//  · Ventana 100% TRANSPARENTE y sin marco: el escritorio se ve detrás. La
//    superficie GL lleva alfa (app.py: QSurfaceFormat.setAlphaBufferSize).
//  · EL ORBE ES EL PROTAGONISTA: centrado en la ventana, tamaño adaptativo
//    (mínimo/ideal/máximo). Todo lo demás flota a su alrededor como HUD
//    holográfico: identidad arriba, métricas y estado en las esquinas,
//    conversación en columna lateral (o apilada abajo si no cabe), barra de
//    comando flotante centrada abajo. Sin fondo global, sin panel, sin caja.
//  · Un ÚNICO FrameAnimation global mueve `tick`.
Window {
    id: win
    width: 1360
    height: 820
    minimumWidth: 380
    minimumHeight: 360
    visible: true
    title: "J.A.R.V.I.S"

    // Transparencia REAL: sin fondo, sin marco del SO. El chrome propio
    // (arrastrar / cerrar / redimensionar) lo pone WindowChrome.
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint

    readonly property bool maxed: visibility === Window.Maximized

    property real pointerX: 0
    property real pointerY: 0

    Item {
        id: rootItem
        objectName: "rootItem"
        anchors.fill: parent
        focus: true

        // ── reloj y actividad (addendum §3 y §7) ─────────────────────────
        property bool paused: false          // hook de tests
        readonly property bool reducedMotion:
            (typeof ReducedMotion !== "undefined") && ReducedMotion === true
        readonly property bool motionActive:
            win.active
            && win.visibility !== Window.Minimized
            && win.visibility !== Window.Hidden
            && !paused
            && (!reducedMotion || (Vm && (Vm.state === "listening"
                                          || Vm.state === "speaking")))
        property real tick: 0

        // ÚNICO FrameAnimation de todo el sistema. Además mide los fps para la
        // ruta de degradación (§7): no es un `if` teórico, se dispara de verdad.
        property real _fpsEma: 60
        property real _lowSince: 0            // ms de `tick` en que empezó a ir <40
        FrameAnimation {
            objectName: "coreLoop"
            running: rootItem.motionActive
            onTriggered: {
                rootItem.tick += frameTime
                if (frameTime > 0.001 && frameTime < 0.5 && rootItem.tick > 2.0) {
                    rootItem._fpsEma = rootItem._fpsEma * 0.9 + (1.0 / frameTime) * 0.1
                    if (rootItem._fpsEma < 40) {
                        if (rootItem._lowSince === 0)
                            rootItem._lowSince = rootItem.tick * 1000
                        else if (rootItem.tick * 1000 - rootItem._lowSince > 3000)
                            rootItem._degradedLatch = true       // engancha, no vuelve
                    } else if (rootItem._fpsEma > 46) {
                        rootItem._lowSince = 0
                    }
                }
            }
        }

        // ── RUTA DE DEGRADACIÓN (§7) ────────────────────────────────────────
        // backend software / Null, o fps <40 sostenidos 3 s → sin bloom ni
        // atmósfera; se mantiene el shader del núcleo. Es un LATCH: una vez que
        // degrada, se queda así toda la sesión (evita oscilar el pipeline).
        property int  perfOverride: 0        // 0 auto · 1 forzar degradado · -1 forzar completo (tests)
        // FASE I · I6: qué RHI usa realmente esta sesión — para que una
        // captura de verificación pueda decir de qué pipeline es evidencia
        // (Software/Null nunca ejecuta bloom ni atmósfera de verdad).
        property string rhiBackendName: "?"
        property bool _softwareBackend: false
        property bool _degradedLatch: false
        readonly property bool _lowFpsSustained: _degradedLatch
        readonly property bool degraded:
            perfOverride === 1 ? true
          : perfOverride === -1 ? false
          : (_softwareBackend || _degradedLatch)

        // La atmósfera global (viñeta/grano/aberración cromática + máscara de
        // esquinas redondeadas) va como `layer.effect` de TODA la escena.
        // FASE I · I6: se había descartado porque con la ventana transparente
        // pintaba un marco oscuro en los bordes — la causa real era que el
        // grano y la máscara de esquinas tocaban el alfa sin tocar el color
        // en la misma proporción, rompiendo el invariante premultiplicado
        // justo donde debía quedar transparente (visible en el compositor
        // real del SO, no en una captura de `grabToImage`). Corregido en
        // `atmosphere.frag`: grano y máscara escalan también el color.
        //
        // Se apaga por completo SÓLO en backend de software/Null
        // (`_softwareBackend`): ahí el shader puede no ejecutarse en
        // absoluto — límite de hardware, no una decisión de coste, mismo
        // trato que el bloom. La máscara de esquinas redondeadas, en cambio,
        // NO depende de `degraded` (fps sostenidos <40 o `perfOverride`
        // forzado): ahí el GPU real sigue pudiendo correr el shader, sólo
        // más despacio, así que se apagan grano/viñeta/aberración (el coste)
        // pero la forma de la ventana se mantiene.
        readonly property bool _atmosphereOn: !_softwareBackend
        layer.enabled: _atmosphereOn
        layer.effect: Atmosphere {
            // FASE I · I6: grano a 15 fps — el reloj que alimenta el hash se
            // cuantiza, así que el grano sólo "salta" 15 veces por segundo
            // aunque la escena renderice más rápido (nunca se ve como un
            // parpadeo: es la misma cadencia perceptual de un grano de
            // película, no una animación).
            time: rootItem.degraded ? 0.0 : Math.floor(rootItem.tick * 15.0) / 15.0
            grainAmt: rootItem.degraded ? 0.0 : 0.026
            vignette: rootItem.degraded ? 0.0 : 0.30
            aberration: rootItem.degraded ? 0.0 : 1.2
            cornerRadius: Design.windowCornerRadius
        }

        // alcance de la luz del núcleo, en función del tamaño de la ventana
        Binding {
            target: Design; property: "lightRadius"
            value: Math.hypot(win.width, win.height) * 0.62
        }
        // reloj global de fotogramas → Design: micro-movimiento del HUD sin
        // timers propios (sigue habiendo UN solo FrameAnimation).
        Binding { target: Design; property: "tick"; value: rootItem.tick }
        // alcance del frente de reacción (Fase 11): toda la diagonal.
        Binding {
            target: Design; property: "waveReach"
            value: Math.hypot(win.width, win.height)
        }

        // ── ARRANQUE (addendum §5): oscuridad → el núcleo se enciende desde un
        //    punto → su luz revela la interfaz por distancia. ≤900 ms, una vez,
        //    saltable con cualquier tecla. Sin texto, sin barras, sin ASCII.
        property real boot: 0.0
        readonly property bool booted: boot >= 1.0
        Binding {
            target: Design; property: "bootReach"
            value: Math.hypot(win.width, win.height) * 0.9
        }
        Binding { target: Design; property: "bootReveal"; value: rootItem.boot }
        NumberAnimation {
            id: bootAnim
            target: rootItem; property: "boot"
            from: 0.0; to: 1.0; duration: Design.durBoot
            easing.type: Design.easeType; easing.bezierCurve: Design.easeCurve
            running: true
        }
        function _skipBoot() {
            if (!rootItem.booted) { bootAnim.stop(); rootItem.boot = 1.0 }
        }

        // ── SISTEMA DE ZONAS (Fase I · I1) ───────────────────────────────
        //  Composición reencuadrada: el núcleo ~1,6× más grande, su centro en
        //  el TERCIO INFERIOR IZQUIERDO (no centrado), sangrando por detrás de
        //  la columna de conversación. La conversación va ENCIMA, sobre un
        //  panel translúcido, anclada abajo y creciendo hacia arriba desde el
        //  input. La columna izquierda deja de estar vacía: ActivitySpine.
        readonly property int margin: Design.sp(6)
        readonly property int topBandH: Design.sp(19)
        readonly property int cmdReserve: cmdBar.implicitHeight + Design.sp(5)
        readonly property int stageTop: margin + topBandH + Design.sp(3)
        readonly property int stageBottom: Math.max(stageTop + 120, height - cmdReserve)
        readonly property int stageH: stageBottom - stageTop

        // espina de actividad (izquierda) — historial de energía + estado + reloj
        readonly property int spineW: Math.round(Math.max(Design.sp(26),
                                                Math.min(Design.sp(34), width * 0.11)))
        readonly property int spineGap: Design.sp(3)
        readonly property int stageLeft: margin + spineW + spineGap
        readonly property int stageW: Math.max(120, width - stageLeft - margin)

        // ventana estrecha: se colapsa a apilado (orbe arriba, chat abajo).
        readonly property bool tightLayout: width < Design.sp(190) || stageH < 320

        // conversación: panel translúcido en la mitad derecha, montado sobre el
        // orbe. Anclado abajo (junto al input), crece hacia arriba.
        readonly property int convLeft: tightLayout
            ? stageLeft
            : Math.round(stageLeft + stageW * 0.40)
        readonly property int convRight: width - margin
        readonly property int convBottom: Math.round(cmdBar.y - Design.sp(3))
        readonly property int convTop: Math.round(stageTop + (tightLayout ? stageH * 0.52 : Design.sp(1)))

        // tamaño del orbe = protagonista, ~1,6× lo anterior (factor 0.66 → 1.06).
        // Se mide contra la altura del escenario (o su mitad superior si apila).
        readonly property real _orbFactor: tightLayout ? 0.66 : 1.06
        readonly property real orbStageH: tightLayout ? stageH * 0.50 : stageH
        readonly property real orbSize:
            Math.min(Math.max(300, Math.min(stageW * 1.15, orbStageH) * _orbFactor),
                     orbStageH * 1.35, 1200)
        // centro en el tercio inferior izquierdo del escenario
        readonly property real orbCX: tightLayout
            ? width / 2
            : Math.round(stageLeft + stageW * 0.32)
        readonly property real orbCY: tightLayout
            ? stageTop + orbStageH * 0.5
            : Math.round(stageTop + stageH * 0.60)

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            onPositionChanged: (m) => {
                win.pointerX = (m.x / win.width - 0.5) * 2
                win.pointerY = (m.y / win.height - 0.5) * 2
            }
            onExited: { win.pointerX = 0; win.pointerY = 0 }
        }

        // el borde de la ventana ES parte de la entidad: retícula emisiva que
        // respira con el orbe y adopta el color del estado (Fase 12).
        HudFrame {
            anchors.fill: parent
            opacity: Design.reveal(rootItem.orbCX, rootItem.orbCY)
        }

        // ── ESPINA DE ACTIVIDAD (columna izquierda — I1) ─────────────────
        ActivitySpine {
            objectName: "activitySpine"
            id: activitySpine
            visible: !rootItem.tightLayout
            opacity: Design.reveal(x + width / 2, y + height / 2)
            coreState: Vm ? Vm.state : "idle"
            metrics: Vm ? Vm.metrics : ({})
            x: rootItem.margin
            y: rootItem.stageTop
            width: rootItem.spineW
            height: rootItem.stageBottom - rootItem.stageTop
        }

        // ── HUD DE IDENTIDAD (flota arriba, centrado sobre el escenario) ──
        Hud {
            objectName: "hud"
            id: hud
            keys: ["sistema", "modelo", "voz", "memoria", "herramientas"]
            opacity: Design.reveal(x + width / 2, y + height / 2)
            x: Math.round(rootItem.stageLeft + (rootItem.stageW - width) / 2)
            y: rootItem.margin
            width: Math.min(implicitWidth, rootItem.stageW)
            height: rootItem.topBandH
            clip: true
        }
        // conector: una línea de 1px que "amarra" la identidad al núcleo — el
        // HUD sale del Core. Iluminada por la luz del propio núcleo.
        Rectangle {
            id: hudConnector
            readonly property real _cy: y + height / 2
            readonly property real _wave: Design.waveAt(x, _cy)
            readonly property real _l: Design.lightLevel(x, _cy)
            x: Math.round(rootItem.orbCX)
            y: hud.y + hud.height
            width: 1 + 3 * _wave                         // se engrosa al pasar el frente
            height: Math.max(0, (rootItem.orbCY - rootItem.orbSize / 2) - y - Design.sp(2))
            // I3: el divisor vertical recibe la luz real del núcleo (distancia
            // + ángulo + energía), no un tinte de estado plano. La opacidad
            // también responde a la luz (antes sólo el color): en reposo se
            // apaga de verdad, hablando se enciende — no sólo cambia de tinte.
            color: Design.litHairline(x, _cy)
            opacity: (0.04 + 0.85 * _l + 0.12 * Design.breath() + 0.5 * _wave)
                     * Design.reveal(x, _cy)

            // impulso de datos que baja por el conector hacia el orbe: un punto
            // de luz recorre la línea de forma continua (reloj global, sin timer).
            Rectangle {
                width: 3; height: 14; radius: 1.5
                x: (parent.width - width) / 2
                y: (((Design.tick * 0.35) % 1.0) + 1.0) % 1.0 * parent.height
                color: Design.stateWash(Design.cyan, 0.7)
                opacity: 0.5 + 0.4 * Design.breath()
                visible: parent.height > 20
            }
        }

        // ── MÉTRICAS EN VIVO ────────────────────────────────────────────
        //  Fase I·I1: cpu/ram/latencia/tok·s se mudan a la ActivitySpine (la
        //  columna izquierda es ahora la telemetría de actividad). En ventana
        //  estrecha, donde la espina se oculta, se muestran aquí abajo.
        Hud {
            id: hudMetrics
            visible: rootItem.tightLayout
            keys: ["cpu", "ram", "latencia", "tokens/s"]
            opacity: 0.9 * Design.reveal(x + width / 2, y + height / 2)
            x: rootItem.margin
            y: rootItem.stageBottom - height - Design.sp(1)
            width: Math.min(implicitWidth, rootItem.width - 2 * rootItem.margin)
            height: Design.sp(19)
            clip: true
        }

        // ── EL ORBE — protagonista, centrado en el escenario ─────────────
        Item {
            id: coreZone
            objectName: "coreZone"
            width: rootItem.orbSize
            height: rootItem.orbSize
            x: rootItem.orbCX - width / 2
            y: rootItem.orbCY - height / 2

            Core {
                id: core
                anchors.fill: parent
                bootIgnite: Math.min(1.0, rootItem.boot / 0.42)
                degraded: rootItem.degraded
                compact: false
                coreState: Vm ? Vm.state : "idle"
                audioLevel: Vm ? Vm.audio.level : 0
                spectrum: Vm ? Vm.audio.spectrum : []
                tokensPerSecond: (Vm && Vm.metrics.tokensPerSecond !== undefined)
                                 ? Vm.metrics.tokensPerSecond : 0
                pointer: Qt.point(win.pointerX, win.pointerY)
                time: rootItem.tick
                loopRunning: rootItem.motionActive
                reducedMotion: rootItem.reducedMotion
            }
        }

        // El estado del núcleo (palabra + acento) vive ahora en la
        // ActivitySpine (I1). Se retira el CoreStatus suelto bajo el orbe:
        // duplicaba la lectura y chocaba con el orbe agrandado.

        // ── CONVERSACIÓN — sobre un PANEL TRANSLÚCIDO, montada sobre el orbe,
        //    anclada abajo (junto al input) y creciendo hacia arriba (I1) ────
        Item {
            id: convZone
            objectName: "convZone"
            opacity: Design.reveal(x + width / 2, y + height / 2)
            x: rootItem.convLeft
            width: rootItem.convRight - rootItem.convLeft
            y: rootItem.convTop
            height: Math.max(0, rootItem.convBottom - rootItem.convTop)

            // panel translúcido: el orbe SANGRA por detrás de su borde
            // izquierdo. Iluminado desde arriba (lenguaje holo del sistema),
            // borde de 1px teñido por el estado, esquina redondeada.
            Rectangle {
                id: convPanel
                anchors.fill: parent
                radius: Design.radiusSurface
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Design.holoTop }
                    GradientStop { position: 1.0; color: Design.holoBot }
                }
                border.width: 1
                border.color: Design.stateWash(Design.widgetStroke, 0.85)
                // vela de fondo: translúcida, pero suficiente para que el ruido
                // del orbe justo detrás no compita con el texto. Más densa en el
                // filo izquierdo (donde el orbe está más brillante), se aclara
                // hacia la derecha.
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    radius: parent.radius - 1
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0
                            color: Qt.rgba(Design.surfaceColor.r, Design.surfaceColor.g,
                                           Design.surfaceColor.b, 0.90) }
                        GradientStop { position: 0.45
                            color: Qt.rgba(Design.surfaceColor.r, Design.surfaceColor.g,
                                           Design.surfaceColor.b, 0.74) }
                        GradientStop { position: 1.0
                            color: Qt.rgba(Design.surfaceColor.r, Design.surfaceColor.g,
                                           Design.surfaceColor.b, 0.62) }
                    }
                }
            }
            // filo izquierdo emisivo: marca dónde el orbe pasa por detrás
            Rectangle {
                width: 1
                x: 0
                y: Design.sp(1); height: parent.height - Design.sp(2)
                color: Design.litHairline(convZone.x, convZone.y + convZone.height / 2)
                opacity: 0.5 + 0.4 * Design.breath()
            }

            Conversation {
                id: convo
                anchors { fill: parent
                          leftMargin: Design.sp(3); rightMargin: Design.sp(3)
                          topMargin: Design.sp(2); bottomMargin: Design.sp(2) }
                measure: Math.min(640, width - Design.sp(10))
            }
        }

        // ── BARRA DE COMANDO — flotante, compacta, centrada abajo ────────
        CommandBar {
            id: cmdBar
            objectName: "cmdBar"
            opacity: Design.reveal(x + width / 2, y + height / 2)
            width: Math.round(Math.min(Design.sp(170),
                              rootItem.width - rootItem.stageLeft - rootItem.margin))
            x: Math.round(rootItem.stageLeft
                          + (rootItem.width - rootItem.stageLeft - rootItem.margin - width) / 2)
            y: parent.height - height - rootItem.margin
            showViz: rootItem.tightLayout && rootItem.stageH < 320
        }

        Keys.onPressed: (e) => {
            rootItem._skipBoot()                     // cualquier tecla salta el arranque
            const map = { "1": "idle", "2": "listening", "3": "thinking",
                          "4": "speaking", "5": "alert", "6": "offline" }
            if (map[e.text] !== undefined && Vm) Vm.set_state(map[e.text])
        }
        // un clic también salta el arranque (sólo mientras dura)
        TapHandler { enabled: !rootItem.booted; onTapped: rootItem._skipBoot() }

        // aviso honesto si el backend de render cae en software (addendum §2)
        Rectangle {
            id: swBanner
            visible: false
            z: 999
            anchors { bottom: cmdBar.top; bottomMargin: Design.sp(3)
                      horizontalCenter: parent.horizontalCenter }
            width: swText.implicitWidth + Design.sp(6)
            height: swText.implicitHeight + Design.sp(3)
            color: Qt.rgba(Design.warn.r, Design.warn.g, Design.warn.b, 0.14)
            border.width: 1
            border.color: Design.warn
            Text {
                id: swText
                anchors.centerIn: parent
                text: "render por software — sin bloom ni atmósfera (sólo el núcleo)"
                color: Design.warn
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
            }
        }

        Component.onCompleted: {
            var api = GraphicsInfo.api
            var name = api === GraphicsInfo.Software ? "Software"
                : api === GraphicsInfo.OpenGL ? "OpenGL"
                : api === GraphicsInfo.Direct3D11 ? "Direct3D11"
                : api === GraphicsInfo.Vulkan ? "Vulkan"
                : api === GraphicsInfo.Metal ? "Metal"
                : api === GraphicsInfo.Null ? "Null" : ("api=" + api)
            console.log("[hud] RHI backend:", name)
            rootItem.rhiBackendName = name
            rootItem._softwareBackend = (api === GraphicsInfo.Software
                                         || api === GraphicsInfo.Null)
            swBanner.visible = rootItem._softwareBackend
        }
    }

    // chrome propio: arrastre, controles de ventana, redimensionado por el
    // compositor. La ventana no tiene decoración del SO — esto es lo único
    // que permite mover/cerrar/redimensionar.
    WindowChrome {
        win: win
        anchors.fill: parent
        z: 500
    }

    Component.onCompleted: win.requestActivate()
}
