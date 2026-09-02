# PLAN MAESTRO — EFICACIA DE JARVIS

> **Este es EL plan maestro activo.** Supera a `IMPLEMENTACION_DE_MEJORAS.md`
> (histórico: 86/86 tareas completadas). Todo agente o desarrollador que trabaje
> en este repositorio ejecuta **este** documento, en orden, sin saltarse tareas.
>
> **Objetivo:** que cada funcionalidad de JARVIS sea **útil, certera y rápida**.
> La interfaz ya se siente viva; las funcionalidades deben estar a la altura.
>
> **Origen:** auditoría funcional del 2026-09-02 con Ollama vivo, red y
> `secrets.yaml` cargados (ver `docs/AUDITORIA_2026-09.md`, se crea en la Tarea 0).

---

## REGLAS DE ORO (no negociables)

1. **Secuencial. Sin saltos.** La Tarea N+1 no se empieza hasta que la Tarea N
   está **mergeada a `main`** y toda su batería de pruebas en verde.
2. **Una rama por tarea.** Nunca se trabaja directo sobre `main`.
3. **Se prueba TODO lo que exista, hasta que pase.** Se corre el *Protocolo de
   pruebas* completo. Si algo falla → se corrige → se **repite la batería entera
   desde el principio**. No se avanza con nada en rojo. No se acepta un test que
   "pasa a veces" (flaky): se estabiliza o se arregla la causa.
4. **Cero regresiones.** `python -m pytest test -q` sigue 100% verde siempre. No
   se borra, se salta ni se debilita un test existente para pasar.
5. **Cada tarea añade sus propios tests.** Un arreglo sin test que lo blinde no
   está terminado.
6. **Verificación real, no sólo tests.** Además del pytest, se ejercita la
   funcionalidad de verdad (CLI o `Jarvis.chat()` con Ollama vivo) y se pega la
   evidencia (entrada → salida → tiempo) en el commit o en la auditoría.
7. **Honestidad.** Si algo no se puede arreglar del todo (depende de red, de una
   cuenta externa o de hardware), se documenta el límite y se deja un mensaje de
   error **accionable**. Nunca fingir que funciona.

---

## PROTOCOLO DE PRUEBAS

Se corre **entero** por tarea, y se **repite completo** después de cada
corrección, hasta que todo esté verde a la vez.

| # | Tipo | Comando | Criterio de aprobación |
|---|------|---------|------------------------|
| 1 | **Lint** | `ruff check .` | `All checks passed!` |
| 2 | **Unit — nuevos** | `python -m pytest test/<test_nuevo>.py -q` | 100% verde |
| 3 | **Regresión — suite completa** | `QT_QPA_PLATFORM=offscreen python -m pytest test -q` | **cero `FAILED` / `ERROR`** en toda la corrida (skips conocidos OK) |
| 4 | **Cobertura del código tocado** | `python -m pytest test/<...> --cov=jarvis_local.<módulo> --cov-report=term-missing` | líneas nuevas/tocadas cubiertas **≥ 90%** |
| 5 | **Integración e2e** | `Jarvis.chat("<frase real>")` con Ollama vivo | ruta correcta (`last_route`) + respuesta correcta |
| 6 | **Latencia** (si la tarea la afecta) | script de medición de la tarea | dentro del presupuesto declarado |
| 7 | **Seguridad** (si toca entrada de usuario, rutas o shell) | tests de inyección / *path traversal* | **todo** intento malicioso BLOQUEADO |
| 8 | **Manual exploratorio** | ejercicio libre relacionado con la tarea | sin sorpresas |
| 9 | **CI** | GitHub Actions en la rama tras el `push` | *Tests* y *Auditoría de seguridad* en verde |

> **Nota de entorno:** la suite completa a veces no imprime la línea final
> `=== N passed ===` por un fallo de Qt en el *teardown* del proceso. El criterio
> real del paso #3 es **no encontrar ni un `FAILED`/`ERROR`** en toda la salida
> (sólo caracteres `.` y `s`).

---

## FLUJO GIT POR TAREA (exacto)

