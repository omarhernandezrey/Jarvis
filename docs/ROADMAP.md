# ROADMAP — JARVIS CONTROL COMPLETO DE LINUX

> Objetivo: que JARVIS controle esta máquina Linux de forma **completa, fiable y
> rápida**, dentro de los recursos reales (Intel HD 520, CPU 2015, 2 núcleos /
> 4 hilos, RAM limitada, un modelo cargado a la vez, todo local).
>
> Este documento es plan, no código. Se apoya en `docs/INFORME_ARQUITECTURA.md`.

---

## 1. ESTADO REAL (sin optimismo)

### 1.1 Funciona de punta a punta
Marcado ✅ solo si se ejercitó en sesión real o tiene commit con evidencia e2e
en `PLAN_MAESTRO.md` (fases A–D).

- **Cascada completa** (normalización → fast_response → parser → agente → chat).
  Verificado: `Jarvis.chat()` sobre "clima en Cali" (1,6 s), "cómo anda la
  máquina" (0,02 s), "va a llover en Cartagena" (1,5 s).
- **Parser determinista** (`intent/parser.py`): abrir/cerrar apps, clima
  natural, "pon `<canción>`" → Spotify, notas, multi-acción, calculadora
  (`%`, raíz, potencias, ecuaciones lineales), ubicaciones (Nominatim),
  volumen/mute (`wpctl`), multimedia (`playerctl`), energía, estado del
  sistema (`psutil`), recordatorios, WhatsApp, archivos (con whitelist).
- **Agente** (`agent/loop.py` + `registry.py`): tool calling nativo de Ollama,
  validación estricta + 1 reintento + rescate de tool calls escritos como
  texto. Modelo `llama3.2:3b`. Batería de routing: **10/12**, ~19,5 s/decisión.
- **Voz**: STT `faster-whisper small int8`, TTS `edge-tts`. Prueba e2e real
  WAV → STT → router (`test/test_voice_e2e.py`, marcada `live`).
- **Seguridad**: blocklist de shell (`safety/permissions.py`), whitelist de 6
  carpetas de usuario con anti path-traversal, redacción de secretos antes de
  logs/modelo, `ActionPlan` → `/confirmar` para DELETE/CRITICAL.
- **`jarvis doctor`**: diagnóstico de entorno (Ollama, modelos + capacidad
  `tools`, red, credenciales, micrófono, navegador).
- **Config**: modelo único `llama3.2:3b` (chat + routing), override por entorno
  `JARVIS_AGENT_MODEL` / `JARVIS_CHAT_MODEL`.

### 1.2 Funciona con límites conocidos
- **Memoria semántica** (`storage/semantic.py`, `bge-m3`): el código existe y
  hay tests unitarios, pero **NO hay prueba e2e** de "recuerda X" → reinicio →
  "¿cuál es X?". No se puede afirmar que funcione de punta a punta.
- **Energía** (`tools/power.py`): apagar/reiniciar hacen `sudo -n shutdown` →
  **requieren una regla sudoers sin contraseña que no está documentada ni
  instalada**. Bloquear y suspender sí funcionan.
- **Gestión de ventanas** (`tools/desktop_actions.py`): minimizar todo / snap /
  Alt-Tab son **solo Windows**. En Wayland responde "no soportado" (honesto).
- **Empleo** (`tools/jobs.py`): scraping de portales, frágil ante cambios de
  su HTML.
- **Calendar** (`tools/gcalendar.py`): solo lee próximos eventos, no crea.
- **Portapapeles** (`tools/reader.py`): solo lee, no escribe.

### 1.3 Escrito pero DESCONECTADO (código muerto)
Nadie lo importa en el flujo:
- `jarvis_local/vision/` — `capture_screenshot`, `describe_screen` (OCR
  `pytesseract`), `vision_available`. 52 líneas.
- `jarvis_local/proactive/` — `ProactiveEngine.get_suggestions()` con reglas por
  hora/día. 63 líneas.
- `jarvis_local/plugins/` — `__init__.py` (84) + `hello_plugin.py` de ejemplo.
  No hay carga real de plugins.
- `jarvis_local/profiles.py` (57) — perfiles de usuario, sin uso.
- `jarvis_local/performance.py` (71) — utilidades de medición, uso parcial.

### 1.4 No existe
- **VERIFY post-acción** genérico (JARVIS ejecuta y asume éxito).
- **Catálogo único** de herramientas (hay 2: `_READ_TOOLS`/`_WRITE_TOOLS`/
  `_PLAN_TOOLS` en `jarvis.py` + `registry.TOOLS`).
