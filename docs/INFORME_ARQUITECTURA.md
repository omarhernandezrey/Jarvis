# INFORME DE ARQUITECTURA Y FUNCIONALIDADES — JARVIS LOCAL

> Fecha: 2026-09-03 · Versión del repo: `v7.0.0-116-g26badee` · Rama: `main`
> Objetivo del documento: que puedas **entender JARVIS de arriba a abajo** y
> decidir cómo llevarlo a "control total de esta máquina" a nivel profesional.
>
> Hardware objetivo: Intel i5-6200U (2 núcleos / 4 hilos), 16 GB RAM, iGPU sin
> VRAM útil, Linux (Ubuntu/GNOME) + soporte Windows. Todo local, sin APIs de
> pago.

---

## 1. RESUMEN EJECUTIVO

JARVIS es un **asistente por voz y texto, 100 % local y en español**. No es un
chatbot: es un **agente con cascada de capas** que intenta resolver cada
petición por el camino más barato posible y sólo sube al modelo de lenguaje
cuando de verdad hace falta.

- **~15.600 líneas** de Python en `jarvis_local/`, **787 tests** en 51 archivos,
  `ruff` limpio, CI en GitHub Actions (Windows 3.11/3.12/3.13 + job de
  seguridad + job `live` nocturno).
- **Modelo único:** `llama3.2:3b` vía Ollama, para chat y para elegir
  herramientas (routing). `bge-m3` para memoria semántica (opcional).
  `qwen2.5:3b` queda como fallback opcional del router.
- **~60 acciones** distintas: abrir/cerrar apps, terminal, energía, ventanas,
  volumen, multimedia, capturas, archivos, clima, Wikipedia, noticias,
  calculadora, WolframAlpha, IP, calendario, correo, WhatsApp, Spotify,
  YouTube, empleo, navegador Selenium, notas, recordatorios, memoria.
- **Capa de seguridad real:** niveles de riesgo, plan→confirmación para acciones
  destructivas, whitelist de carpetas, blocklist de comandos de shell,
  redacción de secretos antes de tocar el modelo o los logs.

### Lo que ya funciona bien
Parser determinista muy afinado (frases comunes se resuelven en < 1 ms sin
LLM), tool calling nativo de Ollama con validación estricta, seguridad de
shell/rutas, voz STT+TTS local, memoria semántica, `jarvis doctor`.

### Lo que falta para "control total de la máquina" (detalle en §16)
Gestión de ventanas en Wayland, control de procesos/servicios, red/wifi,
brillo, portapapeles de escritura, entrada de teclado/ratón arbitraria,
automatización de GUI, monitorización proactiva, y una capa de **verificación
post-acción** (hoy JARVIS ejecuta y asume que funcionó).

---

## 2. CÓMO SE EJECUTA

| Interfaz | Comando | Qué es |
|---|---|---|
| **CLI** (principal) | `python -m jarvis_local.cli` | REPL de texto con comandos `/…`. El núcleo. |
| **HUD de escritorio** | `python -m jarvis_local.ui.hud` | Ventana Qt/QML (PySide6) con orbe animado, chat y voz. `scripts/jarvis.service` lo lanza como servicio de usuario systemd. |
| **Servidor web** | `python -m jarvis_local.ui.server` | HTTP local (`jarvis_local/ui/server.py`, 802 líneas) con chat + estado. |
| **Modo voz puro** | `python -m jarvis_local.voz` | Bucle de escucha continua sin interfaz. |
| **Diagnóstico** | `python -m jarvis_local.cli doctor` | Chequea Ollama, modelos, red, credenciales, micrófono, navegador. |
| **Re-autorización** | `... cli --reauth-calendar` / `--reauth-spotify` | Renovar tokens OAuth. |

**Punto de entrada lógico único:** `jarvis_local/jarvis.py` → clase `Jarvis`,
método `chat(user_input: str) -> str`. Todas las interfaces terminan llamando
ahí.

---

## 3. ARQUITECTURA: LA CASCADA

Cada mensaje entra por `Jarvis.chat()` y **baja por esta cascada, deteniéndose
en la primera capa que lo resuelve**. El coste sube en cada escalón.

