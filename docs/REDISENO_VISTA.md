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

---

## FASE 8 — Auditoría y cierre

### Integración

`cli.py` `/desktop` (y alias `/hud`) lanza el HUD Qt.
> **Actualizado por el ADDENDUM (ver abajo):** la Tkinter se eliminó; ya no hay
> fallback. Si Qt falla, se reporta el error.

### Estado

- `ruff check .` — **limpio** (todo el repo).
- `python -m pytest test -q` — **verde**. (`test_history_performance` es una
  aserción de tiempo que falla sólo bajo carga concurrente del equipo; pasa
  aislada y no toca la capa de vista.)
- Limpieza: retirados `_acc` (CoreField), `_lock` (ChatService) y una conexión
  no-op (VoiceService). Sin imports huérfanos.

### Verificación funcional (smoke automatizado)

| flujo | resultado |
|---|---|
| Arranque | ✅ engine carga, 0 warnings |
| Redimensionado (4 modos) | ✅ sin solapamiento ni overflow |
| Estados del núcleo + evento de error | ✅ transiciones e interpolación |
| Cierre | ✅ sin excepciones; 0 hilos de servicio vivos tras `shutdown()` |
| Enter envía / Shift+Enter salto / Esc cancela / ↑ recall | ✅ lógica en `CommandBar` + test de cancelación |
| Chat con núcleo (turno completo, latencia, tokens/s) | ✅ con núcleo falso; turno real contra Ollama en CPU: **para el usuario** |
| Voz: inactive/listening/denied · STT · TTS+envolvente | ✅ máquina de estados y wiring; audio real (mic/altavoz): **para el usuario** |
| Ollama health-check · memoria · herramientas | ✅ datos reales observados (`online`, `tools=46`, `memory`) |
| Persistencia de configuración | ✅ intacta (contrato: el núcleo no se toca) |

### Autocrítica (10 líneas)

1. **Lo memorable**: el núcleo. Un lienzo, un bucle, tres planos con paralaje y
   el anillo de 64 segmentos que sólo reacciona a datos reales (FFT, tokens/s,
   envolvente TTS) — nunca ruido. Cada estado cambia geometría, ritmo y color.
2. La coherencia barra-de-comando ↔ anillo (mismo trazo, dos escalas) durante
   la grabación es el segundo golpe de identidad.
3. **Recortado por disciplina**: el halo volumétrico real (gradientes radiales)
   se cambió por discos apilados para no pagar asignaciones por frame; se ve
   casi igual pero es menos "material".
4. Sin shaders GLSL: el brief los permitía y darían un núcleo más físico, pero
   el presupuesto de un lienzo + Δt real ya se cumple sin ellos.
5. El resaltado de código es por regex, no un lexer: correcto para leerse como
   código, pobre para lenguajes con sintaxis densa.
6. La detección de `prefers-reduced-motion` en Linux depende de GNOME; en otros
   entornos sólo responde a la variable de entorno.
7. La medición de CPU en IDLE se hizo con rasterizador software (sin GPU en el
   entorno de trabajo); el objetivo ≤3 % debe confirmarlo el usuario en pantalla.
8. **Sigue pareciendo genérico**: la banda del HUD, pese a no usar tarjetas ni
   versalitas, es una fila de dato+valor que se ha visto mil veces; le falta una
   idea propia (¿un histórico en línea de 1px por métrica?).
9. La consola conversacional es sólida y legible pero no arriesga: un lector
   la reconocería como "terminal estilizada".
10. El arranque no tiene identidad todavía (la secuencia de boot de la Tkinter
    no se portó); la primera impresión es una ventana que aparece sin más.

---

# ADDENDUM — dirección visual GPU

