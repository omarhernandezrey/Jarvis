# ARQUITECTURA — Capa de presentación (FASE 0, solo lectura)

> Mapa del sistema actual como base para el rediseño de la vista.
> Cero cambios de código. Complementa a `docs/architecture.md` (visión de producto
> y cascada de 4 capas); este documento se centra en **la vista y su frontera con
> el núcleo**.

---

## 1. Framework GUI, punto de entrada, árbol de módulos

### Vistas que existen hoy (tres, independientes)

| Módulo | Stack | Líneas | Entrada | Rol |
|---|---|---|---|---|
| `jarvis_local/ui/desktop.py` | **Tkinter** (stdlib) + `tkinter.Canvas` | 1352 | `python -m jarvis_local.cli` → `/desktop` → `desktop.main()` | Vista principal. HUD "arc-reactor". |
| `jarvis_local/ui/server.py` | `http.server.ThreadingHTTPServer` (stdlib) + HTML/JS/Canvas2D servido inline, se abre en el navegador del sistema | 797 | `/ui` → `server.main()` (puerto 8080, token de sesión) | Vista web alternativa "estilo Iron Man". |
| `jarvis_local/ui/dashboard.py` | `http.server.HTTPServer` (stdlib) + HTML estático | 99 | `python -m jarvis_local.ui.dashboard` (puerto 8081) | Huérfano: no está cableado en `cli.py`. Métricas de relleno (`"31+"`, `"Variable"`). |

No hay **PySide6 / PyQt5 / PyQt6 / pywebview / Qt** instalados en el `.venv`
(ver §7). La única GUI nativa hoy es Tkinter.

### Punto de entrada real

`jarvis_local/cli.py` (bucle REPL de texto). El subcomando `/desktop`
(líneas ~712-720) hace `from jarvis_local.ui.desktop import main as desktop_main; desktop_main()`.
`desktop.main()` (desktop.py:1341) llama a `_get_jarvis()` (construye `Jarvis()`
de forma **eager**, imprime "Ollama: CONECTADO") y luego `JarvisDesktop().run()`
(`self.root.mainloop()`).

### Árbol de módulos relevante para la vista

```
jarvis_local/
  cli.py                 # REPL; lanza /desktop y /ui
  jarvis.py              # Jarvis: orquestador. chat(str) -> str (bloqueante)
  config.py              # get_config() -> dict (cache singleton). config.yaml
  ui/
    desktop.py           # JarvisDesktop (Tk). Objetivo del rediseño.
    server.py            # vista web
    dashboard.py         # huérfano
  ollama_client/client.py# OllamaClient: HTTP a Ollama. chat(stream=True) -> Iterator[str]
  voice/
    stt.py               # faster-whisper. _get_whisper_model(), listen(), capture_and_transcribe()
    tts.py               # edge-tts -> PyAV -> sounddevice. speak(), is_speaking(), is_available()
    streaming.py         # speak_stream(token_iter, speak_fn, on_token=None) -> str
    continuous.py        # ContinuousVoiceController (modo CLI "siempre escuchando"); NO lo usa la GUI
    audio_devices.py
  agent/
    registry.py          # TOOLS: list[Tool] (~45). all_schemas(), tool_names(), execute()
    loop.py              # run_agent(client, texto, history) -> AgentResult
  memory/history.py      # ConversationHistory (en RAM)
  memory_context/
    session.py           # SessionMemoryContext.list_active() / build_context()
    recall.py            # AutoRecall (semántico; fallback a palabras)
  storage/
    history.py           # HistoryStore (data/, con filelock)
    memory.py            # MemoryStore.list()/add()/delete()  (MAX_MEMORIES)
    semantic.py          # SemanticIndex.sync()/search()  (embeddings bge-m3)
```

### Estructura interna de `desktop.py` (para el contrato de no-regresión)

- **Globals de módulo** (estado compartido entre hilos): `_jarvis`, `_backend_ready`,
  `_last_latency_ms`, `_live_mic_level` (lista de 1 elemento, mutada desde el
  callback de audio), `_result_queue` (`queue.Queue`), `_voice_buffer`,
  `_voice_stream`, `_voice_lock`.
- **Helpers de backend** llamados directamente desde la vista o sus hilos:
  `_get_jarvis()`, `_chat_async()`, `_mic_available()`, `_read_cpu_mem()`,
  `_count_tools()`, `_voice_start()`, `_voice_stop()`, `_tts_speak()`.
