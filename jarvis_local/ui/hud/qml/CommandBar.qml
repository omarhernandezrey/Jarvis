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
        color: bar.busy ? Qt.rgba(1, 1, 1, 0.02)
             : editor.activeFocus ? Qt.rgba(1, 1, 1, 0.05)
             : Design.mix(Design.surfaceColor,
                   Qt.rgba(Design.coreTint.r, Design.coreTint.g, Design.coreTint.b,
                           Design.surfaceColor.a),
                   Math.min(0.16, Design.lightLevel(bar._c.x, bar._c.y) * 0.18))
        border.width: 1
        border.color: bar.vizOn ? "transparent"
             : bar.busy ? Design.glow(Design.azure, 0.55)
             : editor.activeFocus ? Design.glow(Design.cyan, 0.6)
             : fieldHover.hovered ? Design.glow(Design.textSecondary, 0.45)
             : Design.litHairline(bar._c.x, bar._c.y)

        Behavior on border.color { ColorAnimation { duration: Design.durFast } }

        HoverHandler { id: fieldHover }
        // un toque en cualquier parte del campo enfoca el editor
        TapHandler { onTapped: editor.forceActiveFocus() }

        // "generating": barrido azul lento en el borde inferior
        Rectangle {
            visible: bar.busy
            height: 1
            width: parent.width * 0.35
            y: parent.height - 1
            color: Design.azure
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
            width: Design.sp(2.5); height: Design.sp(3)
            x: Design.sp(4)
            y: bar._vpad + (bar.lineH - height) / 2
            onPaint: {
                var ctx = getContext("2d"); ctx.reset()
                ctx.strokeStyle = bar.busy ? "" + Design.azure
                    : editor.activeFocus ? "" + Design.cyan
                    : "" + Design.textSecondary
                ctx.lineWidth = 1.5; ctx.lineCap = "round"; ctx.lineJoin = "round"
                ctx.beginPath()
                ctx.moveTo(width * 0.15, height * 0.1)
                ctx.lineTo(width * 0.85, height * 0.5)
                ctx.lineTo(width * 0.15, height * 0.9)
                ctx.stroke()
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

        // ── editor ──────────────────────────────────────────────────────
        Flickable {
            id: flick
            anchors {
                left: chevron.right; leftMargin: Design.sp(2.5)
                right: parent.right; rightMargin: Design.sp(4)
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

                property string _placeholder: bar.recording ? "escuchando…" : "escribe una orden"
                Text {
                    anchors.fill: parent
                    visible: !editor.text
                    text: editor._placeholder
                    color: Design.textMeta
                    font: editor.font
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
