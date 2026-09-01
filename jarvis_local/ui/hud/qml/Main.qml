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
        property bool _softwareBackend: false
        property bool _degradedLatch: false
        readonly property bool _lowFpsSustained: _degradedLatch
        readonly property bool degraded:
            perfOverride === 1 ? true
          : perfOverride === -1 ? false
          : (_softwareBackend || _degradedLatch)

        // La atmósfera global (viñeta/grano/aberración) se aplicaba como
        // `layer.effect` de TODA la escena. Con la ventana transparente eso
        // pintaría un marco oscuro en los bordes — justo lo que NO se quiere.
        // El orbe conserva su propio bloom (CoreBloom); no hay post-proceso
        // de ventana.

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

        // ── SISTEMA DE ZONAS ─────────────────────────────────────────────
        // El orbe se centra en un "escenario" = ventana menos la franja de
        // identidad (arriba) y la barra de comando flotante (abajo). Los
        // demás elementos flotan en los márgenes.
        readonly property int margin: Design.sp(6)
        readonly property int topBandH: Design.sp(16)
        readonly property int cmdReserve: cmdBar.implicitHeight + Design.sp(5)
        readonly property int stageTop: margin + topBandH + Design.sp(3)
        readonly property int stageBottom: Math.max(stageTop + 120, height - cmdReserve)
        readonly property int stageH: stageBottom - stageTop
        readonly property int stageW: Math.max(120, width - 2 * margin)

        // conversación: columna lateral si CABE a la derecha del orbe sin
        // solaparlo; si no, apilada bajo el orbe.
        readonly property int convW: Math.round(Math.min(Design.sp(94), width * 0.28))
        // tamaño del orbe = protagonista: 72% del lado más corto disponible,
        // con mínimo (240) y máximo (960). El orbe SIEMPRE domina la composición.
        readonly property real _orbFactor: 0.72
        readonly property real _orbIfSide:
            Math.min(Math.max(240, Math.min(stageW, stageH) * _orbFactor),
                     stageH * 0.98, stageW * 0.96, 960)
        readonly property real _orbXIfSide: (width - _orbIfSide) / 2
        readonly property bool stackedChat:
            (_orbXIfSide + _orbIfSide + Design.sp(4)) > (width - convW - margin)

        // altura del escenario asignada al orbe (todo, o la parte de arriba
        // si el chat se apila debajo)
        readonly property real orbStageH: stackedChat ? stageH * 0.55 : stageH
        readonly property real orbSize:
            Math.min(Math.max(240, Math.min(stageW, orbStageH) * _orbFactor),
                     orbStageH * 0.98, stageW * 0.96, 960)
        readonly property real orbCX: width / 2
        readonly property real orbCY: stageTop + orbStageH / 2

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

        // ── HUD DE IDENTIDAD (flota arriba, centrado) ────────────────────
        Hud {
            objectName: "hud"
            id: hud
            keys: ["sistema", "modelo", "voz", "memoria", "herramientas"]
            opacity: Design.reveal(x + width / 2, y + height / 2)
            x: Math.round((parent.width - width) / 2)
            y: rootItem.margin
            width: Math.min(implicitWidth, parent.width - 2 * rootItem.margin)
            height: rootItem.topBandH
            clip: true
        }

        // ── MÉTRICAS EN VIVO (flotan abajo-izquierda, junto al comando) ──
        Hud {
            id: hudMetrics
            keys: ["cpu", "ram", "latencia", "tokens/s"]
            opacity: 0.9 * Design.reveal(x + width / 2, y + height / 2)
            x: rootItem.margin
            y: rootItem.stageBottom - height - Design.sp(1)
            width: Math.min(implicitWidth, parent.width - 2 * rootItem.margin)
            height: Design.sp(16)
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

        // estado del orbe: justo debajo, centrado — "modo actual de JARVIS"
        CoreStatus {
            id: coreStatus
            opacity: Design.reveal(x + width / 2, y + height / 2)
            coreState: Vm ? Vm.state : "idle"
            x: Math.round(rootItem.orbCX - width / 2)
            y: Math.round(rootItem.orbCY + rootItem.orbSize * 0.5 + Design.sp(2))
        }

        // ── CONVERSACIÓN — capa flotante (columna lateral o apilada) ─────
        Item {
            id: convZone
            objectName: "convZone"
            opacity: Design.reveal(x + width / 2, y + height / 2)
            readonly property real _orbBottom:
                rootItem.orbCY + rootItem.orbSize / 2
            x: rootItem.stackedChat
               ? rootItem.margin
               : Math.round(rootItem.width - rootItem.convW - rootItem.margin)
            y: rootItem.stackedChat
               ? Math.round(Math.max(coreStatus.y + coreStatus.height + Design.sp(2),
                                     _orbBottom + Design.sp(4)))
               : rootItem.stageTop
            width: rootItem.stackedChat
                   ? rootItem.stageW
                   : rootItem.convW
            // apilada: deja libre la fila de métricas (abajo-izquierda)
            height: Math.max(0, rootItem.stageBottom - y
                    - (rootItem.stackedChat ? hudMetrics.height + Design.sp(2) : 0))

            // scrim localizado SÓLO detrás del texto: sin él, texto claro sobre
            // un wallpaper claro es ilegible. Muy suave, con bordes difuminados,
            // NO un panel. (El brief lo permite explícitamente.)
            Rectangle {
                anchors.fill: parent
                anchors.margins: -Design.sp(2)
                radius: Design.radiusSurface
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.12; color: Qt.rgba(0, 0, 0, 0.30) }
                    GradientStop { position: 0.88; color: Qt.rgba(0, 0, 0, 0.30) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: convo.hasContent ? 0.9 : 0.0
                Behavior on opacity { NumberAnimation { duration: Design.durSlow } }
            }

            Conversation {
                id: convo
                anchors { left: parent.left; right: parent.right; top: parent.top
                          bottom: parent.bottom }
                measure: Math.min(620, width - Design.sp(8))
            }
        }

        // ── BARRA DE COMANDO — flotante, compacta, centrada abajo ────────
        CommandBar {
            id: cmdBar
            objectName: "cmdBar"
            opacity: Design.reveal(x + width / 2, y + height / 2)
            width: Math.round(Math.min(Design.sp(170), parent.width - 2 * rootItem.margin))
            x: Math.round((parent.width - width) / 2)
            y: parent.height - height - rootItem.margin
            showViz: rootItem.stackedChat && rootItem.stageH < 320
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
