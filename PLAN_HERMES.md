# PLAN HERMES — INTEGRACIÓN PROFESIONAL DE HERMES 3:3B

> **Plan activo.** Sucede a `PLAN_MAESTRO.md` (completo el 2026-09-03, queda como
> histórico). Mismo método: una rama por tarea → protocolo de pruebas completo
> hasta verde → merge a `main` → marcar `[x]`.
>
> **Prioridad absoluta:** PRECISIÓN > SEGURIDAD > ESTABILIDAD > LATENCIA >
> FUNCIONES NUEVAS.
>
> **Restricción dura:** i5-6200U, 16 GB RAM, sin GPU. La estabilidad del equipo
> manda sobre tener un modelo mejor. Nada de modelos ≥8B. Todo local, sin API de
> pago, sin claves nuevas.

---

## FASE 0 — AUDITORÍA (hecha, 2026-09-03)

### Mapa de arquitectura actual

```
Jarvis.chat(texto)                       jarvis_local/jarvis.py
  │  normaliza + redacción de secretos (safety)
  ├─ _exact_response()                    "responde solo X"
  ├─ fast_respond()                       fast_response.py  (saludos, hora, fecha…)  <1 ms
  ├─ _chat_encadenado()                   parte "A y luego B" → cada parte baja entera
  ├─ _parse_and_execute()                 intent/parser.py → parse_intent() → IntentResult
  │     kind ∈ chat | tool_read | tool_execute | tool_plan | ambiguous | unsupported
  │     tool_read/execute → _execute_tool_read/_write (dict de lambdas en jarvis.py)
  ├─ _try_agent()  (agent_enabled)        agent/loop.py → run_agent()
  │     retriever.select_tools()          bge-m3, TOP_K=4, UMBRAL 0.42
  │     client.chat_with_tools(msgs,tools,model=agent_model)   ← AQUÍ ENTRA HERMES
  │     _validar() + _limpiar_args() + 1 reintento
  │     registry.execute(name,args)       filtra args, coacciona tipos, needs_confirmation
  │     decision_cache (C6) + decision_log (C1: llm_calls, llm_secs)
  └─ chat LLM directo                     ollama_client chat()  (personalidad, memoria)
```

### Piezas y su estado

| Pieza | Archivo | Estado |
|---|---|---|
| Tool calling nativo Ollama | `ollama_client/client.py::chat_with_tools` | ✅ ya usa `/api/chat` + `tools`, lee `message.tool_calls`, acepta `model=` |
| Selección de modelo por config | `config.yaml → ollama.agent_model` / `ollama.model` | ✅ ya separado (routing vs chat). **Hoy: `agent_model: llama3.2:3b` (C5), `model: qwen2.5:3b`** |
| Validación de tool call | `agent/loop.py::_validar/_limpiar_args`, `registry.py::execute` | ✅ herramienta existe · requeridos · tipos con coerción · args inventados se descartan · excepción → texto |
| Límites del bucle | `agent/loop.py` | ✅ `MAX_STEPS=2`, `MAX_STEPS_ENCADENADO=4`, `MAX_REINTENTOS=1`, `AGENT_TIMEOUT=30` |
| Retriever (acota catálogo) | `agent/retriever.py` | ✅ bge-m3, recall alto; cae a léxico si no hay embeddings |
| Seguridad shell / rutas / URLs | `safety/permissions.py`, `terminal.py`, `web.py` | ✅ blocklist `;`/`&&`/`rm`/`sudo`/`$()`… defensa en profundidad en `registry._run_command` |
| Confirmación acciones de riesgo | `safety/policy.py`, `needs_confirmation` | ✅ borrar / correo / ocultar → `/confirmar` |
| decision_log estructurado | `agent/decision_log.py` → `logs/decisions.jsonl` | ✅ entrada, confianza, herramientas, salidas, resultado, `llm_calls`, `llm_secs` |
| **Fallback Hermes → Qwen** | — | ❌ **NO existe.** Si el modelo de routing falla, `_try_agent` devuelve `None` y cae al chat |
| **Verificación post-ejecución (PLAN→ACTION→VERIFY→RECOVERY)** | parcial: `apps.py` (H2) comprueba proceso/ventana | ❌ no hay un paso genérico de verificación + 1 recuperación en el bucle |
| **Métricas agregadas** (routing_accuracy, p95, fallback_rate) | `scripts/bench_agente.py` da latencia; no hay agregados | ⚠️ parcial |