- **Clase `JarvisDesktop`**: `_resolve_fonts`, sistema de zoom (`_F`, `_apply_zoom`,
  persistido en `data/ui_zoom.json`), `_boot_sequence`, `_build_ui` /
  `_build_info_strip` / `_build_quick_buttons`, dibujo (`_draw_grid`,
  `_draw_hud_frame`, `_draw_orb`, `_dim`), bucles de animación (§3),
  `_append`/`_typewrite`/`_settle_glitch` (efecto máquina de escribir + "glitch"),
  acciones (`_send_message`, `_voice_*`, `_toggle_tts`), `_poll_results`,
  `_reset_ui`, `_trigger_alert`/`_clear_alert`, `_on_close`.

**Frontera núcleo↔vista hoy:** no existe ViewModel ni bus de eventos.
`desktop.py` importa y llama directamente a `jarvis_local.jarvis.Jarvis`,
`agent.registry.TOOLS`, `voice.stt`, `voice.tts`, `config.get_config`, `psutil`
y `sounddevice` desde el módulo de la vista y desde sus hilos de trabajo.
La comunicación hilo→UI es una única `queue.Queue` (`_result_queue`) drenada por
`_poll_results` con `root.after(100, ...)`.

---

## 2. Máquina de estados existente

### GUI de escritorio — `self.orb_state` (string)

Valores reales: **`idle` · `processing` · `listening` · `speaking` · `error`**.
(El comentario en desktop.py:241 solo lista los 4 primeros; `error` se añadió después.)

Consumido cada frame por `_state_color()`, `_ORB_SPEED`, `_animate_orb`,
`_animate_wave`, `_animate_termbar`. **No hay estado `OFFLINE` en el núcleo visual**:
la desconexión solo se refleja en los puntos de estado y en la franja inferior
vía el global `_backend_ready`.

| Estado | Color (`C[...]`) | Disparado por |
|---|---|---|
| `idle` | `primary` (cyan) | fin de `_boot_sequence`; `_reset_ui()`; `_clear_alert()`; hilo de TTS al terminar; "voice" sin texto |
| `processing` | `gold` | `_send_message()` (texto, botón rápido, o voz transcrita); `_voice_stop_recording()` |
| `listening` | `danger` (rojo) | `_voice_start_recording()` (press del botón HABLAR, o `Ctrl+Espacio`) |
| `speaking` | `success` (verde) | `_poll_results()` al recibir `("ok", texto)` |
| `error` | `danger` (rojo) | `_poll_results()` al recibir `("error", msg)` → `_trigger_alert()` |

Transiciones:
- Son **asignaciones directas** de `self.orb_state`. Los bucles de animación
  leen el valor en cada frame. **No hay interpolación** entre estados (corte seco).
- `processing → speaking → idle`: el paso a `idle` lo hace un hilo daemon
  (`_speak_then_reset`) tras `_tts_speak()`, o de inmediato si TTS está apagado.
- `error → idle`: `root.after(2500, _clear_alert)`.
- `listening` y `error` comparten el rojo `C["danger"]`; se distinguen por el
  ritmo de animación (pulso duro on/off en `error`, respiración suave en el resto).

### Vista web (`server.py`) — estado JS aparte

Función `setOrbState(state)` (server.py:476) con `'listening'` / `'thinking'`.
El cliente hace `setInterval(refreshStatus, 10000)` contra `/api/status`. Modelo
distinto e incompatible con el de la GUI de escritorio.

### Modo voz continuo — `VoiceState` (enum, `voice/continuous.py:65`)

`ContinuousVoiceController` tiene su propia máquina (`LISTENING`,
`COLLECTING_COMMAND`, …) con `_state_lock`. **La GUI de escritorio NO lo usa**
(es para el modo "siempre escuchando" del CLI). Se documenta para no confundirlo
con `orb_state`.

---

## 3. Hilos, timers y callbacks — y dónde se cancelan

### Bucles de animación (todos `self.root.after(...)` auto-reprogramados)

