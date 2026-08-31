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

            Text {
                id: proseView
                visible: !seg.modelData.code
                width: mdb.measure
                textFormat: Text.MarkdownText
                wrapMode: Text.WordWrap
                text: seg.modelData.code ? "" : seg.modelData.text
                color: Design.textPrimary
                font.family: Design.fontSans
                font.pixelSize: Design.fsBody
                lineHeight: 1.6
                lineHeightMode: Text.ProportionalHeight
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
