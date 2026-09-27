"""Impacto real del HUD (`hud_pro`) sobre los tokens/s de Ollama.

    python scripts/bench_hud_llm.py [--rounds N] [--prompt "..."]

Compara tres condiciones con el MISMO prompt fijo contra Ollama real:
  - cerrado:     el HUD no corre (referencia).
  - pausado:     el HUD corre, GPU activa, render PAUSADO (set_paused).
  - gobernador:  el HUD corre, GPU activa, estado THINKING forzado — el
                 gobernador de render aplica su preset completo (24fps,
                 escala interna 0.66, fondo congelado, bloom de 1 iteración).

Corre las 3 condiciones INTERCALADAS en rondas (cerrado, pausado,
gobernador, cerrado, pausado, gobernador, ...) en vez de en bloques — así
la deriva del sistema (otros procesos, memoria, frecuencia de CPU) que
esta sesión encontró repetidamente afecta por igual a las 3 condiciones
de cada ronda, y no contamina la comparación relativa entre ellas.

Requiere: Ollama corriendo (`systemctl status ollama` o `ollama serve`),
el modelo ya descargado, y el venv del proyecto activo. Pensado para
correr en la máquina real, con el mínimo de otros procesos posible — el
propio script no puede garantizar eso, sólo reportar lo que mide.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.2:3b"
DEFAULT_PROMPT = (
    "Explica en tres frases breves que es una cache de CPU y por que "
    "importa la localidad de referencia."
)

_LAUNCH_HUD = """
import sys, os, time
sys.path.insert(0, {repo!r})
from hud_pro.qt_compat import QtWidgets, QtCore
from hud_pro.window import HudWindow
from hud_pro.state import OrbState

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
w = HudWindow()
w.resize(1920, 1080)
w.show()
for _ in range(20):
    app.processEvents()
    time.sleep(0.01)

mode = os.environ.get("BENCH_HUD_MODE", "paused")
if mode == "paused" and w.gpu_stage is not None:
    w.gpu_stage.set_paused(True)
elif mode == "governor":
    w.set_state(OrbState.LISTENING)
    for _ in range(10):
        app.processEvents()
    w.set_state(OrbState.THINKING)  # dispara el gobernador completo

print("HUD_READY", flush=True)
timer = QtCore.QTimer()
timer.timeout.connect(lambda: None)
timer.start(16)
app.exec()
"""


def _one_generate(prompt: str) -> tuple[float, float]:
    """(ttft_s, tokens_por_segundo) de una llamada real a Ollama."""
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": True}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    ttft = None
    eval_count = 0
    eval_duration_ns = 0
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            if not line.strip():
                continue
            chunk = json.loads(line)
            if ttft is None and chunk.get("response"):
                ttft = time.perf_counter() - t0
            if chunk.get("done"):
                eval_count = chunk.get("eval_count", 0)
                eval_duration_ns = chunk.get("eval_duration", 0)
    tok_s = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns else 0.0
    return ttft or 0.0, tok_s


class _HudProcess:
    """HUD del `hud_pro` como subproceso — vive sólo durante la condición
    que lo necesita, nunca de fondo entre rondas."""

    def __init__(self, mode: str) -> None:
        self._mode = mode
        self._proc: subprocess.Popen | None = None

    def __enter__(self) -> _HudProcess:
        env = dict(os.environ)
        env["JARVIS_HUD_GPU"] = "auto"
        env["BENCH_HUD_MODE"] = self._mode
        env["PYTHONPATH"] = REPO_ROOT
        script = _LAUNCH_HUD.format(repo=REPO_ROOT)
        self._proc = subprocess.Popen(
            [sys.executable, "-c", script], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        # espera a que la ventana esté lista de verdad (no un sleep fijo a ciegas)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if "HUD_READY" in line:
                break
            if self._proc.poll() is not None:
                raise RuntimeError(f"el HUD ({self._mode}) terminó antes de arrancar")
        time.sleep(0.3)  # deja que el primer paintGL real corra
        return self

    def __exit__(self, *exc) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc.wait(timeout=5)


def _run_condition(mode: str, prompt: str) -> tuple[float, float]:
    if mode == "closed":
        return _one_generate(prompt)
    with _HudProcess(mode):
        return _one_generate(prompt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = ap.parse_args()

    conditions = ["closed", "paused", "governor"]
    labels = {"closed": "cerrado", "paused": "pausado", "governor": "gobernador"}

    # calentamiento: carga el modelo en RAM antes de medir nada.
    print("calentando Ollama...", flush=True)
    _one_generate(args.prompt)

    results: dict[str, list[float]] = {c: [] for c in conditions}
    print(f"\n{'ronda':<6}" + "".join(f"{labels[c]:>14}" for c in conditions))
    for round_i in range(1, args.rounds + 1):
        row = []
        for cond in conditions:
            ttft, tok_s = _run_condition(cond, args.prompt)
            results[cond].append(tok_s)
            row.append(tok_s)
        print(f"{round_i:<6}" + "".join(f"{v:>11.2f} tok/s" for v in row), flush=True)

    print("\n--- resumen ---")
    baseline_per_round = results["closed"]
    for cond in conditions:
        vals = results[cond]
        mean = statistics.mean(vals)
        median = statistics.median(vals)
        print(f"{labels[cond]:<12} media={mean:6.2f} tok/s  mediana={median:6.2f} tok/s")

    print("\n--- perdida relativa por ronda (cancela la deriva: mismo ronda, mismo instante) ---")
    for cond in ("paused", "governor"):
        ratios = [
            results[cond][i] / baseline_per_round[i]
            for i in range(len(baseline_per_round))
            if baseline_per_round[i] > 0
        ]
        loss_pct = [(1.0 - r) * 100 for r in ratios]
        mean_loss = statistics.mean(loss_pct)
        print(
            f"{labels[cond]:<12} perdida media={mean_loss:5.1f}%  "
            f"(por ronda: {', '.join(f'{v:.1f}%' for v in loss_pct)})"
        )
        verdict = "OK (<=10%)" if mean_loss <= 10.0 else "supera el 10%"
        print(f"             -> {verdict}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