```bash
git checkout main && git pull origin main
git checkout -b <rama-de-la-tarea>

#  ── implementar + añadir tests ──
#  ── correr el PROTOCOLO DE PRUEBAS completo hasta que TODO esté verde ──
#  ── repetir si algo falla ──

git add -A
git commit -m "$(cat <<'EOF'
fix(<área>): <TAREA> — <qué cambió y por qué>

<evidencia e2e: entrada → salida → tiempo>
Protocolo de pruebas: lint OK · unit nuevos OK · suite completa 0 fallos ·
cobertura <n>% · e2e OK · (latencia <n>s si aplica) · seguridad OK.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: <url>
EOF
)"
git push origin <rama-de-la-tarea>
#  ── esperar a que la CI de la rama pase en verde ──

git checkout main
git merge --no-ff <rama-de-la-tarea> -m "merge: <TAREA>"
git push origin main
git branch -d <rama-de-la-tarea>
git push origin --delete <rama-de-la-tarea>
```

En el commit de merge, marcar la casilla `- [x]` de la tarea en este documento.

---
---

# TAREA 0 — Preparación y línea base  ✅ COMPLETADA (merge a `main`)

**Rama:** `chore/plan-maestro-baseline`

- [x] **0.1** Crear `docs/AUDITORIA_2026-09.md` con el resultado de la auditoría
  funcional (estado por funcionalidad, bugs B1–B11 con `archivo:línea`, tabla de
  latencias medidas). Es la referencia "ANTES" contra la que se mide todo.
- [x] **0.2** En `.claude/CLAUDE.md`, cambiar la "Primera acción obligatoria" y el
  "Flujo de trabajo" para que apunten a **`PLAN_MAESTRO.md`**.
- [x] **0.3** En `README.md`, reemplazar la sección "Plan de Mejoras en Curso".
- [x] **0.4** `IMPLEMENTACION_DE_MEJORAS.md`: aviso de archivado / completado.
- [x] **0.5** Línea base: `pytest test -q` → **595 passed / 7 skipped / 0 fallos**;
  `ruff check .` → limpio; tabla de latencias "ANTES" en `docs/AUDITORIA_2026-09.md §3`.

**Pruebas:** protocolo #1 (ruff limpio) y #3 (suite 0 fallos). Sin código de
producción tocado.

---

# FASE A — Cerrar los huecos del parser
> Efecto: frases comunes y ya "conocidas" que hoy se escapan al agente lento
> (30–110 s) pasan a resolverse en el parser determinista (< 3 s). Bajo riesgo.

## A1 — Batería de cobertura del parser  ✅ COMPLETADA (merge a `main`)
**Rama:** `test/parser-coverage`

- [x] `test/test_parser_coverage.py`: **80 casos** (frases coloquiales) →
  `tool`/`kind` esperado, más un bloque `MULTI` para `dividir_acciones()`.
- [x] Casos que HOY funcionan → aserción normal.
- [x] Casos rotos → `pytest.mark.xfail(strict=True, reason="TAREA A2/A3/A4/A6/A7/B2/B3")`.
  Cada tarea quita su xfail.
- [x] Casos negativos (conversación pura → `kind=chat`).
- [x] **Hallazgos nuevos** al construir la batería → añadidas **TAREA A6**
  (`"lanza <app>"` se iba a `run_command`) y **TAREA A7** (estado del sistema
  coloquial → `chat`).

**Resultado:** `pytest test/test_parser_coverage.py` → **64 passed, 16 xfailed,
0 failed**. Suite completa: sin regresiones.

## A2 — `"pon <canción>"` → Spotify  ✅ COMPLETADA (merge a `main`)
**Rama:** `fix/parser-pon-cancion`
**Archivo:** `jarvis_local/intent/parser.py` (`_parse_fase4`, nueva rama `m_pon` tras `m_play`)

- [x] Nueva rama: `"pon(me|le) <X>"` a secas → `spotify_play`, con *lookahead*
  negativo para no tragarse `"pon una nota"` / `"pon un recordatorio"`. Volumen,
  recordatorios, multimedia, ventanas y `"pon música [de X]"` / `"pon X en
  youtube"` ya se resolvían antes en la cascada.
- [x] Quitados los 4 `xfail` `_A2` + 2 variantes nuevas.

**Resultado:** batería `test_parser_coverage.py` → **70 passed, 12 xfailed**.
**e2e:** `Jarvis.chat("pon bohemian rhapsody")` → ruta `tool`, **0,09 s**
(auditoría: 92 s), `spotify.play_song("bohemian rhapsody")` llamada correcta.
Suite completa: sin regresiones. `ruff` limpio.