| Bucle | Intervalo normal | Con ventana minimizada | Trabajo por tick |
|---|---|---|---|
| `_animate_particles` | `after(45)` (~22 fps) | `after(400)` | grid + 52 partículas + líneas "constelación" O(n²) + línea de escaneo, en `bg_canvas` |
| `_animate_orb` | `after(33)` (~30 fps) | `after(200)` | halos, arcos móviles, radar sweep, 24 ticks, 3 electrones, núcleo con respiración |
| `_animate_wave` | `after(55)` | `after(300)` | 13 barras en la barra de estado |
| `_animate_termbar` | `after(70)` | `after(300)` | 20 barras en la cabecera del "enlace neural" |
| `_animate_telemetry` | `after(1400)` | `after(4000)` | `psutil.cpu_percent(interval=0)` + `virtual_memory()`; escribe `CPU/MEM/LAT` |
| `_animate_live_dot` | `after(650)` | — | parpadeo de un punto rojo |
| `_cursor_blink` | `after(500)` | — | cursor de bloque del chat |
| `_poll_results` | `after(100)` | — | drena `_result_queue`; aplica resultados de chat/voz |
| `_update_status` | `after(15000)` | `after(4000)` | `tts.is_available()`, `_mic_available()` (`sd.query_devices`), `_count_tools()`, franja inferior |

Arranque: `_boot_sequence` corre un `tick` con `after(16)` (~60 fps) que se
autotermina en `step > 95` y entonces llama a `_start_animations()` (que lanza
los 8 bucles de arriba) + `_poll_results()` + `_update_status()`.

Timers de una sola vez: `_pulse_orb` (6× `after(45)`), `_typing_anim`
(`after(350)` mientras `is_processing`), cadena `_typewrite`/`_settle_glitch`
(`after(12)`, referencia en `self._typewriter_job`), debounce de resize
(`self._resize_after`, `after(150)`) + `after(10)` para `_redraw_huds`,
`_trigger_alert`→`_clear_alert` (`after(2500)`).

**Cancelación:**
- `self._typewriter_job` — sí: `after_cancel` al inicio de `_typewrite`.
- `self._resize_after` — sí: `after_cancel` en `_on_left_resize`.
- **Los 8 bucles de animación y `_poll_results` / `_update_status` NO se cancelan
  nunca.** `_on_close()` solo hace `self.root.destroy()`. No hay registro central
  de `after` ids ni limpieza al cerrar.
- La ventana **minimizada** (`<Unmap>`/`<Map>` sobre `self.root` → `self._minimized`)
  solo **ralentiza** los bucles (200-400 ms); no los detiene. **No se reacciona a
  `FocusOut`.** ⇒ Hoy no se cumple "0 fps sin foco / minimizada" que pide el brief.

### Hilos (`threading.Thread(daemon=True)`)

| Hilo | Se crea en | Función |
|---|---|---|
| `_chat_async` | `_send_message()` | uno por mensaje; llama `Jarvis.chat()` (bloqueante); mide latencia real; `_result_queue.put(("ok"/"error", ...))` |
| `_voice_start` | `_voice_start_recording()` | abre el `InputStream` de captura |
| `_finish` (`_voice_stop`) | `_voice_stop_recording()` | cierra stream, concatena buffer, transcribe con Whisper; `_result_queue.put(("voice", texto))` |
| `_speak_then_reset` | `_poll_results()` rama "ok" | `_tts_speak(texto)` y vuelve el orbe a `idle` |
| callback de `sd.InputStream` | dentro de `_voice_start` | hilo de PortAudio; `_voice_buffer.append(indata.copy())` + RMS → `_live_mic_level[0]` |
| `_warmup_model` | `Jarvis.__init__` | POST `/api/generate` con `num_predict:1` para precargar el modelo |

`Jarvis` en la ruta GUI se construye **sin `speak_fn`** ⇒ `Jarvis.chat()` hace
`"".join(tokens)` (no streaming hacia la vista) y `speak_stream` / su hilo
`_hablador` **no se usan** desde el escritorio (la GUI habla la respuesta completa
una vez con `_tts_speak`).

Sincronización: `_voice_lock` (buffer/stream de audio), `_result_queue` (hilo→UI).
`_live_mic_level` es una lista de 1 elemento sin lock (escritura escalar desde el
callback, lectura desde el hilo de UI).

---

## 4. API de voz — ¿el visualizador puede ser real?

### Entrada (micrófono) — mientras se graba en la GUI

`_voice_start(sr=16000)` abre
`sd.InputStream(channels=1, dtype="int16", blocksize=1024, callback=_cb)`.
El callback `_cb`:
1. `_voice_buffer.append(indata.copy())` — **los bloques PCM int16 crudos quedan
   accesibles** en memoria.
2. `rms = sqrt(mean(indata**2)) / 32768`; `_live_mic_level[0] = min(1.0, rms*6.0)`.