```
Jarvis.chat(texto)                                   jarvis_local/jarvis.py:384
  │
  ├─ 0. NORMALIZACIÓN + SEGURIDAD DE ENTRADA
  │     · redact_secrets()   → censura contraseñas/API keys/tokens ANTES de nada
  │     · contains_secrets()  → si el mensaje trae un secreto, se BLOQUEA el envío
  │
  ├─ 1a. _exact_response()            respuestas fijas ("responde solo X" → X)
  │
  ├─ 1b. fast_respond()              fast_response.py — saludos, hora, fecha,
  │                                  gracias, "qué puedes hacer", franja del día
  │                                  → 0 LLM, < 1 ms. last_reply_kind = "fast"
  │
  ├─ 2a. _chat_encadenado()          si es multi-acción ("abre Chrome y dime la
  │                                  hora"): dividir_acciones() parte la frase y
  │                                  CADA parte vuelve a bajar la cascada entera
  │
  ├─ 2b. _parse_and_execute()        intent/parser.py → parse_intent(texto)
  │        → IntentResult(kind, tool, arguments, clarification, reason)
  │        kind ∈ {chat, tool_read, tool_execute, tool_plan, ambiguous, unsupported}
  │        · tool_read   → _READ_TOOLS[nombre](args)     (solo lectura, sin confirmar)
  │        · tool_execute→ _WRITE_TOOLS[nombre](args)    (acción, sin confirmar)
  │        · tool_plan   → _PLAN_TOOLS[nombre](args)     (crea ActionPlan → /confirmar)
  │        · ambiguous   → pide aclaración
  │        · unsupported → dice que no puede
  │        · chat        → sigue bajando
  │        last_reply_kind = "tool"
  │
  ├─ 3. _try_agent()  (si cfg.agent.enabled)     agent/loop.py → run_agent()
  │        · retriever.select_tools(frase)  → bge-m3, top-4 herramientas plausibles
  │        · si 0 herramientas plausibles  → es conversación, no gasta LLM
  │        · decision_cache.get(frase)     → frase repetida < 10 min = 0 LLM
  │        · client.chat_with_tools(msgs, tools, model=agent_model)   ← EL LLM
  │        · _salvage_tool_calls()          → si "llamó" en texto, se recupera
  │        · _validar() + _limpiar_args()   → herramienta existe, args requeridos,
  │                                            tipos con coerción; 1 reintento
  │        · registry.execute(name, args)   → ejecuta; needs_confirmation → /confirmar
  │        · decision_cache.put() + log_decision() → logs/decisions.jsonl
  │        last_reply_kind = "tool"
  │
  └─ 4. CHAT LLM DIRECTO                         ollama_client.chat(stream=True)
           · system prompt (jarvis_local/prompts/system.txt)
           · + contexto de memoria de sesión + auto-recall semántico
           · + historial (últimos N turnos)
           · respuesta en streaming, hablada mientras se genera si TTS on
           last_reply_kind = "llm"
```

**Regla de oro (PARSER-FIRST):** si el parser determinista puede resolver la
frase, el LLM **no** se invoca. El agente (capa 3) sólo entra ante lenguaje
ambiguo, varias herramientas posibles o frases que el parser no anticipó.

### Los dos "namespaces" de herramientas (importante)

Hay **dos catálogos de herramientas distintos**, con nombres distintos:

| | Capa 2 (parser) | Capa 3 (agente) |
|---|---|---|
| Dónde | `jarvis.py` dicts `_READ_TOOLS` (19), `_WRITE_TOOLS` (41), `_PLAN_TOOLS` (10) | `agent/registry.py` — `TOOLS: list[Tool]` (46) |
| Nombres | `open_app`, `weather`, `run_command`, `system_status`… (inglés) | `abrir_aplicacion`, `clima`, `ejecutar_comando`… (español) |
| Formato | `lambda args: modulo.funcion(args.get(...))` | `Tool(name, description, JSON-Schema, run, needs_confirmation)` |
| Quién elige | reglas regex del parser | el LLM vía tool calling nativo de Ollama |

Ambos terminan llamando a las **mismas funciones** en `jarvis_local/tools/*.py`.
Esta duplicación de catálogos es deuda técnica: cada herramienta nueva hay que
darla de alta en dos sitios. (Ver §16, mejora "catálogo único").

---

## 4. COMPONENTES EN DETALLE

### 4.0 Normalización y seguridad de entrada — `safety/secrets.py`
- `redact_secrets(text) -> (texto, nº)` — regex sobre patrones tipo
  `password=…`, `api_key: …`, tokens tipo `sk-…`, bearer, etc. Reemplaza por
  `[REDACTED]`. Se aplica **antes** de logs y antes de mandar nada al modelo.
- `contains_secrets(text)` — si el usuario pega un secreto, `chat()` corta y
  responde "he detectado información sensible… no la he enviado al modelo".

### 4.1 Capa 1 — respuestas instantáneas — `fast_response.py` (137 líneas)
- `_exact_response()` en `jarvis.py`: "responde solo `<X>`" → `X` literal.
- `fast_respond(m)`: regex compiladas como constantes. Cubre saludos (con
  detección de franja: "buenas noches" a las 3 pm saluda de noche, no según el
  reloj), hora, fecha, día de la semana, "gracias", "adiós", "quién eres",
  "qué puedes hacer". Devuelve `str` o `None`. **0 dependencias de red/LLM.**
- Presupuesto: < 100 ms (se verifica en `test/test_latency.py`).

### 4.2 Capa 2 — parser determinista — `intent/parser.py` (1214 líneas)
El módulo más grande y afinado. `parse_intent(message) -> IntentResult`:

1. `_sin_tildes()` — los patrones son ASCII (el dictado trae acentos).
2. `es_multi_accion()` → si hay "y"/"luego"/"después" entre acciones → delega al
   agente (que encadena).
3. `es_anaforica()` → "y en Bogotá?", "abre la segunda" → delega al agente
   (tiene el contexto).
