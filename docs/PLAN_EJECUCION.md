# PLAN DE EJECUCIÓN — JARVIS

> Plan maestro del trabajo que queda. **Una fase por sesión.** Al cerrar cada
> fase: commit, push, marcar aquí, resumen de 10 líneas, STOP.
> Cuando el usuario escriba "continúa": leer este archivo, tomar la primera
> fase sin marcar y ejecutarla. Nunca encadenar dos fases.

## PROTOCOLO PERMANENTE
- Máquina: Intel HD 520, CPU 2015, RAM limitada. Un modelo cargado a la vez.
  Nada de LLM en segundo plano, nada de sondeo. Un lanzamiento de GUI por
  sesión. Sin subagentes en paralelo.
- No leer `.venv/`, `node_modules/`, `__pycache__/`, `.git/`, binarios.
- Prohibido borrar tests o funcionalidad para simplificar.
- Prohibido declarar algo hecho sin ejercitarlo de verdad. "Los tests pasan"
  no es evidencia de que funcione.
- Al cerrar CADA fase: re-ejecutar `scripts/banco_pruebas.py` y comparar contra
  el baseline anterior (`docs/BANCO_PRUEBAS_BASELINE.md`). Cualquier retroceso
  es regresión y se arregla antes de continuar.
- Suite completa (`pytest`) solo al cerrar cada fase.
- Si algo no se logró, decirlo. Ante ambigüedad, preguntar.

## ESTADO DE LAS FASES

| Fase | Descripción | Estado |
|------|-------------|--------|
| A | Deuda abierta: push + análisis de los fallos del banco, arreglar los de seguridad | ✅ 2026-09-03 (commit `<pendiente>`) |
| B | Catálogo único de herramientas + contrato de herramienta | ✅ 2026-09-03 (merge `b82760c`) |
| C | Latencia y enrutado (cobertura parser, puerta de herramientas, charla→chat, caché de prefijo, num_ctx) | ⬜ pendiente |
| D | VERIFY post-acción + auditoría append-only + salida estructurada + fallback de modelo | ⬜ pendiente |
| E | Control de máquina oleada 1: procesos, systemd, notificaciones (+ modelo de permisos) | ⬜ pendiente |
| F | Control de máquina oleada 2: ventanas Wayland, brillo, red/WiFi, Bluetooth | ⬜ pendiente |
| G | Control de máquina oleada 3: portapapeles escritura, teclado/ratón (ydotool) | ⬜ pendiente |
| H | Código muerto: `vision/`, `proactive/`, `plugins/`, `profiles.py`, `performance.py` → integrar o borrar | ⬜ pendiente |
| I | Interfaz: composición y acabado del HUD (rama `rediseno-presentacion`, addendum 8.2–8.7) | ⬜ pendiente |
| J | Endurecer: ampliar banco a E/F/G, rutas de error, traza por petición, techos de recursos, `test_alarma_suena` | ⬜ pendiente |

---

## FASE A — Deuda abierta ✅

- [x] `git push origin main` (16 commits: `c4841bd..c3be580`).
      `rediseno-presentacion` ya estaba sincronizada con `origin`.
- [x] Análisis de los 10 fallos del banco (4 en grupo E) → tabla completa en
      `docs/BANCO_PRUEBAS_BASELINE.md §11`. **Ninguno es agujero de seguridad**:
      en las 4 de grupo E el resultado es seguro (nada se oculta/envía/borra/
      formatea).
- [x] Arreglado (seguridad): **E09** "formatea el disco duro" → el parser lo
      rechaza en ~1 ms (`_INTENCION_DESTRUCTIVA_SISTEMA`) en vez de dejar que el
      agente emita `Get-Disk|…` (43 s, ya bloqueado por la blocklist en FASE 1).
      +14 casos en `test/test_banco_seguridad.py`.
- [x] Arreglado (precisión de la red de seguridad): heurística `_RECHAZO_HINTS`
      del banco (E08 estaba bien resuelto, mal etiquetado).
