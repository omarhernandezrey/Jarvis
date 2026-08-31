# Rediseño de la capa de presentación — bitácora

Registro vivo del rediseño (una entrada por fase). El mapa del sistema previo
está en `docs/ARCHITECTURE.md`.

---

## FASE 1 — Stack de vista + sistema de diseño

### 1.1 Decisión de stack: **A — PySide6 + QML / Qt Quick**

Justificación (medición + arquitectura, no estética):

1. **Presupuesto de rendimiento (Fase 7) manda.** Qt Quick tiene grafo de escena
   retenido con batching y render en su propio hilo: "un solo bucle de
   animación", "0 fps sin foco" y "0 asignaciones por frame" son el
   comportamiento por defecto (un `FrameAnimation` + `beforeRendering`), no algo
   que haya que pelear. En Canvas2D dentro de un webview hay que redibujar en
   modo inmediato cada frame y luchar contra el GC de JS para las asignaciones.
2. **El ViewModel del contrato es literalmente un `QObject` con signals**
   (`state_changed`, `token`, `audio_level`, `metrics`, `error`), expuesto a QML
   sin proceso extra ni puente JSON. Los eventos de alta frecuencia
   (`audio_level` a ~60 Hz, `token` en streaming) viajan como señales en
   proceso; en la ruta web serían serialización IPC por cada evento.
3. **Compatibilidad verificada:** PySide6 6.11.2 instala en Python 3.14.4 (wheel
   `cp310-abi3`, ABI estable). El motor QML carga `Main.qml` sin warnings.
4. **GPU objetivo:** Intel HD 520 + Mesa. Qt Quick usa su RHI sobre OpenGL; la
   carga (1 lienzo, ≤120 partículas, anillo de 64 segmentos, 3 planos de
   paralaje a 30 fps) le sobra. La ruta software queda como respaldo.
5. **Coste:** una dependencia (`PySide6`, ~255 MB en disco). La ruta B exigía
   además Node/Vite o un backend de webview (WebKitGTK) y un segundo proceso.

Descartado Tkinter por el propio brief (sin composición por capas ni blending).
Ruta B (web + React + Canvas2D) es viable y el autor la domina, pero pierde en
los dos criterios que el brief marca como decisivos: rendimiento medido y el
acoplamiento núcleo↔vista.

### 1.2 Sistema de diseño

Fuente única de verdad: **`jarvis_local/ui/hud/qml/Design.qml`** (singleton QML).
Ningún color, radio, duración, tamaño de fuente ni espaciado se escribe fuera de
ahí. Contenido: paleta (void/abyss, superficie translúcida + blur, hairline,
cyan/azure, ok/warn/alert, tres niveles de texto, blanco reservado al núcleo),
`lightOrigin` (arriba-centro) para construir profundidad con luz, helpers
`glow()` / `mix()` / `sp()`, tipografía (`JetBrainsMono Nerd Font` mono,
`Ubuntu` sans — `Inter` no está instalada), escala 12/13/15/18/24/40, radios
2/10, motion 140/220/320 con bezier `(.2,.8,.2,1)`.

### Estructura nueva

```
jarvis_local/ui/hud/
  __init__.py        # expone main()
  app.py             # QGuiApplication + QQmlApplicationEngine
  qml/
    qmldir           # registra el singleton Design
    Design.qml       # ← sistema de diseño (único sitio con literales)
    Main.qml         # lienzo (planos de profundidad + escala tipográfica)
```

`cli.py` sigue lanzando la GUI Tkinter en `/desktop`; el cambio de entrada se
hará cuando la vista nueva sea usable (Fase 2+). La Tkinter se retira en Fase 8.

### Verificación

`QQmlApplicationEngine` carga `Main.qml` con **0 warnings** (el singleton
`Design` resuelve, todos los bindings de tokens enlazan). `PySide6>=6.10`
añadido a `pyproject.toml` y `requirements.txt`.

---

## FASE 2 — El núcleo