4. Cadena de bloques, **en orden de prioridad** (el orden importa: "borra el
   recordatorio 2" no debe caer en "borrar archivo"):
   `_parse_fase5` (empleo, navegador) → `_parse_reminder` → `_parse_media`
   (volumen/multimedia) → `_parse_power` (energía) → ventanas → `_parse_whatsapp`
   → leer en voz alta → resumen del día → `_parse_fase4` (clima, web, sistema,
   wiki, correo, calculadora, ubicaciones, notas, captura…) → wikipedia →
   cerrar app → abrir app → listar/buscar/crear/borrar archivos.
5. Si nada matchea → `IntentResult(kind="chat")` y sigue bajando.

`IntentResult` (`intent/schemas.py`): `kind, tool, arguments, clarification,
reason`.

**Estado:** muy robusto tras el `PLAN_MAESTRO` (fases A–D): clima natural,
"pon `<canción>`", notas, multi-acción, calculadora (`%`, raíz, potencias,
ecuaciones lineales con solver propio), ubicaciones con Nominatim, saludo por
franja. Batería `test/test_parser_coverage.py` (114 casos).

### 4.3 Capa 3 — el agente — `agent/`

| Archivo | Rol |
|---|---|
| `retriever.py` (308) | **Tool-RAG.** Embebe la descripción de cada herramienta con `bge-m3` y recupera las `TOP_K=4` más parecidas por coseno. Da una señal de confianza: bajo `UMBRAL_MINIMO=0.42` → es conversación, ni se invoca el LLM. Si no hay embeddings → cae a `selector.py` (léxico). Motivo: un 3B razonando sobre 46 esquemas tarda 1–2 min y elige mal; con ≤4, ~15 s y acierta. |
| `selector.py` (161) | Selector léxico de respaldo (palabras clave → herramientas). |
| `loop.py` (471) | **El bucle.** `run_agent(client, msg, history)` → `_run_simple` o `_run_encadenado`. `MAX_STEPS=2`, `MAX_STEPS_ENCADENADO=4`, `MAX_REINTENTOS=1`, `AGENT_TIMEOUT=30 s`. Valida cada tool call, reintenta 1 vez con mensaje de corrección, rescata tool calls escritos como texto (`_salvage_tool_calls`), registra todo. |
| `registry.py` (749) | **Catálogo del agente.** 46 `Tool`. `execute(name, args)` filtra args inventados, valida/coacciona tipos, comprueba requeridos, captura excepciones (nunca traceback al usuario), gestiona `needs_confirmation`. |
| `prompts.py` | `AGENT_SYSTEM_PROMPT` con 8 ejemplos few-shot (cada uno era un fallo real de la batería de eval). `CONTEXT_HINT` para anáforas. Mensajes de corrección. |
| `decision_cache.py` | `frase normalizada → (herramienta, args)`, TTL 600 s, máx 128. Sólo cachea la **elección**, la ejecución siempre se rehace (datos frescos). |
| `decision_log.py` | Escribe `logs/decisions.jsonl`: entrada, confianza, herramientas, salidas, resultado, `llm_calls`, `llm_secs`. Base de la observabilidad. |

`ollama_client/client.py` (323): HTTP a Ollama (`httpx` con fallback a
`requests`). `chat()` (streaming real) y `chat_with_tools()` (tool calling
nativo: POST `/api/chat` con `tools`, lee `message.tool_calls`). Parámetros por
config: `num_ctx`, `num_predict`, `keep_alive` (30m — evita ~10 s de recarga),
`agent_num_predict: 60` (el router elige, no redacta).

### 4.4 Capa 4 — chat LLM directo
`jarvis.py:chat()` final: arma `system.txt` + memoria de sesión + auto-recall
semántico + historial, y hace `client.chat(stream=True)`. La respuesta se habla
token a token si TTS está activo (`voice/streaming.py`).

---

## 5. INVENTARIO COMPLETO DE FUNCIONALIDADES

Estado: ✅ funciona · ⚠️ funciona con límites · 🔴 roto / no implementado.
Riesgo: nivel de `RiskLevel` que le asigna la capa de seguridad.

### 5.1 Control de la máquina

| Acción | Archivo | Implementación | Linux | Windows | Riesgo | Estado |
|---|---|---|---|---|---|---|
| Abrir app por nombre | `tools/apps.py` (491), `tools/app_index.py` (255) | Índice de apps instaladas: escanea `.desktop` (+ Snap/Flatpak) en Linux, `Get-StartApps` en Windows. Búsqueda difusa + sinónimos. Antes de lanzar comprueba si ya está abierta (`_ya_esta_abierta` vía psutil) y la enfoca (`wmctrl -a`, sólo X11). | ✅ | ✅ | EXECUTE | ✅ |
| Cerrar app / cerrar todas | `tools/apps.py` | `close_app` mata por nombre de proceso; `close_all_apps` cierra sólo lo que JARVIS abrió esta sesión (registro en memoria). | ✅ | ✅ | EXECUTE | ✅ |
| Ejecutar comando de terminal | `tools/terminal.py` (118) | `execute_command`: rechaza metacaracteres de shell, corre `subprocess.run` con `shell=False`, timeout, captura stdout. Blocklist en `safety/permissions.py` (defensa en profundidad en `registry._run_command`). PowerShell en Windows, bash en Linux. | ✅ | ✅ | EXECUTE (plan si viene del agente) | ✅ |
| Energía: bloquear / apagar / reiniciar / suspender / cancelar | `tools/power.py` (146) | Bloqueo: `loginctl lock-session` (Linux) / `LockWorkStation` (Win). Apagar/reiniciar: `sudo -n shutdown` (Linux, **requiere sudoers sin contraseña**) / `shutdown` (Win), con 60 s cancelables. Suspender: `systemctl suspend`. | ⚠️ (apagar necesita sudoers) | ✅ | EXECUTE | ⚠️ |
| Estado del sistema (CPU/RAM/disco/batería) | `tools/system_info.py` | `psutil`. | ✅ | ✅ | READ | ✅ |
| Volumen (subir/bajar/mute/fijar nivel) | `tools/media_controls.py` (339) | Linux: `wpctl` (PipeWire nativo, lee y fija nivel real). Windows: WASAPI vía `ctypes`/`comtypes`. | ✅ | ✅ | EXECUTE | ✅ |
| Multimedia (play/pausa/siguiente/anterior) | `tools/media_controls.py` | Linux: `playerctl` (MPRIS). Windows: teclas multimedia virtuales. | ✅ | ✅ | EXECUTE | ✅ |
| Captura de pantalla | `tools/desktop_actions.py` (268) | Linux: portal de escritorio `org.freedesktop.portal.Screenshot` vía D-Bus (evita el fallback X11 roto de `gnome-screenshot`). Windows: PIL `ImageGrab`. Guarda PNG en `Imágenes/Capturas JARVIS`. | ✅ | ✅ | CREATE | ✅ |
| Minimizar todo / snap ventana / Alt-Tab | `tools/desktop_actions.py` | **Sólo Windows** (API `user32`). En Wayland devuelve "no soportado" con mensaje honesto. | 🔴 Wayland | ✅ | EXECUTE | ⚠️ |
| Reproducir música local | `tools/desktop_actions.py` | Busca en `~/Música`, abre con `xdg-open` / asociación de Windows. | ✅ | ✅ | EXECUTE | ✅ |
| Leer portapapeles en voz alta | `tools/reader.py` (164) | `xclip` (Linux) / `ctypes` (Win) → TTS. **Sólo lectura**, no escribe en el portapapeles. | ✅ | ✅ | READ | ⚠️ (falta escribir) |

### 5.2 Archivos — `tools/files.py` (309) + `tools/hidden_files.py`

| Acción | Riesgo | Estado |
|---|---|---|
| Listar / buscar archivos | READ | ✅ |
| Metadatos de archivo | READ | ✅ |
| Crear archivo / carpeta | CREATE | ✅ |
| Copiar / mover / renombrar | CREATE | ✅ |
| Borrar archivo | DELETE → **plan + `/confirmar`** | ✅ |
| Ocultar / mostrar archivos de una carpeta | DELETE → **plan + `/confirmar`** | ✅ |

Todo validado contra la **whitelist de carpetas** (`safety/permissions.py::is_within_allowed`):
sólo Documentos, Descargas, Escritorio, Música, Imágenes, Vídeos, con
protección contra `../` y symlinks. `_validate_filename` rechaza nombres
reservados de Windows (`CON`, `PRN`, `NUL`…).

### 5.3 Web e información

| Acción | Archivo | Implementación | Estado |
|---|---|---|---|
| Clima de cualquier ciudad | `tools/weather.py` | Open-Meteo (sin API key). Geocodifica la ciudad. | ✅ |
| Ubicación / distancia | `tools/location.py` | Geocodifica con Nominatim/OSM (POIs, monumentos) → si no hay match abre Google Maps. Calcula distancia desde tu IP. Nunca dice "no encontré". | ✅ |
| Wikipedia | `tools/wiki.py` | API REST de Wikipedia ES, resumen. | ✅ |
| Noticias | `tools/news.py` | Titulares (RSS). | ⚠️ (depende de la fuente) |
| Calculadora | `tools/calculator.py` (230) | AST seguro (sin `eval`). Lenguaje natural: `%`, `raíz cuadrada de`, `al cubo`, potencias. Ecuaciones lineales de una incógnita con **solver propio** (no SymPy). | ✅ |
| WolframAlpha | `tools/wolfram.py` | Para lo que no resuelve en local (derivadas, sistemas). Requiere `app_id` en `secrets.yaml`. | ⚠️ (opcional) |
| IP pública y local | `tools/ip_info.py` | `ifconfig.me` + interfaces locales. | ✅ |
| Abrir web / buscar en Google / reproducir en YouTube | `tools/web.py` | `webbrowser.open` con validación de esquema (sólo http/https, bloquea `javascript:`/`data:`). | ✅ |

### 5.4 Productividad

| Acción | Archivo | Implementación | Estado |
|---|---|---|---|
| Notas rápidas | `tools/notes.py` | Guarda `.txt` con fecha/hora y lo abre en el bloc de notas. | ✅ |
| Recordatorios / alarmas | `tools/reminders.py` (218) | Persistencia en JSON, hilo temporizador, suena + habla a la hora. Por minutos o por hora exacta. Listar / cancelar por número o texto. | ✅ |
| Google Calendar | `tools/gcalendar.py` | OAuth. Refresca token solo; si el refresh token está muerto → `ReauthRequired` con mensaje accionable (`--reauth-calendar`). **Sólo lectura de próximos eventos** (no crea eventos). | ⚠️ |
| Enviar correo | `tools/email_sender.py` | SMTP (Gmail app password). **Siempre plan + `/confirmar`.** | ⚠️ (opcional) |
| WhatsApp | `tools/whatsapp.py` (156) | Abre WhatsApp Web/Desktop con el mensaje escrito; el usuario pulsa enviar. Agenda de contactos en JSON. | ✅ |
| Resumen del día | `tools/briefing.py` | Fecha + clima + agenda + titulares en una respuesta. | ✅ |
| Chistes | `tools/jokes.py` | Lista local. | ✅ |

### 5.5 Empleo y navegador automatizado

| Acción | Archivo | Implementación | Estado |
|---|---|---|---|
| Buscar vacantes | `tools/jobs.py` (372) | Scraping de Computrabajo + LinkedIn en paralelo, ordena por recientes, dedup, filtra ruido. | ⚠️ (frágil ante cambios de los portales) |
| Abrir oferta N / mostrar portales | `tools/jobs.py`, `tools/browser.py` (152) | Abre en el navegador. El Empleo sólo se abre (su HTML no es scrapeable). | ⚠️ |
| Navegador Selenium | `tools/browser.py` | Chrome controlado por JARVIS (`navigate`, `close_browser`). `atexit` lo cierra. | ⚠️ (poco usado) |

### 5.6 Memoria (ver §7)

| `recordar <dato>` → memoria permanente | `storage/memory.py` + `storage/semantic.py` | ✅ |
| Recuerdo automático por significado | `memory_context/recall.py` | ✅ (si `bge-m3` está) |

---

## 6. VOZ — `jarvis_local/voice/`

| Módulo | Rol |
|---|---|
| `stt.py` (539) | **Speech-to-Text** con `faster-whisper` (modelo `small`, `int8`, CPU). Singleton del modelo. `capture_and_transcribe()` graba del micro con VAD; `transcribe_file(path)` transcribe un WAV (usado por la prueba e2e). Calibración de ruido, diagnóstico. |
| `tts.py` (303) | **Text-to-Speech** con `edge-tts` (voz neural `es-MX-JorgeNeural`, requiere internet). Caché en `data/tts_cache`. Respaldo offline: SAPI5 (Win) / espeak-ng (Linux) — configurable, por defecto se queda en silencio si la voz neural falla. |
| `streaming.py` | Habla la primera frase mientras el modelo sigue generando (baja la latencia percibida). |
| `continuous.py` (368) | **Modo manos libres.** Wake word "Jarvis" (regex sobre variantes de transcripción: "jarvis", "yarvis", "charvis"…), máquina de estados (escuchando wake / capturando orden / procesando), fusión de fragmentos, timeout de silencio. |
| `audio_devices.py` | Enumera micrófonos. |
| `voz.py` (raíz, 174) | Modo voz puro sin interfaz: ciclos de 4 s, Whisper decide si hubo habla. |

**No hay wake word con modelo dedicado** (Porcupine/openWakeWord): se detecta la
palabra "jarvis" **después** de transcribir con Whisper. Funciona pero gasta STT
en cada ciclo.

---

## 7. MEMORIA — tres sistemas

| Sistema | Archivo | Qué guarda | Persistencia |
|---|---|---|---|
| **Historial de conversación** | `memory/history.py`, `storage/history.py` (131) | Últimos N turnos (config `max_history: 20`). Se restaura al arrancar. | `data/history.json` |
| **Memorias permanentes** | `storage/memory.py` | Datos que el usuario pide recordar ("soy alérgico a los mariscos"). `add/list/delete/clear`. Versionado de esquema + limpieza de archivos corruptos. | `data/memories.json` |
| **Índice semántico** | `storage/semantic.py` (201) | Embeddings `bge-m3` de cada memoria. `sync()` + `search(query, top_k)`. Si no hay embeddings → `keyword_scores` (Jaccard de palabras). | `data/semantic_index.json` |
| **Memoria de sesión** | `memory_context/session.py` | Memorias "activadas" manualmente para el contexto de esta sesión. | en RAM |
| **Auto-recall** | `memory_context/recall.py` | Antes de cada turno de chat, busca las memorias relevantes al mensaje y las inyecta como contexto **marcadas como datos, no instrucciones** (defensa anti prompt-injection). | — |

**Límite conocido:** la memoria semántica no tiene aún una prueba e2e que
verifique "recuerda X" → (reinicio) → "¿cuál es X?" (está en el plan como FASE
13).

---

## 8. CAPA DE SEGURIDAD — `jarvis_local/safety/`

### `policy.py` (228)
- `RiskLevel`: `NONE(0) < READ(1) < CREATE(2) < EXECUTE(3) < DELETE(4) < CRITICAL(5)`.
- `ActionStatus`: `PLANNED · CONFIRMED · EXECUTED · REJECTED · BLOCKED · ERROR`.
- `ActionPlan` (dataclass): `action, params, paths_affected, risk, reason,
  simulation_result, status, result, error, timestamp`. Es el objeto que
  devuelven casi todas las herramientas; `.result` es el texto para el usuario.
- `SafetyPolicy`: `pending_plan`, `confirm()` / `auto_confirm()` / `reject()`,
  `simulate()` (modo simulación), `execute_plan(plan, executor_fn)`,
  `block(reason)`. Riesgo ≥ DELETE **exige confirmación explícita**, nunca
  auto-confirma.

### `permissions.py` (283)
- `BLOCKED_COMMAND_PATTERNS` (regex): `.ps1/.bat/.cmd`, `Invoke-Expression`,
  `rm -rf`, `rm -r`, bomba fork `:(){ :|:& };:`, `curl … | sh`,
  `systemctl poweroff/reboot`, `> /dev/sd*`, `chmod -R 777 /`, `format`,
  `diskpart`, `reg add/delete`, `schtasks /create`, `takeown`, `icacls`…
- `BLOCKED_CMD_KEYWORDS` (token completo, cualquier orden de argumentos):
  `del, rmdir, rd, format, diskpart, reg, schtasks, taskkill, shutdown, rm,
  remove-item, restart-computer, stop-computer, stop-process, set-acl, sudo,
  dd, mkfs, passwd, userdel, visudo, iptables, ufw, crontab`.
- `is_within_allowed(path)` — whitelist de carpetas con `resolve()` +
  `relative_to()` (anti path-traversal).
- `is_command_blocked(command) -> (bool, motivo)`.

### `secrets.py` — redacción (ver §4.0). `logger.py` — `logs/actions.log`
(toda acción), `logs/errors.log`.

**El modelo NUNCA ejecuta acciones destructivas por su cuenta.** Borrar, ocultar
y enviar correo pasan siempre por `ActionPlan` → `/confirmar`.

---

## 9. CONFIGURACIÓN

| Archivo | Contenido |
|---|---|
| `config.yaml` | `ollama` (host, `model`, `agent_model`, `router_fallback`, `num_ctx`, `num_predict`, `keep_alive`, `agent_num_ctx`, `agent_num_predict`, `timeout`), `agent` (enabled, timeout, max_steps), `hud` (frameless, agent), `jarvis` (language, max_history), `memory.auto_recall`, `safety` (allowed_apps, allowed_folders, simulation_mode), `voice` (stt_*, tts_*), `logging`. |
| `secrets.yaml` | (gitignored) email SMTP, WolframAlpha app_id, Spotify client_id/secret. |
| `credentials.json` / `token.json` | (gitignored) OAuth Google Calendar. |

`jarvis_local/config.py` (166): `ConfigManager` singleton, `DEFAULT_CONFIG` +
merge profundo de `config.yaml` + **overrides por entorno**
(`JARVIS_AGENT_MODEL`, `JARVIS_CHAT_MODEL`). `get_config()`, `get_secrets()`,
`user_dir(kind)` (resuelve Documentos/Descargas/… según SO e idioma).

---

## 10. MODELOS

| Rol | Modelo | Notas |
|---|---|---|
| Chat + routing (agente) | **`llama3.2:3b`** | Modelo único. 10/12 en la batería de routing, ~19,5 s/decisión en esta CPU. |
| Fallback del router (opcional) | `qwen2.5:3b` | Empata en precisión, ~10 % más lento. Sólo se usaría ante fallo técnico del modelo (aún **no cableado** — FASE 12 del plan). |
| Memoria semántica | `bge-m3` | Embeddings multilingües. Opcional (sin él, memoria por palabras). |
| STT | `faster-whisper small int8` | Local, CPU. |
| Descartado | `hermes3:3b` | Evaluado (FASE 9): **1/12** en routing — no emite `tool_calls` fiables en el 3B. `ollama rm hermes3:3b` hecho. Evidencia en `docs/AUDITORIA_2026-09.md §7`. |

---

## 11. INTERFACES

- **CLI** (`cli.py`, 806): REPL. Comandos: `/ayuda`, `/memoria guardar|buscar|listar|activar`,
  `/voz on|off|continuo`, `/apps`, `/archivos`, `/terminal`, `/plan`,
  `/confirmar`, `/cancelar`, `/ui`, `/desktop`, `doctor`, `salir`.
- **HUD** (`ui/hud/`): PySide6 + QML. `app.py`, `viewmodel.py`, `chat_service.py`,
  `voice_service.py`, `conversation_model.py`, shaders del orbe. Servicio
  systemd de usuario (`scripts/jarvis.service`).
- **Servidor web** (`ui/server.py`, 802): `ThreadingHTTPServer`, HTML embebido,
  endpoints de chat/estado/voz.
- **Dashboard** (`ui/dashboard.py`).

---

## 12. OBSERVABILIDAD Y EVALUACIÓN

- `logs/decisions.jsonl` — una línea por decisión del agente (`llm_calls`,
  `llm_secs`, herramientas, resultado). **La fuente para entender por qué algo
  tardó.**
- `logs/actions.log` / `logs/errors.log`.
- `jarvis_local/eval/` — `cases.py` (batería de casos de routing), `harness.py`,
  `run_eval.py`. Mide acierto de selección de herramienta.
- `scripts/bench_agente.py` — latencia del agente en un set fijo.
- `scripts/bench_router_modelos.py` — compara modelos de routing (acierto +
  latencia + JSON válido).
- `jarvis_local/doctor.py` — diagnóstico (Ollama, modelos + capacidad `tools`,
  red, secrets, Calendar, Spotify, micrófono, navegador). `OK / ~~ / FALTA`.

---

## 13. TESTS Y CI

- **787 tests** en 51 archivos. `pytest`, `-p no:randomly`,
  `QT_QPA_PLATFORM=offscreen`. Marcadores `live` (APIs reales, opt-in) y `slow`.
- Cuirk del entorno: la suite completa a veces no imprime el resumen por un
  fallo de Qt en el teardown → se corre `test --ignore=test/test_ui_hud.py` +
  `test/test_ui_hud.py` aparte; criterio = 0 `FAILED`/`ERROR`.
- CI (`.github/workflows/tests.yml`): matriz Windows 3.11/3.12/3.13 · `ruff` ·
  job de seguridad (`bandit`, `pip-audit`, verificación de que no haya
  credenciales versionadas) · job `live` nocturno (cron `17 3 * * *`).

---

## 14. CÓDIGO MUERTO / STUBS (candidatos a completar o borrar)

| Módulo | Estado | Comentario |
|---|---|---|
| `jarvis_local/vision/` | **Escrito pero no conectado.** `capture_screenshot`, `describe_screen` (OCR con `pytesseract`), `vision_available`. Nadie lo importa. | Base para "que JARVIS vea la pantalla". |
| `jarvis_local/proactive/` | **Escrito pero no conectado.** `ProactiveEngine.get_suggestions()` con reglas por hora/día. | Base para proactividad. |
| `jarvis_local/plugins/` | `__init__.py` (84) + `hello_plugin.py` de ejemplo. No hay carga real de plugins en el flujo. | Sistema de extensiones a medio hacer. |
| `jarvis_local/profiles.py` (57) | Perfiles de usuario. Sin uso claro. | |
| `jarvis_local/performance.py` (71) | Utilidades de medición. Uso parcial. | |

---

## 15. RENDIMIENTO MEDIDO (i5-6200U, Ollama caliente)

| Capa | Ejemplo | Latencia |
|---|---|---|
| 1 · instantánea | "qué hora es" | < 1 ms |
| 2 · parser (enrutado puro) | "abre whatsapp" | ~0,2 ms |
| 2 · parser → tool con red | "clima en Cali" | ~1,6 s |
| 3 · agente (una decisión + tool) | frase que el parser no cubre | **19–70 s** |
| 4 · chat directo | conversación | ~1,5 s (caliente) / ~60 s (frío) |

El cuello de botella es **el 3B haciendo tool calling en CPU de 2 núcleos**. Eso
no se arregla por software; se mitiga **manteniendo frases fuera del agente**
(el trabajo del `PLAN_MAESTRO`): "va a llover en Cartagena" pasó de ~90 s
(agente) a ~1,5 s (parser).

---

## 16. ANÁLISIS DE BRECHAS — HACIA EL "CONTROL TOTAL DE LA MÁQUINA"

Ordenado por **valor / esfuerzo**. Prioridad declarada: FIABILIDAD > SEGURIDAD >
ESTABILIDAD > RECURSOS > LATENCIA > CAPACIDAD.

### A. Fiabilidad (lo que más falta hoy)

1. **Verificación post-acción (VERIFY).** Hoy JARVIS ejecuta y asume éxito.
   Falta: tras `open_app` comprobar que el proceso existe; tras `create_file`
   comprobar que el archivo está; tras `volume_set` releer el nivel. Diseño:
   cada `Tool` declara un `verify: Callable` opcional; si falla → **1**
   recuperación → reverificar → si sigue mal, decirlo con honestidad. Límite
   duro: 1 recuperación, sin bucles. *(FASE 10–11 del plan activo.)*
2. **Catálogo único de herramientas.** Unificar los dos namespaces (parser vs
   agente) en una sola estructura con nombre, schema, ejecutor, riesgo,
   timeout, verificador. Elimina la doble alta y las discrepancias.
3. **Structured Output real.** Usar el parámetro `format` (JSON Schema) de
   Ollama para el routing en vez de sólo tool calling + rescate de texto. Más
   determinista con modelos pequeños. *(FASE 6 del plan.)*
4. **Fallback de modelo cableado.** `router_fallback` está en config pero no se
   usa. Cablearlo: 1 intento primario + 1 fallback ante fallo **técnico** del
   modelo (no ante fallo de herramienta). *(FASE 12.)*

### B. Control de máquina que falta (capacidad)

| Capacidad | Hoy | Qué haría falta |
|---|---|---|
| **Ventanas en Wayland** | 🔴 sólo Windows | Extensión de GNOME Shell + D-Bus, o `gdbus`/`wlrctl` según compositor. Mover, redimensionar, listar, enfocar, cerrar ventanas. |
| **Gestión de procesos** | parcial (`close_app` por nombre) | Listar procesos (psutil ya está), matar por PID con confirmación, ver uso por proceso, "¿qué está comiendo la RAM?". |
| **Servicios systemd** | 🔴 | `systemctl --user status/start/stop` de servicios en whitelist. |
| **Red / WiFi** | 🔴 | `nmcli`: listar redes, conectar, ver IP/estado, activar/desactivar. |
| **Brillo de pantalla** | 🔴 | `brightnessctl` / `gdbus` al portal. |
| **Bluetooth** | 🔴 | `bluetoothctl`. |
| **Portapapeles: escribir** | 🔴 (sólo lee) | `xclip -selection clipboard` / `wl-copy`. "copia esto al portapapeles". |
| **Teclado/ratón sintético** | 🔴 | `ydotool` (Wayland) / `xdotool` (X11) / `pyautogui`. Peligroso — whitelist estricta + confirmación. |
| **Automatización de GUI / "haz clic en X"** | 🔴 | Requiere visión (OCR + detección de elementos) + `ydotool`. El módulo `vision/` es la semilla. |
| **Monitor de recursos activo** | 🔴 | El HUD podría mostrar CPU/RAM/temperatura en vivo (hay hooks en `ui/hud/services.py`). |
| **Notificaciones de escritorio** | 🔴 | `notify-send` / portal. Para recordatorios y proactividad. |
| **Gestión de archivos ampliada** | whitelist estricta | Permitir (con confirmación y fuera de whitelist) operaciones puntuales: "comprime esta carpeta", "busca en todo el disco". |
| **Instalar/actualizar software** | 🔴 | `apt`/`flatpak` en modo consulta + confirmación para instalar. Alto riesgo. |
| **Calendar: crear/editar eventos** | 🔴 (sólo lee) | La API de Google ya está integrada; añadir `events().insert`. |

### C. Estabilidad y recursos

5. **Un solo modelo residente.** Con `model` y `agent_model` iguales
   (`llama3.2:3b`) ya no hay 2 modelos 3B en RAM a la vez. Verificar con
   `ollama ps` bajo `keep_alive`. Documentar el pico de RAM real.
6. **Detección de bucles del agente** (misma herramienta + mismos args + mismo
   resultado → STOP). Parcialmente cubierto por `MAX_STEPS`; falta la
   comprobación explícita de repetición.
7. **Batería de estabilidad** (10 → 20 turnos secuenciales midiendo RAM/CPU/
   procesos huérfanos, con corte de emergencia). *(FASE 15.)*
8. **Métricas agregadas** desde `decisions.jsonl`: `routing_accuracy`,
   `tool_success_rate`, `avg_latency`, `p95`, `llm_calls/turn`, `fallback_rate`,
   `recovery_rate`. Un `scripts/metricas.py` que las calcule.

### D. Capacidades "inteligentes"

9. **Visión de pantalla** (`vision/`): conectar `describe_screen` como
   herramienta read-only ("¿qué hay en mi pantalla?", "lee el error"). OCR con
   `pytesseract` (ya contemplado).
10. **Proactividad** (`proactive/`): sugerencias por hora/contexto en el HUD,
    opt-in, sin interrumpir.
11. **Wake word dedicada** (openWakeWord / Porcupine) para no gastar Whisper en
    cada ciclo del modo continuo.
12. **Plugins reales**: cargar `jarvis_local/plugins/*.py` que registren
    herramientas nuevas sin tocar el core.

---

## 17. HOJA DE RUTA PROFESIONAL SUGERIDA

Método (el que ya se sigue): **una rama por tarea → protocolo de pruebas
completo (`ruff` + unit nuevos + regresión 0 fallos + cobertura ≥ 90 % + e2e con
Ollama vivo + latencia + seguridad) → merge a `main`**. Nunca marcar hecho sin
la batería en verde. Parar `jarvis.service` durante las pruebas, `nice -19`, un
modelo residente a la vez.

### Fase I — Robustez del núcleo (fiabilidad primero)
1. Catálogo único de herramientas (unificar parser/agente).
2. VERIFY + RECOVERY (×1) en el bucle del agente y en `_parse_and_execute`.
3. Structured Output (`format` JSON Schema) para el routing.
4. Fallback de modelo cableado + `decision_log` con `modelo`/`fallback`.
5. Detección explícita de bucles.

### Fase II — Cobertura de "control de máquina" (Linux/Wayland)
6. Ventanas en Wayland (extensión GNOME + D-Bus) — la brecha más visible.
7. Procesos: listar / matar por PID (confirmación) / "qué consume recursos".
8. Red (`nmcli`), brillo (`brightnessctl`), bluetooth (`bluetoothctl`),
   notificaciones (`notify-send`), portapapeles de escritura.
9. Servicios systemd de usuario (whitelist).
10. `power.py`: documentar/instalar la regla sudoers para apagar/reiniciar, o
    usar el portal de logind.

### Fase III — Inteligencia y percepción
11. Visión de pantalla como herramienta read-only (`vision/` → registry).
12. Wake word dedicada.
13. Proactividad opt-in en el HUD.
14. Memoria: crear eventos en Calendar; prueba e2e de recall.

### Fase IV — Observabilidad y calidad
15. `scripts/metricas.py` (agregados de `decisions.jsonl`).
16. Batería adversarial (typos, órdenes sin objeto) y de estabilidad.
17. Batería por herramienta (happy path · input inválido · falta input · red
    caída · timeout · excepción · respuesta malformada — nunca traceback).
18. Informe final con números reales (benchmark, p95, RAM, CPU, accuracy,
    fallback rate).

### Principios que NO se tocan
- Local, gratis, sin claves nuevas, sin APIs de IA de pago.
- Nada de modelos ≥ 8B.
- La capa de seguridad no se debilita: toda acción nueva declara su
  `RiskLevel`; DELETE/CRITICAL siempre `/confirmar`.
- Cada arreglo lleva su test que lo blinde. Cero regresiones.

---

## APÉNDICE — MAPA DE ARCHIVOS CLAVE

```
jarvis_local/
├── jarvis.py            (586)  Orquestador. Jarvis.chat(). Los 3 dicts de tools del parser.
├── cli.py               (806)  REPL + comandos /…
├── fast_response.py     (137)  Capa 1
├── config.py            (166)  ConfigManager, env overrides, user_dir()
├── doctor.py            (182)  Diagnóstico del entorno
├── intent/
│   ├── parser.py        (1214) Capa 2 — parse_intent + bloques
│   └── schemas.py              IntentResult
├── agent/
│   ├── loop.py          (471)  Bucle del agente, validación, rescate, límites
│   ├── registry.py      (749)  46 Tool + execute()
│   ├── retriever.py     (308)  Tool-RAG con bge-m3
│   ├── selector.py      (161)  Selector léxico de respaldo
│   ├── prompts.py              System prompt + few-shot
│   ├── decision_cache.py       Caché de decisión (TTL 600 s)
│   └── decision_log.py         logs/decisions.jsonl
├── ollama_client/client.py (323) HTTP a Ollama (chat + chat_with_tools)
├── safety/
│   ├── policy.py        (228)  RiskLevel, ActionStatus, ActionPlan, SafetyPolicy
│   ├── permissions.py   (283)  Blocklists de comandos + whitelist de carpetas
│   └── secrets.py              Redacción de secretos
├── tools/              (24 archivos)  Implementación real de cada acción
├── voice/
│   ├── stt.py           (539)  faster-whisper
│   ├── tts.py           (303)  edge-tts
│   ├── continuous.py    (368)  Modo manos libres + wake word
│   └── streaming.py            Habla mientras genera
├── storage/            history · memory · semantic
├── memory_context/     session · recall (auto-recall)
├── ui/                 hud/ (Qt/QML) · server.py (web) · dashboard.py
├── eval/               Batería de evaluación de routing
├── vision/             ⚠️ escrito, sin conectar
├── proactive/          ⚠️ escrito, sin conectar
└── plugins/            ⚠️ a medio hacer
```

**Documentos relacionados:** `PLAN_MAESTRO.md` (eficacia — completo),
`PLAN_HERMES.md` (evaluación de Hermes + hardening — en curso),
`docs/AUDITORIA_2026-09.md` (auditoría con medidas ANTES/DESPUÉS),
`docs/AUDITORIA_ROUTER.md` (análisis del router), `README.md`, `CHANGELOG.md`.
