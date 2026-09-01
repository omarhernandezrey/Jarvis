import QtQuick
import "."

// Retícula técnica de fondo: profundidad de "centro de mando", casi
// subliminal. Se pinta UNA vez por tamaño (Canvas.onPaint sólo corre en
// onWidthChanged/onHeightChanged) — cero coste por frame, no vive en el
// FrameAnimation. Nunca compite visualmente con el núcleo ni el texto.
Canvas {
    id: grid
    readonly property int step: Design.sp(24)      // separación de la retícula

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var ctx = getContext("2d"); ctx.reset()
        var w = width, h = height
        ctx.strokeStyle = Qt.rgba(Design.textSecondary.r, Design.textSecondary.g,
                                  Design.textSecondary.b, 0.035)
        ctx.lineWidth = 1
        ctx.beginPath()
        for (var x = 0; x <= w; x += step) { ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, h) }
        for (var y = 0; y <= h; y += step) { ctx.moveTo(0, y + 0.5); ctx.lineTo(w, y + 0.5) }
        ctx.stroke()
        // marcas un poco más presentes cada 4 celdas: lectura de "instrumento"
        ctx.strokeStyle = Qt.rgba(Design.textSecondary.r, Design.textSecondary.g,
                                  Design.textSecondary.b, 0.07)
        ctx.beginPath()
        for (var xi = 0; xi <= w; xi += step * 4) { ctx.moveTo(xi + 0.5, 0); ctx.lineTo(xi + 0.5, 10) }
        for (var yi = 0; yi <= h; yi += step * 4) { ctx.moveTo(0, yi + 0.5); ctx.lineTo(10, yi + 0.5) }
        ctx.stroke()
    }
}
