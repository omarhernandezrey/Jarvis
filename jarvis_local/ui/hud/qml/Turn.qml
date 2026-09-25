import QtQuick
import "."

// Un turno de la consola estilo TERMINAL: prompt de canal a la izquierda
// (`USER ❯` / `JARVIS ❯`), regla vertical y cuerpo monoespaciado con colores
// ANSI vivos. Sin burbujas.
Item {
    id: turn
    property string channel: "user"
    property string body: ""
    property string timestamp: ""
    property string meta: ""
    property bool streaming: false
    property string kind: "chat"
    property real measure: 520

    // color del canal: rojo error · verde brillante usuario · cian JARVIS
    readonly property color _accent: kind === "error" ? Design.alert
        : channel === "user" ? Design.chatUser : Design.chatPrompt
    // color del cuerpo del mensaje
    readonly property color _bodyColor: kind === "error" ? Design.alert
        : channel === "user" ? Design.chatUser : Design.chatJarvis

    implicitHeight: col.implicitHeight + Design.sp(4)

    // prompt del canal
    Text {
        id: chLabel
        x: 0
        y: 0
        width: Design.sp(17)
        text: (channel === "user" ? "USER" : "JARVIS") + " ❯"
        color: turn._accent
        font.family: Design.fontMono
        font.pixelSize: Design.fsMeta
        font.bold: true
        font.letterSpacing: 0.6
        style: Text.Outline; styleColor: Design.textEdge
    }
    // regla vertical del turno: degradado que nace brillante en el NODO
    // (donde el prompt toca el espinazo) y se apaga hacia abajo.
    Rectangle {
        x: Design.sp(17)
        y: 2
        width: 1
        height: turn.implicitHeight - Design.sp(4)
        opacity: kind === "error" ? 0.95 : 0.7
        gradient: Gradient {
            GradientStop { position: 0.0; color: turn._accent }
            GradientStop { position: 1.0
                color: Qt.rgba(turn._accent.r, turn._accent.g, turn._accent.b, 0.18) }
        }
    }
    // nodo: pequeño rombo en la cabeza de la regla, en el color del canal.
    // Late con la respiración del orbe (el turno sigue "conectado" a la entidad).
    Rectangle {
        x: Design.sp(17) + 0.5 - 3
        y: 1.5
        width: 6; height: 6
        radius: 1
        rotation: 45
        color: turn._accent
        opacity: Math.min(1.0, (kind === "error" ? 0.9 : 0.62)
                          + 0.30 * Design.breath())
        scale: 0.9 + 0.15 * Design.breath()
    }

    Column {
        id: col
        x: Design.sp(20)
        width: turn.measure
        spacing: Design.sp(1)

        Row {
            spacing: Design.sp(2)
            // mientras se genera y aún no hay texto: aviso de que está trabajando
            Text {
                visible: turn.streaming && !turn.body.length
                text: "procesando… (modelo en CPU)"
                color: Design.warn
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                style: Text.Outline; styleColor: Design.textEdge
            }
            MarkdownBody {
                id: md
                visible: turn.body.length > 0
                raw: turn.body
                measure: turn.measure
                textColor: turn._bodyColor
            }
            // cursor de bloque estilo terminal — en el color del canal
            Text {
                visible: turn.streaming
                text: "▌"
                color: turn._bodyColor
                font.family: Design.fontMono
                font.pixelSize: Design.fsBody
                SequentialAnimation on opacity {
                    running: turn.streaming
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.18; duration: Design.blinkHalf
                        easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: Design.blinkHalf
                        easing.type: Easing.InOutSine }
                }
            }
        }

        // metadatos: verde apagado, sin competir con el mensaje. A su derecha,
        // la acción de copiar el turno (ver `copiar()` más abajo).
        Row {
            spacing: Design.sp(3)
            Text {
                visible: !turn.streaming && (turn.timestamp.length || turn.meta.length)
                anchors.verticalCenter: parent.verticalCenter
                text: turn.timestamp + (turn.meta.length ? "   " + turn.meta : "")
                color: Design.chatMeta
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                style: Text.Outline; styleColor: Design.textEdge
            }
            Text {
                id: copyBtn
                objectName: "copiarTurno"
                visible: turn.body.length > 0
                anchors.verticalCenter: parent.verticalCenter
                text: copyState.copied ? "copiado ✓" : "copiar ⧉"
                color: copyHover.hovered ? Design.cyan : Design.chatMeta
                opacity: copyHover.hovered ? 1.0 : 0.5
                Behavior on opacity { NumberAnimation { duration: Design.durFast } }
                font.family: Design.fontMono
                font.pixelSize: Design.fsMeta
                font.letterSpacing: 0.6
                style: Text.Outline; styleColor: Design.textEdge
                HoverHandler { id: copyHover }
                TapHandler { onTapped: turn.copiar() }
            }
        }
    }

    // ── COPIAR EL TURNO ───────────────────────────────────────────────────
    // El cuerpo ya es seleccionable con el ratón (MarkdownBody lo renderiza
    // con TextEdit de solo lectura), pero el botón evita arrastrar la
    // selección exacta: un clic y el turno entero va al portapapeles. Mismo
    // recurso que CodeBlock: un TextEdit invisible hace de puente.
    // Se copia el `raw` tal cual (markdown incluido), sin el rótulo de canal
    // ni la hora: lo que se pega es el mensaje, no la decoración.
    function copiar() {
        clip.text = turn.body
        clip.selectAll()
        clip.copy()
        clip.deselect()
        copyState.copied = true
        resetAnim.restart()
    }
    QtObject { id: copyState; property bool copied: false }
    // sin Timer suelto: una animación de una pasada (addendum §7)
    SequentialAnimation {
        id: resetAnim
        PauseAnimation { duration: Design.durHold }
        ScriptAction { script: copyState.copied = false }
    }
    TextEdit { id: clip; visible: false }
}
