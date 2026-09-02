import QtQuick
import QtQuick.Window
import "."

// Chrome propio de la ventana sin marco (addendum §8.1): zona de arrastre en la
// banda del HUD, controles de ventana, y redimensionado por los 8 bordes vía
// el compositor (startSystemMove / startSystemResize).
Item {
    id: chrome
    required property Window win
    property int gutter: Design.windowShadowGutter

    function _toggleMax() {
        win.visibility = (win.visibility === Window.Maximized)
            ? Window.Windowed : Window.Maximized
    }

    // ── zona de arrastre (banda superior del contenido) ──────────────────
    MouseArea {
        id: dragZone
        x: chrome.gutter
        y: chrome.gutter
        width: parent.width - 2 * chrome.gutter - controls.width - Design.sp(4)
        height: Design.sp(10)
        acceptedButtons: Qt.LeftButton
        onPressed: chrome.win.startSystemMove()
        onDoubleClicked: chrome._toggleMax()
    }

    // ── controles de ventana, alineados a la rejilla del HUD ─────────────
    Row {
        id: controls
        anchors {
            top: parent.top; right: parent.right
            // anidados DENTRO de la retícula de HudFrame (corchete de esquina)
            topMargin: chrome.gutter + Design.sp(4)
            rightMargin: chrome.gutter + Design.sp(5)
        }
        spacing: Design.sp(1)
        WinButton { kind: "min"; onActivated: chrome.win.showMinimized() }
        WinButton {
            kind: chrome.win.visibility === Window.Maximized ? "restore" : "max"
            onActivated: chrome._toggleMax()
        }
        WinButton { kind: "close"; onActivated: chrome.win.close() }
    }

    // ── redimensionado por los 8 bordes (en la canaleta transparente) ────
    component Edge: MouseArea {
        property int edges: 0
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        enabled: chrome.gutter > 0
        onPressed: chrome.win.startSystemResize(edges)
    }
    Edge {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: chrome.gutter; edges: Qt.TopEdge; cursorShape: Qt.SizeVerCursor
    }
    Edge {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: chrome.gutter; edges: Qt.BottomEdge; cursorShape: Qt.SizeVerCursor
    }
    Edge {
        anchors { top: parent.top; bottom: parent.bottom; left: parent.left }
        width: chrome.gutter; edges: Qt.LeftEdge; cursorShape: Qt.SizeHorCursor
    }
    Edge {
        anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
        width: chrome.gutter; edges: Qt.RightEdge; cursorShape: Qt.SizeHorCursor
    }
    Edge {
        anchors { top: parent.top; left: parent.left }
        width: chrome.gutter; height: chrome.gutter
        edges: Qt.TopEdge | Qt.LeftEdge; cursorShape: Qt.SizeFDiagCursor
    }
    Edge {
        anchors { top: parent.top; right: parent.right }
        width: chrome.gutter; height: chrome.gutter
        edges: Qt.TopEdge | Qt.RightEdge; cursorShape: Qt.SizeBDiagCursor
    }
    Edge {
        anchors { bottom: parent.bottom; left: parent.left }
        width: chrome.gutter; height: chrome.gutter
        edges: Qt.BottomEdge | Qt.LeftEdge; cursorShape: Qt.SizeBDiagCursor
    }
    Edge {
        anchors { bottom: parent.bottom; right: parent.right }
        width: chrome.gutter; height: chrome.gutter
        edges: Qt.BottomEdge | Qt.RightEdge; cursorShape: Qt.SizeFDiagCursor
    }
}
