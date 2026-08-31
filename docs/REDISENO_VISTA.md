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
