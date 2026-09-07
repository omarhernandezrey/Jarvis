"""PLAN_EJECUCION FASE D · D3 — medición: ¿la salida estructurada baja los
rescates / reintentos de `agent/loop.py`?

Corre un set fijo de peticiones que llegan al AGENTE (el parser las deja
pasar) contra Ollama VIVO, con las dos vías —tool calling nativo y salida
estructurada (`format=<schema>`)— y compara:

  - rescates: veces que `_salvage_tool_calls` tuvo que reconstruir un tool
    call que el modelo escribió como texto.
  - reintentos por formato: veces que `_validar` rechazó la llamada
    (herramienta inventada / argumentos obligatorios ausentes).
  - llamadas al LLM por turno (1 = ideal; más = bucle de corrección).
  - acierto de enrutado (contra jarvis_local/eval/cases).
  - latencia por turno (p50 / p95).

Uso:  python -m jarvis_local.eval.measure_structured [--reps N]
Escribe docs/D3_MEDICION_SALIDA_ESTRUCTURADA.md
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time

from jarvis_local.agent import loop as agent_loop
from jarvis_local.config import BASE_DIR
from jarvis_local.eval.cases import es_correcto
from jarvis_local.eval.harness import _a_nombre_de_herramienta
from jarvis_local.intent.parser import parse_intent

# Peticiones que EL PARSER deja pasar al agente (si alguna la atrapa el
# parser, se salta: se filtra en runtime). Mezcla a propósito lo que más hace
# fallar el formato del 3B: coloquial, fuera de alcance (camino "responder"),
# negación y algún caso limpio de control.
PROMPTS: list[tuple[str, str | None]] = [
    # coloquiales con herramienta esperada (llegan al agente)
    ("estoy buscando pega de disenador", "buscar_empleo"),
    ("necesito la pagina de github abierta", "abrir_sitio_web"),
    ("necesito revisar mis correos", "abrir_aplicacion|abrir_sitio_web"),
    ("se me antoja escuchar algo de musica",
     "reproducir_musica_local|reproducir_en_youtube|reproducir_en_spotify"),
    ("ando aburrido, dime algo divertido", "contar_chiste"),
    ("me consigues unas vacantes de programador por Medellin", "buscar_empleo"),
    ("quien diablos fue Simon Bolivar", "wikipedia"),
    ("mi pc esta lentisimo, revisa", "estado_del_sistema"),
    # fuera de alcance: NO llamar herramienta, responder con honestidad
    # (aquí es donde el 3B más waffle-a y filtra JSON como texto)
    ("pideme una pizza", None),
    ("llama a mi mama por telefono", None),
    ("de que color es el cielo", None),
    ("imprime este documento en la impresora", None),
    ("recomiendame una pelicula", None),
    ("traduce hola al ingles", None),
    ("agenda una reunion manana", None),
    ("necesito buscar apartamento en arriendo", None),
    ("hazme un cafe", None),
    ("cual es la capital de francia", None),
]


class _Contadores:
    def __init__(self):
        self.rescates = 0
        self.reintentos = 0


def _instrumentar(cont: _Contadores):
    """Envuelve _salvage_tool_calls y _validar para contar sin cambiar lógica,
    y DESACTIVA la caché de decisiones (C6): es una optimización de latencia
    ortogonal a "tool calling vs estructurada" y, si se deja viva, la 2ª vía
    medida recibe cache hits de la 1ª y nunca llega al LLM."""
    from jarvis_local.agent import decision_cache

    salvage0 = agent_loop._salvage_tool_calls
    validar0 = agent_loop._validar
    cache_get0 = decision_cache.get
    cache_put0 = decision_cache.put

    def salvage(content, ofrecidas):
        r = salvage0(content, ofrecidas)
        if r:
            cont.rescates += 1
        return r

    def validar(name, args):
        ok, msg = validar0(name, args)
        if not ok:
            cont.reintentos += 1
        return ok, msg

    agent_loop._salvage_tool_calls = salvage
    agent_loop._validar = validar
    decision_cache.get = lambda *_a, **_k: None
    decision_cache.put = lambda *_a, **_k: None
    decision_cache.clear()

    def _restaurar():
        agent_loop._salvage_tool_calls = salvage0
        agent_loop._validar = validar0
        decision_cache.get = cache_get0
        decision_cache.put = cache_put0

    return _restaurar


def _una_rep(client, prompts, structured: bool) -> dict:
    """Una pasada por todas las peticiones. Devuelve los agregados de ESA rep,
    para poder comparar la varianza entre reps con la diferencia entre vías."""
    cont = _Contadores()
    restore = _instrumentar(cont)
    aciertos = con_llm = 0
    lat_llm: list[float] = []
    llm_calls: list[int] = []
    try:
        for entrada, esperado in prompts:
            t0 = time.perf_counter()
            r = agent_loop.run_agent(client, entrada, structured=structured)
            dt = time.perf_counter() - t0
            obtenidas = [_a_nombre_de_herramienta(t) for t in r.tools_used]
            if es_correcto(esperado, obtenidas):
                aciertos += 1
            n = _ultimas_llm_calls()
            llm_calls.append(n)
            if n >= 1:
                con_llm += 1
                lat_llm.append(dt)
    finally:
        restore()
    return {
        "casos": len(prompts), "aciertos": aciertos, "con_llm": con_llm,
        "rescates": cont.rescates, "reintentos": cont.reintentos,
        "llm_calls_media": (statistics.mean([n for n in llm_calls if n >= 1])
                            if any(llm_calls) else 0.0),
        "lat_p50": statistics.median(lat_llm) if lat_llm else 0.0,
        "lat_p95": (max(lat_llm) if lat_llm else 0.0),
    }


def _medir(client, prompts, structured: bool, reps: int) -> dict:
    rep_dicts = []
    for i in range(reps):
        print(f"    rep {i + 1}/{reps} ({'estructurada' if structured else 'tool calling'})…",
              flush=True)
        rep_dicts.append(_una_rep(client, prompts, structured))
    agg = {k: statistics.mean(d[k] for d in rep_dicts)
           for k in ("aciertos", "con_llm", "rescates", "reintentos",
                     "llm_calls_media", "lat_p50", "lat_p95")}
    agg["casos"] = rep_dicts[0]["casos"]
    agg["reps"] = rep_dicts
    # spread = max-min entre reps (0 con reps=1)
    for k in ("aciertos", "rescates", "reintentos"):
        agg[f"{k}_spread"] = max(d[k] for d in rep_dicts) - min(d[k] for d in rep_dicts)
    return agg


def _ultimas_llm_calls() -> int:
    import json
    p = BASE_DIR / "logs" / "decisions.jsonl"
    try:
        last = p.read_text(encoding="utf-8").strip().splitlines()[-1]
        return int(json.loads(last).get("llm_calls", 0) or 0)
    except (OSError, ValueError, IndexError):
        return 0


def _rep_vals(d: dict, k: str) -> str:
    """'a / b' con el valor de cada rep, para ver la varianza a ojo."""
    return " / ".join(f"{r[k]:g}" for r in d["reps"])


def _tabla(a: dict, b: dict) -> str:
    filas = [
        ("casos por rep", str(a["casos"]), str(b["casos"])),
        ("aciertos (media)", f"{a['aciertos']:.1f}/{a['casos']}", f"{b['aciertos']:.1f}/{b['casos']}"),
        ("aciertos por rep", _rep_vals(a, "aciertos"), _rep_vals(b, "aciertos")),
        ("rescates (media)", f"{a['rescates']:.1f}", f"{b['rescates']:.1f}"),
        ("rescates por rep", _rep_vals(a, "rescates"), _rep_vals(b, "rescates")),
        ("reintentos (media)", f"{a['reintentos']:.1f}", f"{b['reintentos']:.1f}"),
        ("reintentos por rep", _rep_vals(a, "reintentos"), _rep_vals(b, "reintentos")),
        ("turnos con LLM (media)", f"{a['con_llm']:.1f}", f"{b['con_llm']:.1f}"),
        ("llamadas LLM / turno (media)", f"{a['llm_calls_media']:.2f}", f"{b['llm_calls_media']:.2f}"),
        ("latencia p50 turno-con-LLM (s)", f"{a['lat_p50']:.0f}", f"{b['lat_p50']:.0f}"),
        ("latencia p95 turno-con-LLM (s)", f"{a['lat_p95']:.0f}", f"{b['lat_p95']:.0f}"),
    ]
    w = max(len(f[0]) for f in filas)
    out = [f"| {'métrica'.ljust(w)} | tool calling | estructurada |",
           f"| {'-' * w} | :---: | :---: |"]
    for k, x, y in filas:
        out.append(f"| {k.ljust(w)} | {x} | {y} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0,
                    help="usar solo las primeras N peticiones (0 = todas)")
    ap.add_argument("--timeout", type=int, default=120,
                    help="tope por llamada al LLM (s); una llamada colgada "
                         "cuenta como error, no como 10 min de espera")
    args = ap.parse_args(argv)

    from jarvis_local.ollama_client.client import OllamaClient
    client = OllamaClient()
    client.timeout = args.timeout
    if not client.is_running():
        print("Ollama no está corriendo.", file=sys.stderr)
        return 2

    prompts = [(e, x) for (e, x) in PROMPTS if parse_intent(e).kind == "chat"]
    saltados = [e for (e, _) in PROMPTS if parse_intent(e).kind != "chat"]
    if args.limit:
        prompts = prompts[:args.limit]

    print(f"[D3] {len(prompts)} peticiones × {args.reps} reps × 2 vías. "
          f"Saltadas por el parser: {len(saltados)}. Caché de decisiones DESACTIVADA.",
          flush=True)
    t0 = time.perf_counter()
    print("[D3] midiendo tool calling nativo…", flush=True)
    base = _medir(client, prompts, structured=False, reps=args.reps)
    print("[D3] midiendo salida estructurada…", flush=True)
    estr = _medir(client, prompts, structured=True, reps=args.reps)
    mins = (time.perf_counter() - t0) / 60

    tabla = _tabla(base, estr)
    veredicto = _veredicto(base, estr, args.reps)

    md = f"""# FASE D · D3 — Medición de la salida estructurada (JSON Schema)