- **Fallback de modelo** cableado (`router_fallback` está en `config.yaml`, no se
  usa).
- **Structured Output** (`format` JSON Schema de Ollama) — solo tool calling.
- **Registro de auditoría** append-only de acciones de escritura/sistema.
- **Métricas agregadas** desde `decisions.jsonl` (accuracy, p95, fallback_rate…).
- Control de: procesos (matar por PID), servicios systemd, red/WiFi (`nmcli`),
  brillo (`brightnessctl`), Bluetooth, portapapeles de escritura, teclado/ratón
  sintéticos (`ydotool`), notificaciones (`notify-send`), ventanas en Wayland.

---

## 2. PRESUPUESTO DE CÓMPUTO

### 2.1 Coste real medido (i5-6200U, `llama3.2:3b`, Ollama caliente)

| Operación | Coste |
|---|---|
| `fast_response` | < 1 ms |
| `parser` (enrutado puro) | ~0,2 ms |
| `parser` → herramienta con red (clima) | ~1,6 s (la red, no el parser) |
| recall de memoria semántica (1 `embed` con `bge-m3`) | ~0,3–1 s |
| **1 llamada de tool calling** (`chat_with_tools`, agente) | **19–70 s**, media ~20 s |
| generación de chat, primer token (caliente) | ~1,5 s |
| generación de chat, primer token (frío / modelo evacuado) | ~50–60 s |
| recarga de modelo tras evicción | ~10 s (por eso `keep_alive: 30m`) |

### 2.2 Llamadas al LLM por petición

| Tipo de petición | Llamadas al LLM permitidas |
|---|---|
| Resuelta por `fast_response` o `parser` | **0** |
| Conversación pura | **1** generación en streaming |
| Requiere 1 herramienta | **1** decisión de tool calling (+ 0 si cae la caché de decisión) |
| Multi-acción explícita ("A y luego B") | **≤ 1 por cláusula**, `MAX_STEPS_ENCADENADO = 4` → tope 4 |
| Cualquier petición | **NUNCA ≥ 2 llamadas para una sola acción**. Si el bucle pide una 2.ª, es un fallo: `MAX_STEPS = 2`, `MAX_REINTENTOS = 1`. |

### 2.3 Presupuesto de latencia por capa (objetivo)

| Capa | Presupuesto | Realista hoy |
|---|---|---|
| Normalización + `fast_response` | **< 100 ms** | ✅ < 1 ms |
| `parser` (sin red) | **< 200 ms** | ✅ ~0,2 ms |
| `parser` → herramienta local (volumen, sistema, ventanas) | **< 300 ms** | ✅ |
| `parser` → herramienta con red (clima, wiki) | **< 3 s** | ✅ ~1,6 s |
| Chat conversacional, primer token | **≤ 3 s** | ⚠️ ~1,5 s caliente / falla en frío |
| Agente (1 decisión + ejecución de herramienta local) | **≤ 15 s** | 🔴 19–70 s — **fuera de presupuesto** |

El presupuesto de agente ≤ 15 s **no se cumple hoy** y probablemente no se
cumpla nunca en esta CPU. La estrategia no es acelerar el agente: es **no
usarlo** (§2.4).

### 2.4 Reparto de tráfico obligatorio

Para que una sesión típica (≈ 20 peticiones) no esté dominada por esperas:

| Camino | % objetivo del tráfico | Justificación numérica |
|---|---|---|
| `fast_response` + `parser` (0 LLM) | **≥ 85 %** | 17 de 20 peticiones a < 300 ms. |
| Chat conversacional (1 generación, ~1,5–3 s) | **≤ 10 %** | 2 de 20 → ~6 s de modelo en toda la sesión. |
| Agente / tool calling (1 decisión, ~20 s) | **≤ 5 %** | 1 de 20 → ~20 s. Total modelo/sesión ≈ 26 s. |

Contraejemplo: si el agente absorbiera el 30 % del tráfico → 6 peticiones ×
20 s = **120 s de espera pura de modelo por sesión**. Inaceptable.

**Métrica de primera clase:** `% de peticiones resueltas con 0 llamadas al
LLM`. Debe medirse en cada release y no bajar de 85 %.

---

## 3. CAPACIDADES QUE FALTAN — VALOR / COSTE / RIESGO / DEPENDENCIAS