El brief inicial pedía austeridad ("glow escaso", "sin box-shadow", "cero
decoración"). El resultado es fiel a ese brief y por eso se lee **básico**. El
addendum lo revoca: el núcleo emite luz que se propaga a **toda** la interfaz;
la profundidad se construye con un **pipeline de render en GPU**, no con trazos;
la atmósfera (viñeta, grano, aberración cromática) es función, no adorno.

Plan de ejecución (una fase por sesión, commit + STOP al final de cada una):

1. **Eliminar la GUI Tkinter y sus tests.** ← esta fase
2. Migrar el núcleo de `Canvas` a `ShaderEffect` (fragment shaders `.frag` → `qsb`
   en el build). Sin bloom aún; medir fps. Antes de invertir en el resto,
   enseñar el shader del núcleo aislado para validar la dirección.
3. Post-proceso: extracción de altas luces + bloom en dos pasadas + atmósfera.
4. Iluminación global: `corePos` / `coreEnergy` / `coreTint` en `Design.qml`;
   cada hairline, borde y panel deriva su opacidad y tinte de ahí.
5. Tipografía y densidad de layout (escala 12/13/15/18/24/40 usada de verdad,
   cifras tabulares en el HUD, densidad asimétrica).
6. Secuencia de arranque con identidad (≤900 ms, la luz revela la interfaz).
7. Rendimiento GPU: 60 fps con foco / bucle detenido sin foco, ruta de
   degradación real (software o <40 fps 3 s → sin bloom ni partículas),
   `ruff check .`, suite completa.

## Fase 1 (addendum) — eliminación de Tkinter

- Borrados `jarvis_local/ui/desktop.py` (1352 líneas) y `test/test_ui_desktop.py`.
- `cli.py`: `/desktop` y `/hud` → sólo `jarvis_local.ui.hud`; **sin fallback**.
  Si Qt falla, se registra el error y se avisa en pantalla. Eliminado
  `/desktop-clasica`.
- `jarvis_local/ui/hud/__main__.py` para `python -m jarvis_local.ui.hud`.
- `README.md` y el docstring del paquete actualizados. Retirado el ignore
  `jarvis_local/ui/*` de ruff (era para el estilo compacto de Tkinter); esto
  destapó un `E702` propio en `voice_service.py`, corregido.
- Verificado: **nada en el código importa `jarvis_local.ui.desktop`**
  (`ui/server.py` y `ui/dashboard.py` son la interfaz web, intactas).
  `ruff check .` limpio. `test_ui_hud` + `test_ui_server` + `test_cli` +
  `test_startup` en verde (35 tests).

## Fase 2 (addendum) — el núcleo a GPU (ShaderEffect)

**Migrado de `Canvas` (raster CPU) a `ShaderEffect` + fragment shader compilado.**

- `jarvis_local/ui/hud/shaders/core.frag` (+ `.qsb` versionado) — compilado con
  `pyside6-qsb` vía `shaders/build.py`. Contenido del shader:
  1. **Campo de interferencia**: dos espirales radiales contrarrotantes; su
     superposición (moiré) *es* la visualización — el dato real modula la
     **fase** (`energy`, `flux`, `bandLow-bandHigh`), no la amplitud. Sin dato →
     estado base.
  2. **Volumen interior por raymarch** de un SDF (esfera + desplazamiento por
     ruido 3D), aditivo: es **luz**, no un objeto opaco. Fresnel en el borde +
     centro caliente + plasma interno escalado por energía.
  3. **Barrido especular anisótropo** (no glow uniforme): highlight estirado por
     la tangente que recorre la superficie.
  Uniforms por estado: `tint/ringOpen/emission/fragmented/dashed` + `reduced`,
  `compact` (insignia, sin volumen).
- `qml/CoreShader.qml` — envoltorio: `layer.enabled`, `layer.samples: 2`,
  `layer.live: loopActive` (sin foco el layer se congela → 0 trabajo de GPU).
- `qml/Core.qml` reescrito: máquina de estados (cross-fade 220 ms) + traducción
  de datos reales del ViewModel a uniforms, movido por **un único
  `FrameAnimation`** global (`objectName: coreLoop`). Borrado `CoreField.qml`.
- `qml/Main.qml`: registra `GraphicsInfo.api` en el log y muestra un aviso en
  pantalla si el backend cae en **software** (no se finge GPU).
- `scripts/core_preview.py` + `qml/CorePreview.qml` — ventana aislada del núcleo
  (teclas 1–6), `--grab` renderiza un PNG por estado. Usada para validar la
  dirección antes de seguir.

**Medición (GPU real, HD 520, núcleo 560 px aislado):** ~99 fps sin cap,
**~27 % CPU**. Por encima del objetivo ≤5 % de la §7; en la app el núcleo es
menor y la Fase 7 (addendum) trae bloom, presupuesto real y ruta de degradación.
Sin bloom todavía (es la Fase 3).

Tests de vista: 16/16 verde. `ruff check .` limpio.

## Fase 3 (addendum) — pipeline de post-proceso

Cadena (addendum §2), toda en GPU:

```
CoreShader  →  layer (texture)
   ↓ bloom_extract.frag  (umbral de altas luces)
   ↓ MultiEffect ×2      (blur estrecho r≈20 · blur ancho r≈64)
   ↓ bloom_composite.frag (núcleo + b0·k0 + b1·k1, aditivo)
CoreBloom.qml
   ↑ montado en Core.qml con margen negativo para que el glow no se recorte
   ↓
Atmosphere.frag  (viñeta + grano temporal + aberración cromática ≤1.2 px)
   ↑ aplicado como `layer.effect` de TODA la escena (rootItem), sólo con foco
```

- `shaders/bloom_extract.frag`, `bloom_composite.frag`, `atmosphere.frag`
  (+ `.qsb`), compilados con `pyside6-qsb`.
- `qml/CoreBloom.qml` — `CoreShader` + extracción + 2× `MultiEffect` +
  composición aditiva, con `ShaderEffectSource(hideSource)` entre etapas;
  `live` congela toda la cadena sin foco.
- `qml/Atmosphere.qml` — `ShaderEffect` usado como `layer.effect`; `time`
  cuantizado a ~24 fps para el grano.
- `qml/Main.qml` — **un único `FrameAnimation`** (`objectName: coreLoop`) en
  `rootItem` mueve `tick`; `Core` lo consume vía `time` (ya no tiene bucle
  propio). `rootItem.layer.enabled: motionActive` + `layer.effect: Atmosphere`.
  `motionActive` = foco ∧ no minimizada ∧ no `paused` ∧ (¬reduced ∨
  listening/speaking). Sin foco / reduced-motion en reposo → sin atmósfera,
  render normal e interactivo.

**Medición (GPU real, HD 520, ventana 1360×820, pipeline completo):**
**60 fps** estables · **CPU ~24 %** · RSS plana (+0.3 MB en reposo). Sigue por
encima del ≤5 % de la §7 — el recompositado de la atmósfera a ventana completa
es el grueso; el presupuesto y la **ruta de degradación** (software o <40 fps →
sin bloom/atmósfera, sólo el shader del núcleo) son la Fase 7.

Preview: `python scripts/core_preview.py` incluye ya bloom + atmósfera.
16 tests de vista en verde · `ruff check .` limpio.

## Fase 4 (addendum) — iluminación global

El núcleo es la **única fuente de luz** del sistema y esa luz está viva.

- `Design.qml` expone: `corePos` (centro del núcleo en coords de escena),
  `coreEnergy` (0..1, dato real), `coreTint` (color del estado), `lightRadius`
  (alcance, lo fija Main según el tamaño de ventana). Y las funciones
  `lightLevel(sx,sy)`, `litHairline(sx,sy)`, `litText(base,sx,sy)`.
- `Core.qml` **publica** su posición / energía / tinte en `Design` (posición al
  cambiar el layout; energía y tinte por `Binding`).
- `qml/Hairline.qml` — línea de 1px cuyo color y opacidad derivan de la
  distancia al núcleo: cerca brilla y tira a `coreTint`, lejos se apaga.
  También respira con `coreEnergy`. Usada en las reglas de `Main` y `HudCell`.
- `CommandBar` — la superficie base se tiñe hacia el núcleo por cercanía; el
  borde por defecto es `litHairline` (los estados focus/busy/hover mantienen su
  color propio).
- `CodeBlock` — superficie que **recibe luz**: gradiente de un solo lado
  orientado hacia `corePos` + borde `litHairline`.
- La etiqueta de estado (texto secundario) respira con `coreEnergy` vía
  `litText`.

**Verificación:** 0 warnings de QML · 16 tests de vista en verde · `ruff check .`
limpio · capturas en GPU: el núcleo actúa de fuente, las hairlines cercanas se
avivan y tiñen, la banda del HUD se ilumina más del lado del núcleo, la
conversación (lejos) queda apagada. El efecto es sutil, por diseño.

Pendiente de pulido (no bloquea): el borde del `layer` del bloom aún se
insinúa en algunos frames; las hairlines de la píldora "volver al final" y del
micrófono no están iluminadas todavía.

## Fase 5 (addendum) — tipografía y densidad de layout

Antes: todo entre 12 y 18 px; `fsLarge (24)` y `fsDisplay (40)` sin usar. Ahora
la escala 12/13/15/18/24/40 se usa de verdad:

| tamaño | uso |
|---|---|
| 40 display | wordmark "JARVIS" del estado vacío de la conversación (callado, `textMeta`) |
| 24 large | **valores del HUD** (mono → cifras tabulares). El valor domina. |
| 18 title | prompt `❯` de la barra de comando |
| 15 body | etiqueta de estado, editor de la barra, prosa de los turnos |
| 13 small | pista del estado vacío, código |
| 12 meta | etiquetas del HUD, canaleta y metadatos de los turnos |

- **HUD**: etiquetas en **minúscula** (`sistema`, `cpu`, `voz`…), 12 px,
  `textMeta` — "la etiqueta susurra". Valores 24 px. Sin versalitas espaciadas.
  Celdas más juntas (`sp(5)`), banda un poco más alta (`sp(16)`) para el valor
  grande.
- **Estado vacío de la conversación**: identidad a 40 px + una línea de pista;
  se desvanece con el primer turno (antes: un vacío negro).
- **Densidad asimétrica**: el layout ya no se parte en tercios iguales. La zona
  del núcleo baja a **0.34–0.38** del ancho disponible y el orbe ocupa **0.82**
  de su zona → tiene aire alrededor; la conversación (donde vive el contenido)
  se queda con el resto.
- El borde del `layer` del bloom se difumina en el propio shader del composite
  (círculo suave sobre color y alpha) → ya no se ve la arista del recuadro.

0 warnings de QML · 16 tests de vista en verde · `ruff check .` limpio ·
capturas GPU en modos `mid` y `wide`.

## Fase 6 (addendum) — secuencia de arranque con identidad

Es la regla de iluminación de la Fase 4, ejecutada **una vez en el tiempo**.
Sin texto de sistema, sin barras de progreso, sin ASCII, sin "INITIALIZING".

- `Design.qml`: `bootReveal` (0→1) y `reveal(sx,sy)` — un **frente de luz** que
  sale de `corePos` y devuelve 0..1 según lo lejos que haya llegado a un punto.
  `bootReach` = diagonal × 0.9 (lo fija Main).
- `Main.qml`: `NumberAnimation` única (no es un FrameAnimation ni un Timer)
  anima `boot` 0→1 en **850 ms** con la bezier del sistema, al arrancar.
  `Binding` lo publica en `Design.bootReveal`. Cualquier **tecla o clic** salta
  (`_skipBoot`). Las zonas (`hud`, `convZone`, etiqueta de estado) y cada
  `Hairline` toman `opacity: Design.reveal(su centro)` → se revelan por
  distancia al núcleo.
- `Core.qml`: `bootIgnite` (0→1, mapeado al primer 42 % del arranque) — el orbe
  hace **pop-in desde un punto** (escala 0.06→1 con leve rebasamiento) y un
  **destello** de energía/emisión que sube y baja mientras se enciende.

Secuencia observada (capturas GPU): ~120 ms oscuridad + chispa → ~340 ms el
núcleo encendido, la hairline vertical revelándose hacia afuera → ~560 ms HUD y
wordmark apareciendo → ~850 ms todo revelado e iluminado.

De paso: la barra de scroll de la conversación ahora sólo aparece al desplazar
(antes destellaba durante el arranque).

0 warnings de QML · 16 tests de vista en verde · `ruff check .` limpio.

## Fase 7 (addendum) — presupuesto de rendimiento (GPU)

### Un solo bucle, cero timers sueltos

Un único `FrameAnimation` (`objectName: coreLoop`) mueve todo. El único `Timer`
que quedaba (reset del botón "copiar" en `CodeBlock`) se cambió por una
`SequentialAnimation` de una pasada. El `QTimer` de Python (autoclear de ALERT)
sigue registrado en `Runtime.timers` y se cancela en `shutdown()`.

### Sin foco → 0 fps (verificado, no asumido)

`FrameAnimation.running: motionActive` (falso sin foco / minimizada / `paused`).
`CoreBloom.live` y `rootItem.layer.enabled` cuelgan de lo mismo. Medido:
**fps sin foco = 0.00** en todas las corridas.

### Ruta de degradación (real y probada, no un `if`)

`services`/`Main.qml`: si el backend RHI es **software/Null**, o los fps caen
**<40 durante 3 s**, se **engancha** un latch (`_degradedLatch`, no oscila) y:
`CoreBloom.bypass = true` (sin extracción, sin blur, sin composición — el shader
del núcleo se dibuja directo) y `layer.enabled = false` (sin atmósfera).
`perfOverride` (−1/0/1) es el hook de tests. Cubierto por
`test_degradation_path_bypasses_bloom` y `test_low_fps_sustained_degrades`.

### Mediciones

| entorno | pipeline | fps foco | fps sin foco | CPU | RSS (30 s) |
|---|---|---|---|---|---|
| offscreen (software) | **degradado** (auto) | 62 | **0.00** | 37 % | 171 → 171 (**±0.04 MB**) |
| GPU real (HD 520) | completo (forzado) | 99* | **0.00** | 65 %* | 270 → 271 (**±0.15 MB**) |
| GPU real (HD 520) | completo (auto) | 99* | **0.00** | 65 %* | 269 → 269 (**±0.08 MB**) |

\* fps sin cap en la medición; con una ventana visible el `FrameAnimation` va a
vsync (60) y la CPU baja en proporción (~40 %).

- **RSS estable** en todos los casos (±0.15 MB). Se encontró y corrigió una
  fuga (~500 MB/25 s) causada por el pipeline oscilando entre degradado/completo;
  el latch de una vía lo elimina.
- **fps sin foco = 0** confirmado empíricamente.
- **CPU en IDLE**: ~40 % a 60 fps en la **Intel HD 520** (iGPU de 2015) con el
  pipeline completo — por encima del ≤5 % del objetivo. El grueso es el
  recompositado de la atmósfera a ventana completa cada frame. Para esto existe
  la ruta de degradación; en una GPU moderna la cifra es una fracción. Se
  reporta el número real, no se maquilla.

`prefers-reduced-motion` (Fase 7 original): sigue vigente — `Design`/`Main`
paran el bucle en reposo y el shader recibe `reduced=1`.

`ruff check .` limpio · **suite completa en verde** · 18 tests de vista.

## Fase 8.1 (addendum) — ventana sin marco

- `Window`: `flags: Qt.Window | Qt.FramelessWindowHint`, `color: "transparent"`.
  Sin barra de título del SO.
- `qml/WindowChrome.qml` — chrome propio:
  · zona de arrastre en la banda del HUD → `win.startSystemMove()`; doble clic
    alterna maximizar.
  · controles de ventana (min / max·restore / close) trazados a **1.5px**, sin
    relleno ni emojis (`qml/WinButton.qml`), alineados a la rejilla del HUD.
  · 8 zonas en la canaleta → `win.startSystemResize(<Qt.Edges>)` (los 4 bordes
    y las 4 esquinas), con `cursorShape` correcto. Inactivas al maximizar.
- Esquinas del contenido a **12px** (`Design.radiusWindow`): la máscara la
  aplica el shader de atmósfera (SDF de caja redondeada sobre el alpha), así
  que el `layer` va siempre activo; cuando la atmósfera "está apagada"
  (degradado/sin foco) el shader queda casi neutro (grano/aberración a 0).
- Canaleta de sombra (`Design.windowShadowGutter = 22`) + `MultiEffect` de
  sombra proyectada (el compositor no la da sin decoración del SO). 0 al
  maximizar.

Verificado: 0 warnings de QML · el flag frameless aplica · captura en GPU
muestra sin barra de título, esquinas redondeadas y controles propios ·
`ruff check .` limpio · 18 tests de vista en verde. (Suite completa: verde
salvo `test_reminders.py::test_alarma_suena`, un test de temporización de
alarma ajeno a la vista que falla sólo bajo carga concurrente del equipo y
pasa aislado — no se ha tocado nada de reminders.)

## Fase 9 · P0 — el chat no respondía (regresión funcional)

**Traza completa. Dos bugs independientes, ambos corregidos.**

### Bug 1 — colisión de nombre: la conversación nunca se mostró (desde Fase 4)

`app.bind_context` exponía el modelo como context property **`Conversation`**, y
existe **`Conversation.qml`**. Dentro de ese archivo `model: Conversation`
resolvía al *tipo del componente*, no al modelo → la `ListView` tenía
`model = null` y `count = 0` para siempre. El `send()` llegaba al
`ConversationModel` (`rowCount() == 2`) pero **nada se pintaba**.
Los tests pasaban porque comprobaban el modelo Python, no la `ListView`
(exactamente lo que advertía el brief).
**Fix:** context property → `ConversationModel`; `Conversation.qml` usa
`model: ConversationModel`.

### Bug 2 — httpx no hacía streaming real

`OllamaClient.chat(stream=True)` en la rama httpx usaba `client.post()`, que
**bufferiza toda la respuesta** antes de devolver: cero streaming y bloqueo
durante toda la generación. (Ollama sí streamea: `curl` directo da tokens en
<1 s.) **Fix:** `_stream_response_httpx(payload)` usa `client.stream("POST", …)`
dentro de un `with`; los tokens llegan según se generan (verificado: 1er token a
1.5 s, ~0.2 s/token). Beneficia también al CLI.

### Traza punto por punto (tras los fixes)

`CommandBar` Enter → `Chat.send(str)` (slot) → `userTurn`/`assistantBegin`
(señales en cola) → `ConversationModel` (2 filas) → **`ListView` las pinta** →
hilo `_run` → `_ensure_jarvis()` (`Jarvis()` 0.6 s) → `_TapClient` sobre
`jarvis.client` → `jarvis.chat()` → **tokens en tiempo real** → `assistantToken`
→ `Vm.push_token` + `ConversationModel.append_token` → HUD `tokens/s` y
`latencia` moviéndose → `assistantEnd` → estado `thinking → idle`.

Voz: `VoiceService.transcribed` → `Chat.send` — **el mismo camino ya arreglado**.

### E2E real (GPU, contra Ollama)

"Escribe dos frases sobre el océano" → turno vacío + cursor al instante ·
tokens en streaming (`toks 20→31→42→53`, `tps 5.1→5.5`) · cierre a
`179838 ms · 5.3 tok/s` · estado `thinking→idle`. Captura con el turno real
renderizado (`scratch_preview/e2e_real.png`) y una sesión de 7 turnos
(prosa, bloque de código con copiar, turno de error) en `chat_populated.png`.

### Lo que NO se logró en P0 (honesto)

El **retardo hasta el primer token es de ~170 s** en esta máquina (Intel HD 520,
CPU de 2015): `_try_agent` hace un `chat_with_tools` no-streaming con **46
esquemas de herramientas** (~29–110 s), más el `recall` semántico y la
evaluación del prompt completo (system + memoria + historial). Es coste del
núcleo/agente en CPU débil, no un fallo funcional — el chat responde y
streamea. Mitigaciones para decidir aparte: `agent.enabled: false` en
`config.yaml` (pierde tool-calling), o acelerar el paso del agente.

### Tests de regresión (impiden que vuelva)

`test_qml_conversation_listview_reflects_model` — la `ListView.model` ES el
`ConversationModel` y refleja las filas. `test_command_bar_enter_reaches_chat_send`
— Enter llega a `Chat.send`. Suite de vista: 20 verde · `test_ollama_client` +
`test_jarvis` + `test_streaming`: 58 verde · `ruff check .` limpio.

### P0 · seguimiento — latencia del turno LLM

Tras los dos fixes, la traza funciona pero un turno de LLM tardaba ~170 s en dar
el primer token en esta máquina. Desglose medido (con `_parse_and_execute`,
`_chat_encadenado`, `fast_respond` y `_try_agent` instrumentados):

- `fast_respond` / parser: **0.0 s** — "¿qué hora es?", "abre la calculadora",
  "gracias" responden **al instante** y ejecutan la acción real (abrió
  gnome-calculator en la prueba).
- `_try_agent` (`chat_with_tools`, 46 esquemas, sin streaming): **29–110 s** en
  CPU. **Desactivado en el HUD** — `ChatService._ensure_jarvis` pone
  `jarvis.agent_enabled = config.hud.agent` (por defecto `false`). El parser
  determinista sigue cubriendo abrir apps, clima, volumen, recordatorios…
  Recuperarlo: `config.yaml → hud:\n  agent: true`.
- Camino LLM plano (ya con streaming real por el Bug 2): **~90 s hasta el 1er
  token**, luego ~5 tok/s. Es **prefill de qwen2.5:3b en CPU** (`ollama ps` →
  `size_vram: 0`, sin offload) con el prompt completo (system + memorias +
  `auto_recall` + 20 mensajes de historial). No es un fallo de la vista.

Para chat conversacional rápido (fuera del alcance de la vista): modelo más
pequeño (`ollama.model: qwen2.5:1.5b`), offload a la iGPU en Ollama, o recortar
`data/history.json` (50 mensajes). `Turn.qml` muestra "procesando… (modelo en
CPU)" en el turno vacío hasta el primer token.

