# FASE D · D3 — Medición de la salida estructurada (JSON Schema)

`python -m jarvis_local.eval.measure_structured --reps 2 --limit 10 --timeout 120`

2 reps × 10 peticiones que llegan al agente (coloquiales con herramienta
esperada + fuera de alcance — donde el 3B más waffle-a; ninguna la atrapa el
parser). Ollama vivo, modelo `llama3.2:3b`. Caché de decisiones (C6)
desactivada para que **ambas vías lleguen al LLM en todos los casos** — si no,
la 2ª vía medida recibe cache hits de la 1ª y nunca se ejercita. 17 min.

> Banco pequeño y ejecutado bajo presión de memoria (ver
> `docs/OPERACION_MEMORIA.md`). Sirve para ver **si hay señal**, no para un
> número fino.

## Resultados

| métrica | tool calling | estructurada | lectura |
| --- | :---: | :---: | --- |
| aciertos de enrutado (media / rep) | 7,0 — `7 / 7` | 5,5 — `6 / 5` | estructurada **pierde ~1,5**, y su varianza (±1) no lo tapa |
| rescates `_salvage_tool_calls` (rep) | `0 / 0` | `0 / 0` | **cero en ambas**: con este modelo + lista acotada, el canal nativo nunca filtró un tool call como texto |
| reintentos por formato `_validar` (rep) | `2 / 2` | `1 / 4` | varianza ±3 >> diferencia entre vías (−0,5): **sin señal** |
| llamadas al LLM / turno | 1,00 | 1,00 | ninguna vía entra en bucle de corrección |
| latencia p50 turno-con-LLM (s) | 33 | 11 | estructurada más rápida (JSON corto vs prosa), pero *no cuenta* (D3: la latencia varía por causas ajenas) y el instrumento de latencia aquí es poco fiable |

Varianza entre reps (max−min): aciertos **±1**, rescates+reintentos **±3**.
Diferencia entre vías (media): aciertos **−1,5**, rescates **0**, reintentos **−0,5**.

## Decisión

El desenlace accionable de D3 es: **que bajen rescates y reintentos sin perder
acierto**. No se cumple:

- **Rescates**: ya eran 0 con tool calling en estas 20 corridas. No hay
  problema de formato que resolver con `llama3.2:3b` — el canal nativo de
  `tool_calls` funciona. La maquinaria de rescate (`_salvage_tool_calls`)
  queda como seguro barato para modelos peores, no como algo que estructurar
  arregle.
- **Reintentos**: la diferencia (−0,5) cabe de sobra dentro de la varianza
  entre reps (±3). La medición **no decide** aquí.
- **Acierto**: estructurada **pierde ~1,5 puntos** de 10, por encima de su
  ruido (±1). El `enum` fija el nombre de la herramienta pero los argumentos
  siguen libres, y forzar el JSON parece hacer que el 3B elija peor entre
  "usar_herramienta" y "responder".

**Se mantiene `agent.structured_output: false`.** No se activa por la mejora de
latencia: D3 lo excluye explícitamente y, además, el número de latencia de
este banco no es fiable.

El código queda entero y documentado —`client.chat_structured`,
`loop._decidir_estructurado`, el flag, `STRUCTURED_SYSTEM_SUFFIX` y este
medidor— para repetir la medición con un modelo de router mejor (un 7B, o
`qwen2.5` que ya está pulled) sin tener que reconstruir nada.

## Cómo repetir

```
ollama stop bge-m3                       # baja la presión de RAM (ver OPERACION_MEMORIA.md)
python -m jarvis_local.eval.measure_structured --reps 3 --timeout 120
# o forzar un modelo: JARVIS_AGENT_MODEL=qwen2.5:3b python -m jarvis_local.eval.measure_structured ...
```