`python -m jarvis_local.eval.measure_structured --reps {args.reps}` —
{args.reps} reps × {len(prompts)} peticiones que llegan al agente, Ollama vivo,
caché de decisiones (C6) desactivada para que ambas vías lleguen al LLM.
Modelo: `llama3.2:3b`. {mins:.0f} min de ejecución.

{tabla}

Peticiones (todas fuera del parser): coloquiales con herramienta esperada +
fuera de alcance (donde el 3B más waffle-a). Ninguna la atrapa el parser.

## Veredicto

{veredicto}
"""
    dest = BASE_DIR / "docs" / "D3_MEDICION_SALIDA_ESTRUCTURADA.md"
    dest.write_text(md, encoding="utf-8")
    print("\n" + tabla + "\n\n" + veredicto + f"\n\n-> {dest}", flush=True)
    return 0


def _veredicto(base: dict, estr: dict, reps: int) -> str:
    """El desenlace accionable (según D3): que BAJEN rescates Y reintentos SIN
    perder acierto. La latencia no cuenta (varía por causas ajenas). Y si la
    varianza entre reps es tan grande como la diferencia entre vías, la
    medición NO decide."""
    if reps < 2:
        return ("Con 1 rep no hay varianza que medir; la comparación no "
                "distingue señal de ruido. Repetir con --reps>=2.")

    d_resc = base["rescates"] - estr["rescates"]
    d_reint = base["reintentos"] - estr["reintentos"]
    d_acierto = estr["aciertos"] - base["aciertos"]           # medias
    ruido_acierto = max(base["aciertos_spread"], estr["aciertos_spread"])
    ruido_ruido = max(base["rescates_spread"] + base["reintentos_spread"],
                      estr["rescates_spread"] + estr["reintentos_spread"])

    lineas = [
        f"Varianza entre reps (max-min): aciertos ±{ruido_acierto:g} · "
        f"rescates+reintentos ±{ruido_ruido:g}.",
        f"Diferencia entre vías (media): aciertos {d_acierto:+.1f} · "
        f"rescates {d_resc:+.1f} · reintentos {d_reint:+.1f}.",
        "",
    ]

    baja_ruido = (d_resc + d_reint) > ruido_ruido and (d_resc >= 0 and d_reint >= 0)
    no_pierde_acierto = d_acierto >= -ruido_acierto
    señal_clara = abs(d_acierto) > ruido_acierto or (d_resc + d_reint) > ruido_ruido

    if not señal_clara:
        lineas.append(
            "La diferencia entre vías cabe dentro de la varianza entre reps: "
            "la medición NO decide. Se mantiene `agent.structured_output: false`; "
            "el código (flag + medidor) queda para repetir con un modelo mejor.")
    elif baja_ruido and no_pierde_acierto:
        lineas.append(
            f"La salida estructurada BAJA el ruido de formato ({d_resc:+.1f} "
            f"rescates, {d_reint:+.1f} reintentos) por encima de la varianza, "
            f"sin perder acierto ({d_acierto:+.1f}). Recomendación: activar "
            "`agent.structured_output: true`.")
    else:
        motivos = []
        if not baja_ruido:
            motivos.append("no baja rescates+reintentos por encima del ruido")
        if not no_pierde_acierto:
            motivos.append(f"pierde acierto ({d_acierto:+.1f}, ruido ±{ruido_acierto:g})")
        lineas.append(
            "La salida estructurada NO gana con claridad: " + "; ".join(motivos)
            + ". Se mantiene `agent.structured_output: false` y no se fuerza. "
            "El código queda documentado para revisar con un modelo mejor.")
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