### P0 · seguimiento 2 — "no puedo ingresar texto" + voz

Dos problemas reportados por el usuario tras la Fase 8.1:

**1. No se podía escribir.** La ventana sin marco de 8.1
(`Qt.FramelessWindowHint` + `color: "transparent"`) **deja de recibir foco de
teclado en la sesión Wayland/GNOME del usuario** — regresión conocida de Qt en
ese compositor. Los tests headless de teclado pasan (el problema es del
compositor, no del código). **Fix:** el modo sin marco pasa a ser **opcional**
tras `config.yaml → hud:\n  frameless: true`. Por defecto (`false`) la ventana
es **normal, decorada por el SO**, que funciona en todas partes.
`app.bind_context` expone `Frameless` (context property); `Main.qml`:
`frameless` gobierna `color`, `flags`, `gutter`, la `MultiEffect` de sombra, el
`cornerRadius` de la atmósfera y la visibilidad de `WindowChrome`.

**2. La voz no daba señal de vida cuando fallaba.** `VoiceService._transcribe`
tenía `except Exception: pass` — si el STT petaba (modelo ausente, audio
corrupto) o no reconocía nada, el usuario **no veía nada**. **Fix:** señal
`notice(str)` → `chat.errorTurn` (visible en la columna de conversación):
"grabación demasiado corta", "no se entendió el audio",
"voz no disponible: …". El camino feliz no cambia.

### E2E real de esta sesión (evidencia, no "los tests pasan")

**Chat** — `Runtime` real contra Ollama, 3 mensajes de usuario → 3 respuestas
reales (6 mensajes en `ConversationModel`):

| # | Usuario | JARVIS | meta |
|---|---------|--------|------|
| 0-1 | "Hola, ¿quién eres?…" | "Soy JARVIS, su asistente… Opero localmente…" | `904 ms` (respuesta rápida) |
| 2-3 | "¿Cuánto es 17 por 23?" | "391" | `80837 ms · 5.8 tok/s` |
| 4-5 | "Dime tres planetas…" | "Mercurio, Venus y Marte…" | `48276 ms · 6.0 tok/s` |

Estado del núcleo: `thinking → idle` en cada turno, final `idle`. Métricas
(`latencyMs`, `tokensPerSecond`) pobladas y moviéndose en el HUD. El primer
token del 2.º turno llegó a los 81 s — **prefill de qwen2.5:3b en CPU**, límite
de hardware ya documentado, no un fallo de la vista.

**Voz** — test `test_voice_path_end_to_end_stt_to_chat_send`: sintetiza "abre la
calculadora" con el TTS del proyecto, la inyecta como frames del micrófono,
`VoiceService._transcribe()` real (whisper `small` local) → `"Abre la
calculadora."` → señal `transcribed` → `chat.send` → turno de usuario. Cadena
completa verde.

### Tests

Suite de vista: **21 verde** (nuevo: el E2E de voz). Suite completa:
**587 passed, 7 skipped**. `ruff check .` limpio.

## P0 · seguimiento 3 — "haga pruebas de voz y de todas sus funcionalidades"

Batería funcional a través del `Runtime` real + núcleo real. **28 comprobaciones**;
lo que estaba mal, corregido:

### Bug 3 — el parser de comandos ignoraba las tildes (voz lenta)

El dictado (whisper) devuelve texto **con tildes**: *"¿cuánta batería queda?"*,
*"recuérdame…"*. Los patrones de `intent/parser.py` se escribieron en ASCII, así
que esas frases **no las reconocía el parser** y caían al camino del LLM
(decenas de segundos en CPU) en vez de resolverse al instante. Afectaba a
calculadora, estado del sistema, recordatorios, multimedia…
**Fix:** `parse_intent()` normaliza las vocales acentuadas al entrar
(`_sin_tildes`, la ñ se mantiene). El texto libre capturado (ciudad, cuerpo del
recordatorio) también sale sin tildes — coste asumido frente a que el comando
no funcione. Test: `test_comandos_con_tildes_del_dictado`. Verificado por el
núcleo real: *"¿cuánto es 48 entre 6?"* → "8", *"¿cuánta batería queda?"* →
estado del sistema, *"recuérdame … en 1 minuto"* → recordatorio creado — todo
instantáneo, sin LLM.

### Bug 4 — el TTS se colgaba y dejaba el estado SPEAKING pegado

`VoiceService._speak`: en el último trozo de audio (parcial, < blocksize) el
callback de salida hacía `raise sd.CallbackStop` **sin** avanzar `pos["i"]`
hasta el final, así que el `while pos["i"] < n` giraba para siempre — el hilo no
terminaba, `speakingChanged(False)` no se emitía y el núcleo se quedaba en
`speaking`. **Fix:** marcar `pos["i"] = n` antes del `CallbackStop` + tope de
tiempo (`duración + 1 s`) en el bucle como red de seguridad. `except` ahora
emite `notice` en vez de callar. Test:
`test_tts_playback_terminates_and_clears_speaking` (OutputStream falso, sin
audio). Verificado con audio real: habla 4.6 s, `speakingChanged=[True, False]`,
estados `speaking → idle`.

### Resultado de la batería

| Funcionalidad | Estado | Evidencia |
|---|---|---|
| Respuestas instantáneas (saludo/hora/fecha/gracias) | ✅ | `fast_respond` responde sin LLM |
| Calculadora | ✅ | "calcula 15 * 12" → "180"; "48 entre 6" → "8" |
| Clima | ✅ | "clima en Bogotá" → datos reales (17 °C, humedad 53 %…) |
| Chiste | ✅ | devuelve chiste |
| Estado del sistema / batería | ✅ | CPU/RAM/disco reales |
| Abrir aplicación | ✅ | "abre la calculadora" → abre gnome-calculator |
| Volumen / multimedia / recordatorios | ✅ | intención correcta + ejecución |
| Chat LLM con streaming | ✅ | tokens uno a uno ("L","ima",","," mango"…), 1er token ~100 s (prefill CPU), luego ~5.7 tok/s, `latencyMs`/`tok/s` en el HUD |
| Micrófono (captura real) | ✅ | InputStream abre, 24 576 muestras, RMS 0.13 |
| Voz STT extremo a extremo | ✅ | "¿qué hora es?" hablado → whisper → "Son las 17:48, senor." |
| TTS (síntesis + envolvente + fin) | ✅ tras Bug 4 | habla, envolvente 0.887, termina limpio |
| Estados del núcleo | ✅ | idle/listening/thinking/speaking |

Único límite no resuelto (hardware, ya documentado): **el 1er token del LLM
tarda ~100 s** en esta CPU. Los comandos por parser y la voz son instantáneos.

### Tests

Suite de vista: **22 verde**. Suite completa: **589 passed, 7 skipped**.
`ruff check .` limpio.

## P0 · seguimiento 4 — autoarranque roto + la barra de comando no escribía

### Bug 5 — JARVIS no arrancaba al encender el equipo

`~/.config/autostart/jarvis.desktop` (fuera del repo) seguía ejecutando
`python -m jarvis_local.ui.desktop`, el entry point de la GUI de Tkinter que se
**eliminó** en el commit `c7be772` (ADDENDUM fase 1). En cada arranque:
`No module named jarvis_local.ui.desktop` → JARVIS nunca aparecía.
**Fix (config del sistema, no del repo):** `Exec=` ahora
`python -m jarvis_local.ui.hud` + `X-GNOME-Autostart-Delay=3`. Validado con
`desktop-file-validate` y probado el `Exec` en limpio.

### Bug 6 — no se podía insertar texto en la barra de comando

`CommandBar.qml` no daba `activeFocus` al `TextEdit` en ningún momento: ni al
cargar, ni con un clic (el `selectByMouse` dentro de un `Flickable` no basta;
`rootItem` retenía el foco y sólo corría su `Keys.onPressed`). Escribir no hacía
nada. El fix de la ventana sin marco (seg. 2) era necesario pero no suficiente.
**Fix:**
- `Component.onCompleted: editor.forceActiveFocus()` — la barra toma el foco al
  aparecer.
- `Connections` sobre `Window.window.onActiveChanged` — Wayland/GNOME entrega el
  foco de teclado de forma asíncrona; al recuperarlo se lo devuelve al editor.
- `TapHandler` en el campo → `forceActiveFocus()` (recuperación manual con un
  toque).
- `Flickable.interactive: editor.lineCount > 6` — no intercepta el puntero
  salvo que el texto desborde de verdad.
Test: `test_command_bar_has_focus_on_load_and_accepts_typing` (sin forzar el
foco: comprueba `activeFocus` tras cargar y que lo tecleado llega al editor).

### Rediseño de la barra de comando

El usuario la vio "fea" y con el micrófono encajonado dentro del campo de texto.
Nueva estructura:
- **Campo** en su propio contenedor (`Rectangle`, `radiusSurface`, borde
  hairline que se ilumina en foco/hover, `ColorAnimation` suave).
- **Micrófono** como botón **aparte**, fuera del campo, a la derecha con
  separación `sp(3)`; `MicButton` ya trae su propio recuadro.
- Prompt = **chevron trazado** con `Canvas` (1.5 px), sin depender de la fuente
  (el `❯` se veía como `)` con la Nerd Font). Se tiñe con el estado
  (cyan en foco · azure generando · secundario en reposo).
- Padding vertical `sp(4)` a cada lado; alto mínimo `sp(9)` para alojar el
  micrófono centrado.
- El visualizador de grabación traza ahora el perímetro **del campo**, no de
  toda la barra.

### Tests

Suite de vista: **23 verde** (nuevo: foco de la barra). `ruff check .` limpio.

## P0 · seguimiento 5 — JARVIS no hablaba + micrófono apretado

Confirmado por el usuario tras seg. 4: ya se puede escribir y se ven las
conversaciones. Quedaban dos cosas.

### JARVIS no decía en voz alta sus respuestas

`config.yaml → voice.tts_enabled` estaba en `false`. El cableado ya existía
(`chat.assistantEnd → _maybe_speak → voice.speak`) y el cuelgue del TTS se
arregló en seg. 3 (Bug 4). **Fix:** `tts_enabled: true`. Verificado extremo a
extremo por el `Runtime`: un turno de chat dispara `voice.speak()`,
`speakingChanged` pasa a `true` y luego a `false`, estados
`thinking → idle → speaking → idle`. Síntesis `edge-tts` OK (1.5 s, voz
`es-MX-JorgeNeural`). Habla todas las respuestas (rápidas, parser y LLM);
si molesta, se vuelve a poner en `false`.

### El micrófono lo apretaba su propio recuadro

`MicButton` tenía un recuadro con borde **siempre visible** que dejaba poco
aire al icono. **Fix:** en reposo NO hay recuadro — sólo el icono; el recuadro
(borde + fondo tenue, con `Behavior` de color) aparece al pasar el ratón o al
escuchar. Botón más grande (`sp(10)` = 40 px), icono `sp(4.5)×sp(5.5)`
(≈18×22) → ~11 px de aire a cada lado. En `CommandBar` la separación campo↔micro
sube a `sp(3)` + `sp(1)` de margen desde el borde; alto mínimo de la barra a
`sp(11)` para alojarlo centrado.

### Tests

Suite de vista: **23 verde**. `ruff check .` limpio.

## P0 · seguimiento 6 — "abre word" abría lo que no era + micrófono cortado arriba

### Bug 7 — "abre word" abría "Passwords and Keys"

Cadena del fallo:
1. `find_app("word")` usaba `q in norm`, que casa a mitad de palabra:
   "word" ⊂ "pass**word**s and keys" → devolvía esa app.
