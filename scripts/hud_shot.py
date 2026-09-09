"""Captura del HUD con una conversación real dentro.

Uso:  python -m scripts.hud_shot [salida.png] [--state speaking] [--size 1360x820]

Siembra >=6 turnos reales en el ConversationModel, fija métricas y estado,
espera a que la escena renderice (tras el arranque) y guarda un PNG del
Window compuesto sobre el fondo del sistema (Design.bgVoid) para que se lea.
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

    root_item = win.findChild(QQuickItem, "rootItem")
    if root_item is None:
        print("[hud_shot] no encontré rootItem", file=sys.stderr)
        return 1

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
            p.end()
            canvas.save(out)
            print(f"[hud_shot] guardado {out} ({img.width()}x{img.height()}) estado={state}")
            app.quit()

        res.ready.connect(_ready)

    QTimer.singleShot(2400, _grab)  # pasado el arranque (durBoot 1100 ms + margen)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
