import QtQuick
import "."

// Cuerpo de un turno: markdown renderado para la prosa, CodeBlock para los
// bloques con vallas ```. Se reconstruye al cambiar `raw` (streaming). Si hay
// un número impar de ```, la última valla está abierta: ese resto se trata como
// código en curso.
Column {
    id: mdb
    property string raw: ""
    property real measure: 520          // ancho máx. de la caja de texto (~78 car.)
    property color textColor: Design.chatJarvis   // color del cuerpo (por canal)
    spacing: Design.sp(2)

    function _segments(src) {
        var parts = src.split("```")
        var segs = []
        for (var i = 0; i < parts.length; i++) {
            if (i % 2 === 0) {
                if (parts[i].length) segs.push({ code: false, text: parts[i], lang: "" })
            } else {
                var body = parts[i]
                var nl = body.indexOf("\n")
                var lang = ""
                if (nl >= 0) {
                    var head = body.slice(0, nl).trim()
                    if (head.length && head.indexOf(" ") === -1) {
                        lang = head
                        body = body.slice(nl + 1)
                    }
                }
                segs.push({ code: true, text: body.replace(/\n$/, ""), lang: lang })
            }
        }
        return segs
    }

    Repeater {
        model: mdb._segments(mdb.raw)
        delegate: Item {
            id: seg
            required property var modelData
            width: mdb.measure
            implicitHeight: modelData.code ? codeView.implicitHeight : proseView.implicitHeight

            TextEdit {
                id: proseView
                visible: !seg.modelData.code
                width: mdb.measure
                textFormat: TextEdit.MarkdownText
                wrapMode: TextEdit.WordWrap
                text: seg.modelData.code ? "" : seg.modelData.text
                color: mdb.textColor
                font.family: Design.fontMono          // estilo terminal
                font.pixelSize: Design.fsBody
                // TextEdit (no Text) para poder seleccionar/copiar el
                // mensaje con el mouse; pierde lineHeight/lineHeightMode y
                // el borde óptico (style/styleColor), ninguno existe en
                // TextEdit, a cambio de la seleccion.
                readOnly: true
                selectByMouse: true
                persistentSelection: true
                cursorVisible: false
                selectionColor: Qt.rgba(0x1D / 255, 0x5C / 255, 0xFF / 255, 0.35)
                selectedTextColor: mdb.textColor
                onLinkActivated: (url) => Qt.openUrlExternally(url)
            }
            CodeBlock {
                id: codeView
                visible: seg.modelData.code
                width: mdb.measure
                contentWidth: mdb.measure
                code: seg.modelData.code ? seg.modelData.text : ""
                lang: seg.modelData.lang
            }
        }
    }
}