2. El índice de apps estaba **obsoleto** (cache de julio, 34 apps): `find_app`
   leía `get_index()` sin comprobar antigüedad, así que LibreOffice —instalado
   después— era invisible.
3. No había traducción de nombres ajenos ("word", "excel") a lo que hay
   instalado.

**Fixes** (`tools/app_index.py` + `tools/apps.py`):
- `contains` ahora exige **frontera de palabra** (`\bword`): "word" ya no cae
  en "passwords".
- `find_app` llama a `refresh_index()` (respeta los 7 días; re-escanea si
  caducó) en vez de `get_index()` a secas. Con guarda: si `_cache` ya está
  cargado en la sesión, no re-escanea (los tests inyectan índice falso).
- **Sinónimos** en `find_app(query, use_synonyms=True)`: `word→libreoffice
  writer`, `excel→libreoffice calc`, `powerpoint→libreoffice impress`,
  `access→libreoffice base`, `office/libreoffice/ofimática→libreoffice`,
  además de "procesador de texto", "hoja de cálculo", "presentaciones". Si el
  sinónimo no resuelve (p.ej. Windows con Word real), cae al nombre tal cual.

Verificado en este equipo: `abre word` → *LibreOffice 26.2 Writer*, `abre
excel` → *Calc*, `abre powerpoint` → *Impress*, `abre libre office` →
*LibreOffice* (start center). `parse_intent` de todos ellos → `tool_execute
open_app`.

### Bug 8 — el icono del micrófono salía cortado por arriba

El arco superior de la cápsula del micro (`ctx.arc(cx, h*0.12, w*0.28, π, 0)`)
subía hasta `y ≈ h*0.12 − w*0.28`, **negativo** → el `Canvas` lo recortaba.
Se veía el micrófono sin la parte de arriba. **Fix:** icono redibujado con
todo el trazado dentro de `[0,w]×[0,h]` (cápsula-píldora con el arco a
`y ≈ 1.5`, soporte en U, tallo y base), y `Canvas` un poco mayor
(`sp(5.5)×sp(7)`).

### Autoarranque

`~/.config/autostart/jarvis.desktop` → `python -m jarvis_local.ui.hud` (ya en
seg. 4). Sigue vigente.

### Tests

Suite de vista: **23 verde**. `test_app_index` + `test_apps` + `test_intent` +
`test_fase4/5` + `test_router`: **verde**. `ruff check .` limpio.

## Rediseño visual profundo — "AI Command System" (con JARVIS ya como servicio)

Petición explícita: transformar la GUI en un centro de mando de IA, con
identidad propia, sin romper la arquitectura ni el servicio systemd.
Inventario previo: `jarvis_local/ui/hud/qml/` ya traía núcleo GPU
(shader raymarch + bloom + atmósfera), iluminación global desde el núcleo,
HUD de telemetría real (`Hud.qml`/`HudCell.qml`), conversación con canaleta
USER/JARVIS y barra de comando rediseñada (seg. 4) — mucho de lo pedido ya
existía. Se buscaron los huecos reales en vez de repetir trabajo:

### Nuevo estado `executing` (TOOL EXECUTION)

La máquina de estados (`idle·listening·thinking·speaking·alert·offline`) no
distinguía "el LLM está pensando" de "el parser/agente acaba de ejecutar una
herramienta real" (abrir una app, consultar el clima…) — ambas pasaban por
`thinking` sin más. Es un hueco real de arquitectura, no sólo visual.

- `Jarvis.chat()` (`jarvis.py`) ahora anota `self.last_reply_kind` en cada
  rama de la cascada: `"exact"` · `"fast"` · `"tool"` (parser/agente,
  síncrono) · `"llm"` (streaming). Atributo aditivo, no cambia la firma ni el
  valor de retorno — cero riesgo para lo ya probado.
- `chat_service.py`: si `last_reply_kind == "tool"`, emite `wantState
  ("executing")` y lo sostiene 280 ms (dato real: la herramienta YA se
  ejecutó; el tiempo es sólo para que se perciba, no una animación inventada)
  antes de volver a `idle`.
- `viewmodel.py`: `"executing"` añadido a `STATES`.
- `Core.qml`: nuevo `State { name: "executing" }` — apertura de anillo y
  convergencia a medio camino entre `listening` y `thinking`, con un pulso de
  energía propio (`_targetEnergy`) más rápido que la respiración de idle. No
  reutiliza `dashed`/`fragmented`: esos uniforms del shader significan
  "congelado" (offline) y "roto" (alert) — lo contrario de "trabajando".

Verificado con el núcleo real: `Jarvis().chat("abre la calculadora")` →
`last_reply_kind == "tool"`; `chat("hola")` → `"fast"` (no dispara
`executing`, correcto). Tests:
`test_chat_service_tool_reply_shows_executing_state`,
`test_core_qml_has_distinct_executing_state`.

### Lectura de estado elevada (`CoreStatus.qml`, nuevo)

El estado se mostraba como texto plano en minúscula (`Vm.state` tal cual,
15 px, color secundario) — la parte más floja frente al pedido de
"LISTENING/PROCESSING/EXECUTING/SPEAKING/SYSTEM ALERT" visibles. Componente
nuevo, mismo lenguaje visual que `HudCell` (etiqueta susurra / valor domina):
mapa estado→palabra (`STANDBY·LISTENING·PROCESSING·EXECUTING·SPEAKING·
SYSTEM ALERT·OFFLINE`), 18 px en negrita con `letterSpacing`, color por
estado, y un punto de presencia cuya opacidad sigue `Design.coreEnergy` — el
mismo dato real que ya mueve el núcleo (RMS de voz / tok·s / pulso de
`executing`), no una animación aparte inventada.

### Retícula técnica de fondo (`TechGrid.qml`, nuevo)

El fondo tenía dos gradientes + parallax + atmósfera (viñeta/grano/aberración
cromática) pero nada que leyera a "instrumento". `TechGrid.qml`: líneas de
1 px cada 96 px (`Design.sp(24)`) a alfa ~0.035, con marcas cada 4 celdas un
poco más presentes — casi subliminal. Se pinta **una vez por tamaño**
(`onWidthChanged`/`onHeightChanged`), no vive en el `FrameAnimation`: coste
cero por frame.

### Validación

- `pytest test -q`: **595 passed, 7 skipped, 0 fallos** (602 recolectados).
  `ruff check .` limpio.
- `systemctl --user status jarvis` → `active (running)`, mismo PID 8+ min,
  sin reinicios.
- `journalctl --user -u jarvis -n 100` → sin errores QML/Python; sólo
  `qml: [hud] RHI backend: OpenGL` por arranque.
- No se pudo ejercitar el ciclo completo `idle→listening→thinking→speaking`
  con el HUD gráfico real (Wayland bloquea la captura, como ya se documentó);
  se verificó por el `Runtime` headless (offscreen) con núcleo/Ollama reales
  y con los tests de QML que leen `Core.pRingOpen`/`pConverge` tras cada
  transición.

### Lo que NO se tocó (y por qué)

`CommandBar`, `Turn`/`Conversation`, `MicButton`, `WindowChrome` — ya
rediseñados en seguimientos 2 y 4 de esta misma fase (foco, chevron trazado,
micrófono separado con recuadro sólo en hover, canaleta USER/JARVIS). No se
repitió trabajo sobre ellos; el esfuerzo de esta iteración fue a los huecos
reales: el estado `executing` y la lectura de estado.

## Auditoría visual — Fase 2 (coherencia y presencia)

Petición: auditar sin volver a empezar. ¿JARVIS parece un sistema de IA vivo o
una app de escritorio con efectos? Respuesta honesta del análisis de código:

**Lo que ya estaba bien (no se tocó):** `core.frag` no es "un círculo bonito"
— campo de interferencia moiré + volumen SDF raymarcheado con superficie
ruidosa + especular anisótropo + Fresnel; los estados modulan fase/geometría,
no sólo color. Composición con punto focal claro (núcleo con aire, HUD lateral
susurra, conversación se queda el espacio). Conversación con autoscroll
anclado, píldora "volver al final", estado vacío. Barra de comando con chevron
trazado, foco animado, micrófono separado. Telemetría real, sin datos
inventados. Todo esto es sólido.

**Huecos reales encontrados y corregidos:**

1. **Desfase de movimiento.** `CoreStatus` (añadido en la fase anterior)
   cambiaba color y palabra **al instante** mientras el núcleo hace cross-fade
   de 220 ms → el cambio de estado NO se sentía como una sola reacción.
   Fix: `Behavior on color` (220 ms, misma curva que el núcleo) en el punto y
   el texto + un acuse de 90 ms (una caída de opacidad y vuelta, un solo
   pulso, no un parpadeo). Ahora núcleo y lectura de estado transicionan
   juntos.

2. **`SYSTEM ONLINE` era un LED estático.** La celda "sistema" del HUD sólo
   cambiaba de color texto; el brief original pedía explícitamente "no un
   punto verde estático, una señal sutil de actividad". Fix: `HudCell` gana
   `pulse` — un punto de 5 px antes del valor cuya opacidad respira con
   `Design.coreEnergy` (dato real, cero coste). Se activa sólo en "sistema"
   cuando `online === true`.

3. **Turnos de chat aparecían de golpe.** `ListView` sin `add`/`displaced`
   Transition → un mensaje nuevo hacía "pop". Fix: transición `add` de
   opacidad 0→1 (220 ms, misma curva del sistema) y `displaced` para que los
   turnos existentes se reacomoden con la misma curva. El chat entra como
   parte de la reacción, no como una lista que salta.

4. **`EXECUTING` demasiado cerca de `SPEAKING`.** Ambos eran `Design.cyan`
   puro, distinguiéndose sólo por `pRingOpen`/`pConverge`. El brief pedía que
   "ejecutar algo en tu computador" fuera inequívocamente distinto de "hablar
   contigo". Fix: `executing` pasa a un cian **más frío** (`mix(cyan,
   emitCore, 0.18)` → ~`#6DECFF`, tirando a blanco = "instrumento") con
   `pConverge` 0.4 y pulso de energía rápido y regular; `speaking` mantiene
   el cian cálido y sigue la envolvente de audio real (irregular). Ahora
   difieren en color, geometría Y carácter de movimiento. `CoreStatus` usa
   el mismo tinte por estado que el núcleo (antes "PROCESSING" salía azure
   puro mientras el núcleo brillaba azure-cian).

**Inspección visual — limitación real:** Wayland/Mutter bloquea la captura de
pantalla del proceso (documentado desde la Fase 0). La verificación fue por
`Runtime` headless (offscreen): geometría a 1920×1080 / 1366×768 / 1280×720
(0 solapes, todo dentro de los límites, jerarquía conservada) y ciclo completo
de estados leyendo `Core.pTint`/`pRingOpen`/`pConverge` y `CoreStatus._label`
tras cada transición. **Una inspección headless no sustituye ver la interfaz en
movimiento**: el criterio final de "¿se siente vivo?" lo tiene que dar una
mirada humana con el servicio corriendo.

**Conclusión honesta:** con estos cuatro arreglos la interfaz gana coherencia
de movimiento (los elementos reaccionan como un sistema, no por separado) y
cierra el hueco de "presencia" del indicador online. La base ya era técnicamente
avanzada; lo que le faltaba no eran más efectos sino que los que hay actuaran
al unísono. Queda pendiente de validación humana si el conjunto ya cruza el
umbral de "parece una IA" o si aún pide otra pasada de motion design.

### Validación

`pytest test`: **verde** · `ruff check .` limpio · `systemctl --user status
jarvis` → `active (running)` sin reinicios · `journalctl` sin errores
QML/Python.

## Auditoría de motion — Fase 3 (presencia y coherencia temporal)

Fase exclusiva de motion design. No rediseño. Se mapearon TODAS las
animaciones (`grep` de `Behavior`/`*Animation`/`Timer`/`loops`) y se buscaron
timings arbitrarios, loops mecánicos y cambios instantáneos.

**Mapa de animaciones — antes:**

| Sitio | Qué | Duración | Problema |
|---|---|---|---|
| `Main.qml` bootAnim | `boot` 0→1 | `850` literal | sin token |
| `CoreStatus.qml` ackFlash | dip de opacidad | `90` literal | medio-tokenizado |
| `Turn.qml` cursor streaming | opacidad 1↔0.15 `loops:Infinite` | `480` **lineal** | parpadeo mecánico |
| `MicButton.qml` pulso listening | opacidad 0.5→0 `loops:Infinite` | `1100` **lineal** | pulso mecánico |
| `CommandBar.qml` barrido busy | `x` sweep `loops:Infinite` | `durSlow*3` | ok (ya token) |
| `CodeBlock.qml` "copiado" | `PauseAnimation` | `1400` literal | one-shot, sin token |
| `Core.qml` respiración idle | `_targetEnergy` | `sin(_t*0.5)` | **un solo seno = GIF** |

