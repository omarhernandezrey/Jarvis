"""CLI del HUD.

python -m hud_pro                 # abre el HUD vacío
python -m hud_pro --demo          # ciclo simulado: escuchar → procesar → hablar (hilo worker)
python -m hud_pro --screenshot out.png --state thinking --size 1920x1080
"""

from __future__ import annotations

import argparse
import math
import random
import threading
import time

from .app import create_app
from .bridge import HudBridge
from .qt_compat import QT_API, exec_app
from .state import OrbState, parse_state
from .window import HudWindow

_DEMO_QUESTION = "Jarvis, ¿cómo va el uso de memoria y qué tengo pendiente hoy?"
_DEMO_ANSWER = (
    "Todo en orden. El sistema usa **41 %** de RAM y la CPU está estable.\n\n"
    "Pendientes para hoy:\n"
    "- Revisar el PR del módulo de voz\n"
    "- Ejecutar `pytest test/test_ui_hud.py`\n"
    "- Reunión de proyecto a las **4:00 p. m.**\n\n"
    "¿Quieres que te lo recuerde 15 minutos antes?"
)


def _size(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        return max(320, int(w)), max(240, int(h))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Formato esperado: ANCHOxALTO, p. ej. 1920x1080") from exc


def _demo_worker(bridge: HudBridge, stop: threading.Event) -> None:
    """Simula el backend desde OTRO hilo usando solo la API thread-safe del bridge."""
    rnd = random.Random(3)
    bridge.set_model("llama3.1:8b")
    while not stop.is_set():
        bridge.set_state("listo")
        if stop.wait(3.0):
            return
        bridge.set_state("escuchando")
        words = _DEMO_QUESTION.split()
        t0 = time.monotonic()
        for i in range(len(words)):
            for _ in range(6):
                t = time.monotonic() - t0
                bridge.set_level(0.25 + 0.55 * abs(math.sin(t * 7.1)) * rnd.uniform(0.6, 1.0))
                if stop.wait(0.03):
                    return
            bridge.set_transcript(" ".join(words[: i + 1]))
        bridge.set_level(0.0)
        bridge.add_message("user", _DEMO_QUESTION)
        bridge.set_state("procesando")
        if stop.wait(2.4):
            return
        bridge.set_state("hablando")
        for token in _DEMO_ANSWER.replace("\n", "\n ").split(" "):
            bridge.stream(token + " ")
            if stop.wait(0.05):
                return
        bridge.end_stream()
        if stop.wait(1.0):
            return


def _populate_sample(win: HudWindow) -> None:
    win.set_model_name("llama3.1:8b")
    win.add_system_message("— Sesión iniciada · modelo local —")
    win.add_user_message("Jarvis, resume mi agenda de mañana.")
    win.add_assistant_message(
        "Mañana tienes **3 eventos**:\n\n- 9:00 Daily del proyecto\n- 11:30 Revisión de código\n"
        "- 16:00 Entrega del informe\n\n¿Agrego recordatorios?"
    )
    win.add_user_message(_DEMO_QUESTION)


def main() -> int:
    parser = argparse.ArgumentParser(prog="hud_pro", description="HUD de escritorio de JARVIS")
    parser.add_argument("--demo", action="store_true", help="ciclo de demostración con hilo worker")
    parser.add_argument("--screenshot", metavar="PNG", help="renderiza una captura y sale")
    parser.add_argument("--state", default="idle", help="estado para --screenshot")
    parser.add_argument("--size", type=_size, default=(1280, 820), help="tamaño ANCHOxALTO")
    parser.add_argument("--no-console", action="store_true", help="oculta la consola")
    parser.add_argument("--fps", type=int, default=None, help="fps máximos del orbe")
    args = parser.parse_args()

    app = create_app()
    win = HudWindow()
    win.resize(*args.size)
    if args.fps:
        win.orb.set_fps(args.fps)
    if args.no_console:
        win.toggle_console(False)

    if args.screenshot:
        state = parse_state(args.state)
        _populate_sample(win)
        win.set_state(state)
        if state is OrbState.LISTENING:
            win.set_transcript("Jarvis, ¿cómo va el uso de memoria y qué tengo pendiente")
        if state is OrbState.SPEAKING:
            win.stream_assistant("Todo en orden. El sistema usa **41 %** de RAM y la CPU")
        win.show()
        app.processEvents()
        r = win.orb.renderer
        r.snap()
        for i in range(150):
            if state is OrbState.LISTENING:
                r.set_level(0.35 + 0.3 * abs(math.sin(i * 0.3)))
            r.advance(1 / 60)
        for _ in range(3):
            app.processEvents()
        win.chat.view.scroll_to_bottom()
        app.processEvents()
        ok = win.grab().save(args.screenshot)
        print(f"[{QT_API}] captura {'guardada' if ok else 'FALLÓ'}: {args.screenshot}")
        return 0 if ok else 1

    stop = threading.Event()
    if args.demo:
        bridge = HudBridge(win)
        worker = threading.Thread(target=_demo_worker, args=(bridge, stop), daemon=True, name="hud-demo")
        app.aboutToQuit.connect(stop.set)
        worker.start()
    win.show()
    code = exec_app(app)
    stop.set()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