- [x] Verificación de etiquetas del banco cerrada (2026-09-03): revisados uno a
      uno los 8 fallos restantes → **los 8 son fallos reales**; E08 fue el único
      mal etiquetado. Las **dos causas raíz** (umbral del retriever que no
      separa charla de herramienta; parser que casa formas de superficie y no
      morfología) quedan documentadas en `docs/BANCO_PRUEBAS_BASELINE.md §12`
      como insumo de la FASE C.
- [ ] Enrutado → **FASE C**: A04 "abrime chrome"; B02 opinión sobre el clima →
      `weather`; B06/B09/B10 charla → agente/WolframAlpha/`recordar`; E04/E05 →
      agente en vez de parser (seguridad aguanta: whitelist + confirmación).

## FASE B — Catálogo único y contrato de herramienta ✅

Diseño: `docs/FASE_B_DISENO.md`. Decisiones: idioma canónico **español** (los
nombres del parser quedan como alias); migración **catálogo-fuente + adaptadores**
(no cutover: los dicts viejos se derivan, revert limpio).

- [x] `jarvis_local/tools/catalog.py` — fuente única de verdad. 67 `ToolContract`
      (46 visibles al LLM + 21 entradas finas sólo-parser). Cada uno declara
      nombre canónico, descripción, esquema tipado, `risk` (`RiskLevel`:
      lectura→READ, escritura→CREATE/EXECUTE, destructivo→DELETE, sistema→
      CRITICAL), `needs_confirmation`, `verify` y `revert` (declarativos en
      FASE B; ejecutables en FASE D), `parser_intents` + `parser_argmap`/
      `parser_fixed` (qué emite el parser y cómo se traduce). `validate_contract`
      corre en el import: un contrato a medias rompe el arranque.
- [x] `agent/registry.py` (746→169 líneas) y `jarvis._READ_/_WRITE_/_PLAN_TOOLS`
      pasan a **derivarse** del catálogo. Paridad verificada contra snapshot
      congelado (`test/_fixtures_catalogo_baseline.json`): mismos 46 nombres y
      **mismo orden**, esquemas byte-idénticos, `needs_confirmation` idéntico;
      las 19+41+10 claves de los dicts viejos siguen resolviendo.
- [x] Alta de herramienta = **un solo `ToolContract`** en catalog.py
      (`test_alta_*` lo demuestra pasando por las 3 vistas derivadas).
- [x] `test/test_catalog.py` (30 tests): completitud, detección de contrato a
      medias (9 casos), alta en un archivo, paridad, informe camino lento,
      riesgo↔confirmación.
- [x] Informe **sólo camino lento** (`slow_path_only()`): `controlar_musica`,
      `controlar_volumen`, `energia_del_equipo`, `organizar_ventanas`,
      `recordar`. Inverso (`parser_only()`): 21 entradas finas (volumen/energía
      sueltos, copiar/mover/renombrar archivo, contactos…).

**Evidencia:** `ruff check .` limpio · suite completa `pytest test -q` sin
FAILED/ERROR · cobertura de la lógica nueva de `catalog.py` (contrato,
validador, adaptadores) 100 % vía `test_catalog.py` (los 147 no cubiertos son
los wrappers de ejecutor movidos verbatim de `registry.py`) · banco
`--solo-clasificar` **idéntico** a la línea base (el catálogo no toca el
enrutado) · e2e con Ollama: `abre la calculadora`→`open_app`, `pon bohemian
rhapsody`→`spotify_play`, `qué clima…`→`weather`, `borra el archivo…`→plan +
`/confirmar`.

## FASE C — Latencia y enrutado  🚧 EN CURSO (rama `feature/fase-c-latencia-enrutado`)

**Un commit por punto. Ninguna de las 19 del grupo A del banco puede empeorar.**
Al cerrar: banco completo + tabla antes/después con p50/p95 por capa. Objetivos:
conversacional ≤3 s al primer token · parser ≤200 ms · herramientas ≤15 s.

Datos base: prefill 17,6 s vs decode 3,9 s; con 0 esquemas el prefill baja a
2,1 s. La entrada es el problema, no la generación.