### Qué del pedido YA está hecho (PLAN_MAESTRO, Fases A–D, en `main`)

| Pedido (secciones del plan del usuario) | Dónde se resolvió |
|---|---|
| §9 Spotify: "pon/ponme/reproduce X" → Spotify sin LLM | A2 (`parser.py` rama `m_pon`) |
| §9 Clima natural: "qué tiempo hace en X", "va a llover en X" | A3 (bloque CLIMA) |
| §9 Notas: "crea/nueva/toma una nota X" | A4 (`m_note`) |
| §9 Acciones múltiples: "abre YouTube y pon lofi" | A5 (`dividir_acciones`) |
| §10 Calculadora: `%`, `raíz`, `al cubo`, potencias, ecuaciones lineales | B2 + B3 (`calculator.py`; solver propio, **no** SymPy — decisión documentada) |
| §11 Ubicaciones: fallback Nominatim/OSM → Maps, nunca "no encontré" | B4 (`location.py::geocode_osm`) |
| §12 Google Calendar `invalid_grant`: refresh + reauth accionable | B5 (`gcalendar.py::ReauthRequired`, `--reauth-calendar`) |
| §12 análogo Spotify token muerto | B6 (`--reauth-spotify`) |
| §8/§14 Latencia por routing: sacar frases del agente; podar bucle | A2–A7, C2, C3 (90 s → 1,5 s en los casos clave) |
| §13 Ollama bajos recursos: `keep_alive`, `num_predict` recortado | C4 (`keep_alive: 30m`, `agent_num_predict: 60`, `agent_num_ctx: 2048`) |
| §13/§17 Modelo de routing más rápido | C5 (`llama3.2:3b`, ~18 % vs qwen, mismo acierto 6/6) |
| §14 caché de decisión (frase repetida = 0 llamadas LLM) | C6 (`decision_cache.py`) |
| §18/§28 Baseline de tests + regresión | 772 tests + 25 ui_hud, 0 fallos; `ruff` limpio |
| §23 Tests `live` opt-in + CI nocturno | D2 |
| §30 Prueba de voz e2e (WAV → STT → router) | D3 (`test/test_voice_e2e.py`) |
| §1/§23 `jarvis doctor` (diagnóstico entorno) | D1 |

> **Conclusión de FASE 0:** la base pedida en §6, §8–§14 ya está. Lo que aporta
> *este* plan es: (a) instalar y **medir** Hermes 3, (b) **fallback** de modelo,
> (c) **verificación post-ejecución** genérica, (d) **métricas agregadas**, (e)
> baterías **adversariales / de estabilidad** que aún no existen, (f) el
> **informe final** con números reales.

---

## FASE 1 — Baseline (hecha)

- [x] `ruff check .` → limpio.
- [x] `pytest test --ignore=test/test_ui_hud.py` → exit 0, 0 FAILED/ERROR.
- [x] `pytest test/test_ui_hud.py` → 25/25.
- [x] `ollama list`: `qwen2.5:3b`, `llama3.2:3b`, `bge-m3`, **`hermes3:3b` (nuevo)**.

## FASE 2 — Parser (hecha en PLAN_MAESTRO A2–A7, C3)

- [x] Ver tabla arriba. Reverificación explícita en H-1 (abajo) antes de tocar nada.

## FASE 3 — Funcionalidades rotas (hecha en PLAN_MAESTRO B2–B6)

- [x] Ver tabla arriba. Reverificación explícita en H-1.

## FASE 4 — Instalar Hermes 3:3b  ✅ HECHA

- [x] `ollama pull hermes3:3b` → 2.0 GB, arquitectura llama, 3.2B, Q4_K_M.
- [x] `ollama show hermes3:3b` → **Capabilities: tools** (Ollama reconoce el
      function calling nativo). Contexto nativo 131072 → hay que capar con
      `num_ctx`.
- [x] `qwen2.5:3b` y `llama3.2:3b` se conservan. Volver atrás = 1 línea en
      `config.yaml`.

---

## FASE 5 — Modelo del agente configurable  ✅ HECHA