## A3 — `"qué tiempo hace en X"` / `"cómo está el clima en X"` → clima  ✅ COMPLETADA
**Rama:** `fix/parser-clima-natural`
**Archivo:** `jarvis_local/intent/parser.py` (`_parse_fase4`, bloque CLIMA)

- [x] Nuevo trigger: `clima|temperatura|pronostico`, `(que|como) tiempo
  (hace|hara|va a hacer|habra)`, `(como|que) (esta|estara) el tiempo`,
  `va a llover|llovera|lloveria|va a haber lluvia|hay lluvia`. "tiempo" solo
  dispara con verbo meteorológico (no `"no tengo tiempo"` / `"hace tiempo"`).
- [x] Extracción de ciudad limpia: prioriza `en <X>`, quita adverbios
  temporales (hoy/mañana/sábado/…). Arregla de paso el bug latente de
  `"el clima de hoy en Quito"` → city era `"hoy en quito"`, ahora `"quito"`.
- [x] Quitados los 3 `xfail` `_A3` + 4 positivos + 2 negativos + test de
  extracción de ciudad (`test_weather_city_limpia`).

**e2e:** `"qué tiempo hace en Medellín"` → ruta `tool`, **1,3 s** (auditoría:
30–80 s). `"va a llover en Cartagena"` → **1,2 s** (auditoría: 82 s).
`ruff` limpio · batería y suite sin regresiones.

## A4 — `"crea (una) nota …"` / `"nueva nota …"` → notas  ✅ COMPLETADA
**Rama:** `fix/parser-crea-nota`
**Archivo:** `jarvis_local/intent/parser.py` (`_parse_fase4`, `m_note`)

- [x] Disparadores nuevos de `take_note`: `crea|nueva|haz|hazme|guarda|guardame|
  escribe|escribeme (me)? (una)? nota`, `nota nueva`, `apuntame`. Separadores
  `de|que|con|sobre|:`.
- [x] Verificado que NO colisiona: `"crea un recordatorio"` → `set_reminder`;
  `"crea un archivo notas.txt"` → `create_file` (ambos se resuelven antes o no
  contienen "nota" tras el verbo).
- [x] Quitados los 3 `xfail` `_A4` + 5 casos nuevos (2 de no-colisión).

**e2e:** `Jarvis.chat("crea una nota comprar pan y leche")` → ruta `tool`,
**0,03 s**, `take_note("comprar pan y leche")`.
Batería: **90 passed, 6 xfailed**. `ruff` limpio · suite sin regresiones.

## A5 — Multi-acción con verbos de reproducción, verificada e2e  ✅ COMPLETADA
**Rama:** `fix/parser-multiaccion-reproducir`
**Archivos:** `jarvis_local/intent/parser.py` (`_SITIO_CONOCIDO`, bloque ABRIR APP)

- [x] `dividir_acciones` y `_chat_encadenado` (parser-first por cláusula) ya
  estaban bien; confirmado con tests (bloque MULTI).
- [x] El fallo real: la 1ª cláusula `"abre youtube"` → `ambiguous` (no es app ni
  dominio). Nuevo mapa `_SITIO_CONOCIDO` (youtube, gmail, maps, facebook,
  netflix, …) como *fallback* **tras** fallar `find_app` → `"abre youtube"` →
  `open_website`. `"abre spotify"` / `"abre whatsapp"` siguen abriendo la app
  instalada (el mapa solo actúa si `find_app` no encontró nada).
- [x] Batería: 6 casos nuevos (incl. no-regresión de spotify/whatsapp).

**e2e:** `Jarvis.chat("abre youtube y pon lofi")` → ruta `tool`, **0,06 s**,
ejecuta AMBAS: `open_website("youtube.com")` + `play_song("lofi")`.
Batería: **95 passed, 6 xfailed**. `ruff` limpio · suite sin regresiones.

## A6 — `"lanza / inicia <app>"` no debe irse a `run_command`  ✅ COMPLETADA
**Rama:** `fix/parser-lanza-app`
**Archivo:** `jarvis_local/intent/parser.py` (`_extract_app_candidate`, bloque ABRIR APP)