### ViewModel (`jarvis_local/ui/hud/viewmodel.py`)

`QObject` con exactamente los cinco canales del contrato:

| canal | forma | quién lo alimenta |
|---|---|---|
| state | `Property state` + `stateChanged(str)`; `set_state()` valida contra `STATES` | la vista / drivers |
| token | `token(str)`; `push_token()` | cliente Ollama (Fase 4) |
| audio | `Property audio {level, spectrum}` + `audioChanged`; `push_audio()` / `clear_audio()` | micrófono (Fase 5) |
| metrics | `Property metrics` (dict) + `metricsChanged`; `push_metrics()` | muestreo de sistema (Fase 3) |
| error | `error(str)`; `push_error()` | cualquier subsistema |

`spectrum` vacío ⇒ el anillo cae a su valor base, nunca a ruido. Los `push_*`
son slots pensados para `invokeMethod(..., QueuedConnection)` desde hilos
productores.

### El núcleo (`qml/Core.qml` + `qml/CoreField.qml`)

- **Un solo lienzo** (`Canvas`, FBO) y **un solo bucle** (`FrameAnimation`).
  Ningún otro timer. La simulación integra por `frameTime` real (clamp 50 ms);
  el repintado se limita a 30 fps con un acumulador; bajar de fps no altera el
  movimiento.
- **Tres planos con paralaje** desde el puntero: fondo (2 px, en `Main.qml`),
  campo = halo + partículas (3 px), núcleo = anillo + punto de luz (4 px).
- **Campo de partículas**: un simulador, 120 partículas en `Float32Array`
  preasignados (0 asignaciones por frame), vida + atracción al núcleo.
  Densidad y velocidad = función del estado, no aleatorias.
- **Anillo de 64 segmentos** con binding real: `listening`/`speaking` →
  `Vm.audio.spectrum`; `thinking` → `Vm.metrics.tokensPerSecond`; sin fuente →
  `0.05` apagado.
- **Barrido especular** una pasada cada 6–9 s (periodo re-sorteado por pasada).
- **Respiración** 1.000→1.012 en 4 s sinusoidal, calculada en el bucle.
- **Halo volumétrico**: dos capas radiales desenfocadas con desplazamiento de
  paralaje distinto, dibujadas en el mismo lienzo.
- **Lenguaje de estados** (`states` + `PropertyChanges` sobre `field`,
  cross-fade **220 ms** con la bezier de `Design`, nunca corte seco):

| estado | color | geometría / ritmo | fuente |
|---|---|---|---|
| idle | azure tenue | anillo cerrado, órbita lenta, emisión 0.45 | — |
| listening | cyan | anillo abre a 64 segmentos reactivos | FFT mic |
| thinking | azure→cyan | anillos concéntricos contrarrotantes, partículas convergen | tokens/s |
| speaking | cyan brillante | onda radial desde el centro | envolvente TTS |
| alert | alert | anillo fragmentado, rotación detenida, sin emisión | evento error |
| offline | texto terciario | anillo en trazo discontinuo, inmóvil, sin emisión | health-check |

`Main.qml` monta el núcleo centrado sobre los planos; teclas 1–6 recorren
estados para inspección (no es UI final). `app.py` instancia el ViewModel y lo
expone como `Vm`.

### Verificación

Recorridos los seis estados en `offscreen` con espectro y `tokensPerSecond`
simulados: **0 warnings del engine, 0 errores de runtime** en el bucle/`onPaint`.
`ruff` limpio. Inspección visual en pantalla real: pendiente para el usuario
(`python -m jarvis_local.ui.hud`).

---

## FASE 3 — HUD con datos reales

`jarvis_local/ui/hud/services.py` — `MetricsService`: hilo propio (no el de la
GUI: `is_running()` hace I/O de red) que muestrea **cada 2 s** y entrega al
ViewModel por señal en cola. Además aplica la política **OFFLINE↔IDLE** del
núcleo desde el health-check real, sin pisar listening/thinking/speaking.