⇒ **Nivel RMS real 0..1 en tiempo real: SÍ disponible** (`_live_mic_level`), ya
consumido por `_animate_orb` (respiración en `listening`), `_animate_wave` y
`_animate_termbar`.
⇒ **FFT del micrófono: NO se calcula hoy.** Es viable añadirla en el mismo `_cb`
(hay `numpy`; los bloques de 1024 muestras están ahí). El anillo de 64 segmentos
en `LISTENING` puede ser real con trabajo acotado.

`_voice_stop()`: concatena el buffer, normaliza a float32, si `< 8000` muestras
descarta; si no, `stt._get_whisper_model(...)` + `transcribe(language="es",
beam_size=5, vad_filter=True)`. Devuelve texto.

`stt.py` también ofrece `record_until_silence()`, `listen()`,
`capture_and_transcribe(..., return_extra=True)` → `{text, rms, has_voice}`, y
`calibrate()` / `diagnose()` (lista de micrófonos, `stt_noise_floor`).

### Salida (TTS)

`voice/tts.py`: `speak(text)` → cache en `data/tts_cache` → si no, `edge-tts`
(voz `es-MX-JorgeNeural`) genera MP3 en memoria → `_mp3_bytes_to_numpy` (PyAV) →
`_play_numpy` = `sd.play(audio, sr); sd.wait()` (**bloqueante, sin callback por
frame**). `is_speaking()` → bool global. `is_available()` → hay `edge_tts`
importable (no confirma internet). Sin voz de respaldo por diseño.

⇒ **Envolvente de energía del TTS: NO expuesta hoy.** `SPEAKING` en la GUI usa
`sin()` + `random.uniform()`. Para que sea real haría falta reproducir con
`sd.OutputStream(callback=...)` o trocear el array `numpy` ya decodificado por
posición de reproducción. Trabajo mayor que la FFT de entrada.

### Streaming hablado (existe, sin usar en la GUI)

`voice/streaming.py:speak_stream(token_iter, speak_fn, on_token=None)` — habla por
frases mientras el LLM genera y acepta un `on_token` (del que se podría derivar
**tokens/s**). Hoy solo lo usa el CLI cuando `Jarvis.speak_fn` está puesto.

### Estados de micrófono

Solo `_mic_available()` → bool (`sd.query_devices(kind="input")`). **No existe el
estado "denegado por permisos"** que pide la Fase 5 del brief.

---

## 5. API de Ollama

`jarvis_local/ollama_client/client.py` — `OllamaClient` (usa `httpx`, hay fallback
a `requests`; en este equipo `httpx` está instalado).

| Método | Devuelve | Notas |
|---|---|---|
| `chat(messages, stream=True)` | `Iterator[str]` de tokens | `_stream_response` hace `break` en `data["done"]` **sin leer `eval_count`/`eval_duration`** |
| `chat(messages, stream=False)` | `str` | `_collect_response` |
| `chat_with_tools(messages, tools)` | `dict` (`message` con `tool_calls`) | lo usa `agent/loop.py` |
| `is_running()` | `bool` | `GET /api/tags`, timeout 5 s — **health-check real** |
| `list_models()` / `model_exists(name)` | lista / bool | `/api/tags` |
| `get_running_models()` | lista | `/api/ps` (modelos cargados en RAM) |
| `get_model_info(name)` | dict | `/api/show` |

- **Streaming de tokens: SÍ** a nivel de cliente. **Pero la GUI no lo aprovecha**:
  `_chat_async` llama `Jarvis.chat()` que en la ruta sin `speak_fn` hace
  `"".join(tokens)` y devuelve el string final. Para el binding "THINKING →
  tokens/s" hace falta una entrada de chat que emita tokens + marcas de tiempo
  hacia la vista.
- **Latencia: SÍ, real.** `_last_latency_ms` = reloj de pared de la llamada
  completa a `Jarvis.chat()`, medido en `_chat_async` (`None` hasta la primera
  respuesta; nunca se simula).
- **Modelo activo:** `get_config()["ollama"]["model"]` = `qwen2.5:3b`
  (config.yaml). No hay endpoint de "modelo activo" aparte; se lee de config.
- **tokens/s: NO expuesto.** Habría que cronometrarlo en el bucle de streaming
  (o leer el mensaje final `done` de Ollama, que trae `eval_count` /
  `eval_duration` y hoy se descarta).
- `_backend_ready` (global de `desktop.py`) se pone `True` en `_get_jarvis()` tras
  construir `Jarvis()` con éxito (que valida `is_running()` + `model_exists()`).
  Señal real de conectividad, pero se evalúa una sola vez al crear la instancia.