- [x] `_SHELL_SHAPE` en `_extract_app_candidate`: candidato con flags (`-l`),
  rutas (`/`), operadores (`;&|$\``) o extensión de script (`.sh/.py/.bat/…`)
  → NO es una app → fluye a `run_command` y su blocklist.
- [x] En el bloque ABRIR APP: si `find_app` falla y no es sitio conocido y el
  objeto NO es vago (`_VAGO_OBJ`: "algo", "una aplicacion"…) → `open_app` con el
  candidato (open_app hace su propia resolución difusa y avisa con claridad).
  `"lanza android studio"` → `open_app`, no `run_command`.
- [x] `"abre algo"` sigue → `ambiguous` (test_ambiguous_open intacto).
- [x] Quitado `xfail` `_A6` + 4 casos nuevos (vago, shell-shape).

**e2e:** `"lanza android studio"` → ruta `tool`, 0,03 s, `open_app` → *"no
encontré ninguna app parecida a 'android studio'"* (honesto — no está instalada;
lo pule B7), NO ejecuta shell ni pasa al agente. `"ejecuta rm -rf /"` →
BLOQUEADO. Batería: **100 passed, 5 xfailed**. `ruff` limpio.

## A7 — Estado del sistema en lenguaje coloquial  ✅ COMPLETADA
**Rama:** `fix/parser-sistema-coloquial`
**Archivo:** `jarvis_local/intent/parser.py`

- [ ] Descubierto en A1: `"como anda la maquina"`, `"que tal el equipo"`,
  `"como van los recursos"` → `chat` (caen al agente). Añadir patrones para que
  vayan a `system_status`.
- [ ] Quitar el `xfail` correspondiente en `test_parser_coverage.py`.

**Pruebas:** #1, #2, #3, #5, #6 (frase coloquial de sistema < 3 s vs. los ~25 s
del agente).

---

# FASE B — Arreglar funcionalidad advertida que no funciona

## B1 — Saludo instantáneo según la hora real  ✅ COMPLETADA
**Rama:** `fix/fast-response-saludo-hora`
**Archivo:** `jarvis_local/fast_response.py`

- [ ] El saludo genérico debe usar `datetime.now().hour` (mañana/tarde/noche).
- [ ] `"buenas noches"` / `"buenas tardes"` / `"buenos días"` explícitos deben
  respetar lo que dijo el usuario, no devolver siempre "Buenos días".

**Pruebas:** #1, #2 (parametrizado con `freezegun` o `monkeypatch` sobre
`datetime` para 08:00 / 15:00 / 23:00), #3, #5.

## B2 — Calculadora: porcentajes, raíces y funciones en lenguaje natural  ✅ COMPLETADA
**Rama:** `fix/calculadora-lenguaje-natural`
**Archivo:** `jarvis_local/tools/calculator.py` (`normalize_expression`, `_WORDS`, `_FUNCS`)

- [ ] Soportar `"20% de 350"`, `"el 20 por ciento de 350"` → `0.20 * 350`.
- [ ] Soportar `"raíz cuadrada de 144"`, `"la raíz de 144"` → `sqrt(144)`.
- [ ] Soportar `"144 elevado a 2"`, `"2 al cubo"`, `"factorial de 5"`.
- [ ] Mantener el AST seguro (sin `eval`, sin `Name` no permitidos).

**Pruebas:** #1, #2 (una decena de casos con resultado exacto esperado), #3,
#4 (`--cov=jarvis_local.tools.calculator` ≥ 95%), #5, #7 (que `"__import__('os')"`
y similares sigan lanzando `ValueError`).

## B3 — Calculadora: ecuaciones lineales de una incógnita  ✅ COMPLETADA
**Rama:** `fix/calculadora-ecuaciones`
**Archivo:** `jarvis_local/tools/calculator.py` (+ posible `equation.py`)

- [ ] `"resuelve x + 135 - 234 = 345"`, `"despeja x en 2x + 4 = 10"` → `x = 444`
  / `x = 3`. (Ejemplo insignia del README.)
- [ ] **Decisión documentada en el commit:** solver propio (parseo simbólico
  mínimo con el AST ya existente, sin `sympy` para no engordar dependencias) vs.
  rutar a WolframAlpha. Preferencia: solver propio para lineales de 1 incógnita;
  Wolfram como fallback para lo no lineal.
