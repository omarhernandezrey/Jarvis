import QtQuick
import QtQuick.Window
import QtQuick.Effects
import "."

// Composición del HUD.
//  · Ventana SIN marco del SO (addendum §8.1): chrome propio, esquinas a 12px,
//    sombra proyectada, redimensionado por el compositor.
//  · Responsive por reorganización (4 modos): wide ≥1600 · mid 1100–1599 ·
//    narrow <1100 · badge alto <720. Cero solapes / overflow.
//  · Un ÚNICO FrameAnimation global mueve `tick`; la atmósfera se aplica como
//    `layer.effect` de toda la escena (y redondea las esquinas).
Window {
    id: win
    width: 1360
    height: 820
    minimumWidth: 380
    minimumHeight: 360
    visible: true
    title: "J.A.R.V.I.S"

    // Sin marco sólo si se pide explícitamente (context `Frameless`). En algunas
    // sesiones Wayland/GNOME una ventana FramelessWindowHint + transparente
    // deja de recibir foco de teclado → no se puede escribir. Por defecto:
    // ventana normal decorada por el SO (funciona en todas partes).
    readonly property bool frameless: (typeof Frameless !== "undefined") && Frameless === true
    color: frameless ? "transparent" : Design.bgVoid
    flags: frameless ? (Qt.Window | Qt.FramelessWindowHint) : Qt.Window

    readonly property bool maxed: visibility === Window.Maximized
    readonly property int gutter: (frameless && !maxed) ? Design.windowShadowGutter : 0

    property real pointerX: 0
    property real pointerY: 0

    // sombra proyectada (el compositor no la da sin decoración del SO)
    MultiEffect {
        anchors.fill: rootItem
        source: rootItem
        visible: win.frameless && !win.maxed
        shadowEnabled: true
        shadowColor: "#000000"
        shadowOpacity: 0.5
        shadowBlur: 1.0
        blurMax: 40
        shadowVerticalOffset: 8
        autoPaddingEnabled: true
    }

    Item {
        id: rootItem
        objectName: "rootItem"
        anchors.fill: parent
        anchors.margins: win.gutter
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
        readonly property real grainTick: Math.floor(tick * 24) / 24

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
        property bool _softwareBackend: false
        property bool _degradedLatch: false
        readonly property bool _lowFpsSustained: _degradedLatch
        readonly property bool degraded:
            perfOverride === 1 ? true
          : perfOverride === -1 ? false
          : (_softwareBackend || _degradedLatch)

        // atmósfera global: con foco + movimiento y sin degradar
        readonly property bool atmosphereOn: motionActive && !degraded
        // el layer va SIEMPRE activo (redondea las esquinas de la ventana sin
        // marco); cuando `atmosphereOn` es falso, el shader queda casi neutro.
        layer.enabled: true
        layer.effect: Atmosphere {
            time: rootItem.grainTick
            cornerRadius: (win.frameless && !win.maxed) ? Design.radiusWindow : 0
            grainAmt: rootItem.atmosphereOn ? 0.026 : 0.0
            aberration: rootItem.atmosphereOn ? 1.2 : 0.0
            vignette: rootItem.atmosphereOn ? 0.30 : 0.10
        }

        // alcance de la luz del núcleo, en función del tamaño de la ventana
        Binding {
            target: Design; property: "lightRadius"
            value: Math.hypot(win.width, win.height) * 0.62
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

        readonly property int pad: Design.sp(5)
        readonly property string mode: win.height < 720 ? "badge"
            : win.width >= 1600 ? "wide"
            : win.width < 1100 ? "narrow" : "mid"
        readonly property bool singleCol: mode === "narrow" || mode === "badge"
        readonly property int hudSideW: Design.sp(42)
        readonly property int headerH: mode === "badge" ? Design.sp(20) : Design.sp(22)
        readonly property int bandH: Design.sp(16)

        // ── planos de profundidad ────────────────────────────────────────
        Rectangle {
            anchors.fill: parent; anchors.margins: -4
            x: win.pointerX * 2; y: win.pointerY * 2
            gradient: Gradient {
                GradientStop { position: 0.0; color: Design.bgAbyss }
                GradientStop { position: 1.0; color: Design.bgVoid }
            }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Design.glow(Design.azure, 0.10) }
                GradientStop { position: 0.4; color: "transparent" }
            }
        }
        // retícula técnica: profundidad de "centro de mando", casi subliminal
        // (se pinta una vez por tamaño, cero coste por frame — ver TechGrid.qml)
        TechGrid { anchors.fill: parent }
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

        // ── HUD ──────────────────────────────────────────────────────────
        Hud {
            objectName: "hud"
            id: hud
            opacity: Design.reveal(x + width / 2, y + height / 2)   // arranque
            vertical: rootItem.mode === "wide"
            // en single, el HUD va a la derecha de la insignia del núcleo
            x: rootItem.singleCol ? rootItem.pad + rootItem.headerH + Design.sp(4)
                                  : rootItem.pad
            y: rootItem.pad
            width: rootItem.mode === "wide" ? rootItem.hudSideW
                 : rootItem.singleCol ? Math.max(0, parent.width - x - rootItem.pad)
                 : parent.width - 2 * rootItem.pad
            height: rootItem.mode === "wide" ? parent.height - 2 * rootItem.pad
                  : rootItem.singleCol ? rootItem.headerH
                  : rootItem.bandH
            clip: true
        }

        Hairline {   // regla bajo la banda superior (mid) / bajo el header (single)
            visible: rootItem.mode === "mid" || rootItem.singleCol
            x: rootItem.pad
            width: parent.width - 2 * rootItem.pad
            y: rootItem.singleCol ? rootItem.pad + rootItem.headerH + Design.sp(2)
                                  : rootItem.pad + rootItem.bandH + Design.sp(3)
        }

        // ── NÚCLEO ───────────────────────────────────────────────────────
        Item {
            id: coreZone
            objectName: "coreZone"
            x: {
                if (rootItem.mode === "wide") return rootItem.pad + rootItem.hudSideW + Design.sp(6)
                return rootItem.pad
            }
            y: {
                if (rootItem.mode === "wide") return rootItem.pad
                if (rootItem.mode === "mid") return rootItem.pad + rootItem.bandH + Design.sp(6)
                return rootItem.pad          // single: insignia en el header
            }
            width: {
                // densidad asimétrica: el núcleo tiene AIRE, la conversación
                // (donde vive el contenido) se queda con el espacio
                if (rootItem.singleCol) return rootItem.headerH
                if (rootItem.mode === "wide")
                    return (parent.width - x - rootItem.pad) * 0.38
                return (parent.width - 2 * rootItem.pad) * 0.34
            }
            height: {
                if (rootItem.singleCol) return rootItem.headerH
                if (rootItem.mode === "wide") return parent.height - 2 * rootItem.pad
                return parent.height - y - rootItem.pad
            }

            Core {
                id: core
                anchors.centerIn: parent
                // el orbe tiene AIRE en su zona; el bloom (margen negativo del
                // CoreBloom) queda dentro sin recortarse contra la ventana
                width: Math.min(coreZone.width, coreZone.height)
                       * (rootItem.singleCol ? 1.05 : 0.82)
                height: width
                bootIgnite: Math.min(1.0, rootItem.boot / 0.42)   // se enciende primero
                degraded: rootItem.degraded
                compact: rootItem.singleCol
                coreState: Vm ? Vm.state : "idle"
                audioLevel: Vm ? Vm.audio.level : 0
                spectrum: Vm ? Vm.audio.spectrum : []
                tokensPerSecond: (Vm && Vm.metrics.tokensPerSecond !== undefined)
                                 ? Vm.metrics.tokensPerSecond : 0
                pointer: Qt.point(win.pointerX, win.pointerY)
                time: rootItem.tick
                loopRunning: rootItem.motionActive       // 0 fps sin foco / minimizada
                reducedMotion: rootItem.reducedMotion
            }

            CoreStatus {
                visible: !rootItem.singleCol
                opacity: Design.reveal(parent.x + Design.sp(4),
                                       parent.y + parent.height - Design.sp(4))
                anchors { left: parent.left; bottom: parent.bottom }
                coreState: Vm ? Vm.state : "idle"
            }
        }

        Hairline {   // regla vertical entre núcleo y conversación (wide/mid)
            vertical: true
            visible: !rootItem.singleCol
            x: coreZone.x + coreZone.width + Design.sp(4)
            y: coreZone.y
            height: coreZone.height
        }

        // ── CONVERSACIÓN + BARRA DE COMANDO ──────────────────────────────
        Item {
            id: convZone
            objectName: "convZone"
            opacity: Design.reveal(x + width / 2, y + height / 2)   // se revela al final
            x: rootItem.singleCol ? rootItem.pad
               : coreZone.x + coreZone.width + Design.sp(5)
            y: {
                if (rootItem.mode === "wide") return rootItem.pad
                if (rootItem.mode === "mid") return rootItem.pad + rootItem.bandH + Design.sp(6)
                return rootItem.pad + rootItem.headerH + Design.sp(5)   // single
            }
            width: parent.width - x - rootItem.pad
            height: parent.height - y - rootItem.pad

            Conversation {
                id: convo
                anchors { left: parent.left; right: parent.right; top: parent.top
                          bottom: cmdBar.top; bottomMargin: Design.sp(3) }
                measure: Math.min(640, width - Design.sp(6))
            }
            CommandBar {
                id: cmdBar
                objectName: "cmdBar"
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                showViz: rootItem.mode === "badge"
            }
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
            anchors { top: parent.top; horizontalCenter: parent.horizontalCenter }
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
            rootItem._softwareBackend = (api === GraphicsInfo.Software
                                         || api === GraphicsInfo.Null)
            swBanner.visible = rootItem._softwareBackend
        }
    }

    // chrome propio: arrastre, controles, redimensionado por el compositor.
    // Sólo en modo sin marco; con ventana normal, el compositor pone el suyo.
    WindowChrome {
        win: win
        anchors.fill: parent
        z: 500
        visible: win.frameless
        enabled: win.frameless
    }

    Component.onCompleted: win.requestActivate()
}
