import QtQuick
import QtQuick.Window
import "."

// FASE 1 — lienzo mínimo que prueba el sistema de diseño: tres planos de
// profundidad construidos SOLO con luz (gradientes desde Design.lightOrigin),
// una hairline, y la escala tipográfica real. El núcleo, el HUD y la
// conversación llegan en fases siguientes.
Window {
    id: win
    width: 1280
    height: 800
    minimumWidth: 900
    minimumHeight: 560
    visible: true
    color: Design.bgVoid
    title: "J.A.R.V.I.S"

    // Plano 0 — fondo absoluto. Gradiente sutil que sube hacia la fuente de luz.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Design.bgAbyss }
            GradientStop { position: 1.0; color: Design.bgVoid }
        }
    }

    // Plano 1 — campo. Halo de luz único, arriba-centro, muy tenue.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: Design.glow(Design.azure, 0.10) }
            GradientStop { position: 0.45; color: "transparent" }
        }
    }

    // Plano 2 — superficie translúcida de muestra, con su regla lateral (la
    // etiqueta vive en la regla, no flotando sobre el bloque).
    Item {
        id: panel
        x: Design.sp(10); y: Design.sp(10)
        width: Math.min(420, parent.width - Design.sp(20))
        height: Design.sp(56)

        Rectangle {   // regla lateral de 1px
            width: 1; height: parent.height
            color: Design.cyan; opacity: 0.5
        }
        Text {
            x: Design.sp(4); y: 0
            text: "sistema de diseño"
            font.family: Design.fontMono
            font.pixelSize: Design.fsMeta
            color: Design.textMeta
        }
        Rectangle {
            anchors.fill: parent
            anchors.leftMargin: Design.sp(4)
            color: Design.surfaceColor
            radius: Design.radiusSurface
            border.width: 1
            border.color: Design.hairline
        }
        Column {
            anchors.fill: parent
            anchors.margins: Design.sp(3)
            anchors.leftMargin: Design.sp(6)
            spacing: Design.sp(1)
            Text { text: "JARVIS"; color: Design.textPrimary
                   font.family: Design.fontSans; font.pixelSize: Design.fsTitle }
            Text { text: "capa de vista · PySide6 + Qt Quick"; color: Design.textSecondary
                   font.family: Design.fontMono; font.pixelSize: Design.fsSmall }
        }
    }

    // Hairline horizontal de separación.
    Rectangle {
        anchors { left: parent.left; right: parent.right }
        y: Design.sp(10) + Design.sp(56) + Design.sp(6)
        height: 1
        color: Design.hairline
    }

    // Escala tipográfica — evidencia de jerarquía real.
    Column {
        x: Design.sp(10)
        y: Design.sp(10) + Design.sp(56) + Design.sp(12)
        spacing: Design.sp(2)
        Repeater {
            model: [
                { s: Design.fsDisplay, t: "40 · display" },
                { s: Design.fsLarge,   t: "24 · large" },
                { s: Design.fsTitle,   t: "18 · title" },
                { s: Design.fsBody,    t: "15 · body" },
                { s: Design.fsSmall,   t: "13 · small" },
                { s: Design.fsMeta,    t: "12 · meta" }
            ]
            delegate: Text {
                required property var modelData
                text: modelData.t
                color: Design.textPrimary
                font.family: Design.fontMono
                font.pixelSize: modelData.s
            }
        }
    }
}