Parámetros de generación (client.py): `num_ctx` 2048, `num_predict` 120,
`temperature` 0.7 (chat) / 0.1 (agente). `timeout` 600 s.

---

## 6. Memoria y tools — qué es representable en el HUD

### Herramientas

- `agent/registry.py:TOOLS` — `list[Tool]` (~45). `Tool` = `{name, description,
  parameters (JSON Schema), run, needs_confirmation, aliases}`.
- Helpers: `tool_names()`, `all_schemas()`, `get_tool(name)`, `execute(name, args)`.
- `desktop.py:_count_tools()` = `len(TOOLS)` (import perezoso; 0 si falla).
- `config["agent"]["enabled"]` (hoy `true`) alterna agente (tool calling) vs solo
  parser. La franja inferior ya muestra `"{n} LISTAS"` / `"{n} (parser)"`.
- Herramientas destructivas (`borrar_archivo`, `enviar_correo`, `ocultar_archivos`)
  tienen `needs_confirmation=True` → devuelven un plan que exige `/confirmar`.

### Memoria

- `config["memory"]["auto_recall"]` (hoy `true`) — hoy el HUD solo muestra
  `ACTIVA` / `INACTIVA`.
- `storage/memory.py:MemoryStore(BASE_DIR/"data")` — `.list()` → items;
  `MAX_MEMORIES` como tope. **Conteo disponible** (`len(store.list())`), no
  mostrado hoy.
- `memory_context/session.py:SessionMemoryContext.list_active()` — memorias
  activadas a mano (`/memoria usar`). Conteo disponible.
- `memory_context/recall.py:AutoRecall` — recuperación semántica; requiere
  embeddings `bge-m3` en Ollama; si no, cae a búsqueda por palabras.
- `storage/semantic.py:SemanticIndex` — `sync()` / `search()`.
- `memory/history.py:ConversationHistory` — historial en RAM;
  `storage/history.py:HistoryStore` — persistido en `data/` con `filelock`.

### Sistema

- `desktop.py:_read_cpu_mem()` — `psutil.cpu_percent(interval=0)`,
  `virtual_memory().percent`; `(None, None)` si no hay psutil (nunca inventa).
- `tools/system_info.py:system_status()` — además disco y batería.
- Voz: `tts.is_available()`, `_mic_available()`, `stt.diagnose()` (modelo Whisper
  descargado o no, lista de micrófonos).

### Tabla de disponibilidad para el anillo de 64 segmentos (brief, Fase 2)

| Binding pedido | Estado hoy |
|---|---|
| `LISTENING` → FFT del micrófono | **Parcial.** RMS real en `_live_mic_level`; PCM crudo en `_voice_buffer`. FFT hay que calcularla (viable en `_cb`, hay numpy). |
| `THINKING` → tokens/s del stream | **No.** El cliente sabe hacer streaming; ni `Jarvis.chat` ni la GUI exponen callback por token en la ruta normal. Falta una entrada de chat con streaming + timestamps. |
| `SPEAKING` → envolvente del TTS | **No.** `sd.play/sd.wait` bloqueante sin feed de amplitud. Requiere `OutputStream(callback)` o trocear el numpy decodificado. |
| CPU / RAM | **Real** (psutil). |
| Ollama online | **Real** (`is_running()`). |
| Latencia último turno | **Real** (`_last_latency_ms`). |
| Modelo activo | **Real** (config.yaml). |
| Nº de herramientas | **Real** (`len(TOOLS)`). |
| Memorias (activas / total) | **Disponible** (`list_active()`, `MemoryStore.list()`); hoy solo bool. |

---

## 7. Entorno (verificado en esta máquina)