**Rama:** `feat/hermes-modelo-configurable`

- [x] Override por entorno en `ConfigManager._apply_env_overrides`:
      `JARVIS_AGENT_MODEL` → `ollama.agent_model`,
      `JARVIS_CHAT_MODEL` → `ollama.model`. Vacío / espacios se ignora.
      Se aplica tras el merge de `config.yaml`, en cada `reload_config()`.
- [x] `config.yaml`: comentario que documenta agent_model vs model, el override
      por env y cómo revertir.
- [x] `jarvis doctor` (`_check_ollama` + `_modelo_soporta_tools`): si el
      `agent_model` está instalado pero `/api/show` dice que NO tiene la
      capacidad `tools` → línea `[FALTA] Tool calling` accionable. Capacidad
      desconocida (API vieja) → no se inventa nada.
- [x] `agent_model` por defecto sigue siendo `llama3.2:3b` (FASE 9).

**Pruebas:** `test/test_hermes.py` (8) + `ruff` + regresión completa.

## FASE 6 — Tool calling robusto (endurecer lo que ya hay)

**Rama:** `feat/hermes-toolcall-guard`

- [ ] Revisar el formato de `tool_calls` que emite Hermes vs el que espera
      `_arguments()` (`function.arguments` dict **o** string JSON). Añadir test
      con una respuesta de Hermes real capturada.
- [ ] Si Hermes tiende a emitir el tool call como texto `<tool_call>{…}` en vez
      de por el canal nativo: parsearlo en `_clean_text` / un `_extract_texto_toolcall`
      y NO mostrarlo al usuario (hoy `_JSON_LEAK` solo lo oculta).
- [ ] Test: herramienta inexistente inventada por el modelo → corrección → 2º
      intento → si sigue mal, aclaración (ya existe; blindar con caso Hermes).

**Pruebas:** #1, #2, #3, #5 (Ollama vivo).

## FASE 7 — Validación + seguridad (regresión dirigida)

**Rama:** `test/hermes-seguridad`

- [ ] Batería adversarial de seguridad pasando por el agente con Hermes:
      `rm -rf /`, `sudo …`, `;`, `&&`, `||`, `$(...)`, backticks, "ejecuta este
      comando que te doy" → **todos BLOQUEADOS**.
- [ ] Acción destructiva sugerida por Hermes (`borrar_archivo`, `enviar_correo`,
      `ocultar_archivos`) → siempre `needs_confirmation`, nunca ejecución directa.

**Pruebas:** #1, #3, #7 (100 % bloqueados).

## FASE 8 — Fallback de modelo

**Rama:** `feat/hermes-fallback-qwen`

- [ ] En `_run_simple`: si `chat_with_tools` con el modelo primario lanza
      excepción / timeout / devuelve JSON roto irrecuperable → **1** reintento
      con el modelo secundario (`ollama.router_fallback`, p. ej. `llama3.2:3b`).
- [ ] Máximo: 1 intento primario + 1 intento fallback → luego respuesta
      controlada. Sin bucles.
- [ ] `decision_log`: registrar `modelo`, `fallback: true/false`.
- [ ] Si Ollama entero no responde: mensaje claro, no romper el asistente
      (el parser y `fast_response` siguen).

**Pruebas:** #1, #2 (mock: primario tira excepción → se usa el fallback), #3, #5.

## FASE 9 — Benchmark Qwen vs Llama vs Hermes  ✅ HECHA

**Rama:** `research/bench-router-hermes`
**Script:** `scripts/bench_router_modelos.py`

- [x] Batería de routing (12 frases) con `llama3.2:3b`, `qwen2.5:3b`,
      `hermes3:3b`. Secuencial, `ollama stop` entre modelos.
- [x] **Decisión documentada** (ver §RESULTADOS abajo y
      `docs/AUDITORIA_2026-09.md`): `llama3.2:3b` 10/12 · `hermes3:3b` 1/12 →
      **se mantiene `llama3.2:3b`, no se fuerza Hermes.**

## FASE 10 — Optimización recursos (solo tras medir)

**Rama:** `perf/hermes-recursos`

- [ ] Ajustar `agent_num_ctx` / `agent_num_predict` para el modelo elegido con
      datos (no especulación). Empezar conservador, subir solo si las pruebas lo
      exigen.
