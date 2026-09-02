"""TAREA C7 — presupuestos de latencia por capa de la cascada.

La capa 1 (respuestas instantáneas) y la capa 2 (parser determinista) tienen
presupuestos DUROS: son puro Python, no dependen de la máquina. Si un cambio
las degrada, este test lo caza en CI antes del merge.

El agente (capa 3) depende del hardware (un 3B haciendo tool-calling: ~20 s con
GPU decente, 25-90 s en una CPU de 2 núcleos). Aquí sólo se comprueba que no se
CUELGA: presupuesto amplio, no un benchmark. El objetivo real (< 20 s) se
verifica en hardware con GPU con `scripts/bench_agente.py`.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

# --- Presupuestos (segundos) ---
L1_INSTANTANEA = 0.15
L2_PARSER = 0.35
E2E_FRASE_DE_PARSER = 3.0
AGENTE_UNA_ACCION_TOPE = 180.0   # guarda de "no se cuelga", no benchmark (asserted en el test)


def _mide(fn, *a, **kw):
    t0 = time.perf_counter()
    fn(*a, **kw)
    return time.perf_counter() - t0


# ── CAPA 1: respuestas instantáneas ─────────────────────────────────────────
@pytest.mark.parametrize("frase", ["hola", "que hora es", "que dia es hoy",
                                   "gracias", "buenas noches"])
def test_l1_instantanea_bajo_presupuesto(frase):
    from jarvis_local.fast_response import fast_respond

    # warm-up (compilar regex, importar) fuera de la medición
    fast_respond("hola")
    dt = _mide(fast_respond, frase)
    assert dt < L1_INSTANTANEA, f"L1 {frase!r} tardó {dt*1000:.0f} ms (tope {L1_INSTANTANEA*1000:.0f})"


# ── CAPA 2: parser determinista ────────────────────────────────────────────
@pytest.mark.parametrize("frase", [
    "abre whatsapp", "clima en Bogota", "pon bohemian rhapsody",
    "sube el volumen", "recuerdame llamar a mama en 10 minutos",
    "resuelve x + 10 = 25", "como anda la maquina", "de que color es el cielo",
])
def test_l2_parser_bajo_presupuesto(frase):
    from jarvis_local.intent.parser import parse_intent

    parse_intent("abre whatsapp")  # warm-up
    dt = _mide(parse_intent, frase)
    assert dt < L2_PARSER, f"L2 {frase!r} tardó {dt*1000:.0f} ms (tope {L2_PARSER*1000:.0f})"


# ── E2E: una frase que resuelve el PARSER no debe pasar por el LLM ─────────
_HAS_OLLAMA = None


def _ollama_vivo() -> bool:
    global _HAS_OLLAMA
    if _HAS_OLLAMA is None:
        try:
            from jarvis_local.storage.semantic import embeddings_available
            _HAS_OLLAMA = embeddings_available()
        except Exception:
            _HAS_OLLAMA = False
    return _HAS_OLLAMA


@pytest.mark.skipif(not _ollama_vivo(), reason="Ollama/embeddings no disponibles")
@pytest.mark.parametrize("frase,ruta_ok", [
    ("hola", ("exact", "fast")),
    ("clima en Cali", ("tool",)),
    ("como anda la maquina", ("tool",)),
])
def test_e2e_frase_de_parser_no_toca_el_llm(frase, ruta_ok):
    from unittest.mock import patch

    from jarvis_local.jarvis import Jarvis

    j = Jarvis()
    with patch("jarvis_local.tools.weather.get_weather") as _w, \
         patch("jarvis_local.tools.system_info.system_status") as _s:
        from jarvis_local.safety.policy import ActionPlan, ActionStatus
        for m in (_w, _s):
            ap = ActionPlan(action="x", params={})
            ap.status = ActionStatus.EXECUTED
            ap.result = "ok"
            m.return_value = ap
        t0 = time.perf_counter()
        j.chat(frase)
        dt = time.perf_counter() - t0

    assert j.last_reply_kind in ruta_ok, f"{frase!r} fue por '{j.last_reply_kind}', no {ruta_ok}"
    assert dt < E2E_FRASE_DE_PARSER, f"e2e {frase!r} tardó {dt:.1f} s (tope {E2E_FRASE_DE_PARSER})"


# ── AGENTE: sólo comprobamos que no se cuelga ─────────────────────────────
@pytest.mark.skipif(not _ollama_vivo(), reason="Ollama no disponible")
def test_agente_una_accion_no_se_cuelga():
    from jarvis_local.agent import decision_cache
    from jarvis_local.agent.loop import run_agent
    from jarvis_local.ollama_client.client import OllamaClient

    decision_cache.clear()
    t0 = time.perf_counter()
    r = run_agent(OllamaClient(), "que tal anda mi maquina de recursos", history=None)
    dt = time.perf_counter() - t0

    assert r.tools_used, "el agente no eligió ninguna herramienta"
    assert dt < AGENTE_UNA_ACCION_TOPE, (
        f"el agente tardó {dt:.0f} s (> {AGENTE_UNA_ACCION_TOPE:.0f}); "
        "objetivo real < 20 s en hardware con GPU")