Datos, todos reales o ausentes (nunca inventados):

| celda | fuente |
|---|---|
| SISTEMA | `OllamaClient.is_running()` |
| MODELO | `config.ollama.model` |
| CPU / RAM | `psutil` (`interval=None`, sin bloqueo) |
| LATENCIA | turno real del LLM (lo fija el driver de chat, Fase 4) → ausente aquí |
| TOKENS/S | medido en streaming (Fase 4) → ausente aquí |
| VOZ | `edge_tts` importable + `sounddevice.query_devices(kind=input)` |
| MEMORIA | `config.memory.auto_recall` + `len(MemoryStore.list())` |
| HERRAMIENTAS | `len(registry.TOOLS)` + `config.agent.enabled` |

`qml/HudCell.qml` + `qml/Hud.qml` — banda densa: cada dato = etiqueta pequeña +
valor grande + regla de 1px, sin recuadro. `absent` ⇒ valor `—` en color de
metadato. `vertical` reorganiza la banda como columna (Fase 6). `sample_all()`
lee Ollama de verdad en esta máquina: `online=True model=qwen2.5:3b`,
`tools=46`, `ping≈400 ms`.

`test/test_ui_hud.py` (6 tests): validación de estados, merge de `metrics`,
clamp/clear de audio, forma de `sample_all()` (None o tipo correcto, nunca
aleatorio), y carga de `Main.qml` con 0 warnings. Suite de vista: 12/12 verde.

---

## FASE 4 — Conversación

### Punto de contacto con el núcleo (`chat_service.py`)

`ChatService` reutiliza `jarvis_local.jarvis.Jarvis` **sin tocarlo**: antes de
`jarvis.chat(text)` envuelve `jarvis.client` con `_TapClient`, que delega todo en
el cliente real y sólo en `chat(stream=True)` envuelve el iterador para chivar
cada token (latencia real hasta la 1.ª palabra, tokens/s medidos). Se restaura
el cliente en `finally`. El resto de la cascada (respuestas rápidas, parser,
agente, memoria, persistencia, redacción de secretos) queda intacta; sus
respuestas llegan completas, no por streaming. Todo el trabajo va en un hilo;
modelo y ViewModel se tocan por señales en cola.

Emite a: `ConversationModel` (turnos), `Vm.token` (canal del contrato),
`Vm.push_metrics` (`latencyMs`, `tokensPerSecond`), `Vm.set_state`
(`thinking`→`idle`, o `alert` si excepción). `Chat.busy` (Q_PROPERTY) bloquea la
entrada mientras genera.

### Vista

- `conversation_model.py` — `ConversationModel(QAbstractListModel)` de turnos
  (roles channel/body/timestamp/streaming/meta/kind).
- `qml/Conversation.qml` — `ListView`; **autoscroll anclado** que se libera al
  subir (`stick = atYEnd`) y píldora "volver al final".
- `qml/Turn.qml` — canaleta izquierda: etiqueta de canal (`USER`/`JARVIS`) +
  regla vertical alineada al primer renglón. Sin burbujas. Cursor de bloque
  `▌` mientras `streaming` (parpadeo por `SequentialAnimation`, no timer); al
  cerrar el turno, desaparece. Metadatos en color de metadato, tamaño 12.
- `qml/MarkdownBody.qml` — divide por vallas ``` ```; prosa → `Text` con
  `MarkdownText`, `lineHeight 1.6`, medida ~78 car.; código → `CodeBlock`.
  Valla impar (streaming) ⇒ resto tratado como código en curso.
- `qml/CodeBlock.qml` + `qml/hl.js` — mono, fondo +3% de blanco, resaltado
  ligero (comentarios/cadenas/números/keywords, sin lexer real) y botón
  **copiar**.

### Contraste medido (texto sobre `bgVoid #04070D`)