Valor: utilidad real diaria (1 bajo … 5 alto). Coste: sesiones de trabajo
(S ≈ 1, M ≈ 2, L ≈ 3+). Riesgo sistema: probabilidad de romper/colgar la
máquina (1 bajo … 5 crítico).

| Capacidad | Valor | Coste | Riesgo | Dependencias externas | Notas de riesgo |
|---|---|---|---|---|---|
| **Procesos**: listar por consumo, matar por nombre/PID | 5 | S | 2 | `psutil` (ya está) | Matar el proceso equivocado. Mitiga: confirmación + nunca PID 1 / procesos de sesión / kernel threads. |
| **Notificaciones** `notify-send` | 3 | S | 1 | `libnotify` / portal D-Bus (viene con GNOME) | Casi nulo. |
| **systemd --user** status/start/stop | 3 | S | 2 | `systemctl` (está) | Parar un servicio propio necesario. Mitiga: whitelist de units. |
| **Portapapeles escritura** `wl-copy` | 3 | S | 1 | `wl-clipboard` (instalar) | Sobrescribir algo que el usuario tenía copiado. Mitiga: avisar qué se copió. |
| **Brillo** `brightnessctl` | 3 | S | 1 | `brightnessctl` (instalar) o `sysfs` (permisos udev) | Casi nulo. |
| **Red / WiFi** `nmcli` | 5 | M | 3 | `NetworkManager` (está) | Desconectarte de tu red mientras trabajas. Mitiga: confirmación para desconectar/olvidar/cambiar; conectar y listar sin confirmar. |
| **Bluetooth** `bluetoothctl` | 2 | S | 1 | `bluez` | Bajo. |
| **Ventanas Wayland**: listar, enfocar, mover, cerrar | 4 | L | **4** | Extensión propia de GNOME Shell + D-Bus; atado a la versión de GNOME | Una extensión con un bug **cuelga GNOME Shell entero** (y la sesión gráfica). Mitiga: extensión mínima que SOLO expone D-Bus, sin lógica; probar en sesión desechable; comando para desactivarla. |
| **Teclado / ratón sintéticos** `ydotool` | 3 | M | **5** | `ydotool` + `ydotoold` (daemon, permisos `uinput`) | Puede hacer literalmente cualquier cosa. Mitiga: confirmación SIEMPRE, rate-limit, whitelist de secuencias, **interruptor global** para desactivar toda la oleada. |
| **Visión / OCR de pantalla** | 4 | M | 1 | `tesseract-ocr` + `tesseract-ocr-spa` + `pytesseract`; captura ya resuelta (portal) | Solo lectura. Riesgo real: **lentitud** del OCR en esta CPU (medir antes de integrar). |
| **Proactividad** (reglas deterministas) | 2 | S | 1 (si NO toca el LLM) | `upower` (batería), `os.statvfs` (disco) | Ruido/molestia. Prohibido consultar el LLM en segundo plano. |
| **Calendar crear/editar eventos** | 2 | S | 1 | API Google ya integrada | Bajo. |

---

## 4. FASES ORDENADAS POR (VALOR ÷ RIESGO)

Regla transversal antes de tocar nada nuevo: **toda capacidad entra primero por
el parser** (regla determinista → 0 LLM). El agente es el fallback, no la vía
principal. Toda herramienta de escritura declara su VERIFY.

### FASE 0 — Banco de pruebas (red de seguridad) · valor 5 / riesgo 1
- **Qué**: 60 peticiones reales en lenguaje natural sobre la cascada ACTUAL
  (las 4 capas). Para cada una: capa esperada, resultado esperado.
- **Aceptación**: se ejecuta con un comando, reporta tasa de acierto, capa que
  resolvió cada una, y latencia p50/p95. Línea base registrada en el repo.
- **Cómo se prueba**: es la prueba. Se corre entero.
- **Si falla**: cada discrepancia (capa incorrecta, resultado incorrecto) es un
  bug a fichar; no se avanza a FASE 1 con la línea base en rojo salvo que el
  fallo sea preexistente y documentado.

### FASE 1 — Fundación · valor 5 / riesgo 2  (= PROMPT 2)
- **Qué**: catálogo único de herramientas (fuente de verdad de la que se derivan
  parser y esquemas del agente); contrato por herramienta (nombre, schema,
  riesgo lectura/escritura/destructivo/sistema, requiere confirmación, cómo se
  VERIFICA, cómo se revierte); VERIFY post-acción en toda herramienta de
  escritura + 1 reintento con estrategia distinta + reporte honesto si falla;
  registro de auditoría append-only; Structured Output (`format` JSON Schema);
  fallback de modelo cableado.
