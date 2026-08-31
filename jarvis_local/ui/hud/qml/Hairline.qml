import QtQuick
import "."

// Línea de 1px cuyo color y opacidad derivan de la distancia al núcleo
// (Design.corePos): cerca brilla y tira al color del estado, lejos se apaga.
// También "respira" con Design.coreEnergy. Nada de color fijo.
Rectangle {
    id: hl
    property bool vertical: false

    implicitWidth: vertical ? 1 : 0
    implicitHeight: vertical ? 0 : 1

    property point _mid: Qt.point(0, 0)
    function _remap() { _mid = mapToItem(null, width / 2, height / 2) }
    onWidthChanged: _remap()
    onHeightChanged: _remap()
    onXChanged: _remap()
    onYChanged: _remap()
    Component.onCompleted: _remap()
    Connections { target: Design; function onCorePosChanged() { hl._remap() } }

    color: Design.litHairline(_mid.x, _mid.y)
    opacity: Design.reveal(_mid.x, _mid.y)      // el frente de arranque la revela
}