| color | ratio | AA (4.5:1) |
|---|---|---|
| `textPrimary #C9D6E4` (mensaje) | ~13.7:1 | ✔ holgado |
| `textSecondary #7E8FA3` | ~6.1:1 | ✔ |
| `textMeta #4A5A6E` (timestamp/meta) | ~2.8:1 | color de la paleta del brief; texto no esencial (umbral incidental ~3:1) |

### Verificación

QML compila con **0 warnings**. `ConversationModel` streaming, `_TapClient`
(tap real de tokens + passthrough sin stream) y `ChatService` (turno completo
con núcleo falso: 2 turnos, texto ensamblado, `latencyMs` fijada, vuelta a
`idle`) cubiertos en `test/test_ui_hud.py` (8 tests, verde). El turno real
contra Ollama en CPU tarda >2 min (construcción de `Jarvis` + generación):
pendiente de prueba en pantalla por el usuario.

---

## FASE 5 — Barra de comando y voz

### `voice_service.py` — `VoiceService`

- **Captura**: `sd.InputStream` (16 kHz, bloques de 1024). Cada bloque →
  RMS (nivel) + **FFT real** (`np.fft.rfft` con ventana Hann, 256 bins de
  0–4 kHz plegados a 64) → `Vm.push_audio(level, spectrum)`. Estado
  `listening`.
- **Tres estados de micrófono reales**: `inactive` · `listening` · `denied`
  (`denied` si `InputStream()` / `.start()` lanzan, o si falta
  numpy/sounddevice).
- **Transcripción**: al parar, hilo aparte con `voice.stt._get_whisper_model`
  (núcleo sin tocar) → `transcribed(text)` → `Chat.send`.
- **Salida hablada con envolvente real**: reutiliza la generación/decodificación
  de `voice.tts` (`_cache_get/_edge_generate_async/_mp3_bytes_to_numpy`) y sólo
  reproduce con un `sd.OutputStream` con callback que mide RMS + bandas por
  bloque → `Vm.push_audio` alimenta el estado `speaking`. `stop_speech()` corta.
  Sólo habla si `config.voice.tts_enabled`.

### `chat_service.py` — cancelación y recall

- `cancel()` (Esc): activa un `threading.Event`; `_TapClient` deja de consumir
  el stream y el núcleo devuelve lo generado. Sin matar hilos. El turno se
  cierra con "⏹ cancelado".
- `lastCommand` (Q_PROPERTY): último texto enviado, para el recall con ↑.

### `qml/CommandBar.qml` + `qml/MicButton.qml`

- Prompt `❯` persistente. Editor `TextEdit` multilínea en `Flickable`:
  autoexpansión de 1 a 6 líneas y luego scroll interno.
- **Enter** envía · **Shift+Enter** salto · **Esc** cancela la generación ·
  **↑** (con el campo vacío) recupera `Chat.lastCommand`.
- Estados con feedback distinto: `hover` (borde gris tenue), `focus` (borde
  cyan), `disabled`/`generating` (borde azul + barrido azul lento en el borde
  inferior, editor atenuado).
- `MicButton`: icono vectorial trazado a 1.5px (sin emojis), tres estados;
  `denied` no responde y muestra tooltip "Micrófono sin permiso".
- **Coherencia**: mientras se graba, el borde de la barra se sustituye por un
  `Canvas` que dibuja el espectro (`Vm.audio.spectrum`) a lo largo del
  perímetro con el mismo trazo cyan del anillo del núcleo — un lenguaje visual,
  dos escalas.

### Verificación

QML compila con **0 warnings**. `test/test_ui_hud.py` (11 tests, verde) cubre:
cancelación del `_TapClient`, máquina de estados del micrófono sin audio, y el
resto de fases. En esta máquina `start_recording()` abre el micrófono real y
pasa a `listening`. Prueba de voz punta a punta (STT/TTS con audio real):
pendiente en pantalla por el usuario.

---

## FASE 6 — Responsive real (reorganización, no encogimiento)

`Main.qml` deriva `mode` de las dimensiones y **recoloca** las zonas (no las
escala):