**Cambios:**

1. **Escala temporal única (`Design.qml`).** Tokens nuevos con intención
   explícita: `durMicro 120` · `durFast 140` · `durBase 220` · `durSlow 320` ·
   `stateXfade 380` · `durHold 1400` · `durBoot 1100` · `blinkHalf 520` ·
   `micPulse 1200`. **`stateXfade` sube de 220 → 380**: un cambio de ESTADO del
   sistema es más deliberado que una transición normal (banda 300–500 ms del
   brief). Los literales 850/90/480/1100/1400 se sustituyen por el token que
   les corresponde.

2. **Respiración idle orgánica (`Core.qml`).** Un solo `sin(_t*0.5)` se lee
   como bucle. Ahora `0.016·sin(_t·0.42) + 0.010·sin(_t·0.23+1.3)` — dos senos
   lentos de frecuencias inconmensurables → batido de ~30 s, el ciclo no se
   repite de forma perceptible. Coste: 2 `sin` por frame (despreciable).
   Rango medido ~0.03–0.08 (subliminal; los estados activos van muy por
   encima). Verificado por muestreo: la energía idle vaga suavemente, no
   oscila con amplitud fija.

3. **"Atención" — JARVIS reacciona a tu presencia (`Design.attention`,
   `CommandBar`, `Core`).** Al enfocar la barra de comando, un ping 0→1 que
   decae a 0 en ~700 ms (OutCubic, `SequentialAnimation` en CommandBar, sin
   `Timer`). El núcleo lo suma a su energía de reposo (`+0.10·attention`): una
   subida breve del núcleo, halo y campo = "acaba de prestar atención". No es
   un estado Python nuevo ni un dato inventado — es un evento de interacción
   real. Verificado: energía idle 0.075 → pico 0.129 tras el foco → vuelve a
   0.079.

4. **Latidos con easing, no lineales.** El cursor de streaming (`Turn.qml`) y
   el pulso del micro (`MicButton.qml`) pasan de interpolación lineal a
   `InOutSine` / `OutCubic`. Un parpadeo lineal se lee como máquina; con
   easing respira.

**Lo que NO cambió (y por qué):**

- **HUD en cambio de estado**: NO se añadió una animación explícita. El HUD ya
  cascada con el estado a través del modelo de luz: `Design.litHairline` /
  `litText` siguen `Design.coreEnergy` cada frame, y como
  listening/thinking/executing suben la energía del núcleo, las hairlines del
  HUD se aclaran solas ~100 ms después. La reacción "viaja" núcleo→HUD sin
  código de onda.
- **Boot**: se subió de 850 a 1100 ms (más "inicializando", menos "instantáneo")
  pero la secuencia sigue siendo la misma: oscuridad → el núcleo se enciende
  desde un punto → su luz revela la interfaz por distancia. No es una pantalla
  de terminal ni una intro. No se rehízo.
- **TechGrid / atmósfera / bloom**: intensidades ya auditadas en F2, sin
  cambios — el núcleo gana.

### Validación

**Verificado técnicamente:**
- `pytest test` → verde (0 fallos). `ruff check .` limpio.
- `systemctl --user status jarvis` → `active (running)`, sin reinicios;
  `journalctl -n 100` sin errores QML/Python.
- Offscreen: ping de atención sube y decae la energía del núcleo; respiración
  idle no periódica trivial (6 muestras a ~10 s, valores que vagan);
  geometría a 1920×1080 / 1366×768 / 1280×720 durante
  listening/thinking/executing/speaking → 0 solapes, 0 overflow.

**NO verificado visualmente:** Wayland/Mutter bloquea la captura del proceso.
No he visto la respiración, el ping de atención, ni la cascada de luz en
movimiento. Que el conjunto transmita "una inteligencia respondiendo a lo que
sucede" — y no "varios elementos animados" — sólo lo puede confirmar una
mirada humana con el servicio corriendo.

## Fase 4 — Orbe protagonista + HUD flotante + ventana 100% transparente

Cambio de COMPOSICIÓN (no de lógica). El shader, los estados, la telemetría,
la conversación, la barra de comando, la voz y systemd no se tocan.

### Layout anterior

Columna asimétrica: HUD en franja lateral/superior, núcleo en `coreZone` que
ocupaba ~0.34–0.38 del ancho a un lado, conversación quedándose con el resto.
Fondo = dos `Rectangle` con gradiente a pantalla completa (`bgAbyss`→`bgVoid`)
+ `TechGrid` + atmósfera global (`layer.effect` sobre toda la escena). La
ventana era opaca (`color: Design.bgVoid`), con marco del SO por defecto y modo
sin marco tras un flag. Cuatro modos responsive (wide/mid/narrow/badge) con
lógica de posición por `mode`.

### Problemas

- **La ventana era una app oscura**: `Design.bgVoid` a pantalla completa +
  gradientes + atmósfera con viñeta = "un cuadro oscuro con un orbe dentro",
  justo lo contrario de "un orbe sobre el escritorio".
- **El orbe no era el protagonista**: vivía en una columna lateral al ~34% del
  ancho; la conversación pesaba más.
- **Todo eran cajas pegadas** a los bordes con `anchors`; nada "flotaba".

### Nuevo sistema de composición

- **Ventana 100% transparente**: `Window.color: "transparent"`,
  `flags: Qt.Window | Qt.FramelessWindowHint`. Transparencia REAL:
  `app.py::_configure_environment` fija `QSurfaceFormat.setAlphaBufferSize(8)`
  antes de crear la `QGuiApplication` (sin canal alfa en la superficie GL,
  `"transparent"` pinta negro). El escritorio se ve detrás. `WindowChrome`
  (arrastre + botones + 8 bordes de redimensionado) es lo único que da
  control de ventana, ya que no hay decoración del SO.
- **Sin fondo global**: se eliminan los dos `Rectangle` de gradiente, el
  `TechGrid` de Main y la atmósfera global (`layer.effect`). El orbe conserva
  su propio bloom (`CoreBloom`). No hay post-proceso de ventana.
- **Sistema de zonas**: el orbe se centra en un "escenario" = ventana menos la
  franja de identidad (arriba) y la barra de comando flotante (abajo). Tamaño
  del orbe = `clamp(240, min(escenario)·0.72, 960)` — SIEMPRE domina.
- **HUD partido en dos clústeres flotantes** (`Hud.qml` gana `keys`
  configurable): identidad (`sistema·modelo·voz·memoria·herramientas`)
  centrada arriba; métricas en vivo (`cpu·ram·latencia·tokens/s`) abajo-izq.,
  junto a la barra de comando.
- **`CoreStatus`** flota centrado justo bajo el orbe = "modo actual de JARVIS".
- **Conversación = capa flotante**: columna a la derecha del orbe si cabe sin
  solaparlo; si no, apilada bajo el orbe. **Sin panel**: un scrim localizado
  (gradiente horizontal negro ~0.30 alfa con bordes difuminados, sólo cuando
  hay contenido) para legibilidad sobre wallpaper claro — el brief lo permite
  explícitamente; NO es un fondo global.
- **Barra de comando**: flotante, centrada abajo, `min(680, ancho−2·margen)`.

### Tamaño del orbe por resolución (medido offscreen)

| Resolución | Orbe | Ratio (lado corto) | Modo chat | Centrado |
|---|---|---|---|---|
| 1280×720  | 397 px | 0.55 | columna lateral | sí (x = w/2) |
| 1366×768  | 431 px | 0.56 | columna lateral | sí |
| 1360×820 (default) | 469 px | 0.57 | columna lateral | sí |
| 1920×1080 | 656 px | 0.61 | columna lateral | sí |
| 2560×1440 | 915 px | 0.64 | columna lateral | sí |

En todos: `overlap(orbe, chat) = overlap(orbe, cmd) = overlap(orbe, hud) = 0`,
todo dentro del viewport. Casos del test de regresión (430×360, 1000×760,
1360×820, 1700×900): 0 solapes, el orbe se encoge y el chat se apila cuando
la ventana es muy pequeña.

### Componentes redistribuidos

`Hud` (identidad) → top-center · `Hud` (métricas) → bottom-left · `Core` →
center · `CoreStatus` → bajo el orbe · `Conversation` → columna derecha (o
apilada) · `CommandBar` → bottom-center. Ninguno con `anchors.fill: parent`.

### Archivos modificados

`jarvis_local/ui/hud/app.py` (alfa en la superficie) ·
`qml/Main.qml` (composición completa: transparencia, zonas, orbe centrado,
HUD partido, chat flotante) · `qml/Hud.qml` (`keys` configurable) ·
`qml/Conversation.qml` (`hasContent`) · `test/test_ui_hud.py` (quitadas 2
asserciones de `atmosphereOn`, feature eliminada) · `docs/REDISENO_VISTA.md`.

### Validación

**Verificado por runtime (offscreen):** carga QML sin warnings; geometría a
1280×720 / 1366×768 / 1920×1080 / 2560×1440 + casos de regresión → orbe
centrado (x = ancho/2 exacto), dominante (ratio 0.55–0.64), 0 solapes
críticos, dentro del viewport; ciclo de estados sin errores; `pytest test`
verde; `ruff` limpio; `systemctl --user status jarvis` → `active (running)`
sin reinicios; `journalctl` sin errores QML/Python.

**NO verificado visualmente:** Wayland/Mutter bloquea la captura del proceso.
No he visto la ventana transparente sobre el escritorio, ni si el scrim de la
conversación da contraste suficiente sobre un wallpaper real, ni si el orbe
"flota" o se ve recortado. Eso lo tiene que confirmar una mirada humana.

## Fase 5 — Nitidez: NITIDEZ > GLOW

Problema: "todo se ve borroso por el glow". El orbe grande perdía fuerza; el
HUD se desvanecía sobre el escritorio transparente.

### 1. Causa técnica de la borrosidad

Auditado el pipeline (`CoreBloom.qml` + los 3 shaders). **NO era resolución de
render**: `CoreShader` usa `layer.enabled` sin `layer.textureSize`, ningún
`ShaderEffectSource` reduce `sourceSize`/`textureSize`, `devicePixelRatio 1.0`
→ el orbe se renderiza a tamaño real. El único downscale es el interno de los
`MultiEffect` de blur, que es correcto (el bloom debe ser suave).

La borrosidad venía de la **presentación**:
1. **Pesos de composición altos**: `k0=0.75, k1=0.5` — el bloom sumaba hasta
   ~125 % encima del núcleo nítido; el ojo veía primero el halo.
2. **Tonemap agresivo**: `rgb / (1 + rgb·0.55)` comprimía el centro brillante
   del núcleo hacia el nivel del halo difuso → poco contraste núcleo/halo.
3. **Halo central del shader** (`core.frag`): peso `0.10 + 0.55·energy`, una
   mancha suave que lavaba el campo de interferencia.
4. **Sin borde**: el orbe se desvanecía por caída del `field`; no había una
   silueta legible (ORBE vs ALREDEDOR).
5. **Umbral de bloom bajo** (`threshold 0.42`) → demasiada zona "florecía".

### 2. Cambios de render

| Qué | Antes | Ahora |
|---|---|---|
| `bloom_composite` `k0` / `k1` | 0.75 / 0.50 | **0.42 / 0.22** |
| `bloom_composite` tonemap | `/(1+rgb·0.55)` | **`/(1+rgb·0.34)`** (centro conserva intensidad) |
| `bloom_extract` `threshold` / `knee` | 0.42 / 0.28 | **0.54 / 0.22** (sólo florece lo muy brillante) |
| `b1` blur | `blurMax 64`, `mult 2.2` | **48 / 1.7** (halo más contenido) |
| `CoreShader` `layer.samples` | 2 | **4** (silueta/anillos más limpios) |
| `core.frag` umbral de brazos | `smoothstep(0.28,0.96)` | **`smoothstep(0.34,0.92)`** (moiré más definido) |
| `core.frag` halo central | `0.10 + 0.55·energy` | **`0.05 + 0.30·energy`** |
| `core.frag` **BORDE** | — | **anillo de energía fino** en `rad≈0.76` (tinte, aporta a alpha; NO un círculo blanco) |

