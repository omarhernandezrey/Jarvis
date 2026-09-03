# AUDITORÍA FUNCIONAL — JARVIS · 2026-09-02

Referencia "ANTES" del `PLAN_MAESTRO.md`. Pruebas hechas en caliente: Ollama
vivo (`qwen2.5:3b`, `bge-m3`), red disponible, `secrets.yaml` cargado
(email, WolframAlpha, Google Calendar, Spotify).

La suite `pytest test -q` pasa entera (**595 passed / 7 skipped / 0 fallos**),
pero mockea el LLM y usa datos falsos: **no cubre** varias cosas que en uso real
fallan o van lentas. Este documento las recoge.

---

## 1. Estado por funcionalidad

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| L1 · Respuestas instantáneas | ✅ FUNCIONA | hola / hora / fecha / gracias → 0 s |
| └ `"buenas noches"` | 🟠 BUG (B1) | devuelve *"Buenos días, señor Omar…"* |
| L2 · Parser determinista | ✅ FUNCIONA (con huecos) | ~25 frases → intent correcto en <20 ms |
| L3 · Agente (tool calling) | 🟠 FUNCIONA pero LENTO | elige bien la herramienta; **25–82 s** por turno |
| L4 · Chat LLM | ✅ RÁPIDO | "2+2" → "4" en 1,5 s (modelo caliente) |
| Memoria semántica | ⚠️ NO VERIFICADA e2e | falta prueba del flujo "alérgico→camarones" |
| Clima | ✅ FUNCIONA | Bogotá/Cali/Cartagena OK; error limpio en ciudad falsa |
| Wikipedia | ✅ FUNCIONA | García Márquez OK; fallback OK |
| Noticias | ✅ FUNCIONA | titulares RSS del día |
| Calculadora — básica | ✅ FUNCIONA | `15*3+2` → 47 |
| Calculadora — lenguaje natural | 🔴 ROTO (B2/B3) | `raíz de 144`, `20% de 350`, `x+135-234=345` → *"No pude interpretar"* |
| WolframAlpha | ✅ FUNCIONA | `derivada de x^2` → `2 x` |
| IP | ✅ FUNCIONA | local + pública |
| Ubicaciones / distancia | 🔴 ROTO para POIs (B4) | `Torre Eiffel` → *"No encontré el lugar"* (geocoder de ciudades) |
| Estado del sistema | ✅ FUNCIONA | CPU/RAM/disco/batería |
| Recordatorios | ✅ FUNCIONA | "en 10 min" y "mañana a las 3" OK |
| Chistes | ✅ FUNCIONA | |
| Briefing diario | ✅ FUNCIONA | saludo+fecha+clima en 2,5 s |
| Terminal | ✅ FUNCIONA + SEGURO | `;`, `&&`, `rm` → BLOQUEADO |
| Google Calendar | 🔴 ROTO (B5) | `invalid_grant: Bad Request` — token OAuth caducado |
| Spotify | ✅ FUNCIONA | reproduce (por ruta lenta, ver §3) |
| Empleo | ✅ FUNCIONA | Computrabajo+LinkedIn, ofertas recientes |
| Apps (fuzzy) | 🟠 PARCIAL (B7) | `whatsapp` ✅ · `android studio` → `[]` |
| Correo | ✅ FUNCIONA (plan) | parsea to/asunto/cuerpo; exige confirmación |
| Voz (STT/TTS) | ⚠️ NO PROBADA con audio real | módulos importan bien |

## 2. Bugs concretos

| # | Bug | Ubicación | Impacto |
|---|---|---|---|
| B1 | `"buenas noches"` → saludo de mañana | `fast_response.py` | Poco fino |
| B2 | Calculadora sin `%`, sin `raíz cuadrada de`, sin ecuaciones; `normalize_expression` **borra el `=`** | `tools/calculator.py:74,88` | Feature insignia del README no existe |
| B3 | Sin solver de ecuaciones (`x+135-234=345 → x=444`) | `tools/calculator.py` | Ejemplo del README roto |
| B4 | `locate()` geocodifica con la API de *ciudades* → falla con cualquier POI | `tools/location.py:44` | "dónde queda X" roto para lugares reales |
| B5 | Google Calendar sin refresh de token ni mensaje accionable | `tools/gcalendar.py:23` | "mis próximos eventos" muerto hasta re-autorizar a mano |
| B6 | Spotify sin manejo defensivo de token muerto | `tools/spotify.py` | Error técnico en vez de mensaje accionable |
| B7 | `find_app("android studio")` → `[]` | `tools/app_index.py:175` | O no instalada, o umbral difuso alto / falta sinónimo |
| B8 | Parser: `"pon <canción>"` no cae en Spotify (`pon` falta en el regex de reproducción) | `intent/parser.py:480` | El ejemplo insignia tarda **92 s** en vez de ~3 s |
| B9 | Parser: `"qué tiempo hace en X"` no → clima | `intent/parser.py` (`_parse_fase4`) | Cae al agente (30–80 s) |
| B10 | Parser: `"crea una nota X"` no → notas (sólo "toma nota/apunta/anota") | `intent/parser.py:526` | Cae al chat |
| B11 | Parser: `"abre youtube y pon lofi"` no se divide en 2 acciones | `intent/parser.py:634` | Cae al chat |

