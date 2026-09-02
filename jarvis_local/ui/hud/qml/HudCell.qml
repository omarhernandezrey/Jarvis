import QtQuick
import "."

// Un dato del HUD como PROYECCIÓN del núcleo (Fase 10): superficie holográfica
// compartida (HoloFrame: gradiente + corchetes de mira + borde que respira con
// la energía real), barra de acento en degradado con emisor arriba, etiqueta
// que susurra + valor que domina. Si el valor empieza por un número, RUEDA a su
// destino en vez de saltar; al aparecer sube desde 0 (barrido de encendido).
// El orbe se queda en azul/cian; aquí manda el color de firma.
Item {
    id: cell
    property string label: ""
    property string value: ""
    property bool absent: false
    property color accent: Design.sky              // color de FIRMA (barra + borde)
    property color valueColor: accent              // color del VALOR (estado)
    property bool vertical: false      // banda superior vs. regla lateral
    property bool pulse: false         // punto de presencia (respira con coreEnergy)
    property int  ordinal: 0           // orden en la fila → entrada escalonada

    readonly property color _accent: absent ? Design.textDisabled : accent
    readonly property color _value:  absent ? Design.textDisabled : valueColor

    implicitWidth: Math.max(labelText.implicitWidth, valueText.implicitWidth)
                   + Design.sp(vertical ? 6 : 9)
    implicitHeight: vertical ? Design.sp(13) : Design.sp(17)

    // ── telemetría que rueda ───────────────────────────────────────────────
    // Si `value` empieza por un número ("72%", "12.4", "1500 ms"), separamos
    // número + sufijo y animamos hacia el número; el sufijo se mantiene.
    readonly property var parsed: {
        var m = /^-?\d+(?:\.\d+)?/.exec(cell.value || "")
        if (!m) return null
        return { num: parseFloat(m[0]),
                 dec: m[0].indexOf(".") >= 0 ? 1 : 0,
                 suf: cell.value.slice(m[0].length) }
    }
    property real rolled: 0
    property real bump: 0
    onParsedChanged: {
        if (parsed) rollAnim.restart()
        bumpAnim.restart()
    }
    NumberAnimation {
        id: rollAnim
        target: cell; property: "rolled"
        to: cell.parsed ? cell.parsed.num : 0
        duration: Design.durRoll
        easing.type: Design.easeType; easing.bezierCurve: Design.easeCurve
    }
    // un cambio de dato ilumina brevemente toda la celda
    NumberAnimation {
        id: bumpAnim
        target: cell; property: "bump"
        from: 0.45; to: 0.0; duration: Design.durSlow; easing.type: Easing.OutCubic
    }

    // ── entrada escalonada: las celdas se ENSAMBLAN, no aparecen de golpe ──
    opacity: 0
    property real introY: Design.sp(2)
    transform: Translate { y: cell.introY }
    SequentialAnimation {
        running: true
        PauseAnimation { duration: cell.ordinal * 45 }
        ParallelAnimation {
            NumberAnimation { target: cell; property: "opacity"
                to: 1.0; duration: Design.durBase }
            NumberAnimation { target: cell; property: "introY"
                to: 0.0; duration: Design.durSlow
                easing.type: Design.easeType; easing.bezierCurve: Design.easeCurve }
        }
    }

    // ── superficie holográfica ─────────────────────────────────────────────
    HoloFrame {
        anchors.fill: parent
        accent: cell._accent
        radius: Design.widgetRadius
        extraLift: cell.bump
    }

    // barra de acento a la izquierda — degradado (emisor arriba) + punto
    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom
                  topMargin: Design.sp(1); bottomMargin: Design.sp(1)
                  leftMargin: 1 }
        width: 2.5
        radius: 1.5
        opacity: cell.absent ? 0.30 : 0.95
        gradient: Gradient {
            GradientStop { position: 0.0
                color: cell.absent ? cell._accent : Design.stateWash(cell._accent, 0.35) }
            GradientStop { position: 1.0
                color: Qt.rgba(cell._accent.r, cell._accent.g, cell._accent.b, 0.25) }
        }
        Behavior on opacity { NumberAnimation { duration: Design.durBase } }
    }
    Rectangle {   // emisor: chispa en la cabeza de la barra
        visible: !cell.absent
        x: 1 + 1.25; y: Design.sp(1) - 1
        width: 4; height: 4; radius: 2
        color: cell._accent
        opacity: 0.5 + 0.5 * Math.min(1.0, 0.25 + Design.coreEnergy * 1.6 + cell.bump)
    }

    Column {
        anchors.left: parent.left
        anchors.leftMargin: Design.sp(2.5)
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        Text {
            id: labelText
            text: cell.label.toUpperCase()
            color: Design.textMeta
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            font.weight: Design.wLabel
            font.letterSpacing: Design.trkLabel
            style: Text.Outline; styleColor: Design.textEdge
        }
        Row {
            spacing: Design.sp(1.5)
            Rectangle {
                visible: cell.pulse && !cell.absent
                width: 6; height: 6; radius: 3
                anchors.verticalCenter: valueText.verticalCenter
                color: cell._accent
                opacity: 0.4 + 0.6 * Math.min(1.0, 0.3 + Design.coreEnergy * 1.6)
            }
            Text {
                id: valueText
                text: cell.absent ? "—"
                    : cell.parsed ? (cell.rolled.toFixed(cell.parsed.dec) + cell.parsed.suf)
                    : cell.value
                color: cell._value
                font.family: Design.fontMono
                font.pixelSize: cell.vertical ? Design.fsBody : Design.fsTitle
                font.weight: Design.wValue
                style: Text.Outline; styleColor: Design.textEdge
                Behavior on color { ColorAnimation { duration: Design.durBase } }
            }
        }
    }
}
