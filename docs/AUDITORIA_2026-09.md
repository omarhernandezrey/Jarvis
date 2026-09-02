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

## 5. Latencia — medición DESPUÉS

_(se rellena al cerrar la Fase C)_