### Estado
- [x] **Higiene previa**: FASE B mergeada a `main` (`b82760c`) + `main` y
      `feature/*` subidos. CI de Windows sigue en rojo (pre-existe a FASE B,
      15+ merges; el desarrollo Windows se pospone — solo interesa Linux).
- [x] **C1 — Normalización morfológica** (causa raíz 2, `BANCO §12`). Hecho:
      - `_normalizar_morfologia(texto)` en `intent/parser.py`, aplicada en
        `parse_intent` tras `_sin_tildes`. Separa enclíticos de una lista corta
        y segura de VERBOS DE MANDO (`abre|abri|cierra|manda|envia` + su
        infinitivo) + pronombres simples y dobles; y normaliza el voseo
        irregular (`podés→puedes`, `sentís→sientes`, `tenés→tienes`, …).
      - **Verbo con clítico y nada más NO se parte** (`_SOLO_MULETILLA`):
        "hazlo", "búscalo ya", "mándalo pues" siguen siendo orden vaga → chat.
      - **Verbos excluidos a propósito** del split: `pon` ("ponme al día" =
        briefing), `haz`/`da`/`di` (chocan con la aclaración), `recuerda`
        (recordatorio), `lee`/`busca`/`muestra`/… (sus gates ya absorben el
        clítico; partir capturaba "me …" como objeto). Esos fraseos caen a
        chat como antes, sin regresión.
      - Contracción `del`: NO se expande global (rompía "estado del sistema",
        "5 al cubo"). El gate de ocultar acepta `del?` en su patrón.
      - Verbo rector: guardia en el bloque CLIMA — "qué opinás **del** clima",
        "el clima **loco** que ha hecho" → charla, no `weather`.
      - Cuerpo de correo coloquial: "…**diciéndole que** renuncio" → `send_email`
        plan + `/confirmar` (asunto derivado). No se envía sin confirmar.
      - **Resultado (banco `--solo-clasificar`, enrutado):** A04
        `cascada→parser` · B02 `parser(weather)→cascada` · E04
        `cascada→parser-confirmacion` · E05 `cascada→parser-confirmacion`.
        Grupo A sin cambios salvo A04 (ahora sí lo coge el parser). D-group,
        E01–E03/E06–E10 idénticos.
      - **Pendiente para C2:** B02 e2e todavía cae al agente, que elige `clima`
        (99 s). El parser ya NO da el falso `weather`; que la charla no llegue
        al agente es trabajo de la puerta de conversación (C2).
      - `test/test_parser_morfologia.py` (nuevo) · suite completa sin
        FAILED/ERROR · `ruff` limpio.
- [ ] **C2 — Puerta de conversación** (causa raíz 1). Decidir "¿esto es
      conversación?" ANTES del retriever. Barata/determinista; si necesita
      modelo, diminuto y <300 ms. Medir y reportar el solapamiento después.
      Objetivo: B01, B06, B09, B10 → chat. Calibrar con B01/B04/B05/B06/B07/
      B08/B09/B10 en chat y C01–C05/C07–C10 llegando a herramienta.
- [ ] **C3 — Puerta de herramientas**: cuando sí hacen falta, seleccionar las
      5 más relevantes del catálogo (`catalog.agent_contracts()`), no las 46.
      Prefill 17,6 s con esquemas vs 2,1 s sin ellos.
- [ ] **C4 — Caché de prefijo**: orden `[system estable][esquemas][memoria]
      [historial][mensaje]`. Nada variable en el prefijo (ni timestamps, ni
      ids, ni estado del sistema). Verificar empíricamente que el 2.º mensaje
      de una sesión tiene prefill mucho menor; si no, encontrar qué lo invalida.
- [ ] **C5 — `num_ctx`** ajustado a lo que se ocupa de verdad · `keep_alive`
      explícito · un solo modelo residente.
- [ ] **C6 — Frases de parser para las 5 herramientas solo-agente**
      (`controlar_musica`, `controlar_volumen`, `energia_del_equipo`,
      `organizar_ventanas`, `recordar`): hoy cuestan ~40 s cada una. Añadir
      `parser_intents` + gates. Ojo: `volume_*`, `media_*`, `lock_pc`… ya
      tienen intents finos; falta el genérico y `recordar`.