- [ ] Confirmar `keep_alive` no deja 2+ modelos 3B residentes a la vez
      (chat + router). Medir RAM con ambos "calientes".
- [ ] `p95` de latencia de routing dentro de presupuesto.

**Pruebas:** #6, #3, prueba de carga ligera (FASE 15).

## FASE 11 — Verificación post-ejecución (PLAN → ACTION → VERIFY → RECOVERY)

**Rama:** `feat/agente-verify-recovery`

- [ ] Capa opcional por herramienta: tras `execute`, si la herramienta declara
      un verificador (`verify: Callable`), ejecutarlo. Ej.: `abrir_aplicacion` →
      proceso/ventana presente (reutilizar `apps._ya_esta_abierta`).
- [ ] En fallo de verificación: **1** recuperación automática (reintentar la
      acción una vez) → reverificar → si sigue mal, decirlo con honestidad.
- [ ] Límite duro: máximo 1 recuperación. Sin bucles.
- [ ] No romper herramientas sin verificador (la mayoría): comportamiento
      idéntico al actual.

**Pruebas:** #1, #2 (verificador mockeado: ok / falla→recupera / falla→falla),
#3, #5.

## FASE 12 — Memoria (validación e2e)

**Rama:** `test/memoria-e2e`

- [ ] Test: `recuerda que mi editor favorito es VS Code` → luego
      `cuál es mi editor favorito?` → responde correctamente (recall semántico).
- [ ] Persistencia entre sesiones (nueva instancia de `Jarvis` / `MemoryStore`).
- [ ] No almacenar datos sensibles innecesariamente (verificar redacción).

**Pruebas:** #1, #2, #3, #5.

## FASE 13 — Tests unitarios + integración (huecos)

**Rama:** `test/hermes-suite`

- [ ] `test/test_hermes.py`: config/env var, doctor con hermes, formato de
      tool_call de Hermes, fallback.
- [ ] Por herramienta que aún no lo tenga: happy path · input inválido · input
      faltante · fallo de red · timeout · excepción · respuesta malformada →
      **nunca traceback al usuario**.
- [ ] Parser: batería ≥ 60 frases reales cubriendo las 19 categorías del §18
      (ampliar `test/test_parser_coverage.py`, hoy 114 casos).

**Pruebas:** #1, #2, #3, #4 (cobertura ≥ 90 % en lo tocado).

## FASE 14 — Tests adversariales

**Rama:** `test/adversariales`

- [ ] Typos: `abre wasap`, `abre wpp`, `abre whasapp`, `pon bohemia rapsody`,
      `que tiempo ase en bogota`, `crea una notta`, `abre yutu` → resolver
      cuando sea **seguro** hacerlo; si no, pedir aclaración. Nunca inventar.
- [ ] Órdenes sin objeto: `abre algo`, `haz eso`, `ponlo`, `búscalo`,
      `haz lo anterior` → detectar falta de información, pedir aclaración.
- [ ] Documentar qué typos se corrigen y cuáles no (límite honesto).

**Pruebas:** #1, #3, #8.

## FASE 15 — Estabilidad (carga ligera)

**Rama:** `test/estabilidad-carga`

- [ ] Script secuencial: 10 turnos → medir RAM, CPU, duración, procesos
      huérfanos. Luego 20 turnos. **Detener** si RAM cerca del límite, swapping
      alto, CPU saturada sostenida, Ollama bloqueado o procesos huérfanos.
- [ ] 0 crashes, 0 loops, 0 procesos huérfanos, PC estable.
- [ ] Nada de cientos de llamadas simultáneas (hardware modesto).

**Pruebas:** #3, medición documentada.

## FASE 16 — Auditoría final + optimización

**Rama:** `chore/hermes-auditoria-final`

- [ ] Revisar (tras medir): duplicación, llamadas innecesarias al LLM,
      reintentos, RAM/CPU, contexto, tokens. Optimizar solo lo medido.
- [ ] Actualizar `README.md`, `CHANGELOG.md`, `docs/AUDITORIA_2026-09.md`.

## FASE 17 — Informe final