| Ítem | Valor |
|---|---|
| SO / kernel | Linux 7.0.0-30-generic |
| Sesión | **Wayland** (`XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-0`). `DISPLAY=:0` presente ⇒ Tk 8.6 corre vía **XWayland**. |
| Python | **3.14.4** (en `.venv/`; el `python3` del sistema también 3.14.4). `pyproject` pide `>=3.11`. `python` a secas no existe: usar `python3` / `.venv/bin/python`. |
| Tk | **8.6** (`tkinter.TkVersion`). |
| GPU | **Intel HD Graphics 520** (Skylake-U GT2, `00:02.0`). Mesa (`libgl1-mesa-dri`), `libGL.so.1` presente. Integrada, bajo consumo. Sin GPU discreta. `glxinfo`/`mesa-utils` **no** instalados ⇒ versión exacta de GL sin confirmar (HD 520 + Mesa ≈ GL 4.5 / GLES 3.1). |
| Fuentes mono | `JetBrainsMono Nerd Font` / `JetBrainsMono Nerd Font Mono` / `...Propo` **instaladas** (`~/.local/share/fonts/JetBrainsMonoNerdFont/`). También `Ubuntu Mono`. |
| Fuentes sans | `Ubuntu`, `Ubuntu Sans` **instaladas** (`/usr/share/fonts/truetype/ubuntu/`). **`Inter` NO está instalada** ⇒ la sans del brief debe ser Ubuntu, o hay que empaquetar/instalar Inter. |
| GUI toolkits Python | Solo `tkinter` (stdlib). **No** hay PySide6, PyQt5/6, pywebview, Qt en el `.venv`. |
| Paquetes Python relevantes | `numpy 2.5.1`, `sounddevice 0.5.5`, `av 18.0.0` (PyAV), `httpx 0.28.1`, `requests 2.34.2`, `psutil 7.2.2`, `faster-whisper 1.2.1`, `edge-tts 7.2.8`, `pillow 12.3.0`, `selenium 4.46.0`, `spotipy 2.26.0`, `pyttsx3 2.99`. |

`fc-list | grep -iE "jetbrains|ubuntu|inter"` → coincidencias de JetBrains Mono NF
y Ubuntu/Ubuntu Sans/Ubuntu Mono; **ninguna de Inter**.

---

## 8. Tests existentes y cuáles tocan la GUI

- Suite completa: `python -m pytest test -q` (40 archivos `test_*.py`).
  `test/conftest.py` aporta el fixture `_mc_test` (cliente Ollama mockeado).
- **Tocan la vista (solo 2, y solo humo / import):**

| Archivo | Tests | Qué comprueban |
|---|---|---|
| `test/test_ui_desktop.py` | 7 | el módulo importa; existe `main`; `C` es dict con `"bg"`/`"primary"`; `_mic_available()` → `bool`; `_read_cpu_mem()` → `(float,float)` o `(None,None)` con 0..100; `_count_tools() == len(TOOLS)` y `> 0`; el fuente de `_state_color` contiene `"error"`. |
| `test/test_ui_server.py` | 4 | el módulo importa; existe `main`; `PORT` es `int`; `_AUTH_TOKEN` es `str` no vacío. |

  **Ninguno instancia `Tk()` ni ejecuta `mainloop`.** No hay tests de animación,
  hilos, timers ni transiciones de estado. `test_fase4.py` / `test_fase5.py` son
  de fases antiguas del plan maestro (herramientas: clima, empleo), **no** de la GUI.

- Requisitos de test que impone el brief y hoy **no** tienen cobertura: registro
  único de timers cancelados al cerrar (Fase 7), bucle a 0 fps sin foco,
  presupuesto de CPU en IDLE, `prefers-reduced-motion`.

---

## Consecuencias verificadas para el contrato de no-regresión

1. **La vista a sustituir es `ui/desktop.py`.** El núcleo — `jarvis.py`,
   `ollama_client/`, `voice/`, `memory*/`, `storage/`, `agent/`, `tools/`,
   `config.py` — no se toca. `ui/server.py` y `ui/dashboard.py` quedan como están
   salvo decisión explícita.
2. **No existe ViewModel / bus de eventos.** Hay que introducirlo: hoy la vista
   llama al núcleo en directo desde el módulo y desde hilos daemon, y el único
   canal hilo→UI es `_result_queue` + `root.after(100)`.
3. **Datos ya reales y reutilizables:** nivel RMS de micrófono, CPU/RAM, latencia
   del último turno, estado de Ollama (`is_running`), modelo activo, nº de
   herramientas, memorias (activas/total).
4. **Datos que faltan para los bindings del núcleo visual:** FFT de entrada (fácil,
   en `_cb`), tokens/s del stream (medio, requiere entrada de chat con streaming),
   envolvente del TTS (mayor, requiere `OutputStream`/troceo del numpy).
5. **Riesgos técnicos de rendimiento ya presentes:** 8 bucles `after` sin
   cancelar, ninguno se detiene al perder foco, `_animate_particles` es O(n²)
   sobre 52 partículas cada 45 ms, y el `psutil.cpu_percent` se llama cada 1,4 s.
6. `Inter` no está instalada; `Ubuntu` sí. Wayland + Tk = XWayland. GPU integrada
   Intel HD 520 (sin discreta) — decide el desempate de stack de la Fase 1.