- [ ] El parser debe rutar `"resuelve …"` / `"despeja …"` a esta ruta
  (añadir en Fase A si no se cubrió; si no, aquí).
- [ ] Errores claros: `"esa ecuación no es lineal, señor"` en vez de crash.

**Pruebas:** #1–#5, #7. Incluir los ejemplos exactos del README.

## B4 — `locate()` no falla con lugares reales  ✅ COMPLETADA
**Rama:** `fix/locate-fallback`
**Archivo:** `jarvis_local/tools/location.py`

- [ ] Si `geocode_city()` (API de ciudades de Open-Meteo) no encuentra el lugar:
  1. reintentar con **Nominatim / OpenStreetMap** (`User-Agent` obligatorio,
     máx. 1 petición/s, `timeout` corto).
  2. si aún falla, abrir `https://www.google.com/maps/search/?api=1&query=<texto>`
     con la consulta cruda y responder *"Abrí el mapa. No pude calcular la
     distancia."*.
- [ ] Nunca devolver *"No encontré el lugar"* para un POI conocido.

**Pruebas:** #1, #2 (mock de las dos APIs: éxito directo, fallback OSM, fallback
Maps), #3, #5 (`Jarvis.chat("dónde queda la Torre Eiffel")` con red real →
respuesta útil), #8.

## B5 — Google Calendar: refresh de token + re-autorización accionable  ✅ COMPLETADA
**Rama:** `fix/gcalendar-reauth`
**Archivo:** `jarvis_local/tools/gcalendar.py:23` (`_get_service`)

- [ ] Al construir el servicio, si las credenciales están vencidas pero hay
  `refresh_token`, refrescar y guardar el token nuevo.
- [ ] Si el refresh falla (`RefreshError` / `invalid_grant`): NO crashear;
  devolver *"El acceso a tu Google Calendar caducó, señor. Vuelve a autorizar
  con: `python -m jarvis_local.cli --reauth-calendar`"* (o el comando real).
- [ ] Implementar ese comando/flag de re-autorización si no existe.

**Pruebas:** #1, #2 (mock de credenciales: válidas / refrescables / muertas),
#3, #5 (con el token actual real: debe dar el mensaje accionable, no un
*traceback*).

## B6 — Spotify: re-autorización accionable (defensivo)  ✅ COMPLETADA
**Rama:** `fix/spotify-reauth`
**Archivo:** `jarvis_local/tools/spotify.py`

- [ ] Mismo patrón que B5: si el token de Spotify está muerto y no se puede
  refrescar, mensaje accionable con el comando para re-autorizar, no un error
  técnico.

**Pruebas:** #1, #2 (mock del cliente spotipy con token inválido), #3, #5.

## B7 — `find_app`: umbral difuso y sinónimos  ✅ COMPLETADA
**Rama:** `fix/find-app-fuzzy`
**Archivo:** `jarvis_local/tools/app_index.py:175`

- [ ] Revisar por qué `find_app("android studio")` devuelve `[]` en esta máquina
  (¿no instalada? ¿umbral de similitud demasiado alto? ¿falta sinónimo?).
- [ ] Ajustar el umbral y/o la tabla de sinónimos para nombres compuestos.
- [ ] Test parametrizado con **nombres reales** leídos de `data/apps_index.json`
  de la máquina (todos deben resolverse por su nombre y por 1–2 variantes).

**Pruebas:** #1, #2, #3, #5, #8.

---

# FASE C — Latencia del agente
> El README promete "agente: 19 s"; medido: 25–112 s. Objetivo: agente de 1
> acción < 20 s, y que las frases resolubles por parser nunca lleguen al agente.

## C1 — Instrumentar `run_agent`  ✅ COMPLETADA
**Rama:** `feat/agente-instrumentacion`
**Archivo:** `jarvis_local/agent/loop.py`, `jarvis_local/agent/decision_log.py`

- [ ] Registrar por turno: nº de llamadas a `chat_with_tools`, tiempo de cada
  una, tiempo del retriever, nº de pasos, resultado.
- [ ] Script `scripts/bench_agente.py` que corre un set fijo de frases y vuelca
  una tabla (frase → pasos → llamadas LLM → tiempo total) a
  `docs/AUDITORIA_2026-09.md` bajo "latencia — ANTES".