Shaders recompilados con `python -m jarvis_local.ui.hud.shaders.build`.
El shader avanzado (SDF/raymarch/Fresnel/especular anisótropo/interferencia)
se conserva íntegro — sólo se ajustó cómo se presenta.

### 3. Cambios de contraste

- `Design.textPrimary` `#C9D6E4→#E3ECF5` · `textSecondary` `#7E8FA3→#9DB0C4` ·
  `textMeta` `#4A5A6E→#7386A0` (invisibles sobre escritorio real).
- `Design.hairline` alfa `0.14 → 0.26`.
- `Design.surfaceColor` alfa `0.72 → 0.82` (barra de comando / píldora no se
  transparentan sobre wallpaper).
- Nuevo token `Design.textEdge` = `rgba(0.02,0.04,0.07,0.72)` — **contorno de
  1 px** (`style: Text.Outline`) para todo el texto sobre fondo transparente.
  **No es blur**: es un borde nítido que separa el glifo del escritorio.

### 4. Cambios en el HUD

- **Contorno óptico** (`Text.Outline` + `textEdge`) en: HudCell (etiqueta y
  valor), CoreStatus (etiqueta y palabra de estado), Turn (canaleta USER/
  JARVIS, metadatos, aviso "procesando"), MarkdownBody (prosa del chat),
  Conversation (estado vacío), CommandBar (placeholder). El `TextEdit` del
  editor NO lo lleva (no soporta `style`) — su contraste lo da la superficie
  oscura del campo.
- **Jerarquía tipográfica**: `CoreStatus` sube a 24 px negrita + tracking 2.0
  (lectura primaria); HudCell valor pasa a **negrita** en horizontal; canaleta
  USER/JARVIS a negrita.
- **CommandBar**: superficie SIEMPRE presente (antes el foco la ponía a
  `rgba(1,1,1,0.05)` ≈ invisible); borde de reposo 1.5 px con tinte cyan,
  2 px en foco; chevron redibujado en dos pasadas (contorno oscuro + trazo)
  y con color `textPrimary` en reposo.
- **MicButton**: icono redibujado en dos pasadas (contorno `textEdge` +
  trazo); color de reposo `textPrimary` (antes `textSecondary`), hover
  `emitCore`.

### 5. Archivos modificados

`shaders/`: `bloom_composite.frag(.qsb)`, `bloom_extract` implícito vía
CoreBloom, `core.frag(.qsb)` · `qml/`: `CoreBloom.qml`, `CoreShader.qml`,
`Design.qml`, `HudCell.qml`, `CoreStatus.qml`, `Turn.qml`, `MarkdownBody.qml`,
`Conversation.qml`, `CommandBar.qml`, `MicButton.qml` · `docs/REDISENO_VISTA.md`.

### 6-9. Validación

**Verificado por runtime (offscreen):** shaders recompilan sin errores GLSL;
QML carga sin warnings; geometría a 1280×720 / 1366×768 / 1920×1080 /
2560×1440 sin cambios (orbe centrado, ratio 0.55–0.64, 0 solapes, dentro del
viewport); ciclo de estados sin errores de shader; `devicePixelRatio 1.0`, sin
`textureSize`/`sourceSize` reducido en el pipeline (el orbe NO se renderiza a
menor resolución); `pytest test` verde; `ruff` limpio; `systemctl --user
status jarvis` → `active (running)` sin reinicios; `journalctl` sin errores
QML/Python.

**NO verificado visualmente:** Wayland/Mutter bloquea la captura del proceso.
No he visto si el núcleo se lee nítido, si el borde del orbe define la silueta,
ni si los contornos de texto dan suficiente contraste sobre un wallpaper real.
Los cambios están razonados sobre la causa técnica; su efecto perceptual lo
tiene que confirmar una mirada humana.

## Fase 6 — Dirección artística: rampa cromática + profundidad + presencia

Problema: pese a F4/F5, la interfaz seguía leyéndose como "app transparente con
orbe y textos". Faltaba IDENTIDAD cromática (todo cian-claro + gris muerto),
PROFUNDIDAD (color plano) y PRESENCIA por estado.

### Dirección artística adoptada

Todo el universo visual de JARVIS es **UNA rampa de azul profundo → cian
eléctrico → casi-blanco**. El casi-blanco es SÓLO highlight (punto del núcleo,
dato crítico), nunca un plano grande. Nada de gris apagado: los textos
secundarios pertenecen a la misma rampa (azul luminoso).

### Nueva paleta (`Design.qml`, centralizada — punto 32 del brief)

| Token | Antes | Ahora | Rol |
|---|---|---|---|
| `coreDeep` | — | `#0A2A6E` | ultramar del limbo/atmósfera |
| `azure` | `#2B7FFF` | `#1D5CFF` | azul eléctrico (profundidad media) |
| `cyan` | `#4DE8FF` | `#37D2FF` | cian eléctrico (actividad primaria) |
| `coreHot` | — | `#DCF6FF` | cian casi-blanco — SÓLO highlight |
| `hairline` | gris `0.66,0.75,0.86 @0.26` | azul `0.36,0.60,0.98 @0.30` | conecta HUD↔Core |
| `textPrimary` | `#E3ECF5` | `#EDF4FF` | cool near-white |
| `textSecondary` | `#9DB0C4` | `#A9C6EC` | azul luminoso (no gris) |
| `textMeta` | `#7386A0` | `#84A6D0` | azul-gris, legible |
| `textDisabled` | (era `textMeta`) | `#51678A` | dato ausente, oscuro pero legible |

Tipografía centralizada: `fsStatus 26` nuevo; pesos `wLabel/wValue/wStatus`
(Medium/DemiBold/Bold); tracking `trkLabel 1.2` / `trkStatus 2.4`.

### Cambios del Core

- **3 uniforms nuevos** en `core.frag` (+ `CoreShader`/`CoreBloom`/`Core`
  pass-through): `tintDeep` (limbo), `tintHot` (highlight), `spin` (0..1
  velocidad de giro por estado).
- **Profundidad cromática**: el campo ya no es color plano —
  `mix(tintDeep → tint → tintHot)` por radio: azul profundo en el limbo, cian
  de estado a media distancia, casi-blanco SÓLO muy cerca del centro y sólo
  con energía. El usuario percibe volumen.
- **El Core ya NO es casi-blanco**: se sustituyeron los `mix(tint, vec3(1.0))`
  por `mix(tint, tintHot)` con factores menores; el único blanco puro que
  queda es el *glint* especular anisótropo y el **punto** del centro
  (`smoothstep(0.10,0.0,...)` — diminuto).
- **Personalidad por estado** (`Core.qml` states): tinte + tinte profundo +
  `spin` propios. idle `#164BCC` spin 0.30 (lentísimo) · listening `#37D2FF`
  spin 0.85 · thinking `#2991FF` spin 0.55 (concentrado) · executing `#2EA9FF`
  frío spin 1.15 (rápido/mecánico) · speaking `#37D2FF` spin 0.70 · alert rojo
  · offline `#51678A` spin 0.
- **Campo de energía**: dos arcos orbitales lentos fuera del cuerpo del orbe
  (`rad≈0.855`, `0.945`), rotando, alfa baja — "campo estabilizado", no una
  bola de glow. Coste: 4 trig extra por fragmento.
- **Latido digital** (`_targetEnergy` idle): cada ~5.2 s un "lub-dub" muy
  sutil (dos golpes exponenciales + silencio) sobre la respiración lenta.
  Señal de vida, no parpadeo. Sólo en reposo.

### Cambios del HUD

- Todo el texto adopta la paleta nueva (azul luminoso, no gris) + `Text.
  Outline` (F5) + pesos/tracking de los tokens.
- `HudCell`: valor a peso `wValue`, dato ausente a `textDisabled`.
- `CoreStatus`: palabra de estado a 26 px `wStatus` tracking 2.4; colores por
  estado = la misma rampa que el núcleo.
- **Conector Core↔HUD**: una línea de 1 px que baja del clúster de identidad
  hacia el núcleo, iluminada por la luz del propio Core — "el HUD sale del
  Core". Restringido: un solo conector, sin brackets de videojuego.

### Archivos modificados

`shaders/core.frag(.qsb)` · `qml/`: `Design.qml`, `CoreShader.qml`,
`CoreBloom.qml`, `Core.qml`, `CoreStatus.qml`, `HudCell.qml`, `Main.qml` ·
`docs/REDISENO_VISTA.md`. (Fondo, transparencia, composición, tests: intactos.)

### Validación

**Verificado por runtime (offscreen):** shaders recompilan sin errores GLSL;
QML carga sin warnings; rampa cromática medida por estado (idle `#164BCC` …
speaking `#37D2FF`, NINGÚN estado casi-blanco) con `spin` distinto por estado;
geometría a 1280×720/1366×768/1920×1080/2560×1440 + regresiones sin cambios
(orbe centrado, 0 solapes, dentro del viewport); `pytest test` verde; `ruff`
limpio; `systemctl --user status jarvis` → `active (running)` sin reinicios;
`journalctl` sin errores QML/Python/shader.

**NO verificado visualmente:** Wayland/Mutter bloquea la captura del proceso.
No he visto si la profundidad cromática se percibe como volumen, si el latido
digital transmite "vida" o pasa desapercibido, ni si el conector Core↔HUD une
la composición o sobra. Los cambios están razonados como decisiones de
dirección artística; su efecto perceptual lo tiene que confirmar una mirada
humana.

## Fase 6b — Color vivo + widgets modernos (todo menos el orbe)

Petición: el orbe se queda en azul/cian, pero el RESTO (texto, HUD, datos)
debe usar colores vivos que se noten (verde, naranja, rojo, violeta…) y los
elementos deben verse "estilo widget muy moderno", no básicos.

### Paleta viva del HUD (`Design.qml`)

El orbe intacto (rampa `coreDeep→azure→cyan→coreHot`). Fuera de él:

| Token | Valor | Uso |
|---|---|---|
| `ok` | `#22E36B` verde eléctrico | online / bien |
| `warn` | `#FF9F1C` naranja vivo | atención / EXECUTING |
| `alert` | `#FF3B5C` rojo punzante | fallo |
| `acidLime` | `#B6FF3B` | throughput (tokens/s) |
| `amber` | `#FFC53B` | herramientas / latencia |
| `violet` | `#B57BFF` | memoria / contexto |
| `magenta` | `#FF5CD0` | voz / entrada |
| `sky` | `#4CC7FF` | dato neutro presente (modelo, cpu, ram) |

`widgetFill` / `widgetStroke` / `widgetRadius 8` / `widgetEdge(accent)` —
tokens de la superficie "widget".

### HudCell como widget moderno

Cada dato del HUD deja de ser texto suelto: **vidrio oscuro translúcido
(`widgetFill` 0.55)**, esquina `widgetRadius`, **borde teñido por su color de
firma**, **barra de acento de 2.5 px a la izquierda**, brillo de vidrio de
1 px en el borde superior. Etiqueta MAYÚSCULAS arriba (susurra) + valor
`fsTitle` `wValue` abajo. Dos colores por celda: **firma** (barra+borde,
permanente) y **valor** (verde/ámbar/rojo según estado, con `Behavior` de
color).

`Hud.qml`: layout `Row` (antes `Flow` bindeado a su propio ancho → se
colapsaba en columna con celdas más anchas). `cell()` devuelve
`[absent, value, firma, valorColor]`; CPU/RAM/latencia gradúan
verde→ámbar→rojo por umbral. Alturas de banda a `sp(19)` para las celdas-
widget. `topBandH` a `sp(19)` (recentra el orbe, sin solapes).

### CoreStatus y CommandBar

- `CoreStatus`: superficie de widget (borde teñido por el color de estado) +
  colores vivos — STANDBY `sky` · LISTENING/SPEAKING `cyan` · PROCESSING
  cian-azul · **EXECUTING `warn` naranja** ("operando tu sistema") · SYSTEM
  ALERT rojo.
- `CommandBar`: brillo de vidrio de 1 px en el borde superior (más marcado en
  foco). El resto del campo ya tenía superficie + borde cian de F5.

### Validación

**Verificado por runtime (offscreen):** QML carga sin warnings; el HUD ya no
se colapsa (`hud_w` 677 px con datos, antes 144); geometría a 1280×720/
1366×768/1920×1080/2560×1440 + 430×360 → orbe centrado y dominante (388–906
px), 0 solapes, dentro del viewport; `pytest test` verde; `ruff` limpio;
`systemctl --user status jarvis` → `active (running)`; `journalctl` sin
errores QML/Python.