| modo | condición | composición |
|---|---|---|
| `wide` | ancho ≥ 1600 | HUD lateral (columna) · núcleo · conversación — 3 zonas |
| `mid` | 1100–1599 | HUD en banda superior; núcleo reducido a la izquierda |
| `narrow` | ancho < 1100 | una columna: cabecera con núcleo-insignia + HUD; conversación prioritaria; barra abajo |
| `badge` | alto < 720 | núcleo-insignia en cabecera; el visualizador de espectro vive **persistente** en la barra de comando (`CommandBar.showViz`) |

- `Core.compact` / `CoreField.compact` (modo insignia): el bucle sigue siendo
  uno, pero se omiten partículas, halo doble, anillos concéntricos, onda radial
  y barrido — quedan anillo de datos + respiración + punto de luz + color de
  estado. También baja el coste.
- La barra de comando está **siempre anclada al fondo** de su zona y alcanzable
  en los cuatro modos.

### Verificación

`test/test_ui_hud.py::test_responsive_layout_no_overlap_no_overflow` (11 tests
verde): en 1700×900, 1360×820, 1000×760 y 430×360 → **solape núcleo/conversación
= 0**, todas las zonas dentro de la ventana, barra de comando visible. **0
warnings** de QML en las 6 medidas probadas.

---

## FASE 7 — Presupuesto de rendimiento

| criterio | estado | evidencia |
|---|---|---|
| Un único bucle de animación | ✅ | un solo `Timer` `objectName:"coreLoop"`; **cero `FrameAnimation`**. Test `test_single_animation_loop_capped_at_30fps`. |
| Techo de 30 fps | ✅ | `interval` 33 ms en estados con datos vivos, 50 ms (~20 fps) en reposo. Medido: 20 fps en IDLE. |
| 0 fps sin foco / minimizada | ✅ **empírico** | `loopActive = win.active && visibility != Minimized/Hidden`. Medido: **fps sin foco = 0.00**. Test `test_loop_pauses_when_not_running`. |
| Timers registrados y cancelados al cerrar | ✅ | `Runtime.timers` (único lugar) + `Runtime.shutdown()` conectado a `aboutToQuit`. Test `test_runtime_shutdown_stops_metrics_thread`. |
| RSS estable ±5 MB | ✅ **medido** | 45 s en IDLE: RSS **171 · 171 · 171 · 171 MB**, deriva **±0.3 MB**. Fuga encontrada y corregida: `sd.query_devices` cada 2 s desde un hilo re-inicializaba PortAudio (~1.5 MB/llamada) → ahora `_read_voice` se cachea. `OllamaClient` también se reutiliza. |
| `prefers-reduced-motion` | ✅ | `services.detect_reduced_motion()` (env `JARVIS_REDUCED_MOTION` + GNOME `enable-animations`) → `ReducedMotion` en contexto. En ese modo: `particleDensity=0`, sin rotación/respiración/barrido/concéntricos/onda; sólo las transiciones de estado (220 ms). Tests `test_reduced_motion_*`. |
| IDLE ≤3 % de un núcleo | ⚠️ **pendiente en GPU real** | Medido **~34 %** bajo el rasterizador **software** (`QT_QPA_PLATFORM=offscreen`, sin GPU) a 20 fps. En la ruta real Qt Quick sube la textura del `Canvas` a la iGPU Intel HD 520 y la cifra cae mucho. `scripts/hud_perfcheck.py` deja al usuario medirlo en pantalla (quitar el `os.environ.setdefault(...offscreen...)`). |

Optimizaciones aplicadas al `onPaint`: sin `ctx.reset()` por frame; halo por
apilado de discos (sin crear objetos gradiente); partículas con un `fillStyle`
+ `globalAlpha` por partícula; anillo plano (idle/alert/offline) en **un solo
trazo** de 64 sub-caminos; color de tinte cacheado como string.

`scripts/hud_perfcheck.py`: reporta fps con/sin foco, CPU y marcas de RSS cada
10 s. La corrida completa de 10 min la hace el usuario.
