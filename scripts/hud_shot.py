"""Captura del HUD con una conversación real dentro.

Uso:  python -m scripts.hud_shot [salida.png] [--state speaking] [--size 1360x820]
                                 [--cover-core] [--cover-spine]

Siembra >=6 turnos reales en el ConversationModel, fija métricas y estado,
espera a que la escena renderice (tras el arranque) y guarda un PNG del
Window compuesto sobre el fondo del sistema (Design.bgVoid) para que se lea.

--cover-core (FASE I · I3): tapa con un rectángulo negro sólido la zona del
núcleo (`rootItem.orbCX/orbCY/orbSize`), para la prueba de aceptación de la
iluminación global: si el estado se distingue SOLO por la luz del resto de
la interfaz, sin ver el núcleo.

--cover-spine (FASE I · I3, comprobación de refuerzo): tapa ADEMÁS la
ActivitySpine (objectName "activitySpine") — la barra de energía es un
indicador de datos, no iluminación, y si es la única señal que distingue
estados hay que descartarla para juzgar si hairlines/bordes/marco respiran
con el núcleo por sí solos.

--force-full-pipeline (FASE I · I6): fuerza `rootItem.perfOverride = -1`
para forzar bloom+atmósfera incluso bajo un backend de software (el latch
de degradación normalmente los apaga). Sólo tiene sentido para depurar en
una máquina sin GPU real; en una máquina con Wayland/X11 real (como ESTA)
no hace falta y NO SE DEBE usar por defecto — el pipeline real es el que
corre sin forzar nada.

IMPORTANTE (FASE I, corrección de metodología en I6): este script NO fija
`QT_QPA_PLATFORM`. Si el proceso lo hereda como "offscreen" (por el entorno,
no por este script), Qt usará un backend de software y el HUD activará su
propio latch de degradación — sin bloom ni atmósfera, sólo el núcleo puro.
Cada captura queda marcada con el backend real y el estado de `degraded`
(impreso y grabado como texto en la esquina de la imagen) precisamente para
que esto nunca vuelva a pasar desapercibido: una captura que no dice en qué
pipeline se tomó no sirve como evidencia de nada.
"""
from __future__ import annotations

import sys

_TURNOS = [
    ("user", "jarvis, ¿cuánta ram me queda?"),
    ("jarvis", "12,4 GB libres de 16, senor. El modelo bge-m3 no está cargado "
               "ahora mismo; si lo necesitas para memoria semántica lo levanto."),
    ("user", "abre el navegador y busca vuelos a lisboa"),
    ("jarvis", "Firefox abierto y la búsqueda lanzada, senor. Verifiqué que la "
               "ventana existe y tiene el foco."),
    ("user", "qué procesos están comiendo cpu"),
    ("jarvis", "Los tres primeros por CPU: gnome-shell 11 %, firefox 9 %, "
               "ollama 6 %. Ninguno anómalo."),
    ("user", "copia al portapapeles el comando para reiniciar pipewire"),
    ("jarvis", "Es un comando: lo dejo preparado y te pido confirmación antes "
               "de copiarlo. `systemctl --user restart pipewire`."),
]


def _seed(conv) -> None:
    for canal, texto in _TURNOS:
        if canal == "user":
            conv.add_user(texto)
        else:
            conv.end_assistant(texto, "chat · 0.9 s", "chat")


