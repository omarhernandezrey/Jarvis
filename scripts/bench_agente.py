"""Mide la latencia del agente (tool calling) en un set fijo de frases.

Requiere Ollama vivo. Vuelca una tabla: frase -> pasos -> llamadas al LLM ->
tiempo total. Los datos por turno tambien quedan en logs/decisions.jsonl
(campos llm_calls / llm_secs, ver TAREA C1).

    python -m scripts.bench_agente            # set completo
    python -m scripts.bench_agente --quick    # solo 2 frases (maquinas lentas)
"""
import sys
import time

FRASES = [
    "necesito saber si va a llover en Cartagena",
    "que tal anda mi maquina de recursos",
    "consigueme unas vacantes de programador en Medellin",
    "cuentame un chiste",
    "abre la calculadora",
    "cual es mi direccion ip",
]


def main() -> None:
    quick = "--quick" in sys.argv
    frases = FRASES[:2] if quick else FRASES

    from jarvis_local.agent.loop import run_agent
    from jarvis_local.ollama_client.client import OllamaClient

    client = OllamaClient()
    print(f"{'frase':<48} {'tools':<22} {'t(s)':>7}")
    print("-" * 82)
    total = 0.0
    for frase in frases:
        t0 = time.perf_counter()
        try:
            r = run_agent(client, frase, history=None)
            dt = time.perf_counter() - t0
            total += dt
            tools = ",".join(r.tools_used) or ("(aclara)" if r.needs_clarification
                                               else "(chat)")
            print(f"{frase[:47]:<48} {tools[:21]:<22} {dt:>7.1f}")
        except Exception as e:  # noqa: BLE001
            print(f"{frase[:47]:<48} ERROR: {e}")
    print("-" * 82)
    print(f"{'TOTAL':<48} {'':<22} {total:>7.1f}")
    print("\nDetalle por turno (llm_calls / llm_secs): logs/decisions.jsonl")


if __name__ == "__main__":
    main()
