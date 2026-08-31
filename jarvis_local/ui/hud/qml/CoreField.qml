import QtQuick
import "."

// ─────────────────────────────────────────────────────────────────────────────
//  CORE FIELD — un único lienzo, un único bucle de animación.
//
//  Todo lo que se mueve en el núcleo (halo, campo de partículas, anillo de 64
//  segmentos, barrido especular, geometría por estado, respiración) se dibuja
//  en este `Canvas` y se integra en el `FrameAnimation` de abajo. No hay ningún
//  otro timer ni bucle. La simulación integra por Δt real: bajar a 30 fps no
//  altera el movimiento.
//
//  Los `Behavior`/`states` de CORE.qml (cross-fade de 220 ms entre estados)
//  corren sobre el mismo driver de animación de Qt; no son timers propios.
// ─────────────────────────────────────────────────────────────────────────────
Item {
    id: field

    // ── entradas (las fija Core.qml) ───────────────────────────────────────
    property string coreState: "idle"
    property real   audioLevel: 0.0
    property var    spectrum: []          // [] = sin fuente → segmentos en base
    property real   tokensPerSecond: 0.0
    property point  parallax: Qt.point(0, 0)   // -1..1, del puntero
    property bool   loopRunning: true
    property bool   compact: false             // modo insignia (Fase 6)

    // ── parámetros visuales, interpolados por Core.qml al cambiar de estado ─
    property color tint: Design.azure
    property real  ringOpen: 0.0          // 0 anillo cerrado · 1 = 64 segmentos
    property real  spinRate: 6.0          // grados/seg
    property real  converge: 0.0          // 0 órbita · 1 caída al núcleo
    property real  emission: 0.45         // 0 = no emite (ALERT/OFFLINE)
    property bool  fragmented: false      // anillo roto (ALERT)
    property bool  dashed: false          // trazo discontinuo (OFFLINE)
    property real  concentric: 0.0        // anillos contrarrotantes (THINKING)
    property real  radialWave: 0.0        // onda desde el centro (SPEAKING)

    // ── geometría ─────────────────────────────────────────────────────────
    readonly property real cx: width / 2
    readonly property real cy: height / 2
    readonly property real fieldR: Math.min(width, height) * 0.46
    readonly property real ringR: Math.min(width, height) * 0.30

    // ── estado interno del bucle (acumuladores, no bindings) ───────────────
    property real _t: 0                   // segundos de simulación acumulados
    property real _acc: 0                 // acumulador para el techo de 30 fps
    property real _angle: 0               // rotación acumulada (grados)
    property real _sweepAt: -99
    property real _sweepPeriod: 7
    readonly property real _frame: 1 / 30
    readonly property int  _pmax: 120

    // buffers de partículas (Float32Array, asignados una sola vez)
    property var _px; property var _py
    property var _pvx; property var _pvy
    property var _plife; property var _pmaxlife

    Component.onCompleted: {
        _px = new Float32Array(_pmax);  _py = new Float32Array(_pmax)
        _pvx = new Float32Array(_pmax); _pvy = new Float32Array(_pmax)
        _plife = new Float32Array(_pmax); _pmaxlife = new Float32Array(_pmax)
        for (var i = 0; i < _pmax; i++) _spawn(i, true)
    }

    // densidad y velocidad del campo = función del estado (no aleatorias)
    function _density() {
        if (compact) return 0.0            // insignia: sin campo de partículas
        switch (coreState) {
        case "listening": return 0.60
        case "thinking":  return 1.00
        case "speaking":  return 0.70
        case "alert":     return 0.15
        case "offline":   return 0.00
        default:          return 0.42        // idle
        }
    }
    function _speed() {
        switch (coreState) {
        case "listening": return 0.75 + audioLevel * 0.6
        case "thinking":  return 1.15
        case "speaking":  return 0.95
        case "alert":     return 0.20
        case "offline":   return 0.0
        default:          return 0.50        // idle — órbita lenta
        }
    }

    function _spawn(i, initial) {
        var a = Math.random() * Math.PI * 2
        var r = (initial ? Math.random() : 0.82 + Math.random() * 0.18) * fieldR
        _px[i] = Math.cos(a) * r
        _py[i] = Math.sin(a) * r
        var orbit = (0.22 + Math.random() * 0.14) * fieldR
        _pvx[i] = -Math.sin(a) * orbit
        _pvy[i] =  Math.cos(a) * orbit
        _pmaxlife[i] = 4 + Math.random() * 6
        _plife[i] = initial ? Math.random() * _pmaxlife[i] : 0
    }

    function _stepParticles(dt) {
        var active = Math.round(_pmax * _density())
        var spd = _speed()
        for (var i = 0; i < _pmax; i++) {
            if (i >= active) { _plife[i] = -1; continue }
            if (_plife[i] < 0) _spawn(i, false)
            _plife[i] += dt
            if (_plife[i] > _pmaxlife[i]) { _spawn(i, false) }

            var dx = -_px[i], dy = -_py[i]
            var d = Math.max(8, Math.sqrt(dx * dx + dy * dy))
            var pull = (14 + 150 * converge) / d
            _pvx[i] += (dx / d) * pull * dt * 60
            _pvy[i] += (dy / d) * pull * dt * 60
            _pvx[i] *= 0.985; _pvy[i] *= 0.985
            _px[i] += _pvx[i] * spd * dt
            _py[i] += _pvy[i] * spd * dt
            if ((_px[i] * _px[i] + _py[i] * _py[i]) < 36) _spawn(i, false)
        }
    }

    // altura 0..1 del segmento i del anillo — binding REAL o valor base apagado
    function _segHeight(i) {
        var s = spectrum
        if ((coreState === "listening" || coreState === "speaking")
                && s && s.length >= 1) {
            return s[i % s.length]
        }
        if (coreState === "thinking" && tokensPerSecond > 0) {
            var f = Math.min(tokensPerSecond, 24) * 0.25
            return 0.14 + 0.46 * Math.abs(Math.sin(i * 0.49 + _t * f))
        }
        return 0.05        // sin fuente: base, apagado. Nunca ruido aleatorio.
    }

    // ── EL BUCLE ──────────────────────────────────────────────────────────
    FrameAnimation {
        id: clock
        running: field.loopRunning
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)          // clamp tras un stall
            field._t += dt
            field._angle = (field._angle + field.spinRate * dt) % 360

            // respiración: 1.000 → 1.012 en 4 s, sinusoidal (subliminal)
            field.scale = 1.0 + 0.006 + 0.006 * Math.sin(2 * Math.PI * field._t / 4)

            // barrido especular: una pasada cada 6–9 s
            if (field._t - field._sweepAt > field._sweepPeriod) {
                field._sweepAt = field._t
                field._sweepPeriod = 6 + Math.random() * 3
            }

            field._acc += dt
            if (field._acc + 1e-4 >= field._frame) {     // techo de 30 fps
                field._stepParticles(field._acc)
                field._acc = 0
                canvas.requestPaint()
            }
        }
    }

    // ── EL LIENZO ─────────────────────────────────────────────────────────
    Canvas {
        id: canvas
        anchors.fill: parent
        renderTarget: Canvas.FramebufferObject
        renderStrategy: Canvas.Cooperative

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            ctx.lineCap = "round"

            var cx = field.cx, cy = field.cy
            var t = field._t
            var em = field.emission
            var c = field.tint
            function rgba(a) { return Qt.rgba(c.r, c.g, c.b, a) }

            // --- plano CAMPO: halo volumétrico (2 capas, desplazamiento distinto)
            if (em > 0.01) {
                var hx = cx + field.parallax.x * 3
                var hy = cy + field.parallax.y * 3
                if (!field.compact)
                    _halo(ctx, hx, hy, field.ringR * 2.6, rgba(0.05 * em))
                _halo(ctx, hx - field.parallax.x * 1.5, hy - field.parallax.y * 1.5,
                      field.ringR * 1.7, rgba(0.09 * em))
            }

            // --- plano CAMPO: partículas
            var pcx = cx + field.parallax.x * 3
            var pcy = cy + field.parallax.y * 3
            var active = Math.round(field._pmax * field._density())
            for (var i = 0; i < active; i++) {
                var life = field._plife[i]
                if (life < 0) continue
                var lf = life / field._pmaxlife[i]
                var av = Math.sin(Math.min(1, lf) * Math.PI)     // nacer→morir
                ctx.fillStyle = rgba(0.5 * av * Math.max(0.25, em))
                ctx.fillRect(pcx + field._px[i] - 1, pcy + field._py[i] - 1, 2, 2)
            }

            // --- plano NÚCLEO
            var ncx = cx + field.parallax.x * 4
            var ncy = cy + field.parallax.y * 4

            // anillos concéntricos contrarrotantes (THINKING)
            if (field.concentric > 0.01 && !field.compact) {
                var k = field.concentric
                _arc(ctx, ncx, ncy, field.ringR * 0.78, field._angle * 2.0, 210,
                     rgba(0.5 * k), 2)
                _arc(ctx, ncx, ncy, field.ringR * 0.60, -field._angle * 2.6, 160,
                     rgba(0.35 * k), 2)
            }

            // onda radial desde el centro (SPEAKING)
            if (field.radialWave > 0.01 && !field.compact) {
                for (var w = 0; w < 3; w++) {
                    var ph = (t * 0.6 + w / 3) % 1
                    var rr = ph * field.ringR * 1.8
                    ctx.strokeStyle = rgba((1 - ph) * 0.4 * field.radialWave)
                    ctx.lineWidth = 2
                    ctx.beginPath(); ctx.arc(ncx, ncy, rr, 0, Math.PI * 2); ctx.stroke()
                }
            }

            // anillo de datos de 64 segmentos
            var segs = 64
            var baseA = field._angle * Math.PI / 180
            for (var g = 0; g < segs; g++) {
                if (field.fragmented && (g % 8 < 3)) continue           // roto
                if (field.dashed && (g % 2 === 0)) continue             // discontinuo
                var ang = baseA + (g / segs) * Math.PI * 2
                var ca = Math.cos(ang), sa = Math.sin(ang)
                var h = field._segHeight(g)
                var inner = field.ringR
                var outer = field.ringR + 3 + field.ringOpen * (4 + h * 24)
                             + (1 - field.ringOpen) * (1 + h * 3)
                var a = (0.16 + 0.7 * h) * Math.max(0.22, em)
                if (field.dashed || field.fragmented) a = 0.5
                ctx.strokeStyle = field.dashed ? Qt.rgba(c.r, c.g, c.b, 0.5) : rgba(a)
                ctx.lineWidth = field.ringOpen > 0.4 ? 2 : 1.5
                ctx.beginPath()
                ctx.moveTo(ncx + ca * inner, ncy + sa * inner)
                ctx.lineTo(ncx + ca * outer, ncy + sa * outer)
                ctx.stroke()
            }

            // barrido especular lento sobre el anillo (una pasada / 6–9 s)
            var sf = (t - field._sweepAt) / field._sweepPeriod
            if (sf >= 0 && sf < 0.5 && em > 0.01 && !field.compact) {
                var sweepDeg = sf * 720
                var sAng = baseA + sweepDeg * Math.PI / 180
                for (var b = 0; b < 10; b++) {
                    var bb = sAng - b * 0.05
                    var fade = (1 - b / 10) * (1 - sf * 2)
                    ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.10 * fade)
                    ctx.lineWidth = 2
                    ctx.beginPath()
                    ctx.moveTo(ncx + Math.cos(bb) * (field.ringR - 1),
                               ncy + Math.sin(bb) * (field.ringR - 1))
                    ctx.lineTo(ncx + Math.cos(bb) * (field.ringR + 6),
                               ncy + Math.sin(bb) * (field.ringR + 6))
                    ctx.stroke()
                }
            }

            // núcleo: punto de luz (única emisión de blanco puro)
            if (em > 0.01) {
                var pr = field.ringR * 0.16 * (1 + audioLevel * 0.5)
                ctx.fillStyle = rgba(0.22 * em)
                ctx.beginPath(); ctx.arc(ncx, ncy, pr * 1.7, 0, Math.PI * 2); ctx.fill()
                ctx.fillStyle = rgba(0.85 * em)
                ctx.beginPath(); ctx.arc(ncx, ncy, pr, 0, Math.PI * 2); ctx.fill()
                ctx.fillStyle = Qt.rgba(1, 1, 1, Math.min(1, em))
                ctx.beginPath(); ctx.arc(ncx, ncy, pr * 0.42, 0, Math.PI * 2); ctx.fill()
            } else {
                // ALERT / OFFLINE: núcleo inerte, sin emisión
                ctx.strokeStyle = Qt.rgba(c.r, c.g, c.b, 0.55)
                ctx.lineWidth = 2
                ctx.beginPath(); ctx.arc(ncx, ncy, field.ringR * 0.12, 0, Math.PI * 2)
                ctx.stroke()
            }
        }

        function _halo(ctx, x, y, r, col) {
            var grad = ctx.createRadialGradient(x, y, r * 0.1, x, y, r)
            grad.addColorStop(0, col)
            grad.addColorStop(1, Qt.rgba(col.r, col.g, col.b, 0))
            ctx.fillStyle = grad
            ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill()
        }
        function _arc(ctx, x, y, r, startDeg, extentDeg, col, w) {
            ctx.strokeStyle = col; ctx.lineWidth = w
            ctx.beginPath()
            ctx.arc(x, y, r, startDeg * Math.PI / 180,
                    (startDeg + extentDeg) * Math.PI / 180)
            ctx.stroke()
        }
    }
}
