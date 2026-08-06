"""
Corre la bateria de evaluacion del router y reporta el porcentaje de aciertos
por categoria. Uso:  python -m jarvis_local.eval.run_eval
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from jarvis_local.eval.cases import CONTEXTUALES, es_correcto, todos_los_casos
from jarvis_local.eval.harness import trace_message
from jarvis_local.jarvis import Jarvis


def main(salida: str = ""):
    jarvis = Jarvis()
    casos = todos_los_casos()
    total = len(casos) + len(CONTEXTUALES)
    print(f"Evaluando {total} casos de enrutamiento...\n")

    por_categoria = defaultdict(lambda: [0, 0])  # [aciertos, total]
    fallos = []
    registros = []
    t_inicio = time.time()

    for i, (entrada, esperado, categoria) in enumerate(casos, 1):
        tr = trace_message(jarvis, entrada)
        ok = es_correcto(esperado, tr.tools, tr.pidio_aclaracion)
        por_categoria[categoria][1] += 1
        por_categoria[categoria][0] += ok
        registros.append({
            "entrada": entrada, "esperado": esperado, "categoria": categoria,
            "obtenido": tr.tools, "capa": tr.capa, "ok": ok,
            "segundos": round(tr.segundos, 1),
        })
        if not ok:
            fallos.append((categoria, entrada, esperado, tr.tools or ["(ninguna)"],
                           tr.capa))
        marca = "OK " if ok else "FAIL"
        print(f"[{marca}] {i:2}/{len(casos)} ({tr.segundos:4.1f}s) [{tr.capa:11}] "
              f"{entrada[:44]:46} -> {','.join(tr.tools) or '(ninguna)'}")

    # Contextuales (con historial)
    for historial, entrada, esperado in CONTEXTUALES:
        tr = trace_message(jarvis, entrada, historial=historial)
        ok = es_correcto(esperado, tr.tools, tr.pidio_aclaracion)
        por_categoria["contextual"][1] += 1
        por_categoria["contextual"][0] += ok
        registros.append({
            "entrada": entrada, "esperado": esperado, "categoria": "contextual",
            "obtenido": tr.tools, "capa": tr.capa, "ok": ok,
            "segundos": round(tr.segundos, 1),
        })
        if not ok:
            fallos.append(("contextual", entrada, esperado,
                           tr.tools or ["(ninguna)"], tr.capa))
        print(f"[{'OK ' if ok else 'FAIL'}] ctx ({tr.segundos:4.1f}s) "
              f"[{tr.capa:11}] {entrada[:44]:46} -> "
              f"{','.join(tr.tools) or '(ninguna)'}")

    aciertos = sum(a for a, _ in por_categoria.values())
    print("\n" + "=" * 78)
    print(f"{'CATEGORIA':22} {'ACIERTOS':>10}  {'%':>6}")
    print("-" * 78)
    for cat in sorted(por_categoria):
        a, t = por_categoria[cat]
        print(f"{cat:22} {a:>4}/{t:<5} {100*a/t:>6.0f}%")
    print("-" * 78)
    print(f"{'TOTAL':22} {aciertos:>4}/{total:<5} {100*aciertos/total:>6.0f}%")
    print(f"\nTiempo: {time.time()-t_inicio:.0f}s")

    if fallos:
        print(f"\nFALLOS ({len(fallos)}):")
        for cat, entrada, esperado, obtenido, capa in fallos:
            print(f"  [{cat}] '{entrada}'")
            print(f"      esperado: {esperado}  |  obtenido: {','.join(obtenido)}"
                  f"  (capa: {capa})")

    if salida:
        Path(salida).write_text(json.dumps({
            "total": total, "aciertos": aciertos,
            "porcentaje": round(100 * aciertos / total, 1),
            "por_categoria": {k: {"aciertos": v[0], "total": v[1]}
                              for k, v in por_categoria.items()},
            "registros": registros,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nResultados guardados en {salida}")

    return 100 * aciertos / total


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
