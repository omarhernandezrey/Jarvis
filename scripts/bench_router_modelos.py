"""Compara modelos de routing (elección de herramienta) en la misma batería.

Mide SOLO el paso de routing: una llamada a `chat_with_tools` por frase. No
ejecuta la herramienta (no abre apps, no toca la red). Para cada modelo:
frase -> herramienta elegida -> ¿correcta? -> ¿JSON válido? -> tiempo.

    python -m scripts.bench_router_modelos
    python -m scripts.bench_router_modelos --models llama3.2:3b,qwen2.5:3b

Descarga el modelo de RAM (`ollama stop`) al terminar con cada uno para no
acumular 3 modelos residentes en una máquina de 16 GB.
"""
import json
import subprocess
import sys
import time

# frase -> herramienta correcta esperada (None = debe NO llamar herramienta)
CASOS: list[tuple[str, str | None]] = [
    ("abre whatsapp", "abrir_aplicacion"),
    ("abre visual studio code", "abrir_aplicacion"),
    ("que tiempo hace en Bogota", "clima"),
    ("necesito saber si va a llover en Cartagena", "clima"),
    ("pon bohemian rhapsody", "reproducir_en_spotify"),
    ("crea una nota comprar leche", "tomar_nota"),
    ("que tal anda mi maquina", "estado_del_sistema"),
    ("cual es mi direccion ip", "mi_direccion_ip"),
    ("cuales son las noticias de hoy", "noticias"),
    ("consigueme vacantes de programador en Medellin", "buscar_empleo"),
    ("cuentame un chiste", "contar_chiste"),
    ("de que color es el cielo", None),
]

# hermes3:3b se evaluó (1/12, descartado — ver docs/AUDITORIA_2026-09.md §7).
# Para reevaluarlo: --models llama3.2:3b,hermes3:3b
DEFAULT_MODELS = ["llama3.2:3b", "qwen2.5:3b"]


def _tool_call(msg: dict) -> tuple[str | None, dict, bool]:
    """(nombre, args, json_ok). json_ok=False si los args vinieron rotos."""
    calls = msg.get("tool_calls") or []
    if not calls:
        return None, {}, True
    fn = calls[0].get("function", {})
    name = fn.get("name")
    raw = fn.get("arguments", {})
    if isinstance(raw, str):
        try:
            return name, json.loads(raw), True
        except json.JSONDecodeError:
            return name, {}, False
    return name, (raw if isinstance(raw, dict) else {}), isinstance(raw, dict)


def run_model(model: str) -> dict:
    from jarvis_local.agent.prompts import AGENT_SYSTEM_PROMPT
    from jarvis_local.agent.retriever import select_tools
    from jarvis_local.ollama_client.client import OllamaClient

    client = OllamaClient()
    aciertos = 0
    json_ok = 0
    total_t = 0.0
    filas = []
    for frase, esperada in CASOS:
        tools = select_tools(frase)
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": frase},
        ]
        t0 = time.perf_counter()
        try:
            msg = client.chat_with_tools(messages, tools, model=model)
        except Exception as e:  # noqa: BLE001
            filas.append((frase, f"ERROR:{e}", False, 0.0))
            continue
        dt = time.perf_counter() - t0
        total_t += dt
        name, _args, ok = _tool_call(msg)
        correcto = (name == esperada)
        aciertos += int(correcto)
        json_ok += int(ok)
        marca = "OK " if correcto else "XX "
        filas.append((frase, f"{marca}{name or '(texto)'}", ok, dt))

    n = len(CASOS)
    print(f"\n=== {model} ===")
    print(f"{'frase':<46} {'-> elegida':<26} {'json':>5} {'t(s)':>7}")
    print("-" * 88)
    for frase, elegida, ok, dt in filas:
        print(f"{frase[:45]:<46} {elegida[:25]:<26} {'ok' if ok else 'ROTO':>5} {dt:>7.1f}")
    print("-" * 88)
    print(f"acierto: {aciertos}/{n}  json_ok: {json_ok}/{n}  "
          f"t_total: {total_t:.1f}s  media: {total_t / n:.1f}s")

    # liberar RAM
    subprocess.run(["ollama", "stop", model], capture_output=True, check=False)
    return {"model": model, "aciertos": aciertos, "n": n,
            "json_ok": json_ok, "t_total": round(total_t, 1),
            "media": round(total_t / n, 1)}


def main() -> None:
    models = DEFAULT_MODELS
    if "--models" in sys.argv:
        models = sys.argv[sys.argv.index("--models") + 1].split(",")
    resumen = [run_model(m) for m in models]
    print("\n\n=== RESUMEN ===")
    print(f"{'modelo':<16} {'acierto':>9} {'json_ok':>9} {'t_total':>9} {'media':>7}")
    for r in resumen:
        print(f"{r['model']:<16} {r['aciertos']}/{r['n']:>7} "
              f"{r['json_ok']}/{r['n']:>7} {r['t_total']:>8}s {r['media']:>6}s")


if __name__ == "__main__":
    main()