## 3. Latencia — medición ANTES (equipo: Intel i5-6200U, sin GPU, modelo caliente)

| Petición | Ruta | Tiempo medido | Comentario |
|---|---|---|---|
| `"hola"` | L1 instantánea | 0,0 s | ✅ |
| `"clima en Cali"` | L2 parser → tool | 1,6 s | ✅ |
| `"cuéntame un chiste"` | L1/parser | 0,1 s | ✅ |
| LLM directo `"2+2"` | L4 chat | 1,5 s | ✅ (modelo caliente) |
| agente `"qué tal mi máquina de recursos"` | L3 | 25 s | README dice 19 s |
| agente `"vacantes de programador en Medellín"` | L3 | 33 s | |
| agente `"va a llover en Cartagena"` | L3 | 82 s | sospecha de bucle multi-paso |
| e2e `"pon bohemian rhapsody"` | cae a L3 → spotify | **92 s** | debería ser parser ~3 s (B8) |
| e2e `"qué tal mi máquina"` | cae a L3 | **112 s** | el tool directo lo hace en 0,01 s |

**Causas de la latencia:**
1. `qwen2.5:3b` haciendo *tool calling* en CPU: 25–80 s por llamada, muy variable.
2. Huecos del parser (B8–B11): frases comunes se escapan al agente lento.
3. El caso de 82–112 s huele a bucle multi-paso / reintentos (`MAX_STEPS=3` +
   `MAX_REINTENTOS=2` = hasta 5 llamadas al LLM por turno).

---

## 4. Línea base de tests (antes del plan)

- `pytest test -q` → 595 passed / 7 skipped / 0 fallos.
- `ruff check .` → All checks passed!
- CI (`.github/workflows/tests.yml`): matriz Windows 3.11/3.12/3.13 + job de
  seguridad.

> La línea de resumen `=== N passed ===` a veces no se vuelca por un fallo de Qt
> en el *teardown*; el criterio real es **cero `FAILED`/`ERROR`** en toda la
> corrida.

---

## 5. Latencia del agente — instrumentación (TAREA C1)

`decisions.jsonl` ahora registra `llm_calls` y `llm_secs` por turno.
`scripts/bench_agente.py` corre un set fijo.

Medición 2026-09 (bench --quick, máquina cargada, modelo qwen2.5:3b):

| Frase (directo a run_agent) | tools | llm_calls | llm_secs | turno total |
|---|---|---|---|---|
| "va a llover en Cartagena" | clima | **1** | 73,6 s | 107 s |
| "qué tal anda mi máquina de recursos" | estado_del_sistema | **1** | 23,3 s | 25 s |

**Hallazgo clave:** NO es un bucle de reintentos — es **una sola llamada de
tool-calling** que tarda 23–74 s en esta CPU. La variabilidad depende del
tamaño del catálogo que el retriever le pasa al modelo. Implicaciones:
- C3 (parser-first reforzado) es el mayor ahorro: mantener frases fuera del
  agente (como hicieron A2–A7).
- C5 (modelo de routing más pequeño) es el lever real para la latencia de esa
  única llamada.
- C2 (podar el bucle) sigue siendo un tope de seguridad, pero 1 acción ya = 1
  llamada.

## 5b. Modelo de routing — comparación (TAREA C5)

`ollama pull llama3.2:3b`. 6 casos representativos del agente (subconjunto de
`eval/cases`), directo a `run_agent`, esta máquina (2 núcleos, sin GPU):

| Modelo | Acierto | Tiempo total (6) | Media |
|---|---|---|---|
| `qwen2.5:3b` | 6/6 | 272 s | 45 s |
| `llama3.2:3b` | 6/6 | 223 s | 37 s |

**Decisión:** `ollama.agent_model: llama3.2:3b` en `config.yaml`. ~18 % más
rápido, mismo acierto en el subconjunto probado, y el hook `agent_model` deja
revertirlo en una línea. El chat sigue con `qwen2.5:3b` y los embeddings con
`bge-m3`.