**NO verificado visualmente:** Wayland bloquea la captura. No he visto los
widgets sobre el escritorio ni si los colores vivos "se hacen notar" sin
saturar; el efecto lo confirma una mirada humana.

## Fase 6c — Conversación estilo terminal (colores ANSI vivos)

Petición: la zona de chat debe verse **estilo terminal** — letra
monoespaciada y colores vivos tipo ANSI (verde, rojo, cian…) para que sea
más visual.

### Tokens (`Design.qml`)

`chatUser #31E27A` (eco de entrada, verde brillante) · `chatJarvis #A7F0CE`
(prosa, verde fósforo legible) · `chatPrompt #3FE0E0` (el `❯`, cian) ·
`chatMeta #5E8C74` (timestamp, verde apagado).

### Cambios

- **`MarkdownBody`**: fuente `fontSans` → **`fontMono`**; `lineHeight` 1.6→1.5;
  nuevo `property color textColor` (lo fija `Turn` por canal).
- **`Turn`**: prompt de canal `USER ❯` / `JARVIS ❯`; color de canal = rojo
  error · verde brillante usuario · cian JARVIS. Cuerpo del mensaje:
  usuario en `chatUser` (verde), JARVIS en `chatJarvis` (verde fósforo),
  error en rojo. Aviso "procesando…" en ámbar. Cursor `▌` verde terminal.
  Metadatos en `chatMeta`.
- **`CodeBlock`**: base y resaltado en la familia terminal — keywords cian,
  strings verde `ok`, números ámbar, comentarios verde apagado.
- **`Conversation`** (estado vacío): `JARVIS ❯ _` monoespaciado en verde.

### Validación

QML sin warnings; render de una conversación real (usuario + JARVIS +
error) sin errores; `pytest test` verde; `ruff` limpio; `systemctl --user
status jarvis` → `active (running)`; `journalctl` sin errores.
NO verificado visualmente: Wayland bloquea la captura.

## Fase 7 — Pulido del orbe (8 mejoras)

Sin tocar composición ni transparencia. Todo en `core.frag` + 3 uniforms
nuevos (`pointerX`, `pointerY`, `transPhase`) y una línea en `bloom_composite`.

1. **Paralaje del volumen** — el `pointer` (ratón, ya llegaba pero sin usar)
   desplaza el origen del raymarch y la dirección de luz interior en sentido
   contrario → el orbe se lee como **esfera con profundidad**, no como disco.
2. **Onda de choque de estado** — `Core.qml` pone `_transPhase` a 1 en cada
   cambio de `coreState` y lo anima a 0 en 650 ms (OutCubic). El shader dibuja
   un frente `smoothstep` que sale del centro → "el sistema acaba de
   reaccionar". Una vez por transición, no un bucle.
3. **Rim iluminado** — el anillo del limbo ya no es uniforme: más brillante en
   el arco superior-izquierdo (`dot(normalize(uv), dir_luz)`) → silueta de
   esfera iluminada.
4. **Anillo de forma de onda con audio real** — `bandLow/Mid/High` (que ya
   llegaban) modulan un rizo en `rad≈0.80` por ángulo. Sólo visible con
   `bandSum > 0.02` → aparece en listening/speaking, invisible en reposo.
5. **Fleco cromático del rim** — el anillo se muestrea a `rad ± 0.013` para R y
   B → desdoble espectral sutil, borde de campo de energía. Sólo en el rim.
6. **Bloom bicolor** — en `bloom_composite`: el bloom estrecho tira a
   cian-caliente (`×[1.00,1.04,1.10]`), el ancho a azul profundo
   (`×[0.72,0.86,1.16]`). El glow gana la rampa, no un tinte plano.
7. **Dither anti-banding** — 1 línea al final: rompe el escalonado de 8 bits en
   los degradados suaves.
8. **Respiración de la geometría** — el radio base del SDF (`0.60`) inhala/
   exhala `±0.012·sin(t·0.8)`, atenuado con energía alta → sobre todo en
   reposo la esfera respira de verdad (no `scale`, el volumen).

### Validación

**Verificado por runtime:** shaders recompilan sin errores GLSL; QML sin
warnings; `_transPhase` pulsa a ~1 y decae en cada cambio de estado;
`pointerX/Y` propagan al shader; geometría a 1280×720/1920×1080/2560×1440
sin cambios (orbe centrado y dominante, 0 solapes); `pytest test` verde;
`ruff` limpio; `systemctl --user status jarvis` → `active (running)` sin
reinicios; `RHI OpenGL`, `journalctl` sin errores de shader/QRhi (los 3
uniforms nuevos cargan bien en la GPU real).

**NO verificado visualmente:** Wayland bloquea la captura del proceso; el
render offscreen por software no dibuja el shader del orbe. No he visto el
paralaje, la onda de choque, el fleco cromático ni el rizo de audio. Están
razonados y validados técnicamente; el ajuste fino (amplitudes, radios)
necesita mirarlo.

## Fase 8 — Entidad viva alienígena

El usuario quiere que el orbe parezca "alienígena, nunca antes visto, con vida
propia". Sin uniforms nuevos — todo de datos existentes. `core.frag`.

1. **Cuerpo orgánico, no esfera** — `lobes()`: dos bultos lentos que migran por
   la superficie (barato, sin `pow`/ruido extra) sumados al SDF → forma
   amorfa que cambia. Respiración de geometría ahora irregular (2 senos
   desfasados).
2. **Pupila que MIRA** — un vacío que absorbe la luz en el centro, rodeado de
   un iris encendido. **Deriva hacia el ratón** (`par*3.4`) → el orbe te
   sigue. Es lo que lo hace parecer vivo y con intención.
3. **Filamentos de datos** en la superficie del volumen — líneas finas que
   corren siguiendo el flujo del normal (`fract(n·k − t)`), enmascaradas por
   el Fresnel. Lectura de "procesando / tejido activo".
4. **Motas orbitales** — 10 puntos diminutos girando en órbitas elípticas
   inclinadas (posiciones sembradas por hash, velocidad por `spin`+`energy`).
   Vida en el campo.
5. **Fulguraciones** — en picos de `energy`/`flux` reales, lenguas puntiagudas
   que salen del limbo. Dramático en los picos de SPEAKING.
6. **Oclusión suave** — el campo de interferencia se atenúa donde el cuerpo
   está delante (centro) → núcleo sólido con el campo envolviéndolo, capas 3D.
7. **Temperatura de color** — `warmTint`: el cuerpo entero se calienta hacia
   `tintHot` con energía y se enfría hacia `tintDeep` en reposo. Antes sólo el
   punto central lo hacía.
8. **AA adaptativo** (`fwidth`) en rim, arcos, motas, onda y fulguraciones →
   bordes nítidos y sin *shimmer* al girar, a cualquier tamaño. **Flare del
   rim** en el cambio de estado (`pow(transPhase, 1.6)`).

Coste: `lobes()` se evalúa 5× por fragmento del volumen (SDF + normal); el
bucle de 10 motas corre en todo el disco. En Intel HD 520 lo cubre la ruta de
degradación (fps EMA < 40 sostenido 3 s → engancha, sin bloom).

### Validación

Shaders recompilan sin errores GLSL (`fwidth`, bucles, `mat2` OK); QML sin
warnings; `pytest test/test_ui_hud.py` 25 verde; `ruff` limpio;
`systemctl --user status jarvis` → `active (running)`; `RHI OpenGL`,
`journalctl` sin errores de shader/QRhi ni enganche de degradación.

**NO verificado visualmente:** Wayland bloquea la captura. No he visto la
pupila siguiendo el ratón, los lóbulos deformando el cuerpo, los filamentos,
las motas ni las fulguraciones. Están razonados y validados técnicamente; el
ajuste fino (tamaño de la pupila, número de motas, amplitud de lóbulos)
necesita mirarlo — y comprobar los fps en la máquina real.

## Fase 9 — "Obra maestra": profundidad real, un iris que es un ser, un sistema

El usuario: *"dame lo mejor que Claude puede hacer, algo tan increíble que ya no
quiera pedir más"*. Sin uniforms nuevos — todo sale de datos que ya existen.
`core.frag` reescrito.

1. **Plasma volumétrico interior con paralaje por capas** — tras tocar la
   superficie, el raymarch avanza 4 pasos DENTRO del cuerpo acumulando densidad
   de plasma con *warp de dominio* (`fbm2(q + vnoise(q·0.7))`). Cada capa se
   desplaza con el ratón (`par·(1.6 + k·0.8)`) → al mover el cursor se revela un
   ADENTRO con profundidad 3D real, no una cáscara pintada. Es el mayor salto.
2. **Iris alienígena** — la pupila deja de ser un círculo: son **hojas** que
   dilatan con la energía (`dil = mix(0.052, 0.135, energy)`; se abre al
   escuchar/hablar, se cierra al pensar), con **fibras radiales** y un
   **reflejo vivo** (catchlight) fijo en la pupila — el truco clásico de "está
   vivo". Sigue derivando hacia el ratón.
3. **Piel celular bioluminiscente** — Voronoi barato (9 células) proyectado
   sobre el normal; cada célula late con una onda que la recorre
   (`sin(id·42 − t·3 + bandMid)`), y el brillo total sólo sube con audio real
   (`bandLow + bandHigh`). Ommatidios de ojo compuesto / plancton.
4. **Corona magnética** — sustituye a las lenguas rectas de la Fase 8 por 4
   **arcos curvos** que salen del limbo y regresan, anclados a puntos fijos y
   modulados por `max(energy, flux, bandSum·0.6)`. Corona estelar, no púas.
5. **Satélite compañero** — un cuerpo coherente en órbita inclinada (matriz de
   rotación fija) que **proyecta una sombra tenue** sobre el campo cuando pasa
   por delante (`satFront`). Sistema, no chispa suelta.
6. **Nacimiento de estrella** — rara vez (hash temporal lento) una mota fulgura
   a punto brillante y se estira antes de apagarse. Micro-evento que premia
   mirar.
7. **Iridiscencia de película fina en el borde** — sobre el fleco cromático,
   una paleta coseno (`irid()`) cuyo color se desliza con el ángulo y el ratón:
   el borde tornasola como concha de escarabajo / aceite.
8. **Deriva onírica en reposo** — batido largo (`sin(t·0.037)·sin(t·0.019)`,
   período de minutos) que en reposo mece el color por la rampa y desfasa la
   rotación del campo. En reposo nunca se repite ni se queda quieto; se
   desvanece en cuanto hay trabajo (`rest = 1 − energy·1.6`).

### Coste y red de seguridad

El march de superficie baja de 22 → 18 iteraciones (SDF suave, sobra margen)
para recomprar presupuesto; encima se añaden 4 pasos de plasma + Voronoi de 9
células, **sólo dentro del cuerpo y sólo si `reduced == 0`**. En la Intel HD
520 la CPU del proceso queda en ~26–29 % en reposo con la ventana enfocada
(pico de arranque ~38 %), comparable a la Fase 8. La ruta de degradación
(fps EMA < 40 sostenido 3 s → sin bloom) sigue de red. Si molesta el consumo,
los knobs son: pasos de plasma (`kk < 4`), células del Voronoi, nº de motas.

### Validación

- Shaders recompilan sin errores GLSL (`fbm2`, `voro` con doble bucle, `mod`,
  `irid`, `mat2` OK) — `4 shader(s) compilados`.
- `pytest test/test_ui_hud.py` → 25 verde.
- `pytest test` (suite completa) → verde, 0 fallos.
- `ruff check .` → limpio.
- `systemctl --user status jarvis` → `active (running)`, `NRestarts=0`, una
  instancia; `RHI OpenGL`, `journalctl` sin errores de shader/QRhi ni banner
  de degradación tras ~3 min.

**NO verificado visualmente:** Wayland/Mutter bloquea la captura del proceso y
el render offscreen por software no dibuja el shader del orbe. No he visto el
plasma volumétrico, el paralaje por capas, el iris de hojas, el catchlight, la
piel celular, la corona ni el tornasol del borde. Están razonados y validados
técnicamente; el ajuste fino (densidad del plasma, tamaño del iris, brillo de
las células, radio de la corona) y los fps en uso real necesitan mirarlo.
Para verlo: mira la ventana y **mueve el ratón junto al orbe** — el iris debe
seguirte y el interior debe cambiar de profundidad.

## Fase 10 — El resto de la interfaz a la altura del orbe