def main() -> int:
    out = "hud_shot.png"
    state = "speaking"
    size = (1360, 820)
    cover_core = False
    cover_spine = False
    force_full_pipeline = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--state":
            state = args[i + 1]
            i += 2
        elif a == "--size":
            w, h = args[i + 1].lower().split("x")
            size = (int(w), int(h))
            i += 2
        elif a == "--cover-core":
            cover_core = True
            i += 1
        elif a == "--cover-spine":
            cover_spine = True
            i += 1
        elif a == "--force-full-pipeline":
            force_full_pipeline = True
            i += 1
        elif not a.startswith("--"):
            out = a
            i += 1
        else:
            i += 1

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PySide6.QtQuick import QQuickItem

    from jarvis_local.ui.hud.app import _configure_environment, create_engine

    _configure_environment()
    app = QGuiApplication(sys.argv[:1])
    engine = create_engine(app)
    roots = engine.rootObjects()
    if not roots:
        print("[hud_shot] no cargó Main.qml", file=sys.stderr)
        return 1
    win = roots[0]
    rt = engine._runtime  # noqa: SLF001

    _seed(rt.conversation)
    rt.vm.push_metrics({
        "online": True, "model": "llama3.2:3b", "cpu": 34, "ram": 41,
        "latencyMs": 920, "tokensPerSecond": 22.4,
        "voice": {"tts": True, "mic": "available"},
        "memory": {"auto_recall": True, "count": 37},
        "tools": {"count": 84, "agent": False},
    })
    rt.vm.set_state(state)
    rt.vm.push_audio(0.6 if state in ("listening", "speaking") else 0.15)

    win.setProperty("width", size[0])
    win.setProperty("height", size[1])
    win.show()
    # En un WM real (a diferencia de offscreen), el tamaño pedido antes de
    # show() no siempre se respeta (esta ventana sin marco puede llegar
    # ajustada a otra cosa, p.ej. DPI/política del compositor) — un
    # resize() explícito DESPUÉS de show() sí se sostiene.
    win.resize(size[0], size[1])

    root_item = win.findChild(QQuickItem, "rootItem")
    if root_item is None:
        print("[hud_shot] no encontré rootItem", file=sys.stderr)
        return 1

    if force_full_pipeline:
        root_item.setProperty("perfOverride", -1)

    def _grab() -> None:
        res = root_item.grabToImage()
        if res is None:
            print("[hud_shot] grabToImage devolvió None", file=sys.stderr)
            app.quit()
            return

        def _ready() -> None:
            img = res.image()  # QImage con alfa
            canvas = QImage(img.size(), QImage.Format_RGB32)
            canvas.fill(QColor("#04070D"))  # Design.bgVoid
            p = QPainter(canvas)
            p.drawImage(0, 0, img)
            # `root_item.width` (no `win.property("width")`) es lo que de
            # verdad usan orbCX/orbCY/orbSize y demás geometría de Main.qml
            # (coordenadas lógicas de rootItem). En un WM real, la ventana
            # puede reescalarse/redimensionarse (DPI, políticas del
            # compositor) de forma que `win.width` físico y el tamaño lógico
            # de rootItem ya no coincidan 1:1 — usar rootItem.width evita que
            # las tapas de --cover-core/--cover-spine queden mal alineadas.
            scale = img.width() / max(1, root_item.property("width"))
            if cover_core:
                cx = root_item.property("orbCX")
                cy = root_item.property("orbCY")
                r = root_item.property("orbSize")
                if cx is not None and cy is not None and r is not None:
                    side = r * 1.15 * scale  # margen leve por el halo del bloom
                    p.fillRect(
                        (cx * scale) - side / 2, (cy * scale) - side / 2,
                        side, side, QColor("#000000"),
                    )
                else:
                    print("[hud_shot] --cover-core: no encontré orbCX/orbCY/orbSize"
                          " en rootItem", file=sys.stderr)
            if cover_spine:
                spine = win.findChild(QQuickItem, "activitySpine")
                if spine is not None:
                    top_left = spine.mapToItem(root_item, 0, 0)
                    p.fillRect(
                        top_left.x() * scale, top_left.y() * scale,
                        spine.width() * scale, spine.height() * scale,
                        QColor("#000000"),
                    )
                else:
                    print("[hud_shot] --cover-spine: no encontré activitySpine",
                          file=sys.stderr)
            p.end()
            # FASE I · I6: qué pipeline generó esta captura — grabado EN LA
            # IMAGEN (no sólo en el log) porque un PNG sin esta marca no sirve
            # como evidencia: no dice si bloom/atmósfera corrieron de verdad.
            backend = root_item.property("rhiBackendName") or "?"
            degraded = bool(root_item.property("degraded"))
            stamp = f"backend={backend} degraded={degraded}"
            p2 = QPainter(canvas)
            p2.setPen(QColor("#FF9F1C" if degraded else "#37D2FF"))
            p2.drawText(6, canvas.height() - 6, stamp)
            p2.end()
            canvas.save(out)
            tags = []
            if cover_core:
                tags.append("núcleo tapado")
            if cover_spine:
                tags.append("espina tapada")
            suffix = f" [{', '.join(tags)}]" if tags else ""
            print(f"[hud_shot] guardado {out} ({img.width()}x{img.height()}) estado={state} "
                  f"{stamp}" + suffix)
            if degraded:
                print("[hud_shot] AVISO: degraded=True -> bloom y atmósfera "
                      "apagados por el latch de degradación (backend de "
                      "software, o fps sostenidos <40). Esta captura NO es "
                      "evidencia del pipeline completo.", file=sys.stderr)
            app.quit()

        res.ready.connect(_ready)

    QTimer.singleShot(2400, _grab)  # pasado el arranque (durBoot 1100 ms + margen)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
