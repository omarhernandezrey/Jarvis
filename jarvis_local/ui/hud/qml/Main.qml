import QtQuick
import QtQuick.Window
import "."

// Composición del HUD.
//  · Responsive por reorganización (4 modos): wide ≥1600 (HUD lateral | núcleo
//    | conversación) · mid 1100–1599 (HUD en banda) · narrow <1100 (una
//    columna) · badge alto <720 (núcleo insignia). Cero solapes / overflow;
//    la barra de comando siempre alcanzable.
//  · Addendum §3/§7: un ÚNICO FrameAnimation global mueve `tick`; la atmósfera
//    (viñeta/grano/aberración) se aplica como `layer.effect` de toda la escena.
Window {
    id: win
    width: 1360
    height: 820
    minimumWidth: 380
    minimumHeight: 360
    visible: true
    color: Design.bgVoid
    title: "J.A.R.V.I.S"

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
        readonly property real grainTick: Math.floor(tick * 24) / 24

        // ÚNICO FrameAnimation de todo el sistema
        FrameAnimation {
            objectName: "coreLoop"
            running: rootItem.motionActive
            onTriggered: rootItem.tick += frameTime
        }

        // atmósfera global: sólo con foco + movimiento; si no, render normal
        layer.enabled: rootItem.motionActive
        layer.effect: Atmosphere { time: rootItem.grainTick }

        // alcance de la luz del núcleo, en función del tamaño de la ventana
        Binding {
            target: Design; property: "lightRadius"
            value: Math.hypot(win.width, win.height) * 0.62
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

            Row {
                visible: !rootItem.singleCol
                anchors { left: parent.left; bottom: parent.bottom }
                spacing: Design.sp(2)
                Rectangle {
                    width: 1; height: stLabel.height
                    color: stLabel.text === "alert" ? Design.alert
                        : stLabel.text === "offline" ? Design.textMeta : Design.cyan
                }
                Text {
                    id: stLabel
                    text: Vm ? Vm.state : "idle"
                    // texto secundario que respira con el núcleo
                    property point _c: mapToItem(null, width / 2, height / 2)
                    color: Design.litText(Design.textSecondary, _c.x, _c.y)
                    font.family: Design.fontMono
                    font.pixelSize: Design.fsBody
                }
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
            const map = { "1": "idle", "2": "listening", "3": "thinking",
                          "4": "speaking", "5": "alert", "6": "offline" }
            if (map[e.text] !== undefined && Vm) Vm.set_state(map[e.text])
        }

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
                text: "render por software — sin GPU; el núcleo se verá degradado"
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
            swBanner.visible = (api === GraphicsInfo.Software || api === GraphicsInfo.Null)
        }
    }

    Component.onCompleted: win.requestActivate()
}
