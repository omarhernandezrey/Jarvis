import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Window
import "."

// Barra de comando persistente.
//  · Campo de texto en su PROPIO contenedor; el micrófono es un botón aparte a
//    la derecha, fuera del campo (con separación).
//  · Autoexpansión de 1 a 6 líneas y luego scroll interno.
//  · Enter envía · Shift+Enter salto · Esc cancela · ↑ recupera el último.
//  · Recibe el foco de teclado al aparecer y con un toque en cualquier punto
//    del campo (antes no se podía escribir: nada le daba `activeFocus`).
//  · Mientras se graba, el borde del CAMPO se vuelve el visualizador del anillo.
Item {
    id: bar
    property bool busy: Chat ? Chat.busy : false
    property string micState: Voice ? Voice.micState : "inactive"
    property bool showViz: false        // visualizador persistente (modo badge)
    readonly property bool recording: micState === "listening"
    readonly property bool vizOn: recording || showViz
    property var spectrum: (bar.vizOn && Vm) ? Vm.audio.spectrum : []

    property int lineH: Math.ceil(fm.lineSpacing)
    readonly property int _vpad: Design.sp(4)
    implicitHeight: Math.max(
        Design.sp(11),
        Math.min(6, Math.max(1, editor.lineCount)) * lineH + _vpad * 2)

    FontMetrics { id: fm; font.family: Design.fontSans; font.pixelSize: Design.fsBody }

    // centro en coords de escena, para la iluminación del núcleo
    property point _c: Qt.point(0, 0)
    function _remap() { _c = mapToItem(null, width / 2, height / 2) }
    onWidthChanged: _remap()
    onHeightChanged: _remap()
    onXChanged: _remap()
    onYChanged: _remap()
    Component.onCompleted: { _remap(); editor.forceActiveFocus() }
    Connections { target: Design; function onCorePosChanged() { bar._remap() } }

    // Wayland/GNOME entrega el foco de teclado de forma asíncrona tras mapear
    // la ventana: al recuperarlo, devolvérselo al editor (salvo mientras genera).
    Connections {
        target: bar.Window.window
        ignoreUnknownSignals: true
        function onActiveChanged() {
            if (bar.Window.window && bar.Window.window.active && !bar.busy)
                editor.forceActiveFocus()
        }
    }

    // ── CAMPO DE TEXTO (contenedor propio) ───────────────────────────────
    Rectangle {
        id: field
        anchors {
            left: parent.left
            right: micBtn.left; rightMargin: Design.sp(3)
            top: parent.top; bottom: parent.bottom
        }
        radius: Design.radiusSurface
        // superficie SIEMPRE presente (la ventana es transparente): el foco
        // sólo la ilumina un punto, nunca la vuelve invisible.
        color: Design.mix(Design.surfaceColor,
                   Qt.rgba(Design.coreTint.r, Design.coreTint.g, Design.coreTint.b, 0.82),
                   Math.min(0.20,
                       Design.lightLevel(bar._c.x, bar._c.y) * 0.14
                       + (editor.activeFocus ? 0.10 : 0.0)))
        border.width: editor.activeFocus ? 2 : 1.5
        border.color: bar.vizOn ? "transparent"
             : bar.busy ? Design.glow(Design.azure, 0.8)
             : editor.activeFocus ? Design.glow(Design.cyan, 0.85)
             : fieldHover.hovered ? Design.glow(Design.textSecondary, 0.6)
             : Design.mix(Design.litHairline(bar._c.x, bar._c.y),
                          Design.glow(Design.cyan, 0.35), 0.4)

        Behavior on border.color { ColorAnimation { duration: Design.durFast } }
        Behavior on border.width { NumberAnimation { duration: Design.durFast } }

        // corchetes de mira: mismo lenguaje que el resto del HUD. Sin fondo ni
        // borde propios (el campo ya los pinta); sólo las esquinas, que se
        // encienden con el foco y con la energía del núcleo.
        HoloFrame {
            anchors.fill: parent
            fillSurface: false
            showBorder: false
            radius: field.radius
            scan: !bar.vizOn          // chispa recorriendo el campo (salvo grabando)
            accent: bar.busy ? Design.azure
                  : editor.activeFocus ? Design.cyan : Design.textSecondary
            extraLift: editor.activeFocus ? 0.22 : 0.0
        }

        // brillo de vidrio en el borde superior (look "widget moderno")
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right
                      leftMargin: parent.radius; rightMargin: parent.radius; topMargin: 1 }
            height: 1
            color: Qt.rgba(1, 1, 1, editor.activeFocus ? 0.16 : 0.09)
            Behavior on color { ColorAnimation { duration: Design.durFast } }
        }

        HoverHandler { id: fieldHover }
        // un toque en cualquier parte del campo enfoca el editor
        TapHandler { onTapped: editor.forceActiveFocus() }

        // "generating": un cometa (degradado) recorre el borde inferior
        Rectangle {
            visible: bar.busy
            height: 1.5
            width: parent.width * 0.30
            y: parent.height - 1.5
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Design.cyan }
                GradientStop { position: 1.0; color: "transparent" }
            }
            SequentialAnimation on x {
                running: bar.busy; loops: Animation.Infinite
                NumberAnimation { from: 0; to: field.width * 0.65
                                  duration: Design.durSlow * 3
                                  easing.type: Design.easeType
                                  easing.bezierCurve: Design.easeCurve }
                NumberAnimation { from: field.width * 0.65; to: 0
                                  duration: Design.durSlow * 3
                                  easing.type: Design.easeType
                                  easing.bezierCurve: Design.easeCurve }
            }
        }

        // borde = visualizador del anillo mientras se graba
        Canvas {
            id: micViz
            anchors.fill: parent
            visible: bar.vizOn
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                if (!bar.vizOn) return
                var s = bar.spectrum
                ctx.strokeStyle = "" + Design.cyan
                ctx.lineWidth = 1
                ctx.globalAlpha = 0.25
                ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
                ctx.globalAlpha = 1
                if (!s || !s.length) return
                var per = 2 * (width + height)
                var n = s.length
                for (var i = 0; i < n; i++) {
                    var d = (i / n) * per
                    var p = _perimeter(d, width, height)
                    var nrm = _normal(d, width, height)
                    var h = 2 + s[i] * 10
                    ctx.beginPath()
                    ctx.moveTo(p.x, p.y)
                    ctx.lineTo(p.x + nrm.x * h, p.y + nrm.y * h)
                    ctx.strokeStyle = Qt.rgba(0.30, 0.91, 1.0, 0.25 + 0.6 * s[i])
                    ctx.stroke()
                }
            }
            function _perimeter(d, w, h) {
                if (d < w) return { x: d, y: 0 }
                d -= w
                if (d < h) return { x: w, y: d }
                d -= h
                if (d < w) return { x: w - d, y: h }
                d -= w
                return { x: 0, y: h - d }
            }
            function _normal(d, w, h) {
                if (d < w) return { x: 0, y: -1 }
                d -= w
                if (d < h) return { x: 1, y: 0 }
                d -= h
                if (d < w) return { x: 0, y: 1 }
                return { x: -1, y: 0 }
            }
            Connections {
                target: bar
                function onSpectrumChanged() { micViz.requestPaint() }
            }
        }

        // ── prompt (chevron trazado, sin depender de la fuente) ──────────
        Canvas {
            id: chevron
            width: Design.sp(2.75); height: Design.sp(3.25)
            x: Design.sp(4)
            y: bar._vpad + (bar.lineH - height) / 2
            // el prompt de la entidad: pleno con foco/trabajo, atenuado y
            // "respirando" con la energía del núcleo en reposo.
            opacity: (editor.activeFocus || bar.busy)
                     ? 1.0
                     : 0.55 + 0.35 * Math.min(1.0, Design.coreEnergy * 2.2)
            Behavior on opacity { NumberAnimation { duration: Design.durBase } }
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                var w = width, h = height
                // contorno oscuro fino primero (borde óptico), luego el trazo
                function stroke(col, lw) {
                    ctx.strokeStyle = col; ctx.lineWidth = lw
                    ctx.lineCap = "round"; ctx.lineJoin = "round"
                    ctx.beginPath()
                    ctx.moveTo(w * 0.18, h * 0.12)
                    ctx.lineTo(w * 0.82, h * 0.5)
                    ctx.lineTo(w * 0.18, h * 0.88)
                    ctx.stroke()
                }
                stroke("" + Design.textEdge, 4.0)
                stroke(bar.busy ? "" + Design.azure
                       : editor.activeFocus ? "" + Design.cyan
                       : "" + Design.textPrimary, 2.0)
            }
            Connections {
                target: editor
                function onActiveFocusChanged() { chevron.requestPaint() }
            }
            Connections {
                target: bar
                function onBusyChanged() { chevron.requestPaint() }
            }
        }

        // pista de envío: ↵ tenue a la derecha. Reserva su hueco siempre (sin
        // reflujo); se enciende cuando hay algo que enviar.
        Text {
            id: sendHint
            anchors { right: parent.right; rightMargin: Design.sp(3.5)
                      verticalCenter: parent.verticalCenter }
            text: "↵"
            color: bar.busy ? Design.azure : Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsBody
            opacity: (editor.text.length > 0 && !bar.busy) ? 0.75 : 0.0
            Behavior on opacity { NumberAnimation { duration: Design.durFast } }
        }

        // ── editor ──────────────────────────────────────────────────────
        Flickable {
            id: flick
            anchors {
                left: chevron.right; leftMargin: Design.sp(2.5)
                right: parent.right; rightMargin: Design.sp(8)
                top: parent.top; bottom: parent.bottom
                topMargin: bar._vpad; bottomMargin: bar._vpad
            }
            contentWidth: width
            contentHeight: editor.implicitHeight
            clip: true
            interactive: editor.lineCount > 6      // sólo desplaza si de verdad desborda
            boundsBehavior: Flickable.StopAtBounds

            TextEdit {
                id: editor
                width: flick.width
                enabled: !bar.busy
                color: Design.textPrimary
                selectionColor: Design.glow(Design.cyan, 0.35)
                font.family: Design.fontSans
                font.pixelSize: Design.fsBody
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                persistentSelection: true
                opacity: enabled ? 1.0 : 0.45
                // (TextEdit no soporta `style`; el contraste lo da la
                //  superficie oscura del campo detrás)

                // el usuario "despierta" a JARVIS: ping de atención. Sube a 1 y
                // decae a 0 en ~700 ms; el núcleo lo suma a su energía de
                // reposo (Core._targetEnergy).
                onActiveFocusChanged: if (activeFocus) attnPing.restart()
                SequentialAnimation {
                    id: attnPing
                    PropertyAction { target: Design; property: "attention"; value: 1.0 }
                    NumberAnimation { target: Design; property: "attention"
                        to: 0.0; duration: 700; easing.type: Easing.OutCubic }
                }

                property string _placeholder: bar.recording ? "escuchando…" : "escribe una orden"
                Text {
                    anchors.fill: parent
                    visible: !editor.text
                    text: editor._placeholder
                    color: Design.textSecondary
                    font: editor.font
                    style: Text.Outline; styleColor: Design.textEdge
                }

                onCursorRectangleChanged: {
                    var cy = cursorRectangle.y
                    if (cy < flick.contentY)
                        flick.contentY = cy
                    else if (cy + cursorRectangle.height > flick.contentY + flick.height)
                        flick.contentY = cy + cursorRectangle.height - flick.height
                }

                Keys.onPressed: (e) => {
                    if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
                        if (e.modifiers & Qt.ShiftModifier) return   // salto de línea
                        e.accepted = true
                        if (Chat && text.trim().length) { Chat.send(text); text = "" }
                    } else if (e.key === Qt.Key_Escape) {
                        e.accepted = true
                        if (Chat) Chat.cancel()
                    } else if (e.key === Qt.Key_Up && !text.length && Chat) {
                        e.accepted = true
                        text = Chat.lastCommand
                        cursorPosition = text.length
                    }
                }
            }
        }
    }

    // ── MICRÓFONO (botón aparte, fuera del campo) ────────────────────────
    MicButton {
        id: micBtn
        anchors { right: parent.right; rightMargin: Design.sp(1)
                  verticalCenter: parent.verticalCenter }
        width: Design.sp(10); height: Design.sp(10)
        micState: bar.micState
        onToggled: {
            if (!Voice) return
            if (bar.recording) Voice.stop_recording()
            else Voice.start_recording()
        }
    }
}
