import QtQuick
import QtQuick.Controls.Basic
import "."

// Barra de comando persistente. Prompt `❯`, autoexpansión de 1 a 6 líneas y
// luego scroll interno. Enter envía · Shift+Enter salto · Esc cancela la
// generación · ↑ recupera el último comando. Estados hover/focus/disabled/
// generating con feedback distinto. Durante la grabación, el borde se convierte
// en el mismo visualizador del anillo del núcleo (un lenguaje, dos escalas).
Item {
    id: bar
    property bool busy: Chat ? Chat.busy : false
    property string micState: Voice ? Voice.micState : "inactive"
    property bool showViz: false        // visualizador persistente (modo badge)
    readonly property bool recording: micState === "listening"
    readonly property bool vizOn: recording || showViz
    property var spectrum: (bar.vizOn && Vm) ? Vm.audio.spectrum : []

    property int lineH: Math.ceil(fm.lineSpacing)
    implicitHeight: Math.min(6, Math.max(1, editor.lineCount)) * lineH + Design.sp(6)

    FontMetrics { id: fm; font.family: Design.fontSans; font.pixelSize: Design.fsBody }

    // centro en coords de escena, para la iluminación del núcleo
    property point _c: Qt.point(0, 0)
    function _remap() { _c = mapToItem(null, width / 2, height / 2) }
    onWidthChanged: _remap()
    onHeightChanged: _remap()
    onXChanged: _remap()
    onYChanged: _remap()
    Component.onCompleted: _remap()
    Connections { target: Design; function onCorePosChanged() { bar._remap() } }

    // ── contenedor + estados visuales ────────────────────────────────
    Rectangle {
        id: box
        anchors.fill: parent
        radius: Design.radiusSurface
        // superficie que RECIBE luz: base teñida hacia el núcleo por cercanía
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
             : boxHover.hovered ? Design.glow(Design.textSecondary, 0.5)
             : Design.litHairline(bar._c.x, bar._c.y)

        // "generating": barrido azul lento en el borde inferior
        Rectangle {
            visible: bar.busy
            height: 1
            width: parent.width * 0.35
            y: parent.height - 1
            color: Design.azure
            SequentialAnimation on x {
                running: bar.busy; loops: Animation.Infinite
                NumberAnimation { from: 0; to: box.width * 0.65
                                  duration: Design.durSlow * 3
                                  easing.type: Design.easeType
                                  easing.bezierCurve: Design.easeCurve }
                NumberAnimation { from: box.width * 0.65; to: 0
                                  duration: Design.durSlow * 3
                                  easing.type: Design.easeType
                                  easing.bezierCurve: Design.easeCurve }
            }
        }
    }
    HoverHandler { id: boxHover }

    // ── borde = visualizador del anillo mientras se graba ────────────
    Canvas {
        id: micViz
        anchors.fill: parent
        visible: bar.vizOn
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            if (!bar.vizOn) return
            var s = bar.spectrum
            var r = Design.radiusSurface
            ctx.strokeStyle = "" + Design.cyan
            ctx.lineWidth = 1
            // marco base tenue
            ctx.globalAlpha = 0.25
            ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
            ctx.globalAlpha = 1
            if (!s || !s.length) return
            // segmentos a lo largo del perímetro (misma lógica que el anillo)
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

    // ── prompt + editor + micrófono ─────────────────────────────────
    Text {
        id: prompt
        anchors { left: parent.left; leftMargin: Design.sp(3); top: parent.top
                  topMargin: Design.sp(3) }
        text: "❯"
        color: bar.busy ? Design.azure : Design.cyan
        font.family: Design.fontMono
        font.pixelSize: Design.fsBody
    }

    Flickable {
        id: flick
        anchors {
            left: prompt.right; leftMargin: Design.sp(2)
            right: micBtn.left; rightMargin: Design.sp(2)
            top: parent.top; bottom: parent.bottom
            topMargin: Design.sp(3); bottomMargin: Design.sp(3)
        }
        contentWidth: width
        contentHeight: editor.implicitHeight
        clip: true
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
                visible: !editor.text && !editor.activeFocus
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
    MicButton {
        id: micBtn
        anchors { right: parent.right; rightMargin: Design.sp(2)
                  verticalCenter: parent.verticalCenter }
        micState: bar.micState
        onToggled: {
            if (!Voice) return
            if (bar.recording) Voice.stop_recording()
            else Voice.start_recording()
        }
    }
}
