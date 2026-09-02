import QtQuick
import "."

// Un dato del HUD como LECTURA DE INSTRUMENTO (Fase 13). Sin fondo, sin panel:
// sólo la retícula (HoloFrame: corchetes + hairline), una columna de barras de
// señal a la izquierda en el color de firma, un código de índice arriba a la
// derecha, una línea de barrido que lo recorre, y etiqueta + valor. Si el valor
// empieza por un número, RUEDA a su destino; al aparecer sube desde 0.
Item {
    id: cell
    property string label: ""
    property string value: ""
    property string tag: ""            // código de índice técnico (2–3 car.)
    property bool absent: false
    property color accent: Design.sky
    property color valueColor: accent
    property bool vertical: false
    property bool pulse: false
    property int  ordinal: 0

    readonly property color _accent: absent ? Design.textDisabled : accent
    readonly property color _value:  absent ? Design.textDisabled : valueColor

    implicitWidth: Math.max(labelText.implicitWidth, valueText.implicitWidth)
                   + Design.sp(vertical ? 6 : 9)
    implicitHeight: vertical ? Design.sp(13) : Design.sp(17)

    // ── telemetría que rueda ──
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
    NumberAnimation {
        id: bumpAnim
        target: cell; property: "bump"
        from: 0.45; to: 0.0; duration: Design.durSlow; easing.type: Easing.OutCubic
    }

    // ── entrada escalonada ──
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

    // ── retícula (sin fondo) ──
    HoloFrame {
        anchors.fill: parent
        accent: cell._accent
        extraLift: cell.bump
    }

    // ── línea de barrido: recorre la celda de arriba abajo (reloj global) ──
    Rectangle {
        visible: !cell.absent
        height: 1
        anchors { left: parent.left; right: parent.right
                  leftMargin: Design.sp(1); rightMargin: Design.sp(1) }
        y: (((Design.tick * 0.11 + cell.ordinal * 0.13) % 1.0) + 1.0) % 1.0
           * (cell.height - 2) + 1
        color: cell._accent
        opacity: 0.05 + 0.10 * Design.breath()
    }

    // ── barras de señal a la izquierda (indicador de instrumento) ──
    Column {
        anchors { left: parent.left; leftMargin: Design.sp(1.25)
                  verticalCenter: parent.verticalCenter }
        spacing: 2
        Repeater {
            model: 4
            delegate: Rectangle {
                required property int index
                width: 3 + index * 0.6
                height: 2
                color: Design.stateWash(cell._accent, 0.7)
                opacity: cell.absent ? 0.22
                       : (0.30 + 0.14 * index)
                         * (0.55 + 0.45 * Design.breath())
                         + (index === 0 ? 0.3 * cell.bump : 0)
            }
        }
    }
    Rectangle {   // emisor: chispa en la cabeza de la columna — late con el orbe
        visible: !cell.absent
        x: Design.sp(1.25); y: Design.sp(1.5)
        width: 5; height: 5; radius: 2.5
        color: Design.stateWash(cell._accent, 0.6)
        opacity: Math.min(1.0, 0.35 + 0.35 * Design.breath()
                          + 0.5 * Math.min(1.0, Design.coreEnergy * 1.6 + cell.bump))
        scale: 0.85 + 0.25 * Design.breath()
    }

    // ── código de índice, arriba a la derecha ──
    Text {
        visible: cell.tag.length > 0
        anchors { right: parent.right; top: parent.top
                  rightMargin: Design.sp(2.25); topMargin: Design.sp(1.5) }
        text: cell.tag
        color: Design.stateWash(Design.textMeta, 0.5)
        font.family: Design.fontMono
        font.pixelSize: Design.fsMicro
        font.letterSpacing: 0.8
        opacity: 0.55 + 0.25 * Design.breath()
        style: Text.Outline; styleColor: Design.textEdge
    }

    Column {
        anchors.left: parent.left
        anchors.leftMargin: Design.sp(3.25)
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