- **Aceptación medible**:
  1. Dar de alta una herramienta nueva toca **un solo archivo**.
  2. Existe un test que **fuerza el fallo silencioso** de una herramienta de
     escritura y demuestra que ahora se detecta y se reporta.
  3. `logs/auditoria.jsonl` registra qué/cuándo/parámetros/resultado de VERIFY.
- **Cómo se prueba**: tests unitarios del registro y del contrato; test de
  VERIFY con la herramienta mockeada (ok / falla→reintenta / falla→falla);
  e2e real: `abre la calculadora` → VERIFY confirma proceso; `abre una app que
  no existe` → VERIFY falla → mensaje claro.
- **Si falla**: si la migración al catálogo único rompe rutas del parser, se
  revierte la fase entera (rama aislada) y se re-planifica en pasos más
  pequeños (primero el registro, luego el parser, luego el agente).

### FASE 2 — Latencia · valor 5 / riesgo 2  (= PROMPT 3)
- **Qué**: instrumentar y reportar ms por etapa (normalización, fast_response,
  parser, recall, serialización de esquemas, prefill, decodificación,
  generación); medir cobertura del parser sobre tráfico real; mover las 20
  frases más frecuentes que hoy caen al agente; puerta de herramientas
  (clasificador barato < 300 ms decide si hace falta el modelo); caché de
  prefijo (`[system][esquemas][memoria][historial][mensaje]`, nada variable en
  el prefijo); ajustar `num_ctx` a lo ocupado; política explícita de
  `keep_alive`, un modelo residente.
- **Aceptación medible**: petición conversacional ≤ 3 s al primer token;
  petición que resuelve el parser ≤ 200 ms; petición con herramientas ≤ 15 s
  (o, si el hardware no lo permite, documentado con la tabla antes/después y la
  cobertura de parser ≥ 85 %). Segundo mensaje de una sesión con prefill
  medido **menor** que el primero.
- **Cómo se prueba**: `scripts/bench_*` con la tabla de etapas; re-ejecutar el
  banco de FASE 0 y comparar p50/p95; verificar que el tool calling sigue
  activo y no se perdió ninguna herramienta.
- **Si falla**: si el clasificador barato acierta < 90 %, se sustituye por
  reglas + retriever (ya existe) y se documenta que la "puerta" es heurística,
  no un modelo.

### FASE 3 — Visión OCR (solo lectura) · valor 4 / riesgo 1
- **Qué**: conectar `vision/describe_screen` como herramienta read-only. Se
  activa **solo bajo petición explícita**. Una captura + un OCR por petición.
- **Aceptación medible**: "¿qué dice en pantalla?" y "lee el error que tengo
  abierto" funcionan de punta a punta; el OCR tarda **< 4 s** en esta máquina
  (medido). Si tarda más, no se integra y se documenta.
- **Cómo se prueba**: e2e real con una ventana de texto conocida abierta;
  medición del tiempo de OCR.
- **Si falla** (OCR lento): no integrar, borrar `vision/`, documentar la
  decisión y proponer alternativa (p. ej. capturar y adjuntar la imagen sin
  OCR).

### FASE 4 — Oleada A: procesos, systemd, notificaciones, portapapeles ·
valor 4 / riesgo 2
- **Qué**: listar procesos por consumo (READ); matar por nombre/PID
  (DESTRUCTIVO → confirmación, nunca PID de sesión/kernel); `systemctl --user`
  sobre whitelist de units (SISTEMA → confirmación para start/stop);
  `notify-send` (ESCRITURA); `wl-copy` portapapeles de escritura (ESCRITURA).
- **Aceptación medible**: pido cada acción en lenguaje natural → se ejecuta →
  VERIFY confirma (proceso ya no está / notificación enviada / clipboard
  contiene lo pedido) → si falla, JARVIS dice exactamente por qué. Detección de
  disponibilidad en runtime (herramienta del sistema ausente → se dice, no se
  falla en silencio).
- **Cómo se prueba**: e2e real (lanzar un `sleep 300`, pedir matarlo, VERIFY);
  test de "herramienta no instalada" simulando `which` vacío.