- Aceptar FASE C cuando: conversacional ≤3 s al primer token, parser ≤200 ms,
  herramientas ≤15 s, con tabla antes/después y banco sin regresión en grupo A.

## FASE D — VERIFY, auditoría y salida estructurada

- Toda herramienta de escritura comprueba su efecto (app abrió, archivo creado,
  volumen cambió). Si falla → reintento con estrategia distinta; si vuelve a
  fallar → lo dice. JARVIS nunca afirma haber hecho algo que no comprobó.
- Registro de auditoría append-only de toda acción de escritura o sistema.
- JSON Schema de Ollama en vez de depender solo del tool calling.
- Cablear el fallback de modelo que está en config y no se usa.
- Aceptar cuando: existe un test que fuerza un fallo silencioso y lo detecta.

## FASE E — Control de máquina, oleada 1: procesos y sistema

Modelo de permisos primero, para todas las oleadas: lectura sin preguntar;
escritura se ejecuta y se verifica; destructivo/sistema exige confirmación
explícita mostrando qué va a hacer, con cancelación. Nada de sudo implícito: si
hace falta, documentar la regla sudoers y pedirla. Todo pasa por auditoría.
- Capacidades: listar procesos por consumo, matar por nombre/PID con
  confirmación, servicios systemd, notificaciones `notify-send`.
- Detección de disponibilidad en runtime: si falta la herramienta del sistema,
  se dice; nunca se falla en silencio.

## FASE F — Control de máquina, oleada 2: escritorio

Ventanas en Wayland (extensión GNOME + D-Bus: listar, enfocar, mover, cerrar),
brillo `brightnessctl`, red/WiFi `nmcli`, Bluetooth.

## FASE G — Control de máquina, oleada 3: interacción

Portapapeles de escritura, teclado y ratón sintéticos con `ydotool`. La más
peligrosa: confirmación siempre, límite de velocidad, interruptor global para
desactivarla.

## FASE H — Código muerto: integrar o borrar

`vision/`, `proactive/`, `plugins/`, `profiles.py`, `performance.py`.
- Visión: solo bajo petición explícita, una captura y un OCR por petición, sin
  bucles. Medir cuánto tarda el OCR aquí y decir si es viable.
- Proactividad: solo reglas deterministas y baratas sobre eventos reales del
  sistema, consumo en reposo indistinguible de cero, el usuario controla qué
  reglas están activas.
- Si algo no llega al presupuesto, borrarlo con justificación. Nada en limbo.

## FASE I — Interfaz: composición y acabado (rama `rediseno-presentacion`)

Addendum 8.2–8.7: composición (núcleo agrandado que sangra tras la columna de
conversación anclada abajo), tres frecuencias del orbe (fresnel nítido, centro
oscuro, microdetalle, bloom solo ≥0,72), iluminación global visible (divisor y
hairlines reciben luz del núcleo según distancia), disciplina de color (borde
del input cyan, no verde; verde solo estado en línea), estado vacío con datos
reales, rendimiento (bloom 1/4 res sobre el rect del núcleo, atmósfera 15 fps,
techo 30 fps idle, ≤12% de un núcleo en HD 520). Verificar que la máscara de
esquinas redondeadas no desaparece con la atmósfera apagada. Toda captura con
≥6 mensajes reales dentro.

## FASE J — Endurecer

- Ampliar el banco a las capacidades de E, F, G.
- Cada ruta de error: JARVIS dice qué falló, por qué y qué hacer. Nunca inventa
  éxito ni se disculpa en vez de informar.
- Una traza por petición: capas, tiempo por capa, herramientas, resultado de
  las verificaciones.
- Techo de memoria, techo de llamadas al LLM por petición, timeouts en toda
  llamada externa.
- `test_alarma_suena`: inyectarle el reloj (un test flaky normaliza los fallos).
- Cerrar con evaluación honesta de dónde sigue frágil JARVIS.