**Pruebas:** #1, #2 (el log tiene los campos), #3.

## C2 — Podar el bucle del agente  ✅ COMPLETADA
**Rama:** `fix/agente-bucle`
**Archivo:** `jarvis_local/agent/loop.py` (`MAX_STEPS`, `MAX_REINTENTOS`)

- [ ] `MAX_REINTENTOS: 2 → 1`. `MAX_STEPS: 3 → 2` salvo cuando
  `dividir_acciones` detectó multi-acción explícita.
- [ ] Test: una petición de **1 acción simple** hace **exactamente 1** llamada a
  `chat_with_tools` (mock del cliente que cuenta invocaciones).
- [ ] Confirmar con `eval/` que el acierto no baja.

**Pruebas:** #1, #2, #3, #5, #6 (agente 1 acción, medir antes/después).

## C3 — Parser-first reforzado  ✅ COMPLETADA
**Rama:** `feat/parser-first-reforzado`
**Archivo:** `jarvis_local/intent/parser.py` o `jarvis_local/jarvis.py`

- [ ] Antes de invocar el agente, un segundo pase de patrones "casi-deterministas"
  (verbo de acción claro + objeto identificable) que resuelva sin LLM las frases
  que el parser estricto no cazó pero que son inequívocas.
- [ ] No debe capturar conversación ni órdenes vagas (esas siguen al agente / a
  la aclaración).

**Pruebas:** #1, #2 (batería: N frases que ahora resuelve sin LLM; M frases
conversacionales que NO captura), #3, #5, #6.

## C4 — Keep-alive y `num_predict` del agente  ✅ COMPLETADA
**Rama:** `fix/ollama-keepalive`
**Archivo:** `jarvis_local/ollama_client/client.py`, `config.yaml`

- [ ] Enviar `keep_alive` (p. ej. `"30m"`) en las llamadas, y/o documentar
  `OLLAMA_KEEP_ALIVE`.
- [ ] `agent_num_predict: 120 → 60` (el router elige, no redacta).
- [ ] Medir el coste de la primera llamada en frío vs. caliente.

**Pruebas:** #1, #2, #3, #6.

## C5 — Evaluar modelo alternativo sólo para el *routing*  ✅ COMPLETADA
**Rama:** `research/modelo-router`
**Archivos:** `jarvis_local/eval/`, `config.yaml`

- [ ] Con `ollama pull llama3.2:3b` (y opcional `qwen2.5:1.5b`), correr la
  batería de `eval/` midiendo **acierto de herramienta** y **latencia** para
  cada modelo en el paso de *tool calling*.
- [ ] **Decisión documentada** en `docs/AUDITORIA_2026-09.md`: cambiar el modelo
  del agente o mantener `qwen2.5:3b`. Si se cambia, dejar `config.yaml` con un
  `agent_model` separado del `model` del chat.

**Pruebas:** #1, #3, y el informe de `eval/` adjunto al commit.

## C6 — Caché de decisiones del agente
**Rama:** `feat/agente-cache`
**Archivo:** `jarvis_local/agent/loop.py` (+ `agent/decision_cache.py`)

- [ ] Cachear `frase normalizada → (herramienta, args)` con TTL corto (p. ej.
  10 min) y tamaño máximo. Una frase repetida no vuelve a pagar el LLM.
- [ ] Invalidación: la caché es sólo para la **elección**; la ejecución (y sus
  datos frescos: clima, sistema…) siempre se re-ejecuta.

**Pruebas:** #1, #2 (2ª llamada idéntica no invoca `chat_with_tools`), #3, #6.

## C7 — Suite de latencia con presupuestos
**Rama:** `test/latencia-presupuestos`
**Archivo:** `test/test_latency.py`

- [ ] Afirmaciones (con `pytest-timeout` y medición explícita), Ollama vivo
  requerido (`skipif` si no):
  - L1 instantánea `< 0.15 s`
  - L2 parser `< 0.35 s`
  - e2e frase-de-parser (`"pon X"`, `"clima en X"`) `< 3 s`
  - agente 1 acción `< 20 s`
- [ ] Falla la CI si algún presupuesto se degrada.

**Pruebas:** #1, #2, #3, #9.

---

# FASE D — Robustez y verificación continua

