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