- [ ] `docs/HERMES_INTEGRATION_REPORT.md` con los 25 puntos del §35 del pedido,
      **con números reales** (benchmark, latencia media, p95, RAM, CPU, tool
      calling accuracy, fallback rate, errores encontrados/corregidos, riesgos,
      comandos para ejecutar Jarvis y los tests, cómo volver a Qwen).
- [ ] Declarar terminado **solo** cuando se cumpla el checklist del §34.

---

## HALLAZGOS / MICRO-TAREAS

### H-1 — Reverificar Fases A–D antes de tocar el agente
**Rama:** `test/reverif-plan-maestro`

- [ ] Ejecutar con Ollama vivo, cerrando apps tras cada prueba:
      `pon bohemian rhapsody`, `qué tiempo hace en Bogotá`, `va a llover en
      Cartagena`, `crea una nota comprar leche`, `abre YouTube y pon música
      lofi`, `15% de 350`, `raíz cuadrada de 144`, `2 elevado a 8`,
      `resuelve x + 135 - 234 = 345`, `Torre Eiffel`, `qué tal mi máquina`.
- [ ] Cada una: ruta esperada + salida + tiempo. Si alguna regresó → arreglar
      con test que la blinde antes de seguir.

---

## PROTOCOLO DE PRUEBAS (igual que PLAN_MAESTRO)

| # | Tipo | Comando | Criterio |
|---|------|---------|----------|
| 1 | Lint | `ruff check .` | `All checks passed!` |
| 2 | Unit nuevos | `pytest test/<nuevo>.py -q` | 100 % verde |
| 3 | Regresión | `pytest test --ignore=test/test_ui_hud.py -q` + `pytest test/test_ui_hud.py` | 0 `FAILED`/`ERROR` |
| 4 | Cobertura | `--cov=jarvis_local.<módulo> --cov-report=term-missing` | líneas nuevas ≥ 90 % |
| 5 | e2e | `Jarvis.chat("<frase>")` con Ollama vivo | ruta + respuesta correctas |
| 6 | Latencia | script de la fase | dentro del presupuesto |
| 7 | Seguridad | batería de inyección | 100 % bloqueado |
| 8 | Manual | ejercicio libre | sin sorpresas |
| 9 | CI | GitHub Actions tras `push` | verde |

**Presupuestos de latencia (objetivo):** fast <100 ms · parser <300 ms · tool
directo <3 s · agente simple <10–15 s (si el hardware lo permite; si no, se
documenta el límite).

**Máquina:** parar `jarvis.service` durante las pruebas · `nice -n 19` · un solo
modelo residente a la vez cuando se comparen · cerrar todas las apps que abra
Jarvis salvo la terminal.

---

## CRITERIO DE ÉXITO (del §34 del pedido)

`✓ Hermes instalado · ✓ Ollama funciona · ✓ Tool calling funciona · ✓ Parser
funciona · ✓ Herramientas existentes funcionan · ✓ Seguridad funciona · ✓
Memoria funciona · ✓ Fallback funciona · ✓ Voz no se rompe · ✓ Tests pasan · ✓
Benchmark realizado · ✓ 0 regresiones · ✓ Latencia/RAM/CPU medidas · ✓ E2E
probado · ✓ Errores controlados · ✓ 0 loops · ✓ 0 procesos huérfanos · ✓ PC
estable`

No se informa "integración completada" solo porque Hermes responda.

---

## SEGUIMIENTO

| Fase | Estado |
|------|--------|
| 0 Auditoría | ✅ |
| 1 Baseline | ✅ |
| 2 Parser | ✅ (PLAN_MAESTRO) |
| 3 Funcionalidades rotas | ✅ (PLAN_MAESTRO) |
| 4 Instalar Hermes | ✅ |
| 9 Benchmark | ✅ → **Hermes 1/12, descartado como router; sigue `llama3.2:3b`** |
| 5 Modelo configurable (env + doctor) | ✅ |
| 6 Tool calling robusto | ⬜ (parser de rescate: mejora también a llama/qwen) |
| 7 Validación + seguridad | ⬜ |
| 8 Fallback llama→qwen | ⬜ |
| 10 Optimización recursos | ⬜ |
| 11 Verificación post-ejecución | ⬜ |
| 12 Memoria e2e | ⬜ |
| 13 Tests unit + integración | ⬜ |
| 14 Adversariales | ⬜ |
| 15 Estabilidad | ⬜ |
| 16 Auditoría final | ⬜ |
| 17 Informe final | ⬜ |