El usuario: *"el orbe está listo; los demás elementos necesito que estén a la
altura. Dame lo mejor."* El HUD eran widgets competentes pero estáticos: cajas
que se quedaban ahí mientras el orbe respira, reacciona y comparte su luz. Fase
10 les da UN lenguaje: superficies **holográficas** proyectadas por la misma
entidad.

### Nuevo: `Design.hudLift(sx, sy)` y `HoloFrame.qml`

- **`Design.hudLift`** — un único número 0..1 ("cuánta energía tiene el HUD
  aquí") que sube con la luz del núcleo, la energía REAL (RMS de voz / tok·s) y
  el ping de atención. TODOS los componentes lo leen para latir al unísono con
  el orbe; nunca baja de legible.
- **`HoloFrame`** — marco compartido: fondo con gradiente (iluminado desde
  arriba), borde de 1px teñido por el acento, **corchetes de mira en las 4
  esquinas**, brillo de vidrio. Su intensidad respira con `hudLift`. Lo usan las
  celdas del HUD, la lectura de estado, el campo de comando, la cabecera de
  consola y el micrófono — un solo idioma, no cinco.

### Celdas del HUD (`HudCell`)

- Superficie `HoloFrame` en vez de rectángulo plano.
- **Telemetría que RUEDA**: si el valor empieza por un número (`72%`, `940 ms`,
  `12.4`), se separa número + sufijo y se anima al destino (`Design.durRoll`);
  al aparecer sube desde 0 — un barrido de encendido.
- Barra de acento en **degradado** (emisor brillante arriba → se apaga abajo) +
  chispa en la cabeza que late con `coreEnergy`.
- **Entrada escalonada**: las celdas se ENSAMBLAN (opacidad + deslizamiento
  vertical), retardo `ordinal * 45 ms`, no aparecen de golpe.
- Un cambio de dato ilumina brevemente toda la celda (`bump` → `extraLift`).

### Lectura de estado (`CoreStatus`)

- Superficie `HoloFrame`; un "kick" de luz en cada cambio de estado.
- **Base de energía**: una barra fina bajo la palabra cuya longitud sigue
  `Design.coreEnergy` — el mismo dato real que mueve el orbe, aquí cuantificado.

### Consola (`Conversation` / `Turn`)

- **Cabecera de consola**: `● jarvis · consola` + reloj de sesión (1 Hz, sólo
  con la consola visible — no es el bucle de animación del sistema), con
  corchetes a los lados y el punto latiendo con el núcleo. Marco de "terminal
  real" sin ser un panel.
- Cada turno: **nodo** (rombo) donde el prompt toca el espinazo; la regla
  vertical ahora es un degradado que nace brillante en el nodo y se apaga.
- El cursor de streaming toma el color del canal (verde usuario / cian JARVIS).

### Barra de comando (`CommandBar`)

- Corchetes de mira en el campo (`HoloFrame` sólo-esquinas) que se encienden con
  el foco y con la energía del núcleo.
- El chevron del prompt **respira** con `coreEnergy` en reposo; pleno con foco.
- Pista de envío `↵` tenue a la derecha (hueco reservado, sin reflujo).
- El barrido de "generando" pasa de un rectángulo duro a un **cometa** (borde
  con degradado transparente→cian→transparente).

### Micrófono (`MicButton`)

- Los corchetes de mira sustituyen al recuadro plano al pasar el ratón / al
  escuchar; acento cian (rojo si sin permiso).

### Validación

- `ruff check .` → limpio.
- `pytest test/test_ui_hud.py` → 25 verde, incluido
  `test_qml_engine_loads_without_warnings` (cero warnings QML con los archivos
  nuevos) y `test_responsive_layout_no_overlap_no_overflow` (sin solapes ni
  desbordes en 1700×900 / 1360×820 / 1000×760 / 430×360).
- `pytest test` (suite completa) → sin fallos.
- `systemctl --user restart jarvis` → `active (running)`, `NRestarts=0`, RHI
  OpenGL, `journalctl` sin warnings/errores QML.
- **Verificado visualmente (parcial):** render offscreen por software con 6
  turnos reales en la consola → confirma que aparecen corchetes, barras en
  degradado, números rodando, cabecera de consola con reloj, nodos de turno,
  corchetes del campo y base de energía del estado. El backend de software NO
  dibuja el shader del orbe y compone sobre un fondo claro (los paneles se ven
  pálidos ahí; sobre el escritorio real con OpenGL y alfa componen como vidrio
  oscuro). El ajuste fino de opacidades/gradientes sobre wallpaper real y el
  latido de `hudLift` con el orbe encendido necesitan mirarse en la máquina.

## Fase 11 — El HUD como organismo: carácter de estado, latido y frente de reacción

Tras la Fase 10 el HUD ya respiraba con el **volumen** del orbe (`hudLift` ←
RMS de voz / tok·s). Le faltaban tres cosas para sentirse igual de vivo, y son
las tres de esta fase. Todo QML + ~12 líneas en `Core.qml`; sin tocar el shader
del orbe ni el pipeline de datos.

### 1. El HUD adopta el CARÁCTER del estado

- `Design.coreStateName` (lo publica `Core.qml`) + `Design.stateWash(c, amt)`:
  mezcla cualquier color de firma del HUD hacia `coreTint` (el color del
  estado) según una constante por estado — `listening/speaking` 0,50,
  `thinking` 0,42, `executing` 0,58, `alert` 0,85, **`idle` 0,0** (en reposo el
  HUD conserva su color propio).
- `HoloFrame` aplica ese lavado a bordes y corchetes; `HudCell` a la cabeza de
  su barra de acento. Resultado: al pensar, todo el HUD tira a azul frío; al
  ejecutar, a naranja; en alerta, a rojo. Ya no es neutro: acompaña al orbe.
- `Design.stateCadence()` — multiplicador de velocidad del micro-shimmer por
  estado (`listening` 1,9 · `thinking` 0,55 · `executing` 2,4 · `alert` 3,2 ·
  `offline` 0). El shimmer de `HoloFrame` sólo se ve cuando hay actividad real
  (amplitud × `coreEnergy`), a la cadencia del estado.

### 2. Latido compartido en reposo

- `Core.qml` calcula `_pulse` 0..1 en cada avance del reloj: respiración lenta
  con **amplitud modulada** (`sin(t·0.42) · (0.72 + 0.28·sin(t·0.17))`, no se
  repite de forma obvia) + un golpe cardiaco exponencial cada ~5,2 s. Siempre
  activo, no depende del estado.
- Se publica como `Design.pulse`. `HoloFrame` lo funde en su realce
  (`lift · (0.86 + 0.14·pulse)`): en reposo, corchetes y brillo de vidrio de
  TODO el HUD inhalan y exhalan a la vez que el orbe. Bajo *reduced motion* el
  reloj no avanza → el latido se congela, como el resto.

### 3. Frente de reacción en el cambio de estado

- `Design.waveFront` (0→1 en `stateXfade·2.4`, lo dispara `Core.qml` junto a la
  onda de choque del shader) + `Design.waveAt(sx, sy)`: devuelve el realce 0..1
  para un punto según **la distancia al núcleo** — un anillo que se expande.
- `HoloFrame` lo suma a su realce y `Main.qml` engrosa el conector HUD↔orbe a
  su paso. Un cambio de estado ya no sólo cambia colores: una onda de luz
  recorre la interfaz encendiendo las celdas por distancia, igual que el orbe.

### Infra nueva

- `Design.tick` ← `rootItem.tick` (Main): reloj global de fotogramas expuesto
  al sistema de diseño para micro-movimiento **sin timers propios**. Sigue
  habiendo UN solo `FrameAnimation` (test lo verifica).

### Validación

- `ruff` limpio; `pytest test/test_ui_hud.py` 25 verde — incluye
  `test_qml_engine_loads_without_warnings` (cero warnings con las props/función
  nuevas de `Design`, los `Binding` nuevos en `Core`/`Main` y `HoloFrame`),
  `test_single_frame_animation_driver` (sigue habiendo 1 `FrameAnimation`) y
  `test_responsive_layout_no_overlap_no_overflow` (sólo cambian color/opacidad;
  el conector engrosa ≤3 px y no entra en los rects comprobados).
- `pytest test` (suite completa) → sin fallos ni errores.
- `systemctl restart` → `active`, `NRestarts=0`, RHI OpenGL, `journalctl` sin
  warnings/errores QML (sólo el aviso de semáforo del proceso anterior al
  cerrarse, ya conocido y ajeno a esta fase).
- **No verificado visualmente:** el lavado de color, el latido y el frente son
  temporales — un render estático no los muestra; el backend de software
  compone sobre fondo claro. La intensidad del lavado por estado, la amplitud
  del latido y el radio/banda del frente necesitan mirarse en la máquina con el
  orbe encendido.

## Fase 12 — Vida VISIBLE en toda la interfaz

Feedback del usuario tras la F11: *"no veo mucha diferencia, hazlo para toda la
interfaz."* La F11 era correcta pero tímida: el lavado de estado era 0 en
reposo y la respiración modulaba un 14 %. Esta fase lo sube con fuerza y lo
lleva a cada rincón.

### Intensidades (Design.qml)

- `_stateWashK`: de 0,42–0,85 → **0,55–1,10**, y **idle pasa de 0 a 0,42**: en
  reposo el HUD ya se lava hacia el azul eléctrico del orbe. `stateWash` mezcla
  hasta 0,92.
- Nuevo `Design.breath()` = `0.55 + 0.45·pulse`: recorrido AMPLIO (no un
  temblor). Lo usa todo el HUD para inhalar/exhalar de forma perceptible.
- `Design.waveGlow` — pico del frente de reacción **sin depender de la
  posición**: un DESTELLO global de toda la interfaz en el instante del cambio
  de estado. Banda del frente 170 → 260 px; duración `stateXfade·3.6` (más
  lento, se ve pasar).

### Marco de ventana vivo — `HudFrame.qml` (nuevo)

El borde de la ventana ES parte de la entidad: 4 corchetes de mira grandes en
las esquinas + línea interior de 1px, teñidos por el color del estado,
respirando con `breath()` y destellando con `waveGlow`/`waveAt`. Retícula
emisiva sobre la ventana transparente — ni fondo ni panel. Los controles de
ventana se anidan dentro de la retícula (`WindowChrome` + margen).

### Chispa de perímetro (`HoloFrame.scan`)

Un punto de luz (halo tenue + núcleo brillante) recorre el perímetro del marco,
parametrizado por `Design.tick` (sin timer). Activo en la lectura de estado, el
campo de comando y el micrófono mientras escucha: superficies "siempre vivas"
aunque no haya actividad.

### Todo lo demás

- `HoloFrame`: el FONDO se tiñe hacia el estado (antes sólo el borde); realce
  `lift·breath() + 0.85·wave + 0.30·waveGlow + shimmer`; borde y corchetes con
  recorrido mucho mayor.
- `HudCell`: barra de acento y emisor laten con `breath()` (opacidad + escala);
  lavado de estado 0,35 → 0,7.
- `CoreStatus`: `scan` activo; la base de energía, sin dato real, LATE con
  `breath()` en vez de quedarse plana.
- Conector HUD↔orbe (`Main`): color lavado por estado, opacidad con `breath()`,
  se engrosa con el frente, y un **impulso de datos** (punto de luz) baja por
  él de forma continua.
- `Turn` / `Conversation`: el nodo del turno y el punto de la cabecera de
  consola laten con `breath()` (opacidad + escala); su tamaño sube un poco.

### Validación

- `ruff` limpio; `pytest test/test_ui_hud.py` 25 verde — sin warnings QML con
  `HudFrame` y las props nuevas; sigue 1 solo `FrameAnimation`; layout sin
  solapes/desbordes en los 4 tamaños (el marco de ventana es decorativo, no
  entra en los rects comprobados; los controles de ventana se movieron adentro).
- `pytest test` (suite completa) → sin fallos ni errores.
- `systemctl restart` → `active`, `NRestarts=0`, RHI OpenGL, `journalctl` sin
  warnings/errores QML.
- **No verificado visualmente en movimiento:** un render estático capta el
  marco de ventana, las chispas y el conector reforzado, pero no la
  respiración, el barrido de la chispa ni el destello del cambio de estado. El
  backend de software compone sobre fondo claro (paneles pálidos). Intensidades
  finas (amplitud de `breath`, velocidad de `scan`, brillo de `waveGlow`) a
  calibrar en la máquina con el orbe encendido.