## D1 — Comando `jarvis doctor`
**Rama:** `feat/jarvis-doctor`
**Archivo:** `jarvis_local/cli.py` (+ `jarvis_local/doctor.py`)

- [ ] `python -m jarvis_local.cli doctor` chequea y reporta LISTO/FALTA:
  Ollama arriba · modelos `qwen2.5:3b` y `bge-m3` presentes · red · token de
  Google Calendar · token de Spotify · micrófono detectado · `secrets.yaml`
  legible.

**Pruebas:** #1, #2 (mock de cada dependencia: presente / ausente), #3, #5.

## D2 — Tests `live` opt-in + CI nightly
**Rama:** `test/live-integracion`
**Archivos:** `test/`, `pyproject.toml`, `.github/workflows/`

- [ ] Marcar con `@pytest.mark.live` las pruebas que pegan a servicios reales
  (Open-Meteo, Wikipedia, WolframAlpha, empleo). `addopts = "-q -m 'not live'"`
  por defecto.
- [ ] Job nightly en GitHub Actions que corre `-m live`.

**Pruebas:** #1, #3 (con y sin `-m live`), #9.

## D3 — Prueba de voz e2e
**Rama:** `test/voz-e2e`
**Archivos:** `test/fixtures/`, `test/test_voice_e2e.py`

- [ ] Un WAV corto en español en `test/fixtures/` (frase conocida, p. ej.
  *"abre la calculadora"*).
- [ ] Test: STT (faster-whisper) transcribe → el texto esperado (tolerancia) →
  `Jarvis.chat()` lo enruta bien. Marcado `live` (descarga el modelo STT).

**Pruebas:** #1, #2, #3.

## D4 — README y documentación al día
**Rama:** `docs/estado-real`
**Archivo:** `README.md`, `CHANGELOG.md`

- [ ] Sustituir las latencias del README por las **medidas reales** tras las
  Fases A–C.
- [ ] Reflejar el estado real de cada feature (lo que arregló este plan).
- [ ] Quitar o corregir cualquier afirmación que ya no se cumpla (badge de
  tests, "19 s", etc.).
- [ ] `CHANGELOG.md`: entrada con el resumen de las Fases A–D.

**Pruebas:** #1, #3, y revisión de que cada afirmación del README tiene respaldo.

---

## HALLAZGOS DURANTE LA EJECUCIÓN (micro-tareas fuera de fase)

### H2 — Apps se abren más de una vez (VS Code, otros)  ✅ COMPLETADA
**Reportado por el usuario durante la ejecución.** `jarvis_local/tools/apps.py`
(`open_app` / `_open_installed_app` / `_register_opened`): al pedir abrir una
app ya lanzada, o dos veces seguidas, se abren instancias duplicadas. Debe
detectar si la app ya está corriendo (por proceso/ventana) y enfocarla en vez
de relanzar. Rama `fix/apps-doble-apertura`. Pruebas: #1, #2 (mock de
subprocess + psutil), #3, #5, #8. Encaja como micro-tarea antes de la Fase C.

### H1 — Test flaky `test_history_performance`  ✅ COMPLETADA
**Rama:** `fix/flaky-history-perf`
**Archivo:** `test/test_storage_load.py`

- [x] `assert elapsed < 5.0` reventaba de forma intermitente (visto 5,01 s) con
  la máquina cargada (`jarvis.service` + suite a la vez). No es una regresión:
  aislado corre en 0,85 s.
- [x] Reconvertido a **guarda de patología** (regresión O(n²)): techos amplios
  (`15 s` / `10 s`) con mensaje de aserción; una regresión real los supera por
  un orden de magnitud.
- [x] Además: se para `jarvis.service` mientras corre la batería de pruebas
  (recomendación del usuario) para no falsear latencias ni cargar la máquina.

---
---

## SEGUIMIENTO

| Fase | Tareas | Estado |
|------|--------|--------|
| 0 | 0.1–0.5 | ✅ completada |
| A | A1–A7 | ✅ completada |
| B | B1–B7 | ✅ completada |
| C | C1–C7 | ⬜ pendiente |
| D | D1–D4 | ⬜ pendiente |

**Total: 26 tareas.** Se ejecutan en orden. Cada una: rama → implementar →
protocolo de pruebas completo hasta verde → `push` → CI verde → merge a `main`
→ marcar `[x]`.
