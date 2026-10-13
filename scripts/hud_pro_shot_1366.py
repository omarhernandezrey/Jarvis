"""Capturas reales del `hud_pro` (PySide6, esquinas compactas bajo 1400px) en
1366x768 — la resolución de portátil típica que dispara el layout compacto
añadido en FASE D (`HudWindow._is_wide_layout`, umbral 1400px).

Reutiliza exactamente el camino de `python -m hud_pro --screenshot`
(create_app/HudWindow/_populate_sample/OrbRenderer) y añade la rama
PROCESANDO+tool_start que ese CLI no cubre (no hay backend real detrás que
dispare `win.tool_start()` en una captura aislada).

Uso:
    python scripts/hud_pro_shot_1366.py <directorio_salida>
        # genera las 3 capturas de referencia: listo, escuchando, procesando_tool

    python scripts/hud_pro_shot_1366.py <modo> <archivo.png>
        # una sola captura; <modo> es listo | escuchando | procesando_tool
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from hud_pro.__main__ import _populate_sample
from hud_pro.app import create_app
from hud_pro.state import OrbState
from hud_pro.window import HudWindow

MODES = ("listo", "escuchando", "procesando_tool")


def capture(mode: str, out_path: str) -> bool:
    app = create_app()
    win = HudWindow()
    win.resize(1366, 768)
    _populate_sample(win)

    if mode == "listo":
        win.set_state(OrbState.IDLE)
    elif mode == "escuchando":
        win.set_state(OrbState.LISTENING)
        win.set_transcript("Jarvis, ¿cómo va el uso de memoria y qué tengo pendiente")
    elif mode == "procesando_tool":
        win.set_state(OrbState.THINKING)
        win.tool_start("buscar_en_la_web")
    else:
        raise ValueError(f"modo desconocido: {mode!r} (usa uno de {MODES})")

    win.show()
    app.processEvents()
    r = win.orb.renderer
    r.snap()
    for i in range(150):
        if mode == "escuchando":
            r.set_level(0.35 + 0.3 * abs(math.sin(i * 0.3)))
        r.advance(1 / 60)
    for _ in range(3):
        app.processEvents()
    win.chat.view.scroll_to_bottom()
    app.processEvents()
    # El overlay de arranque (checklist real de servicios) se dispara en
    # cuanto se muestra la ventana y tarda unos ticks en cerrarse solo; para
    # una captura de referencia limpia se oculta explícitamente — no es lo
    # que estas capturas documentan.
    win._startup_checklist.hide()  # noqa: SLF001
    app.processEvents()
    ok = win.grab().save(out_path)
    print(f"{mode}: {'guardada' if ok else 'FALLÓ'} -> {out_path}")
    win.close()
    return ok


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        outdir = Path(argv[0])
        outdir.mkdir(parents=True, exist_ok=True)
        ok = True
        for mode in MODES:
            ok = capture(mode, str(outdir / f"hud_1366x768_{mode}.png")) and ok
        return 0 if ok else 1
    if len(argv) == 2:
        mode, out_path = argv
        return 0 if capture(mode, out_path) else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