- **Si falla**: capacidad concreta que no verifique se marca ⚠️ en el informe y
  se deja detrás de un flag; no se declara la oleada cerrada.

### FASE 5 — Oleada B lite: brillo, red, bluetooth · valor 4 / riesgo 3
- **Qué**: `brightnessctl` (ESCRITURA); `nmcli` listar/conectar (ESCRITURA),
  desconectar/olvidar (DESTRUCTIVO → confirmación); `bluetoothctl`
  emparejar/conectar (ESCRITURA).
- **Aceptación medible**: subo/bajo brillo y VERIFY relee el valor; me conecto a
  una red y VERIFY confirma IP; desconectar exige confirmación y muestra a qué
  red estoy conectado antes.
- **Cómo se prueba**: e2e real con brillo (reversible) y con una red conocida.
- **Si falla**: `nmcli` es el más arriesgado; si la confirmación no es 100 %
  fiable, la capacidad de desconectar/cambiar red se deja fuera y solo se
  permite listar y ver estado.

### FASE 6 — Ventanas en Wayland · valor 4 / riesgo 4
- **Qué**: extensión mínima de GNOME Shell que expone por D-Bus: listar
  ventanas, enfocar, mover, cerrar. La lógica vive en Python; la extensión solo
  traduce D-Bus ↔ API de Shell.
- **Aceptación medible**: "enfoca Firefox", "cierra esta ventana", "lista las
  ventanas abiertas" funcionan; la extensión se puede **desactivar con un
  comando** y JARVIS lo detecta y degrada con mensaje honesto.
- **Cómo se prueba**: en una **sesión gráfica desechable** (usuario de prueba o
  Xephyr/nested), nunca en la sesión principal primero. Test de "extensión
  desactivada → degradación honesta".
- **Si falla** (cuelga Shell): se abandona la extensión, se documenta el límite
  (Wayland no da control de ventanas sin ella) y se deja como está. No se
  insiste.

### FASE 7 — Proactividad (reglas deterministas) · valor 2 / riesgo 1
- **Qué**: `proactive/` con reglas puras sobre eventos reales (batería < 15 %,
  disco < 5 %, recordatorio vencido). **Cero LLM en segundo plano.** El usuario
  activa/desactiva cada regla.
- **Aceptación medible**: consumo en reposo indistinguible de cero (medir con
  `psutil` el proceso durante 10 min sin actividad: < 0,1 % CPU medio, sin
  crecimiento de RAM); las 3 reglas disparan con eventos simulados.
- **Cómo se prueba**: test con eventos inyectados; medición de reposo.
- **Si falla** (consumo no despreciable): no integrar, borrar `proactive/`,
  documentar.

### FASE 8 — Oleada C: teclado / ratón sintéticos · valor 3 / riesgo 5
- **Qué**: `ydotool` para teclear y clicar. **La más peligrosa.**
- **Aceptación medible**: confirmación **siempre**; rate-limit configurable;
  **interruptor global** (`config` + comando) que desactiva toda la oleada;
  whitelist de secuencias permitidas. Sin confirmación aceptada, no se ejecuta
  nada.
- **Cómo se prueba**: e2e real de una secuencia trivial y reversible (escribir
  texto en un editor abierto); test del interruptor global; test de rate-limit.
- **Si falla** o si el modelo de permisos no es sólido al 100 %: **no se
  entrega**. Se documenta como "fuera de alcance por riesgo".

### FASE 9 — Endurecer · valor 5 / riesgo 1  (= PROMPT 6)
- **Qué**: ampliar el banco de FASE 0 a las capacidades nuevas; auditar cada
  ruta de error (JARVIS dice qué/por qué/qué hacer, nunca inventa éxito);
  traza por petición consultable (capas, tiempos, herramientas, VERIFY);
  techos de RAM y de llamadas al LLM por petición, timeouts en toda llamada
  externa; arreglar `test_alarma_suena` inestable inyectándole el reloj.
- **Aceptación medible**: banco ≥ 90 % de acierto; p95 dentro de presupuesto
  por capa; ninguna llamada externa sin timeout; `ruff check .` y suite
  completa en verde.
- **Si falla**: cada fragilidad detectada se ficha; se entrega la evaluación
  honesta ("dónde sigue frágil y qué haría a continuación") aunque no todo esté
  cerrado.

---

## 5. LOS TRES RIESGOS QUE MÁS PROBABLEMENTE HACEN FRACASAR ESTO