**Límite honesto:** no se corrió `eval/` completo (60 casos × 2 modelos ×
20–120 s = horas, con riesgo de saturar la máquina). La comparación es sobre 6
casos. El cuello de botella de fondo — un modelo 3B haciendo tool-calling en
CPU de 2 núcleos — no lo resuelve un cambio de modelo; lo resuelve mantener
frases fuera del agente (A2–A7, C3).

## 6. Latencia — medición DESPUÉS (tras Fases A–D)

Mismo equipo (Intel i5-6200U, sin GPU), Ollama caliente, máquina descargada
(`load ~1,2`). Medido con `scripts/bench_agente.py` y un script ad-hoc que
cronometra `Jarvis.chat()` de punta a punta.

| Petición | Ruta ANTES → DESPUÉS | ANTES | DESPUÉS | Tarea |
|---|---|---|---|---|
| `"qué hora es"` | L1 → L1 | 0 s | **<1 ms** | — |
| parser `"abre whatsapp"` | L2 → L2 | — | **0,2 ms** (solo enrutado) | — |
| e2e `"clima en Cali"` | L2→tool → igual | 1,6 s | **1,58 s** (incluye HTTP a Open-Meteo) | — |
| e2e `"va a llover en Cartagena"` | **L3 agente → L2 parser→clima** | 82–107 s | **1,54 s** | A3 |
| e2e `"cómo anda la máquina"` | **L3 agente → L2 parser→tool** | 25–112 s | **0,02 s** | A7 |
| e2e `"pon bohemian rhapsody"` | **L3 agente → L2 parser→spotify** | 92 s | ~0,1 s de enrutado (+ API de Spotify) | A2 |
| agente puro (frase sin patrón, p. ej. "búscame un chiste de programadores") | L3 | 25–74 s (`qwen2.5:3b`) | **35–70 s** (`llama3.2:3b`, ~18 % menos en el subconjunto de C5) | C5 |
| chat directo `"2+2"` (modelo caliente) | L4 | 1,5 s | **~1,5 s** | — |

**Conclusión.** El agente 3B en CPU de 2 núcleos sigue siendo lento (35–70 s):
eso **no se arregla con software**, es el hardware. Lo que el plan sí movió es
**qué frases llegan al agente**. Las peticiones comunes que antes se colaban a
la capa 3 (clima natural, estado del sistema, "pon <canción>", "lanza <app>",
notas, cálculo) ahora las resuelve el parser determinista en milisegundos. El
caso de "va a llover en Cartagena" — 90 s → 1,5 s — es el resumen del plan.

Palancas secundarias aplicadas: `keep_alive: 30m` (evita ~10 s de recarga entre
turnos, C4), caché de decisiones (frase repetida = 0 llamadas al LLM, C6),
bucle podado (`MAX_STEPS 3→2`, `MAX_REINTENTOS 2→1`, C2) y modelo de routing
`llama3.2:3b` (~18 %, C5).

---

## 7. Evaluación de `hermes3:3b` como modelo de routing (2026-09-03)

Contexto: se evaluó `hermes3:3b` (Nous Research, orientado a *function calling*)
como posible reemplazo de `llama3.2:3b` en el paso de routing. Ver
`PLAN_HERMES.md`.

Batería `scripts/bench_router_modelos.py` (12 frases de routing, 1 llamada
`chat_with_tools` por frase, i5-6200U sin GPU, un modelo residente a la vez):

| modelo | herramienta correcta | JSON válido | latencia media |
|---|---|---|---|
| `llama3.2:3b` (actual) | **10/12** | 12/12 | **19,5 s** |
| `qwen2.5:3b` | 10/12 | 12/12 | 21,7 s |
| `hermes3:3b` | **1/12** | 12/12 | 28,8 s |

`hermes3:3b` **no emitió `tool_calls`** en 11 de 12 casos: devolvió el intento
de llamada como texto y, casi siempre, con el JSON corrupto
(`,{"arguments": "app", "name": …, "function": …}`). La plantilla de Ollama para
`hermes3` además **descarta el system prompt propio** cuando se pasan `tools`
(usa el suyo de *function calling*). Se probó `num_predict` 60→400, con/sin
system prompt, y un parser de rescate sobre el `content`: 0/4 recuperables.

**Decisión:** se mantiene `ollama.agent_model: llama3.2:3b`. El 3B de Hermes es
demasiado débil para su propio formato de tool calling; las variantes que lo
hacen bien (8B/70B) están fuera del presupuesto de hardware. `hermes3:3b` queda
instalado por si cambia la plantilla de Ollama; `ollama rm hermes3:3b` para
liberarlo.