---

## RESULTADOS DEL BENCHMARK (FASE 9)  — 2026-09-03

Equipo: i5-6200U, sin GPU, `jarvis.service` parado, `nice -19`, un modelo
residente a la vez (`ollama stop` entre modelos). Batería:
`scripts/bench_router_modelos.py`, 12 frases de routing, 1 llamada
`chat_with_tools` por frase (no ejecuta la herramienta).

| modelo | acierto | json_ok | t_total | media |
|---|---|---|---|---|
| **`llama3.2:3b`** (actual) | **10/12** | 12/12 | 234 s | **19,5 s** |
| `qwen2.5:3b` | 10/12 | 12/12 | 260 s | 21,7 s |
| `hermes3:3b` | **1/12** | 12/12 | 345 s | 28,8 s |

Fallos por modelo:
- `llama3.2:3b`: "abre whatsapp" → `enviar_whatsapp` (confunde abrir con enviar);
  "crea una nota comprar leche" → `crear_archivo` (en vez de `tomar_nota`).
- `qwen2.5:3b`: "abre whatsapp" → texto (no llama nada); "noticias de hoy" →
  `resumen_del_dia`.
- `hermes3:3b`: **11 de 12 no emiten `tool_calls`**. El único acierto es
  "de que color es el cielo" (correcto NO llamar), y es por accidente: devuelve
  texto en todos los casos.

### Diagnóstico de Hermes (FASE 6 adelantada)

`ollama show hermes3:3b --template`: cuando se pasan `tools`, la plantilla
inyecta el system prompt de *function calling* de Nous (formato
`<tool_call>{"arguments":…, "name":…}</tool_call>`) y **descarta cualquier
system prompt propio** (`{{- if .Tools }} … {{- else if .System }}`).

Salida real de `hermes3:3b` (3.2B, Q4_K_M) con `tools`:
- a veces el JSON es casi correcto pero llega como texto sin las etiquetas
  `<tool_call>` → Ollama no lo parsea a `tool_calls`
  (`("/")\n{ "name": "abrir_aplicacion", "arguments": { "app": "whatsapp" } }`).
- la mayoría de las veces el JSON está corrupto:
  `,{"arguments": "app", "name": "abrir_aplicacion", "function": …}` /
  `<tool_response>"arguments": "ciudad Bogota", "name: "clima"`.

Se probó: `num_predict` 60 → 400, con y sin system prompt propio, y un **parser
de rescate** que busca `<tool_call>{…}</tool_call>` o un objeto `{"name",
"arguments"}` suelto en el `content`. Con rescate: **0/4** en las primeras 4
frases (el JSON está demasiado roto para recuperarlo).

### VEREDICTO

> **`hermes3:3b` NO es viable como modelo de routing/tool-calling en este
> equipo.** El 3B (el más pequeño de la familia Hermes 3) no sigue de forma
> fiable su propio formato de function calling; los que sí lo hacen bien son
> 8B/70B, prohibidos por hardware y por las reglas del plan. `llama3.2:3b` gana
> en precisión (10/12 vs 1/12) **y** en latencia (19,5 s vs 28,8 s).
>
> **Decisión:** se mantiene `ollama.agent_model: llama3.2:3b`. **No se fuerza
> Hermes.** (Regla del pedido §17/§34: "los resultados mandan".)
>
> `hermes3:3b` se conserva instalado por ahora (2,0 GB) para no repetir la
> descarga si se quiere reevaluar tras un cambio de plantilla de Ollama; se
> puede borrar con `ollama rm hermes3:3b`.

### Qué sigue teniendo sentido del PLAN_HERMES (independiente de Hermes)

FASE 5 (selección de modelo por config/env limpia + chequeo en `doctor`),
FASE 6 (parser de rescate de tool calls **también** mejora a llama/qwen, que a
veces filtran), FASE 8 (fallback llama→qwen), FASE 11 (verify/recovery),
FASE 12 (memoria e2e), FASE 13–15 (baterías adversarial/estabilidad),
FASE 16–17 (auditoría + informe). El "modelo objetivo" pasa a ser
**`llama3.2:3b` endurecido**, no Hermes.