1. **La latencia del agente hace inusable cualquier capacidad nueva.**
   Cada acción que caiga al agente cuesta 19–70 s en esta CPU. "Apaga el
   bluetooth" tardando 40 s no se usa. → **Mitigación**: toda capacidad nueva
   entra por el parser (regla determinista, 0 LLM); el agente es solo el
   fallback. La cobertura de parser (% con 0 LLM) es una métrica de release con
   umbral duro (≥ 85 %). Ninguna fase se cierra si su capacidad solo funciona
   vía agente.

2. **Una extensión de GNOME Shell mal hecha cuelga el escritorio entero.**
   Wayland no da control de ventanas sin extensión, y una extensión con un bug
   tumba GNOME Shell y con él toda la sesión gráfica. → **Mitigación**:
   extensión mínima que solo expone D-Bus (cero lógica); primera prueba SIEMPRE
   en sesión desechable (usuario de prueba / Xephyr); comando de un paso para
   desactivarla; si cuelga, se abandona y se documenta el límite (FASE 6 tiene
   "si falla" explícito).

3. **Scope creep: 12 capacidades a medias, ninguna fiable.**
   Sin VERIFY + banco de pruebas + límites de recursos, se acumulan features
   que fallan en silencio y erosionan la confianza hasta que dejas de usar
   JARVIS. → **Mitigación**: FASE 0 (banco) y FASE 1 (fundación) son
   **bloqueantes**; nada nuevo sin su contrato + VERIFY + test que fuerce el
   fallo; **una oleada por sesión**, cerrada de verdad (ejercitada, no "los
   tests pasan") antes de la siguiente.

*Riesgo secundario — RAM*: `llama3.2:3b` residente (~2,5 GB) + HUD Qt + navegador
+ apps que JARVIS abre puede provocar swapping en esta máquina. Mitigación: un
solo modelo, `keep_alive` explícito, medir el pico real en FASE 9, opción de HUD
sin shader pesado.

---

## 6. LO QUE NO SE VA A HACER (y por qué)

- **Nada de LLM en segundo plano / proactividad con modelo.** En 2 núcleos es
  inaceptable: bloquearía la máquina. La proactividad son reglas o no es.
- **Nada de modelos ≥ 8B, ni un segundo modelo residente, ni inferencia en la
  nube.** El presupuesto de RAM y el requisito "todo local" lo prohíben.
- **Nada de `sudo` implícito ni elevación automática.** Si una acción necesita
  root (apagar, algunos servicios), se documenta la regla `sudoers` concreta y
  la instala el usuario. JARVIS no elude permisos.
- **Nada de automatización de GUI "genérica"** ("haz clic donde haga falta")
  hasta que visión + `ydotool` + modelo de permisos estén sólidos; y aun así,
  detrás del interruptor global.
- **Nada de instalar/desinstalar paquetes** (`apt`/`flatpak`) de forma
  autónoma en este roadmap. Riesgo alto, valor puntual; se puede hacer a mano.
- **No se reescribe el HUD ni la voz.** Funcionan y no son el cuello de
  botella. Tocarlos es riesgo sin retorno.
- **No se relaja la capa de seguridad para "simplificar".** Se endurece: toda
  herramienta nueva declara su `RiskLevel`; DELETE/SISTEMA siempre confirman.
- **No se persigue "< 15 s en el agente" a base de optimizar el modelo.** Es un
  límite físico de la CPU. La respuesta es no usar el agente, no acelerarlo.
- **No se borran tests ni funcionalidad** para pasar a verde.

---

## RECOMENDACIÓN — POR DÓNDE EMPEZAR

Empezar por **FASE 0 (banco de 60 peticiones) seguida de FASE 1 (fundación:
catálogo único + contrato + VERIFY + auditoría)**. Razón: (1) sin el banco,
cualquier cambio posterior es a ciegas y no hay forma de saber si algo se rompió;
(2) sin catálogo único, cada una de las 12 capacidades nuevas se paga dos veces y
los dos catálogos divergen; (3) sin VERIFY, "control de la máquina" es en
realidad "creer que controlas la máquina" —JARVIS afirmaría haber apagado el
bluetooth sin comprobarlo; (4) es el trabajo de **menor riesgo** (no añade
superficie de ataque ni depende de herramientas externas) y **mayor palanca**
(desbloquea y hace seguras todas las fases siguientes); (5) al terminar tendrás
una medida objetiva de dónde está JARVIS hoy y una red que te avisa en cada
cambio futuro.
