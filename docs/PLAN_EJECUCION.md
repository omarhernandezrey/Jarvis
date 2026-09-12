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
| C | Latencia y enrutado (cobertura parser, puerta de herramientas, charla→chat, caché de prefijo, num_ctx) | ✅ 2026-09-04 (merge `ed26f56`) |
| D | VERIFY post-acción + auditoría append-only + salida estructurada + fallback de modelo | ✅ 2026-09-07 (merge `8dcb8de`) |
| E | Control de máquina oleada 1: procesos, systemd, notificaciones (+ modelo de permisos) | ✅ 2026-09-07 (merge `a3d8afc`) |
| F | Control de máquina oleada 2: ventanas Wayland, brillo, red/WiFi, Bluetooth | ✅ 2026-09-08 — primera mitad merge `ed6da4a`, ventanas Wayland merge `85873e4`. Falta solo F4.3: instalar la extensión en la sesión de `omar` (paso manual, decisión del usuario) |
| G | Interacción: portapapeles de escritura (teclado sintético aplazado con motivo, ratón descartado) | ✅ 2026-09-09 (merge `9270a24`) |
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

## FASE C — Latencia y enrutado  ✅ COMPLETADA

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
- [x] **C2 — Puerta de conversación** (causa raíz 1, `BANCO §12`). Hecho:
      - `_es_conversacion_directa(mensaje)` en `agent/loop.py`, se ejecuta en
        `_run_simple` **antes** de `confidence()`/`select_tools()` (ni
        siquiera se calcula el embedding de confianza del retriever). Es
        regex, **determinista, 0 ms** — se descartó el enfoque por umbral de
        similitud: NO se pudo separar con un solo escalar (ver abajo), y
        también se descartó un clasificador por embeddings (nearest-centroid
        con 18-30 frases ejemplo, probado aparte) porque cada llamada cuesta
        0,46–0,66 s — por encima del presupuesto de 300 ms que pide el plan
        para la opción "modelo".
      - Reconoce la FORMA de la charla dirigida a JARVIS (piropo, pregunta
        sobre sí mismo/sus preferencias, hipotético "si fueras humano", pedir
        una sugerencia u opinión sin tema factual, "cuéntame un dato curioso"
        — sin tocar "cuéntame un chiste", que sigue siendo herramienta), no
        el tema — por eso no colisiona con el grupo C.
      - **Solapamiento medido (confirma la causa raíz, sin cambiar el
        retriever):** `confidence()` de charla sigue en 0,40–0,54 y de
        herramienta legítima en 0,46–0,66 — el solapamiento de 0,46 a 0,54
        **no se tocó ni se necesitaba tocar**: el gate corta ANTES, así que
        para las frases que cubre el solapamiento deja de importar. Para las
        que NO cubre (B04, B07 — declaración personal del usuario, "explícame
        X") el solapamiento sigue intacto y sin resolver: no estaban en el
        objetivo de C2.
      - **Objetivo cumplido:** B01, B06, B09, B10 → conversación directa.
        **Bonus, sin pedirlo:** B02 (opinión sobre el clima, reforzando C1),
        B05 (hipotético), B08 (pedir sugerencia).
      - **Cero falsos positivos**: probado contra las 60 frases del banco —
        el gate sólo dispara en las 7 cuya `capa_esperada` es `chat`
        (`test_cero_falsos_positivos_en_el_banco`).
      - **e2e con Ollama** (las 4 obligatorias): las 4 pasan de `kind=tool`
        (agente eligiendo mal: WolframAlpha fallando en B06/B10, `recordar`
        escribiendo basura en memoria en B09, 37–246 s con resultado
        incorrecto) a `kind=llm` con respuesta conversacional correcta y sin
        efectos secundarios. Latencia observada ahora: 37–48 s — **se evitó
        el sobrecosto del agente/retriever, pero NO se llega al objetivo
        ≤3 s**: eso depende de la velocidad de generación del chat en sí
        (caché de prefijo/`num_ctx`/`keep_alive`), que es C4 y C5, no C2.
        Anotado como pendiente, no como fallo de este punto.
      - `test/test_conversacion_directa.py` (nuevo, 21 tests, incluye mocks
        que prueban que `confidence()`/`select_tools()` NO se llaman) · suite
        completa sin FAILED/ERROR · `ruff` limpio.
- [x] **C3 — Puerta de herramientas**. Hallazgo: el mecanismo **ya existía**
      (`agent/retriever.py`, `TOP_K = 4`, de antes de esta fase) y ya estaba
      enganchado a la ruta real (`run_agent` → `select_tools()` →
      `client.chat_with_tools(messages, tools)` con esos ≤4 esquemas, nunca
      `registry.all_schemas()`). C3 fue **verificarlo contra el catálogo único
      de FASE B y blindarlo**, no reconstruirlo:
      - `TOP_K = 4`, no 5: se deja así — es un número ya calibrado con
        evidencia real en el propio código (`retriever.py`: con 6 seguía
        habiendo ruido en el catálogo ofrecido; con 4, recall suficiente y
        el modelo decide mejor). Lo pedido era "las top-N del catálogo, no
        las 46" — eso ya se cumplía; se prefiere la calibración documentada
        a mover el número sin evidencia nueva. Se puede subir a 5 si se pide
        explícitamente.
      - **Verificado, no dado por hecho:** `catalog.agent_contracts()` (46) ↔
        `retriever._EJEMPLOS` — cobertura exacta 46/46, cero huecos, cero
        huérfanos. El índice del retriever (`_nombres`, tras
        `_construir_indice()`) coincide con el catálogo único, nombre a
        nombre.
      - **Medido de nuevo, con Ollama vivo** (`scripts.banco_pruebas.
        desglose_prefill()`): 8 frases reales, `n_esquemas` 3–4 (nunca 46);
        la única con 0 esquemas (recall roto de C06, ya fichado en `BANCO §4`)
        hace prefill en 2,2 s frente a 10,9–57,1 s con 3–4 esquemas — el
        patrón "menos esquemas = mucho menos prefill" se sostiene. (La media
        absoluta hoy, ~23 s, es más alta que los 17,6 s de la línea base;
        variación de máquina/carga entre sesiones, no una regresión de C3 —
        ninguna herramienta de C3 toca el tamaño del prompt más allá del
        recorte top-K que ya existía.)
      - `test/test_puerta_herramientas.py` (nuevo, 10 tests): cobertura
        catálogo↔ejemplos (sin Ollama), `select_tools()` nunca supera `TOP_K`,
        y — el que de verdad importa — `run_agent` con cliente simulado
        prueba que `chat_with_tools` recibe **≤4 esquemas, nunca los 46**.
      - Suite completa sin FAILED/ERROR · `ruff` limpio.
- [x] **C4 — Caché de prefijo**. Encontrado exactamente lo que se pedía
      encontrar: qué invalidaba el prefijo. Causa raíz en `jarvis.py::chat()`
      (ruta de chat puro, no la del agente): el recuerdo automático
      (`auto_recall.build_context(mensaje)`, que se calcula CON el mensaje de
      ESTE turno y por diseño da algo distinto cada vez) se mezclaba dentro
      de `messages[0]` — el system message, lo PRIMERO del prompt. El
      servidor de Ollama compara el prompt nuevo contra el último que
      procesó, token a token desde el principio: si el primer bloque ya
      difiere, no hay nada que reutilizar — ni el system prompt (que no había
      cambiado), ni el historial (que tampoco).
      - **Arreglo:** `[system estable (prompt + memoria manual, que sólo
        cambia si el usuario hace `/memoria usar`)][historial, que crece solo
        por el final][mensaje de este turno + recuerdo automático de este
        turno]`. El recuerdo automático viaja pegado SOLO al último mensaje
        (la copia que se envía al modelo, nunca la que se persiste en
        `self.history`) — es contenido nuevo de todas formas, no hay caché
        que perder ahí.
      - **"Esquemas"** de la lista `[system][esquemas][memoria][historial]
        [mensaje]` no aplica a esta ruta (el chat puro no manda `tools`); para
        la ruta del agente (`agent/loop.py`), los esquemas son el top-4 de
        C3 y **varían por diseño según la pregunta** — homogeneizarlos
        rompería la calidad de selección que C3 acaba de blindar. La caché
        entre llamadas de la MISMA petición (reintentos) ya funciona sola:
        `tools` es fijo dentro de un `_run_simple`, y los mensajes solo
        crecen por el final.
      - **Verificado, con honestidad:**
        1. Unit (determinista, sin ruido de máquina): `messages[0]` es
           **idéntico** entre dos turnos con recuerdos automáticos
           DISTINTOS (antes cambiaba siempre) — `test_cache_prefijo.py`.
           El recuerdo sigue llegando, solo que pegado al último mensaje.
           La memoria persistida nunca lleva el bloque de recuerdo. La
           memoria manual (`/memoria usar`) se queda en el system, intacta.
        2. e2e con Ollama vivo. **Corrección sobre el reporte anterior**: la
           primera medición (3 turnos) traía un turno 2 anómalo (34,8 s, más
           lento que el turno 1 con menos tokens nuevos) que se archivó como
           "ruido de máquina" sin investigar. Investigado a fondo (ver
           `## 13.` abajo): **no era ruido, era un defecto del propio script
           de medición** — construía un `Jarvis()` real solo para reusar
           `SYSTEM_PROMPT`, y `Jarvis.__init__` dispara en un hilo aparte un
           *warm-up* (`POST /api/generate` vacío) que compitió con las
           llamadas de la prueba por el único slot de `llama-server`
           (`-np 1`), forzando **dos recargas completas del modelo** entre el
           turno 1 y el turno 2 (confirmado en el log de `ollama.service`:
           `"loading model via llama-server"` ×2, más un `POST /api/generate`
           de 58,7 s intercalado). Cada recarga vacía la caché — de ahí el
           `cached n_tokens = 0` del turno 2 pese a ser, en apariencia, la
           continuación de la misma conversación.
           Repetido limpio (sin instanciar `Jarvis()`; solo se importa el
           módulo para leer `SYSTEM_PROMPT`), **6 turnos**, con el HUD
           (`jarvis.service`) parado y el log de Ollama confirmando una única
           carga de modelo en toda la corrida:

           | turno | prompt tok. | nuevos | cache (servidor) | prefill | decode |
           |---|---|---|---|---|---|
           | 1 | 433 | 433 | 0 (frío) | 25,5 s | 20,2 s |
           | 2 | 565 | 132 | 459/565 | 6,9 s | 16,9 s |
           | 3 | 672 | 107 | 653/672 | 1,8 s | 18,3 s |
           | 4 | 791 | 119 | 766/791 | 2,6 s | 14,0 s |
           | 5 | 877 | 86 | 857/877 | 2,2 s | 15,2 s |
           | 6 | 974 | 97 | 948/974 | 3,2 s | 28,8 s |

           `cache (servidor)` es el `cached n_tokens` que el propio
           `llama-server` escribe en su log por cada tarea — no una
           inferencia mía por tiempo, el dato crudo del servidor. Desde el
           turno 2 el prefill se mantiene en 1,8–6,9 s pese a que el prompt
           casi se duplica (433→974 tokens): la caché de Ollama **sí existe,
           sí dispara y se sostiene turno tras turno** cuando nada compite
           por el slot. La lección para futuros scripts de medición queda
           anotada en `BANCO_PRUEBAS_BASELINE.md`: no instanciar `Jarvis()`
           si solo se necesita una constante — arrastra su warm-up en hilo.
      - **Límite reconocido, no escondido:** si el recuerdo automático SÍ
        dispara en un turno, ese turno concreto no se vuelve a mandar tal
        cual (no se persiste con el bloque de recuerdo pegado), así que el
        turno INMEDIATAMENTE siguiente pierde la caché para todo lo posterior
        al system (un solo fallo puntual, no en cascada: desde el turno
        siguiente todo vuelve a alinearse). Resolverlo del todo exigiría
        persistir en el historial exactamente lo que se prefilló cada vez —
        cambio mayor, no se hizo aquí porque no lo pedía el punto y arriesga
        ensuciar el historial con bloques de recuerdo viejos.
      - `test/test_cache_prefijo.py` (nuevo, 6 tests) · suite completa sin
        FAILED/ERROR · `ruff` limpio.
- [x] **C5 — `num_ctx` / `keep_alive` / un solo modelo residente**.
      - **`num_ctx` (chat): 2048→4096, con evidencia, no a ojo.** Medido en
        C4 (`BANCO_PRUEBAS_BASELINE §13`): cada intercambio ronda ~110
        tokens; con `max_history=20` (40 mensajes) una sesión llena se acerca
        a ~2500 tokens de system+historial — por encima de 2048. Al pasar el
        límite, `context-shift` empieza a descartar los turnos más viejos a
        mitad de sesión, **e invalida el prefijo cacheado que C4 acaba de
        arreglar** (el corte de context-shift cambia la base de comparación
        del prefijo). 4096 cubre una sesión de 20 turnos con margen para
        memoria manual + recuerdo automático.
      - **`agent_num_ctx`: se deja en 2048.** Medido en C3: el agente usa
        historial acotado (`history[-6:]`) y 3-4 esquemas del top-K, prompts
        de 800-1100 tokens — le sobra margen dentro de 2048; subirlo no
        arregla nada que esté roto.
      - **`keep_alive` explícito: ya estaba en `chat()`/`chat_with_tools()`
        (histórico); faltaba en `storage/semantic.py::embed()`** — bge-m3
        usaba el default de Ollama (5 min) y se descargaba entre llamadas
        espaciadas del retriever/recuerdo automático, pagando una recarga
        que el resto de rutas ya evitaban. Añadido, mismo valor (`30m`).
      - **Un solo modelo residente**: ya lo estaba — `agent_model == model ==
        llama3.2:3b` desde una decisión anterior (`docs/AUDITORIA_2026-09.md
        §7`). Verificado con un test que lo fija, para que no se rompa sin
        querer si alguien separa los modelos otra vez.
      - **Medido de nuevo tras aplicarlo** (mismo protocolo limpio del §13:
        sin instanciar `Jarvis()`, `jarvis.service` parado, log de Ollama
        confirmando una única carga y `n_ctx_slot = 4096`), 6 turnos:

        | turno | prompt tok. | nuevos | cache (servidor) | prefill |
        |---|---|---|---|---|
        | 1 | 433 | 433 | 0 (frío) | 25,3 s |
        | 2 | 554 | 121 | 534/554 | 1,6 s |
        | 3 | 693 | 139 | 673/693 | 1,8 s |
        | 4 | 838 | 145 | 812/838 | 2,8 s |
        | 5 | 972 | 134 | 952/972 | 2,4 s |
        | 6 | 1107 | 135 | 1081/1107 | 3,5 s |

        Sin regresión frente al `num_ctx=2048` de C4 (1,6–3,5 s vs. 1,8–6,9 s
        — igual o mejor, dentro del ruido esperable) y sin la anomalía del
        turno 2: con la contaminación identificada y evitada, la caché es
        consistente desde el segundo turno en ambas configuraciones.
      - `test/test_config.py` (+4 tests: `num_ctx` cubre la sesión completa
        con la fórmula medida, `agent_num_ctx` cubre el uso medido con
        margen, `keep_alive` seteado, un solo modelo) ·
        `test/test_semantic.py` (+1 test: `embed()` manda `keep_alive`) ·
        suite completa sin FAILED/ERROR · `ruff` limpio · grupo A del banco
        intacto (20/20, sin cambios de enrutado — este punto es config e
        infraestructura, no toca parser ni agente).
- [x] **C6 — Frases de parser para las 5 herramientas solo-agente**. Hallazgo
      inicial: 4 de las 5 (`controlar_volumen`, `controlar_musica`,
      `energia_del_equipo`, `organizar_ventanas`) YA tenían intents FINOS de
      parser cubriendo su capacidad (`volume_up`, `media_play_pause`,
      `lock_pc`, `minimize_all`…) — el hueco real no era de intents
      faltantes, era de FRASEO: el voseo imperativo colombiano no llegaba a
      esos gates. `recordar` sí estaba en cero: sin ningún gate.
      - **Aprovechado C1 tal como se pidió**: los verbos regulares en -ar/-er
        con voseo imperativo (apagá, suspendé, bloqueá, minimizá, maximizá…)
        YA se normalizaban gratis — `_sin_tildes` por sí sola convierte
        "apagá"→"apaga", que es la forma tuteo exacta. Solo hizo falta un
        caso nuevo, -ir con cambio de raíz ("subí"+"me"="subime", igual que
        "abrí"+"me"="abrime" de C1): se añadió "subi"→"sube" al mapa de C1
        (`_RAIZ_BASE`), no una regex nueva por frase.
      - **`recordar`**: nuevo gate `_parse_recordar` (recuerda/recuérdame/
        acuérdate/acordate/no olvides/ten en cuenta/ten cuenta + "que
        &lt;dato&gt;"), corre justo después de `_parse_reminder` en la cascada
        (si hay hora, ya es recordatorio antes de llegar aquí). Contrato del
        catálogo actualizado: `parser_intents=("recordar",)`.
      - **Bug encontrado y arreglado de paso**: "pon pausa" cae en el
        catch-all de Spotify y reproducía una canción llamada "pausa" en vez
        de pausar la música — `pon` está excluido de la lista de C1
        (colisiona con "ponme al día"), así que el hueco no lo tapaba la
        normalización. Se agregó `pon(?:e|le|me)?\s+(?:en\s+)?pausa` al gate
        de pausa, antes de que fase4 vea la frase.
      - **Cuidado #1 (Wayland) — bug real encontrado, no solo verificado**:
        `organizar_ventanas` en Linux SÍ devolvía un mensaje (no fallaba en
        silencio), pero `_execute_tool_write` prioriza `plan.error` sobre
        `plan.result`, así que el usuario veía el crudo `"Error: no soportado
        en Wayland"` en vez de la explicación completa ya escrita
        (`_WAYLAND_UNSUPPORTED`). Arreglado en `desktop_actions._no_soportado`
        (ya no rellena `.error` para esta limitación conocida — no es una
        excepción inesperada que necesite ese diagnóstico crudo).
      - **Cuidado #2 (destructivo) — verificado explícitamente, no solo
        asumido**: test e2e con `subprocess` mockeado que confirma que
        "apagá el equipo"/"reiniciá el equipo" (voseo) siguen invocando
        `shutdown` con la bandera de retraso (`/t`, cuenta regresiva
        cancelable) — nunca un apagado inmediato. La ruta rápida no se salta
        la ventana de confirmación de `tools/power.py`.
      - `test/test_parser_agente_c6.py` (nuevo, 38 tests) · `test/test_
        reminders.py` (+1 caso actualizado) · `test/test_catalog.py`
        (`slow_path_only()` ahora 4, no 5) · suite completa sin FAILED/ERROR ·
        `ruff` limpio · grupo A intacto (20/20) · banco `--solo-clasificar`
        sin cambios en B/C/D/E.
- **FASE C — CIERRE.** Ver evaluación completa (banco íntegro, tabla
  antes/después, objetivos cumplidos/no cumplidos, sin maquillar) en
  `docs/BANCO_PRUEBAS_BASELINE.md §14`.

## FASE D — VERIFY, auditoría y salida estructurada  ✅ COMPLETA 2026-09-07 (rama `feature/fase-d-verify-auditoria`)

**Un commit por punto.** Al cerrar: test que fuerza un fallo silencioso y
demuestra que se detecta · suite completa · `ruff` · banco sin regresión ·
merge a main.

### Estado
- [x] **D0 — CI de Linux como señal real; Windows no bloqueante**.
      - Se añade `test-linux` (Ubuntu, Python 3.11/3.12/3.13): el SO y el
        comando (`QT_QPA_PLATFORM=offscreen pytest test`) del protocolo real
        de `CLAUDE.md`. Antes NO existía job de Linux — solo Windows, en rojo
        desde antes de FASE B sin diagnóstico posible (sin logs del runner,
        sin máquina Windows). `ruff` deja de ser `continue-on-error` ahí: es
        una puerta real (salió limpio en cada commit de FASE B/C).
      - Windows: se conserva con `continue-on-error: true` y el motivo escrito
        en el propio workflow. Ya no bloquea el merge ni el estado.
      - **El job de Linux nuevo TAMBIÉN salía en rojo.** Diagnosticado sin
        acceso a los logs de GitHub: reproducido en local con
        `docker run python:3.11-slim` + las mismas libs del workflow. 40
        fallos, 5 causas raíz, ninguna una regresión de fase — la suite nunca
        se había corrido contra un entorno mínimo (siempre el escritorio del
        dev, con Ollama, `~/Documentos`, reproductor, voces TTS…). "Falla en
        3.11–3.13, pasa en 3.14" era engañoso: 3.14 solo corre en local
        (entorno completo), 3.11–3.13 solo en CI (entorno mínimo). Cero
        correlación con la versión de Python.
        Arreglado:
        · workflow: libs de sistema completas para que PySide6.QtQuick y
          `sounddevice` IMPORTEN (si no, revientan la colección entera, no un
          test); `espeak-ng` (backend de pyttsx3), `playerctl`, `xdg-user-dirs`
          + `xdg-user-dirs-update` (para que `~/Documents` exista — 26 tests de
          archivos escriben ahí).
        · `jarvis._mc_test()`: cortocircuita `is_running()`/`model_exists()`/
          warm-up SOLO durante la construcción, para que el helper "crea
          Jarvis con cliente mockeado" funcione sin Ollama (11 fallos:
          `test_cache_prefijo`, `test_intent`, `test_memory_context`).
        · `test_media::test_media_keys_no_fallan`: acepta un ERROR CONTROLADO
          (sin `playerctl` en CI) — su intención es "no explota", no "tiene
          éxito".
        · `test_apps::test_h2_...`: mockea `get_app_path` (el test asumía VS
          Code instalado en la máquina que corre la suite).
        · `test_reader`: `@skipif` en los 2 tests de portapapeles cuando no
          hay xclip/wl-clipboard + servidor gráfico.
      - **Verificado**: `docker run python:3.11-slim` con el workflow completo →
        `ruff` OK, `pytest test` EXIT 0, 0 FAILED. Suite local (3.14) sigue
        verde.
- [x] **D1 — VERIFY post-acción**: cada herramienta de escritura de los focos
      priorizados comprueba su propio efecto tras ejecutarse. Reintento con
      estrategia distinta si falla; si vuelve a fallar, se informa qué se
      intentó y por qué no se pudo. Cubiertos: volumen, apps, multimedia,
      archivos, y (fallo no perceptible en el momento) recordatorios, notas y
      memoria.
    - [x] **D1·infra + volumen** (`jarvis_local/tools/verify.py`): `VerifyOutcome`
          con tres desenlaces (True hecho / False no-hecho / None no-medible) y
          `finish()` que los pliega igual en todos lados — None se reporta con
          salvedad explícita, nunca como éxito. `set_volume`, `volume_up/down` y
          `volume_mute` leen el estado real tras aplicar; si no cuadra reintentan
          por vía alterna (`pactl` en vez de `wpctl`; handle COM nuevo en Windows)
          y si sigue sin cuadrar → ERROR diciendo qué se intentó.
          Test `test_verify.py`: comando de sistema con returncode 0 pero efecto
          ausente → detectado, reintentado y reportado sin fingir.
    - [x] **D1·apps**: sondeo con tope (`wait_until`, cada 200 ms hasta 3 s), no
          sleep fijo. Foto PREVIA del estado para distinguir "lo abrí yo" de "ya
          estaba". "Proceso existe" ≠ "ventana abrió": proceso vivo pero sin
          poder listar ventanas en Wayland → None con salvedad (FASE F), no True;
          proceso que arranca y muere → False. Caso "ya estaba abierta": se
          verifica el FOCO, no el proceso; sin gestión de ventanas Wayland →
          None. Reintento por vía alterna (`gtk-launch` .desktop vs exec directo).
    - [x] **D1·multimedia**: `media_play_pause/next/previous` — SIN reproductor
          MPRIS activo -> ERROR claro ("no hay nada que pausar"), no el "Hecho,
          senor." incondicional de antes (el caso "pon pausa"). CON reproductor:
          se mide el estado ANTES y se comprueba que el `playerctl status`
          (pausa) o la huella de la pista (siguiente/anterior) cambió de verdad;
          reintento con `--all-players`. Windows: sin estado legible -> None con
          salvedad.
    - [x] **D1·archivos**: `create_file` comprueba existencia + TAMAÑO +
          CONTENIDO byte a byte (un fichero creado y vacío no pasa); reintento
          con escritura cruda + `fsync`. `create_directory`, `copy_file`
          (tamaño == origen), `move_file`/`rename_file` (destino existe Y origen
          ya no) con su reintento por vía alterna.
    - [x] **D1·recordatorios + notas + memoria** (`set_reminder`, `take_note`,
          `recordar`): los únicos cuyo fallo NO se percibe en el momento (un
          volumen que no cambia se oye; una nota que no se guardó se descubre
          días después). Se verifica el EFECTO PERSISTIDO releyendo el
          almacenamiento, no el retorno: `set_reminder` relee `reminders.json`
          (id + texto + hora ±60 s; reintento escritura atómica); `take_note`
          relee el archivo de notas (línea presente; reintento append+fsync);
          `recordar` abre un `MemoryStore` nuevo (dato presente; reintento).
          `_remember` pasa de devolver `str` a devolver `ActionPlan`.
    - **Deuda conocida** — siguen con `verify` DECLARATIVO (texto, no
      ejecutable), a la espera de que una fase posterior las necesite:
      `enviar_whatsapp`, `add_contact`, `organizar_ventanas` / `minimize_all` /
      `snap_window`, `cambiar_ventana`, `energia_del_equipo` / `lock_pc` /
      `shutdown_pc` / `restart_pc` / `suspend_pc` / `cancel_shutdown`,
      `ejecutar_comando`, `ubicar_lugar`, `abrir_sitio_web`, `buscar_en_google`,
      `reproducir_en_spotify` / `reproducir_en_youtube` / `reproducir_musica_local`,
      `navegar_con_selenium` / `cerrar_navegador`, `abrir_oferta_empleo` /
      `mostrar_ofertas_empleo`, `captura_de_pantalla`, `cancelar_recordatorio`,
      `cerrar_aplicacion` / `cerrar_todas_aplicaciones`, `enviar_correo`,
      `ocultar_archivos`, `borrar_archivo`.
- [x] **D2 — Auditoría append-only**.
    - [x] **D2·registro** (`jarvis_local/safety/audit.py`): cada acción de
          escritura/destructiva/sistema (`risk >= CREATE`) queda en
          `logs/audit.jsonl` — herramienta, `ts`, parámetros, el
          `VerifyOutcome` de D1 (`plan.params["verify"]`), `confirmed`
          (true/false/null), status, resultado truncado, `source`
          (parser/agente/confirmacion). Append-only de verdad: `O_APPEND` +
          `fsync` en cada escritura, sin API de update/delete (endurecible con
          `chattr +a`). Rotación por tamaño (`audit_max_bytes` 5 MiB,
          `audit_keep` 10). Redacta secretos (`safety/secrets`) en parámetros
          y resultado ANTES de tocar disco. Enganchada en `_execute_tool_write`
          (parser), `registry.execute` (agente) y `handle_confirm` (CLI). Las
          lecturas NO se auditan.
    - [x] **D2·consulta** (`tools/audit_query.py`): "qué hiciste hoy" / "qué
          cambiaste ayer" desde JARVIS por la RUTA DEL PARSER (`_parse_auditoria`
          → intent `audit_query{dia}`), sin agente. Resumen legible: hora +
          herramienta + params + estado ("hecho y verificado" / "no se pudo
          verificar el efecto" / "la verificación FALLÓ" / "pendiente de
          confirmación" / "error" / "bloqueado") + `[confirmado por usted]`.
          Contrato `consultar_auditoria` con `llm_visible=False` (el LLM no lo ve).
- [x] **D3 — Salida estructurada** (`client.chat_structured` + `loop._decidir_
      estructurado` + flag `agent.structured_output`, apagado): camino JSON
      Schema como alternativa al tool calling nativo. **Medido** con Ollama
      vivo (`jarvis_local/eval/measure_structured.py`, `docs/D3_MEDICION_
      SALIDA_ESTRUCTURADA.md`): con `llama3.2:3b` los rescates ya son 0 con
      tool calling (nada que arreglar), los reintentos no dan señal (varianza
      ±3 >> diferencia −0,5) y la salida estructurada **pierde ~1,5 pts de
      acierto** de 10. **No se activa** — no gana con claridad y la latencia
      no cuenta (D3 la excluye). Código y medidor quedan para repetir con un
      modelo mejor. Hallazgo colateral: `docs/OPERACION_MEMORIA.md`.
- [x] **D4 — Fallback de modelo** (`loop._llamar_modelo`): `ollama.router_
      fallback` estaba sin cablear. Si el router falla técnicamente (no
      responde / no descargado → excepción), reintento único con el modelo de
      fallback; si éste también falla, propaga el error del principal. Log
      `fallback_de_modelo:<modelo>`. **Ejercitado en vivo**: primario
      inexistente → cae a `qwen2.5:3b` y enruta bien; sin fallback → error
      claro ("Tuve un inconveniente…"), sin cuelgue ni éxito fingido.
- [x] **D5 — Ampliar el banco** (`test/test_banco_efecto_fallo.py`, 12 casos;
      `docs/BANCO_PRUEBAS_BASELINE.md §15`): dos clases nuevas.
      **EFECTO** (5): pedir algo y comprobarlo EN LA MÁQUINA por un camino
      independiente del plan — fichero (contenido + tamaño releídos), carpeta,
      volumen al 30 releído (o `verify None` + salvedad sin audio),
      recordatorio en el store con su hora, nota en el archivo.
      **FALLO FORZADO** (7): app inexistente, ruta sin permiso, multimedia sin
      reproductor → error claro que dice qué se intentó, nunca éxito
      inventado (regex lo prohíbe). Incluye el `borrar_archivo` bloqueado ≠
      "Operacion completada" (por agente y por parser) y el `verify None`
      reportado CON salvedad (exigido, no tolerado).

## FASE E — Control de máquina, oleada 1: procesos y sistema  ✅ COMPLETA 2026-09-07 (rama `feature/fase-e-procesos-sistema`)

Modelo de permisos primero, para todas las oleadas: lectura sin preguntar;
escritura se ejecuta y se verifica; destructivo/sistema exige confirmación
explícita mostrando qué va a hacer, con cancelación. Nada de sudo implícito: si
hace falta, documentar la regla sudoers y pedirla. Todo pasa por auditoría.
Si falta la herramienta del sistema, se dice; nunca se falla en silencio (D0).

- [x] **E0 — Presupuesto de memoria (bloqueante)** (`jarvis_local/agent/
      memory_guard.py`): implementa `docs/OPERACION_MEMORIA.md`, sin `psutil`
      (una lectura de `/proc/meminfo`).
      - `ajustado()` = `MemAvailable < 800 MB` → en `loop._run_simple`, tras
        `select_tools()` (última vez que el turno toca bge-m3), se suelta
        bge-m3 de RAM (`/api/embed` con `keep_alive: 0`) antes de la llamada a
        llama. Verificado en vivo: descarga bge-m3 de `/api/ps`.
      - `degradado()` = hay swap en uso **Y** `MemAvailable < 2 GB` (swap
        ocupado con RAM holgada = páginas frías, NO es thrashing — caso real
        observado). `jarvis._try_agent` antepone *"Voy a ir lento, senor: la
        RAM está al límite… en swap…"* a la respuesta, en vez de solo tardar.
      - `estado_del_sistema` gana una línea con MB disponibles, swap y
        veredicto (holgada / ajustada / páginas frías / DEGRADADO).
      - En un SO sin `/proc/meminfo` todo es no-op.
- [x] **E1 — Lista de intocables (guardia DURO)** (`jarvis_local/safety/
      untouchables.py`): `is_untouchable_process(name, pid, cmdline)` y
      `is_untouchable_unit(unit)` devuelven `(True, motivo)` para lo que NO se
      toca nunca — ni a petición explícita. Sin ruta de "forzar": la
      herramienta bloquea, explica POR QUÉ y ofrece la alternativa
      (`alternativa()` por familia). Match tolerante a la truncación de `comm`
      a 15 chars y a la línea de comandos.
      - `[base]` (fijo, del usuario): gnome-shell/mutter, systemd/logind/dbus,
        NetworkManager, sshd, ollama, JARVIS + su árbol (`own_pids()`), PID 1.
      - `[+E1]` (propuesto tras inventariar el sistema): gdm3/Xwayland/
        gnome-session, wpa_supplicant/ModemManager, polkitd, pipewire/
        pipewire-pulse/wireplumber, systemd-journald/udevd/resolved/oomd,
        dbus-broker, llama-server; unidades `user@N.service` y sus equivalentes.
      - `[+E1·b/c]` (criterio ampliado: muerte = estado inconsistente o
        trabajo perdido, no solo pérdida de sesión):
        · contenedores — `docker`/`dockerd`/`containerd` (+ shims),
          `docker.service`/`containerd.service`;
        · gestores de paquetes — `dpkg`/`apt`/`apt-get`/`aptitude`/
          `unattended-upgr`/`packagekitd`/`snapd`, `snapd.service`/
          `packagekit.service`/`unattended-upgrades.service`/`apt-daily*`;
        · discos — `udisksd`, `udisks2.service`;
        · secretos de la sesión — `gnome-keyring-daemon`/`gcr-ssh-agent`/
          `ssh-agent`.
      - **Transacción de paquetes en curso** (`permisos.transaccion_de_
        paquetes_en_curso()`, barato — una pasada de `process_iter`): proteger
        `dpkg` por nombre no basta, lo que importa es la transacción. Mientras
        haya un `dpkg`/`apt`/`unattended-upgrade` corriendo, `matar_proceso`
        (de procesos del sistema), `controlar_servicio` (cualquiera) y
        `energia_del_equipo` (apagar/reiniciar) → BLOQUEADO
        (`bloqueo_por_transaccion`): "espera unos minutos". El kill de un
        proceso propio no-root sigue permitido.
      - **Consulta por parser**: "qué no puedes tocar" / "qué procesos no
        matas" / "lista de intocables" → `listar_intocables`
        (`untouchables.explicar()`), como la consulta de auditoría de D2.
- [x] **E2 — Modelo de permisos** (`jarvis_local/safety/permisos.py`,
      `docs/PERMISOS_SUDO.md`): tres niveles por `RiskLevel` —
      `nivel()` → `auto` (READ) / `verificar` (CREATE·EXECUTE, D1) /
      `confirmar` (DELETE·CRITICAL). `texto_confirmacion(verbo, objetivo,
      detalles)` es el renderizador CANÓNICO (muestra qué y sobre qué,
      `/confirmar`·`/cancelar`) para toda la oleada. **Sin sudo implícito**:
      `bloqueo_por_sudo(capacidad, objetivo, hazlo_tu)` devuelve un ActionPlan
      BLOQUEADO con la regla de sudoers CONCRETA (por unidad, nunca
      `systemctl *`) y la alternativa manual; JARVIS nunca invoca `sudo`.
      `proceso_es_del_usuario(pid)` (matable sin sudo) y `unidad_es_de_sistema
      (scope)` para E3/E4. Todo a la auditoría de D2.
- [x] **E3 — Procesos** (`jarvis_local/tools/processes.py`; parser
      `_parse_procesos`; contratos `listar_procesos`/`matar_proceso`,
      `llm_visible=False` — solo ruta parser, matar es demasiado delicado para
      el 3B).
      - `list_processes(por, top)`: top por CPU (doble sondeo de
        `cpu_percent`) o RAM, con PID y usuario.
      - `plan_kill(objetivo)`: PID o nombre. **E1**: intocable → BLOQUEADO con
        el motivo + `alternativa()`. **PID 1** → BLOQUEADO. **E2**: proceso de
        otro usuario → `bloqueo_por_sudo`. **Varios matches** → BLOQUEADO,
        lista los procesos (marca los protegidos) y pide el PID exacto; JARVIS
        no elige. Uno solo y mío → PLANNED con `texto_confirmacion` (PID,
        usuario, comando).
      - `execute_kill(pid)`: **SIGTERM** + espera (3 s) + VERIFY (`pid_exists`
        / zombie). Si sigue vivo → NO fuerza: arma un plan `forzar_matar_
        proceso` que pide un **segundo** `/confirmar` para SIGKILL. `kill -9`
        nunca es la primera opción.
      - `execute_kill_force(pid)`: **SIGKILL** + espera + VERIFY. Si aún vive →
        ERROR honesto ("ni con SIGKILL… kernel / zombie / root").
      - Re-chequea E1/E2 antes de ejecutar (defensa en profundidad).
      - Sin `psutil` → lo dice; no falla en silencio.
- [x] **E4 — Servicios systemd** (`jarvis_local/tools/services.py`; parser
      `_parse_servicios`; contratos `estado_servicio`/`controlar_servicio`,
      `llm_visible=False`).
      - `service_status(servicio, ambito)`: `systemctl [--user] show` →
        ActiveState/SubState/UnitFileState. Si no es de ese ámbito pero sí del
        otro, lo dice. Sin `systemctl` → error claro.
      - `plan_service(accion, servicio, ambito)`: `iniciar`/`parar`/`reiniciar`.
        **E1**: unidad intocable → BLOQUEADO + `alternativa()`. **E2**: ámbito
        `system` → `bloqueo_por_sudo` con la regla `systemctl … <UNIDAD>`
        sustituida por la unidad exacta (nunca `systemctl *`). No existe →
        lo dice. User + válido → PLANNED con `texto_confirmacion` (unidad,
        acción, estado actual, ámbito).
      - `execute_service(...)`: ejecuta y **RELEE** `systemctl show`; si el
        `ActiveState` no es el esperado (`active` para start/restart,
        `inactive`/`dead`/`failed` para stop) → ERROR, aunque `systemctl`
        haya devuelto 0. Re-chequea E1/E2.
- [x] **E5 — Notificaciones** (`jarvis_local/tools/notify.py`; parser
      `_parse_notificacion`; contrato `enviar_notificacion`): `notify-send`
      (libnotify) con **detección de disponibilidad en runtime** — sin él,
      ERROR claro ("instala `libnotify-bin`"). rc 0 → EXECUTED con salvedad
      (que la notificación se muestre no es comprobable → `verify None`).
      Urgencia baja/normal/alta. Verificado en vivo.
- [x] **Cierre**: banco EFECTO + FALLO FORZADO para lo nuevo — matar un
      `sleep` de prueba y comprobar `pid_exists`; `gnome-shell` bloqueado por
      `plan_kill` y `execute_kill`; servicio de sistema → sudo; `notify-send`
      ausente → error claro (`test_banco_efecto_fallo.py` +5;
      `BANCO_PRUEBAS_BASELINE.md §15.4`). Suite ✅, ruff ✅.

## FASE F — Control de máquina, oleada 2: escritorio

Ventanas en Wayland (extensión GNOME + D-Bus: listar, enfocar, mover, cerrar),
brillo `brightnessctl`, red/WiFi `nmcli`, Bluetooth.

### Primera mitad — brillo, red/WiFi, Bluetooth  ✅ CERRADA 2026-09-07 (merge `ed6da4a`)

F1 verificado en vivo; F2 y F3 NO VERIFICABLES por hardware (sin WiFi, sin
dispositivo BT que persista vinculado) — motivo en la tabla de estado de
verificación en vivo más abajo. Ventanas Wayland (segunda mitad) siguen
pendientes, aparte por su riesgo.

Ventanas Wayland van APARTE por su riesgo (no en esta sesión). Todas: ruta
del parser (`llm_visible=False` si son delicadas), detección de disponibilidad
en runtime con error claro, VERIFY con los tres desenlaces, auditoría D2,
banco EFECTO + FALLO FORZADO al cerrar. Un commit por punto.

> **ESTADO DE VERIFICACIÓN EN VIVO (los tests NO son evidencia de
> funcionamiento — criterio D0).** A fecha de cierre de esta media fase:
>
> | Punto | Lectura en vivo | Escritura en vivo | Motivo |
> |---|---|---|---|
> | **F1 brillo** | ✅ **PROBADO** | ✅ **PROBADO** | Sesión con grupo `video` (2026-09-07). `get_brightness()` → 31%. `set_brightness(60)` → `EXECUTED`, `verify.ok=True` (`método: brightnessctl get`, `detalle: brillo=60%`), relectura = 60%. `set_brightness(25)` → 25%, `verify.ok=True`. `set_brightness(0)` → **recorte a 5%**, `EXECUTED`, `verify.ok=True`, mensaje "no bajo del 5%…", relectura = 5%. `brightness_up`/`down` relativos ±10% OK. Restaurado al valor original. **VERIFY True real, no None.** |
> | F1 brillo — FALLO FORZADO | ✅ probado (sesión anterior) | — | Con el binario real y sin permiso de escritura: `set_brightness(50)` → `ERROR`, `verify.ok=False`, "Intenté: brightnessctl set 50% → Permission denied". No finge éxito. |
> | F2 red/WiFi — lectura | ✅ `net_status`/`wifi_list` responden ("no hay hardware WiFi") | — | — |
> | F2 red/WiFi — escritura | — | ❌ **límite PERMANENTE de hardware — NO VERIFICABLE en esta máquina** | No hay WiFi operativo ni lo habrá: Broadcom BCM43228 en PCI `02:00.0` sin driver (`wl`/`broadcom-sta`), ninguna interfaz `wl*`, `nmcli WIFI-HW: missing`. `connection up/down` y `radio` quedan sin ejercitar. Cubierto solo por tests con `nmcli` simulado. |
> | F3 Bluetooth — lectura | ✅ `bt_status`/`bt_list`, controlador `hci0` activo | — | — |
> | F3 Bluetooth — escritura | — | ❌ **NO VERIFICABLE en vivo con este hardware** | Adaptador presente y funcional, pero `bluetoothctl devices Paired` queda **vacío** tras varios intentos de emparejamiento: ningún dispositivo llega a vincularse (*bonded*) a nivel de BlueZ, y `bt_connect`/`bt_disconnect` operan solo sobre vinculados. Sin un dispositivo BT que persista como emparejado no hay forma de ejercitar el camino de escritura aquí. Cubierto solo por tests con `bluetoothctl` simulado (`test_bluetooth.py`, 15). |
>
> Acciones para cerrar la brecha:
> - **F1:** ✅ nada — verificado en vivo.
> - **F2:** ❌ nada posible — sin hardware WiFi. Límite permanente.
> - **F3:** ❌ nada posible ahora — sin un dispositivo que persista vinculado.
>   Si en el futuro hay uno, ejercitar `bt_connect`/`bt_disconnect` con VERIFY.

- [x] **F1 — Brillo** (`jarvis_local/tools/brightness.py`; parser
      `_parse_brillo`; contratos `controlar_brillo` + `brightness_up`/`down`/
      `set`, `llm_visible=False`).
      - Detección en runtime: sin `brightnessctl` → ERROR ("instala
        `brightnessctl`").
      - **Límite inferior DURO** `MIN_BRILLO_PCT = 5`: nunca por debajo — que
        la pantalla quede a 0 sin poder corregirlo es un fallo del que no se
        sale hablándole a JARVIS. Al recortar, lo dice.
      - VERIFY: se relee `brightnessctl get`; cuadra → True; no cuadra →
        reintento y luego ERROR con "Intenté"; no se puede leer → EXECUTED con
        salvedad.
      - **EJERCITADO EN VIVO Y VERIFICADO (2026-09-07)**, con `brightnessctl`
        instalado y el usuario en el grupo `video`:
        - lectura: `get_brightness()` → 31% real;
        - fijar: `set_brightness(60)` → `EXECUTED`, `verify.ok=True`
          (`brightnessctl get` → `brillo=60%`), relectura = 60%; ídem a 25%;
        - recorte: `set_brightness(0)` → queda en **5%** (`MIN_BRILLO_PCT`),
          `EXECUTED`, `verify.ok=True`, mensaje "no bajo del 5%…";
        - relativos: `brightness_up`/`brightness_down` ±10% OK;
        - valor original restaurado al terminar.
        **VERIFY True real (no None).**
      - FALLO FORZADO (sesión previa, sin permiso de escritura):
        `set_brightness(50)` → `ERROR`, `verify.ok=False`, "Intenté:
        brightnessctl set 50% → Permission denied" — no finge éxito.
      - Deuda menor: cuando falla, el mensaje de `ERROR` repite el stderr 3×
        por el bucle de reintento. Pulir al volver a este módulo.
- [x] **F2 — Red y WiFi** (`jarvis_local/tools/network.py`; parser
      `_parse_red`; contratos `estado_red`/`listar_wifi` (READ),
      `conectar_wifi` (EXECUTE), `wifi_encender`/`wifi_apagar`/`desconectar_red`
      (DELETE, confirmación); `llm_visible=False`).
      - Lectura sin preguntar: `net_status` (interfaces, conexión activa, IP,
        estado WiFi), `wifi_list` (SSID/señal/seguridad). Sin `nmcli` → ERROR.
        Sin hardware WiFi → lo dice.
      - `wifi_connect(red)`: **solo a redes YA GUARDADAS** (`nmcli connection
        up <nombre>`, que usa las credenciales de NetworkManager). Red no
        guardada → BLOQUEADO, lista las que hay. VERIFY: se comprueba que la
        conexión quedó `activated`, no el rc.
      - `wifi_apagar`/`desconectar_red`: **confirmación** (`texto_confirmacion`
        con el aviso de que puede dejar sin conexión). `execute_*` releen el
        estado real (VERIFY).
      - **Contraseñas**: JARVIS nunca maneja una — no hay ninguna en params,
        auditoría ni prompt. Además la **capa 0 ahora redacta `psk` /
        `802-11-wireless-security.psk`** (antes solo `password`): añadido a
        `safety/secrets.py`.
      - **Guardia E1·c**: `wifi_connect`/`wifi_radio`/`disconnect` → BLOQUEADO
        si hay transacción de paquetes en curso.
      - **En vivo:** `net_status`/`wifi_list` OK (responden "no hay hardware
        WiFi"). Escrituras (`connection up/down`, `radio`) **sin verificación
        en vivo**: no hay interfaz WiFi (Broadcom BCM43228 sin driver `wl`,
        límite permanente de esta máquina). El guardia E1·c además bloqueó las
        pruebas por un `unattended-upgrade` real — cubierto por tests con la
        transacción mockeada.
- [x] **F3 — Bluetooth** (`jarvis_local/tools/bluetooth.py`; parser
      `_parse_bluetooth`; contratos `estado_bluetooth`/`listar_bluetooth`
      (READ), `conectar_bluetooth`/`desconectar_bluetooth` (EXECUTE);
      `llm_visible=False`).
      - Lectura sin preguntar: `bt_status` (encendido, nº emparejados/
        conectados), `bt_list` (emparejados, `*` = conectado). Sin
        `bluetoothctl` → ERROR ("instala `bluez`"). Sin controlador → ERROR.
      - `bt_connect`/`bt_disconnect`: **solo dispositivos YA EMPAREJADOS**
        (por nombre o MAC; objetivo vacío = el único). No emparejado →
        BLOQUEADO, lista los que hay. VARIAS coincidencias → BLOQUEADO, pide
        el nombre exacto. VERIFY real: se lee `Connected:` de `bluetoothctl
        info` — yes → True / no → ERROR con "Intenté" / ilegible → EXECUTED
        con salvedad.
      - Desconectar **no** pide confirmación: no deja a JARVIS sin red (a
        diferencia del WiFi en F2).
      - **Emparejar dispositivos nuevos: FUERA.** Pide un PIN/passkey
        interactivo que JARVIS no puede teclear. El parser lo detecta y lo
        explica ("empareja desde Configuración > Bluetooth"); no se finge.
        Encender/apagar el adaptador también queda fuera de F3 y se dice.
      - **En vivo:** `bt_status`/`bt_list` OK (controlador `hci0` /
        `B8:86:87:BE:8D:70` encendido, 0 emparejados). `bt_connect`/
        `bt_disconnect` **NO VERIFICABLES en vivo con este hardware**: tras
        varios intentos, `bluetoothctl devices Paired` queda vacío — ningún
        dispositivo llega a vincularse (*bonded*) a nivel de BlueZ, y esas dos
        herramientas operan solo sobre vinculados. Igual que F2 (WiFi): sin el
        recurso físico no hay camino de escritura que ejercitar. Cubiertos por
        `test_bluetooth.py` (15) con `bluetoothctl` simulado.

### Segunda mitad — ventanas en Wayland  ✅ CÓDIGO CERRADO 2026-09-08 (merge `85873e4`) · falta F4.3 (instalar en la sesión de `omar`, paso manual)

La tarea de más riesgo del plan: una extensión de GNOME corre DENTRO de
`gnome-shell` (el compositor blindado en E1). Un fallo tumba la sesión.
Orden estricto: F4.0 → F4.1 → (OK del usuario) → F4.2.

- [x] **F4.0 — RECUPERACIÓN** (bloqueante). `docs/RECUPERACION_GNOME.md`:
      runbook literal, legible desde el móvil con la pantalla en negro.
      Cubre escenario A (cambio de TTY posible), B (bucle de caída), C (nada
      responde → recovery mode de GRUB). Comandos de rescate verificados en
      vivo (2026-09-07) como `omar` **sin sudo**:
      `dconf write /org/gnome/shell/disable-user-extensions true` y
      `gsettings set` escriben y revierten; `journalctl -b 0 _COMM=gnome-shell`
      se lee sin sudo. Entorno: GNOME Shell 50.1, Wayland, GDM3; sesión en
      tty2, GDM en tty1, tty3–tty6 libres para login (`NAutoVTs=6` por
      defecto → Ctrl+Alt+F3 arranca `getty`).
      **Pendiente de confirmación FÍSICA del usuario:** pulsar Ctrl+Alt+F3 y
      ver el `login:` (paso 0 del doc). Si no aparece, la fase se replantea.
- [x] **F4.1 — INVESTIGACIÓN** (sin código). `docs/F4_INVESTIGACION_VENTANAS.md`.
      Probado en vivo: `org.gnome.Shell.Eval` **desactivado**;
      `org.gnome.Shell.Introspect.GetWindows` → **`AccessDenied`** (allowlist
      fijo); ninguna otra vía D-Bus de ventanas. Xwayland solo ve apps X11
      (hoy: solo WhatsApp) — inútil como capacidad general. No hay portal de
      ventanas. **Conclusión: en Wayland, listar/cerrar ventanas nativas
      requiere código en el compositor.**
      **Recomendación:** partir de **Window Calls / Window Calls Extended**
      (extensión de terceros que ya expone `List`/`Details`/`Activate`/`Close`
      por D-Bus), *vendored* bajo UUID propio `ventanas-jarvis@local` y
      recortada a esos 4 métodos (quitar Move/Resize/Max/Min). Plan B:
      extensión propia mínima (~150 líneas). **Esperando visto bueno del
      usuario para F4.2.**
- [ ] **F4.2 — IMPLEMENTACIÓN** (OK del usuario sobre F4.1 recibido; alcance:
      listar, enfocar, cerrar — mover/organizar FUERA).
  - [x] **Paso 1 — lectura y recorte de la extensión.**
        `docs/F4_2_EXTENSION_LECTURA.md` (análisis) +
        `gnome-extension/ventanas-jarvis@local/` (`extension.js` recortado a
        `List`/`Details`/`Activate`/`Close`, `metadata.json`, `README.md`,
        `LICENSE` GPL-2.0). Origen: Window Calls de ickyicky
        (GPL-2.0-or-later, vendorizado permitido; JARVIS es MIT y habla con
        la extensión solo por D-Bus). Bug del original corregido
        (`_get_window_by_wid` usaba una variable inexistente). 16 métodos
        fuera de alcance **borrados**, no comentados. **No instalado, no
        cableado. Pendiente de revisión del usuario.**
  - [x] **Paso 2 — usuario de pruebas + ejercitar la extensión ahí.**
        `docs/F4_2_PRUEBA_USUARIO_APARTE.md`. Usuario `jarvistest` + `linger`
        + extensión instalada en su home; `gnome-shell --headless
        --virtual-monitor` anidado (mutter 50.1, render por software).
        Ejercitado 2026-09-08: `List` (`[]` → 1 → 2 ventanas), `Details`
        (payload completo), `Activate` (el foco cambia de verdad, `has_focus`
        se mueve), `Close` (la ventana desaparece de `List`, el proceso
        termina), error path `id` inexistente → error D-Bus limpio, **el
        shell NO cae**. Sesión de `omar` intacta (verificado). Comandos
        exactos de montaje/ciclo/limpieza en el doc, repetibles sin depender
        del asistente. Nota de licencia GPL-2.0 llevada también al README raíz.
  - [x] **Paso 3 — cableado.** `jarvis_local/tools/ventanas.py` (habla por
        `gdbus` con la extensión), parser `_parse_ventanas`, contratos
        `listar_ventanas` (READ) / `enfocar_ventana` (EXECUTE+VERIFY) /
        `cerrar_ventana` (DELETE, `/confirmar`) / `integracion_ventanas_on|off`
        — todos `llm_visible=False`. Confirmación de cierre con título +
        `wm_class` + `pid`. Guardia E1 por `wm_class` y por `pid` (nunca
        `gnome-shell` ni la ventana del propio JARVIS), re-comprobado antes de
        ejecutar. Varias coincidencias → se pregunta (como E3). VERIFY:
        `has_focus` releído / ventana ausente de `List()`; si sigue tras
        `Close` → `verify None` + salvedad. Detección en runtime: sin `gdbus`
        o sin la extensión → ERROR con cómo instalarla. Interruptor
        `data/ventanas_integracion.json`. Tests: `test_ventanas.py` (16) +
        banco §F4.2 (6). **Contrato de cable verificado en vivo** contra la
        extensión real en el `gnome-shell --headless` de `jarvistest`.
        `docs/F4_2_PRUEBA_USUARIO_APARTE.md` §"Paso 3".

- [ ] **F4.3 — INSTALAR la extensión en la sesión de trabajo (`omar`).**
      **Pendiente y explícito.** El código está mergeado pero las
      herramientas de ventanas devuelven ERROR ("la extensión no responde")
      hasta que se haga esto. Decisión del usuario por su riesgo (corre
      dentro de `gnome-shell`). Antes: tener a mano `docs/RECUPERACION_GNOME.md`
      y comprobar el TTY de rescate (Ctrl+Alt+F3 → `login:`).

      Instalar:
      ```sh
      cp -r "$(git rev-parse --show-toplevel)/gnome-extension/ventanas-jarvis@local" \
            ~/.local/share/gnome-shell/extensions/
      # cerrar sesión y volver a entrar (Wayland no recarga el shell en caliente)
      gnome-extensions enable ventanas-jarvis@local
      gnome-extensions info ventanas-jarvis@local   # debe decir: Estado: ACTIVE
      ```

      Quitar (cualquiera de las dos vías):
      ```sh
      gnome-extensions disable ventanas-jarvis@local            # desde la sesión
      rm -rf ~/.local/share/gnome-shell/extensions/ventanas-jarvis@local
      # o, si el shell no responde, desde un TTY (Ctrl+Alt+F3):
      dconf write /org/gnome/shell/disable-user-extensions true
      ```

      Sin instalarla (o con la integración apagada por
      `data/ventanas_integracion.json`), el resto de JARVIS funciona igual;
      solo `listar/enfocar/cerrar_ventana` quedan inertes con error claro.

## FASE G — Interacción: portapapeles de escritura  ✅ CERRADA 2026-09-09 (merge `9270a24`)

Cierre: **portapapeles de escritura hecho; teclado sintético aplazado con
motivo; ratón descartado.** No es una fase a medias — es el alcance que el
usuario fijó tras el análisis G0.

- [x] **G0 — ANÁLISIS** (sin código). `docs/G0_ANALISIS_TECLADO.md`.
      Recomendación: (1) portapapeles ya; (2) teclado sintético aplazado
      salvo caso concreto, y solo atajos allowlistados, **nunca**
      `escribir(texto)`; (3) ratón fuera del roadmap. **Alcance aceptado por
      el usuario.**

- [x] **G1 — PORTAPAPELES DE ESCRITURA.** `jarvis_local/tools/clipboard.py` +
      parser `_parse_portapapeles_escritura` + contratos `escribir_portapapeles`
      / `restaurar_portapapeles` / `escritura_portapapeles_on|off` (todos
      `llm_visible=False`).
      - `escribir_portapapeles(texto)`: EXECUTE + VERIFY (se relee y se
        compara; sondeo hasta 1,5 s porque la propiedad del *selection* es
        asíncrona). Guarda el contenido previo → `restaurar_portapapeles`.
      - **Confirmación condicional** (E2): solo si el texto es largo (>280) o
        parece comando / URL / credencial. Texto inocuo va directo.
        Auditoría D2: el plan lleva solo `preview` + longitud + motivo, nunca
        el texto entero.
      - Interruptor `data/portapapeles_escritura.json` (por defecto activo).
      - Backend: `wl-copy`/`wl-paste`; si no, `xclip` (X11 vía Xwayland — las
        apps Wayland puras pueden no verlo). Sin ninguno → ERROR claro
        (`sudo apt install wl-clipboard`).
      - **En vivo (2026-09-09):** ejercitado con `xclip` y, tras instalar
        `wl-clipboard`, con el **backend nativo**: `_backend()` elige
        `wl-clipboard`; `escribir_portapapeles` → EXECUTED, `verify.ok True`;
        **`wl-paste` (protocolo Wayland, no X11) lee lo escrito** con acentos
        y emoji, y `xclip -o` también (Mutter unifica los dos portapapeles);
        `restaurar_portapapeles` → EXECUTED `verify.ok True`; portapapeles del
        usuario dejado como estaba. (Bug corregido de paso:
        `capture_output=True` colgaba `subprocess.run` esperando el EOF de la
        pipe que el hijo daemonizado de `xclip`/`wl-copy` hereda y no cierra
        → ahora `stdout/stderr=DEVNULL`.)
      - Tests: `test_clipboard.py` (14) + banco §G (2 EFECTO + 4 FALLO).

- [ ] ~~**Teclado y ratón sintéticos** (`ydotool`).~~ **DESCARTADO.**
      - **Teclado sintético: APLAZADO.** Motivo: `ydotool` escribe a
        `/dev/uinput` sin saber en qué ventana, rodeando el guardia de shell,
        E1, E2 y D2 (análisis en `docs/G0_ANALISIS_TECLADO.md`). El
        subconjunto seguro (atajos allowlistados, negativa si el foco es una
        terminal, confirmación + re-chequeo, límite de velocidad, interruptor,
        auditoría) es acotable pero **aporta poco**: pulsar Enter/PageDown/
        Ctrl+S en una app ya enfocada. El texto libre —el valor real que se le
        supone— es justo lo que hay que prohibir.
      - **Condición para reabrirlo:** que aparezca un **caso real y repetido**
        que solo el teclado sintético resuelva. Si se hace, **solo atajos de
        una allowlist, nunca `escribir(texto)`**, con todas las capas de G0.
      - **Ratón: fuera del roadmap.** Un clic sintético es estrictamente peor
        (el objetivo es un píxel) y `enfocar_ventana` + atajos cubren lo que
        un asistente necesita. No queda como pendiente.
      - Prerrequisito `ydotoold` + grupo `input` (OPERACION_MEMORIA.md §6):
        solo relevante si se reabre el teclado.

## FASE H — Código muerto: integrar o borrar

`vision/`, `proactive/`, `plugins/`, `profiles.py`, `performance.py`.
- Visión: solo bajo petición explícita, una captura y un OCR por petición, sin
  bucles. Medir cuánto tarda el OCR aquí y decir si es viable.
- Proactividad: solo reglas deterministas y baratas sobre eventos reales del
  sistema, consumo en reposo indistinguible de cero, el usuario controla qué
  reglas están activas.
- Si algo no llega al presupuesto, borrarlo con justificación. Nada en limbo.

## FASE I — Interfaz: composición y acabado del HUD  🚧 EN CURSO (rama `feature/fase-i-interfaz`)

Addendum 8.2–8.7. Toda captura de evaluación lleva ≥6 mensajes reales dentro
(`scripts/hud_shot.py` lo siembra).

> **REGLA DURA para el resto de la fase (desde I2): ningún commit que toque
> un shader se da por hecho sin captura de verificación en vivo.** Las Fases
> 8 y 9 metieron la piel celular Voronoi y el iris alienígena compilando el
> `.qsb` sin mirar el resultado, y el orbe llevó meses fuera de la rampa de
> color sin que nadie lo notara (ver I2). Es exactamente el fallo que D0
> existe para cazar en el resto del proyecto — aquí se aplica igual: se
> compila, se renderiza con `scripts/hud_shot.py`, se mira la captura, y solo
> entonces se da el punto por cerrado.

> **Merge de `main` a la rama del rediseño — NADA QUE RESOLVER.** `origin/
> rediseno-presentacion` (HEAD `505ebf3`, "Fase 13") es **ancestro estricto de
> `main`**: `git merge-base --is-ancestor 505ebf3 main` → true, y no hay ni un
> commit en la rama que no esté en `main`. Todo el HUD ("feat(vista): Fase
> 4–13") lleva en `main` desde antes de la FASE D; se desarrolló en paralelo a
> D–G sin tocar la vista, así que **no divergió y no hubo conflictos**. La
> rama `feature/fase-i-interfaz` sale de `main` al día.

- [x] **I1 — COMPOSICIÓN.** `Main.qml` reencuadrado + `ActivitySpine.qml`
      (nuevo). Núcleo ×1,6 (factor de tamaño 0.66→1.06), centro en el **tercio
      inferior izquierdo** del escenario (`orbCX = stageLeft + stageW·0,32`,
      `orbCY = stageTop + stageH·0,60`), **sangrando por detrás** del panel de
      conversación. Conversación sobre **panel translúcido** (gradiente holo +
      vela de fondo con degradado horizontal 0,90→0,62 + filo izquierdo
      emisivo), anclada abajo junto al input y creciendo hacia arriba. Columna
      izquierda = **ActivitySpine**: reloj de sesión, MODO (estado + acento),
      telemetría cpu/ram/lat/tok·s, e **historial de energía del núcleo** en
      barras apiladas (muestreo del reloj global, sin timer). Se retira el
      `CoreStatus` suelto (lo duplicaba la espina y chocaba con el orbe).
      `test_ui_hud.py::test_responsive_layout…` actualizado: el solape
      núcleo/conversación es ahora **intencionado**; se sigue exigiendo que
      texto, identidad y comando queden dentro de la ventana.
- [x] **I2 — EL ORBE, TRES FRECUENCIAS** (incluye el saneado de color de
      Fases 8-9). `jarvis_local/ui/hud/shaders/core.frag` reescrito.
      - **Diagnóstico previo** (ver también el cierre de I1): comparando
        capturas antes/después de I1 con el mismo shader se confirmó que el
        naranja/rojo/verde caótico del orbe **ya estaba en `main`**, no era
        regresión de I1 — venía de Fase 8 (`a686eff`, piel celular Voronoi +
        iris alienígena) y Fase 9 (`0bb6402`), compiladas y versionadas sin
        verificación en vivo.
      - **LEY DE COLOR aplicada:** se borran (no se comentan) el raymarch
        volumétrico, la piel celular Voronoi y el iris alienígena — no
        podían garantizarse en rampa y eran, medido con `compact:true`, la
        causa principal del caos. También se corrige `irid()` (rotaba por
        todo el espectro) y el fleco cromático del borde, que escribía
        `col.r/g/b` de tres bandas independientes sin base acromática —
        con eso, en el radio donde solo una banda estaba activa, salía un
        píxel de rojo o verde puro. Ahora hay un fresnel acromático de base
        y la dispersión solo lo desplaza, nunca lo sustituye.
      - **Las tres frecuencias:** cuerpo por absorción (radio 0 = denso/
        oscuro, sube monótono hacia el limbo — antes era al revés, "bombilla"
        en el centro); fresnel nítido (~2px) en el limbo; microdetalle de 2ª
        octava con amplitud creciente hacia el limbo. Encima: el patrón de
        interferencia (Fase 6, ya en rampa, es lo que el usuario recordaba
        como "antes"), arcos, corona/anillo de audio (datos reales), onda de
        choque, barrido especular cada 7 s.
      - **Bloom:** `bloom_composite.frag` ya no porta el matiz de su blur —
        se re-tiñe a la rampa por LUMINANCIA (dos tintes fijos, ambos
        cian/azul), así ningún desequilibrio de canal del blur puede colar
        rojo/verde. Umbral en `0,80` (el brief pedía `≥0,72`; a ese número,
        con cualquier knee razonable, apareció un artefacto propio de esta
        GPU — ver más abajo — y subirlo lo elimina sin perder el fresnel ni
        el especular; se prioriza el espíritu del brief —nunca el cuerpo
        entero— sobre el número exacto).
      - **Artefacto encontrado y resuelto (no era regresión, tampoco Fase
        8-9):** con el shader ya saneado, aparecían pequeños fragmentos
        verdes en forma de hoja alrededor del orbe. Se aisló por descarte
        —corona, microdetalle, segunda pasada de blur, dispersión cromática,
        patrón de interferencia y arcos, cada uno probado por separado,
        ninguno era la causa única— hasta confirmar que es un artefacto de
        blur/downsample de `MultiEffect` en esta GPU con highlights pequeños
        y muy nítidos (el shader anterior nunca los tuvo: su brillo estaba
        repartido, no concentrado). Un `knee` de extracción ancho (0,5) con
        el umbral en 0,80 lo elimina por completo, verificado en los 5
        estados (`idle/listening/thinking/speaking/alert`).
      - Verificado en vivo con `scripts/hud_shot.py`: capturas antes/después
        de I1 (mismo shader, para separar la regresión) y antes/después de
        I2 (mismo tamaño, mismo estado, 8 mensajes reales), en los 5 estados.
- [x] **I3 — ILUMINACIÓN GLOBAL VISIBLE.** divisor y hairlines reciben la luz
      del núcleo por distancia y ángulo. Prueba: tapando el orbe, se nota que
      habla por el cambio de luz del resto.
      - `Design.qml`: `lightLevel(sx,sy)` gana un término angular (`lightCast`,
        una dirección preferida) además del de distancia, y la ganancia por
        energía real del núcleo se sube sustancialmente; `litHairline`/
        `litText` ensanchan sus rangos de tinte/alfa en la misma proporción.
      - Elementos que antes usaban un tinte de estado plano y ahora derivan su
        color/opacidad de `Design.litHairline`/`lightLevel` con su propia
        posición real en la escena: el conector vertical HUD↔núcleo
        (`hudConnector` en `Main.qml`), los tres separadores de la
        `ActivitySpine` (vía el componente `Hairline.qml`, ya existía pero no
        se usaba en ningún sitio) y la regla punteada bajo "JARVIS // CONSOLA"
        en `Conversation.qml` (el "subrayado de la derecha" de la prueba de
        aceptación).
      - `HudFrame.qml` reescrito: sus 8 elementos (4 corchetes + 4 ticks)
        compartían UNA sola muestra de luz tomada en el centro de la ventana,
        así que brillaban todos igual sin importar dónde estuviera el núcleo
        — un bug real frente al objetivo de I3 ("más brillante cerca, apagado
        lejos"). Ahora cada uno calcula su propia `Design.lightLevel` en su
        posición real.
      - `scripts/hud_shot.py`: nueva bandera `--cover-core` que tapa con un
        rectángulo negro la zona del núcleo (`rootItem.orbCX/orbCY/orbSize`,
        con un margen del 15% por el halo del bloom) antes de guardar el PNG,
        para poder ejercitar la prueba de aceptación tal como la pidió el
        usuario sin ver el núcleo en absoluto.
      - **Prueba de aceptación ejercitada en vivo** (capturas `idle` vs
        `speaking`, núcleo tapado, 8 mensajes reales sembrados): se distingue
        el estado sin ver el núcleo — la espina de energía y sus hairlines son
        la señal dominante (más del doble de luminancia en `speaking`), los
        corchetes de esquina y la regla punteada de la derecha aportan una
        señal secundaria más sutil pero real, y correctamente más tenue que
        la de la izquierda (el conector vertical queda mayormente bajo el
        propio rectángulo de tapado por estar pegado al núcleo; se verificó
        aparte por inspección directa del motor de lightLevel/litHairline en
        su posición real, con el mismo resultado: la energía alta lo satura
        a brillo máximo).
      - **Comprobación de refuerzo pedida por el usuario** (antes de I4): la
        prueba anterior tapaba sólo el núcleo, y la espina de energía —un
        indicador de datos, no iluminación— podía estar cargando sola toda
        la distinción. Se repitió tapando TAMBIÉN la `ActivitySpine` (nueva
        bandera `--cover-spine` en `scripts/hud_shot.py`, que localiza el
        ítem por `objectName` y lo tapa con su rect real en coords de
        escena). Resultado inicial: con la espina tapada, el resto de la
        interfaz (marco, conector, regla punteada) SÍ respondía a la luz
        real (confirmado analíticamente y con recortes ampliados) pero el
        margen era demasiado pequeño para leerse a simple vista — la
        objeción del usuario era correcta.
      - Se subió la ganancia en dos rondas: `Design.lightLevel` reduce su
        piso de distancia (0,14→0,03) y sube su ganancia por energía
        (0,62–1,55·E → 0,32–2,60·E); `HudFrame._k` y los mapeos de opacidad
        de corchetes/ticks bajan su piso y suben el peso de `lightLevel`
        (de compartir un piso ~0,2-0,3 fijo a casi apagarse del todo en
        reposo); `hudConnector` gana un término de opacidad ligado a
        `lightLevel` que antes no existía (sólo el tinte cambiaba, no el
        brillo); la regla punteada de `Conversation.qml` amplía su rango de
        igual forma. Verificado que esto NO deslució la señal ya buena de
        la espina/hairlines (formalmente más contrastada, no menos).
      - **Resultado final, verificado en vivo** (núcleo + espina tapados,
        `idle` vs `speaking`): los corchetes del marco pasan de un azul casi
        invisible a un cian claramente encendido (×3,4 de contraste medido
        en la esquina más próxima al núcleo), y la regla punteada de la
        derecha se aclara de forma visible aunque más discreta (×1,3–1,5,
        coherente con estar más lejos que la espina). Sigue siendo una señal
        más sutil que la de la espina —por diseño: son detalles de cabina,
        no un panel de estado— pero ya no es "sólo estar puesta": respira de
        forma perceptible por sí sola, sin parpadeo (todo el cambio es por
        opacidad/tinte continuos, ninguna transición discreta).
- [x] **I4 — COLOR.** borde del input a **cyan** (no verde). Auditar cada uso
      de verde/amarillo/rojo: color = estado, nunca decoración.
      - Borde del input (`CommandBar.qml`): verificado en vivo — ya es
        `Design.cyan` con foco (`Design.azure` generando, atenuado con
        `litHairline` en reposo). No usa verde en ningún estado; sin cambios.
      - Auditados todos los usos de `Design.ok`/`warn`/`alert` en
        `jarvis_local/ui/hud/qml/`: estado real de mic/voz, umbrales de
        cpu/ram/latencia, alerta del núcleo, error de turno, banner de
        degradado — todos legítimos (el color sigue un dato real, nunca es
        fijo).
      - **Violación real encontrada y corregida:** el "testigo de canal" en
        la cabecera de `Conversation.qml` ("JARVIS // CONSOLA") era
        `Design.ok` fijo, sin condición — un verde permanente que no
        comunicaba nada. Ahora es `Design.alert` cuando `Vm.metrics.online
        === false` y `Design.ok` en caso contrario: verde/rojo real, no
        decoración. Verificado en vivo (capturas online/offline: el testigo
        y el widget SISTEMA cambian juntos).
      - Revisados y mantenidos sin cambio, con su razón: (1) los "colores de
        firma" de `Hud.qml` (`amber`, `acidLime`, `magenta`, `sky`, `violet`)
        son una decisión ya documentada de Fase 6 (`Design.qml`) — tokens
        DISTINTOS de `ok`/`warn`/`alert`, precisamente para no chocar con el
        estado real; (2) el resaltado de sintaxis de `CodeBlock.qml` reutiliza
        los tokens literales `ok`/`warn` para cadenas/números — es una
        convención de resaltado tipo terminal, no un indicador de estado del
        sistema, y nadie lo lee como tal dentro de un bloque de código; se
        deja así pero se señala por si el usuario prefiere tokens propios.
      - Nota aparte (no es de esta tarea, es FASE H): `CoreStatus.qml` es
        código muerto — ya no se instancia desde `Main.qml` desde I1 (la
        ActivitySpine lo reemplazó), sólo queda un comentario que lo
        menciona. Se deja para el barrido de FASE H.
- [x] **I5 — ESTADO VACÍO.** fuera el "consola conversacional" gris; datos
      reales (modelo cargado, nº de recuerdos, herramientas, última sesión).
      - `Conversation.qml`: la frase de relleno desaparece; en su lugar,
        `Vm.metrics.model`, `Vm.metrics.tools.count` y `Vm.metrics.memory.count`
        — ya reales y en vivo desde `services.sample_all()` (FASE 3/B), sin
        tocar ese camino — más una cuarta pieza nueva, "última sesión".
      - **"Última sesión" (D2)**: `AuditLog.last_entry()` (nuevo método en
        `safety/audit.py`) — la entrada más reciente de la auditoría
        append-only. A diferencia de `read()`, NUNCA carga el histórico
        completo: sólo la cola (últimos 4 KiB) del fichero activo, y sólo si
        éste está vacío (rotación reciente) cae al rotado más nuevo. Se
        sondea cada 2 s desde `MetricsService`, tenía que ser barato sin
        importar el tamaño de `audit.jsonl`. Nueva clave `lastSession` en
        `services.sample_all()`. Formato en QML: "hoy hh:mm" / "ayer hh:mm" /
        "dd/mm hh:mm"; sin ninguna entrada, "—" — nunca una fecha inventada.
      - Sin dato en cualquiera de las cuatro piezas: "—", igual que el resto
        del HUD.
      - Tests nuevos: `test_last_entry_*` (vacío, entrada más reciente,
        superviviente a la rotación) en `test_audit.py`; `sample_all()` shape
        ampliado con `lastSession` en `test_ui_hud.py`.
      - **Captura de verificación en vivo** (sin sembrar conversación, con
        `services.sample_all()` real de este checkout, no datos de prueba
        inventados): "modelo llama3.2:3b · herramientas 46" /
        "memoria 6 recuerdos · última sesión hoy 16:34" — los cuatro datos
        genuinamente en vivo del sistema.
      - **Hallazgo colateral, corregido en su propio commit (ver más abajo)**:
        al usar por primera vez un recuento real de herramientas (46, con
        `agent: true`) en vez del valor fijo de la careta de pruebas
        (`hud_shot.py` usaba 84), el widget superior "HERRAMIENTAS" se
        quedaba en "0" — un dato FALSO en pantalla, lo que FASE D prohíbe en
        todo el sistema. Mismo patrón que `plan_delete` y la `ListView`
        vacía: funciona simulado, falla con datos reales.
- [x] **I5·fix — HudCell: el número que "rueda" se quedaba clavado en 0.**
      Causa raíz en `HudCell.qml`: `NumberAnimation.to` colgaba de un BINDING
      sobre `parsed` (`to: cell.parsed ? cell.parsed.num : 0`). Al pasar de
      ausente (sin dato, `parsed=null`) a un valor real, `onParsedChanged`
      llamaba a `rollAnim.restart()` — pero el orden entre la reevaluación de
      ESE binding y la ejecución del propio handler de la señal no está
      garantizado: si el handler corría primero, la animación arrancaba y
      terminaba apuntando al `to` VIEJO (0), y `rolled` quedaba clavado ahí
      para siempre. Aislado con un componente mínimo fuera del árbol real
      (reproducido con solo `value: ""` → `value: "46"`, sin nada de
      `Hud.qml` de por medio) antes de tocar el archivo, para no confundir
      "roto por I5" con "roto siempre".
      - Fix: fijar `rollAnim.to = parsed.num` A MANO justo antes de
        `restart()`, en vez de depender de un binding declarativo — hace el
        arranque de la animación determinista sin importar el orden de
        reevaluación.
      - **Es un bug del componente, no del dato**: de los 5 widgets de esa
        fila, "herramientas" era el ÚNICO cuyo valor empieza por un dígito
        (los demás — SISTEMA, MODELO, VOZ, MEMORIA — arrancan con letra y
        nunca ejercitaban el camino de "rodar"), lo que explica por qué
        llevaba tiempo sin notarse. Comprobado que NO es exclusivo de
        "herramientas": un nombre de modelo que empiece por dígito (caso
        real, p. ej. "70b-instruct") disparaba el mismo bloqueo antes del
        fix y rueda bien después — cualquier widget futuro con una cifra
        habría heredado el mismo fallo.
      - Test de regresión nuevo (`test_ui_hud.py`,
        `test_hud_cell_rolls_to_real_value_not_stuck_at_zero`): sin el fix
        falla (`0.0 == 46.0`), con el fix pasa — verificado en ambos sentidos
        (`git stash` del archivo corregido y vuelta atrás) antes de dar el
        commit por bueno.
      - Verificado en vivo: captura del estado vacío de I5 con el fix
        aplicado — "HERRAMIENTAS 46" real, resto de widgets sin regresión.
- [ ] **I6 — RENDIMIENTO.** 🚧 EN CURSO. bloom a 1/4 de resolución sobre el
      rect del núcleo (no la ventana) · atmósfera a 15 fps con grano tileado y
      viñeta horneada · techo 30 fps idle / 60 en listening·thinking·speaking
      · ≤12% de un núcleo en la HD 520, medido · la máscara de esquinas
      redondeadas NO desaparece con la ruta de degradación.
      - **Metodología corregida a mitad de fase**: hasta aquí, toda captura de
        verificación de FASE I se tomó con `QT_QPA_PLATFORM=offscreen`
        (renderizado por software forzado), que en este equipo activa el
        LATCH de degradación (`rootItem._softwareBackend`) y por tanto
        **nunca ejecutó de verdad el bloom ni la atmósfera** — sólo el
        `CoreShader` puro, sin post-proceso. El entorno SÍ tiene un display
        Wayland real (`WAYLAND_DISPLAY=wayland-0`); sin `offscreen`, Qt usa
        `RHI backend: OpenGL` de verdad. Se descubrió al empezar I6 porque
        el downsample del bloom no se podía comprobar sin bloom real. Para
        forzar el pipeline completo en pruebas automatizadas existe
        `rootItem.perfOverride = -1` (ya reservado en el código para esto).
        Las verificaciones de I1-I5 (composición, iluminación ambiental,
        color, datos) no dependían del bloom/atmósfera y sus conclusiones se
        mantienen; pero fueron todas contra el núcleo "desnudo", nunca contra
        el pipeline completo que ve un usuario real.
      - **I6·1 — Bloom a 1/4 de resolución** (`CoreBloom.qml`): la cadena de
        extracción + dos pasadas de blur ahora renderiza a mitad de ancho ×
        mitad de alto (1/4 de píxeles, la convención habitual), con
        `blurMax` a la mitad (10/24, antes 20/48) para que el radio aparente
        no cambie al recomponer a resolución completa. El compuesto final
        sigue a resolución completa — la nitidez la pone el núcleo, no el
        halo. Ya estaba "compuesto sólo sobre el rectángulo del núcleo" (el
        `Item` de `CoreBloom` ya vive dentro de `coreZone`, del tamaño del
        orbe, no de la ventana).
      - **Residual verde de I2 — comprobado, diagnóstico CORREGIDO**: con
        bloom real (OpenGL, no software) se reprodujo el fragmento verde en
        forma de flecha/hoja, en el mismo punto aproximado en varias
        capturas. El downsample **NO lo hace desaparecer**: se probó también
        a 1/8 de ancho×alto (1/64 de píxeles, muy por debajo de lo que se
        va a usar) y el fragmento sale IDÉNTICO en forma, tamaño y color.
        Esto descarta la hipótesis de I2 ("artefacto de blur/downsample de
        MultiEffect sobre highlights nítidos a resolución nativa"): si fuera
        un artefacto de blur, degradar tanto la resolución de entrada lo
        habría suavizado o deformado, y no lo hizo — sale idéntico a
        cualquier resolución. Es, con más certeza ahora, una emisión de
        color genuina en `core.frag` anterior al bloom — el umbral de
        extracción (0,80) simplemente la vuelve visible al recortarla y
        ampliarla. Candidato más probable por posición y cadencia de
        movimiento (coincide con un periodo de giro lento): el SATÉLITE
        COMPAÑERO (línea ~223 de `core.frag`) u otra fuente cercana en el
        archivo — su código mezcla `warmTint`/`tintHot` sin escribir canales
        sueltos, así que no se localizó la línea exacta en esta pasada.
        **No se persigue más aquí** (excede "comprobar si el downsample lo
        cierra", que es lo pedido): queda para una rama de shader dedicada,
        con el diagnóstico ya acotado y la vía del artefacto de blur
        descartada, no abierta.
      - **I6·2 — Atmósfera a 15 fps, grano tileado, viñeta horneada** (esta
        última parte, "tileado"/"horneada" en el sentido de: barata y
        estable, no recalculada por-frame a resolución nativa — ver nota
        de coste más abajo): reintroducida en `Main.qml` como
        `layer.effect` de `rootItem`, tras encontrar y corregir la causa
        real del "marco oscuro" que la había hecho descartar en Fase 2:
        `atmosphere.frag` tocaba el alfa del grano y de la máscara de
        esquinas sin tocar el color en la misma proporción, rompiendo el
        invariante premultiplicado (`rgb <= alfa`) justo donde la ventana
        debía quedar transparente — invisible en una captura de
        `grabToImage` (alfa recompuesto correctamente por Qt), pero real
        para el compositor del SO al mezclar contra el escritorio de
        verdad. Corregido: grano escalado por alfa (`col += g * a`) y
        máscara de esquinas aplicada a AMBOS canales (`a *= mask; col *=
        mask`). Verificado sin fuga de color componiendo contra magenta
        puro (ninguna prueba de color inesperado en los bordes).
      - `time` del grano cuantizado a 15 fps (`floor(tick*15)/15`): la
        escena puede renderizar más rápido, pero el grano sólo "salta" 15
        veces por segundo — se lee como grano de película, no como
        parpadeo. Nuevo token `Design.windowCornerRadius` (14 px).
      - Encendido/apagado en dos niveles, no uno: la capa entera
        (`layer.enabled`) depende SÓLO de `_softwareBackend` — ahí el
        shader puede no ejecutarse en absoluto, límite de hardware, mismo
        trato que el bloom. Dentro de la capa, `grainAmt`/`vignette`/
        `aberration` dependen de `degraded` (que sí cubre fps sostenidos
        <40 y `perfOverride` de prueba) y se apagan a 0 ahí, PERO
        `cornerRadius` se pasa siempre que la capa esté encendida — así la
        máscara de esquinas sobrevive a la ruta de degradación por fps
        (GPU real, sólo más lento) aunque no al límite de hardware real
        (software/Null, donde nada de esto puede ejecutarse: mismo
        límite ya aceptado para el bloom). Verificado con
        `perfOverride=1` en GPU real: `degraded=True`,
        `_softwareBackend=False` → capa sigue encendida.
      - Impacto visual del recorte de esquinas: mínimo en esta app en
        concreto porque la ventana no tiene fondo sólido que recortar
        ("sin panel, sin caja" es el lenguaje de diseño desde Fase 4) — el
        recorte importa donde SÍ hay contenido tocando el borde (p. ej. el
        tirador de redimensionado, alfa ~218 visto en la esquina
        inferior-derecha), no en el resto de la ventana, que ya era
        transparente antes del recorte. El código es correcto y queda listo
        para cuando haga falta.
      - No se pudo verificar contra un compositor de escritorio real
        (mutter) con un pantallazo del sistema — los intentos anteriores de
        esta fase con `grim`/`gnome-screenshot`/el portal XDG ya habían
        fallado en este entorno, y `QScreen.grabWindow()` en Wayland nativo
        devuelve un pixmap vacío (bloqueado por seguridad, esperable). Se
        deja constancia del límite en vez de fingir una verificación que no
        se pudo hacer.
      - **I6·3 — Techo de fps por estado** (`Main.qml`): el ÚNICO
        `FrameAnimation` sólo actualizaba `tick` en cada disparo del
        compositor (sin techo propio, lo que el display diera). Ahora
        `tick` — y con él TODA la escena reactiva (shaders, hairlines,
        respiración) — sólo avanza a una cadencia objetivo: 30 fps en
        reposo, 60 sólo en `listening`/`thinking`/`speaking`
        (`rootItem._targetFps`). El resto de disparos del compositor
        acumulan tiempo en `_frameAcc` sin tocar ninguna property visible,
        así que Qt no ensucia el árbol de escena ni repinta — ahorro real,
        no una etiqueta. La medición de fps para el latch de degradación
        sigue usando el `frameTime` CRUDO de cada disparo (no el
        acumulado): el techo propio nunca se puede confundir con una
        degradación real del hardware.
      - Verificado en vivo (GPU real): `tick` sigue representando segundos
        reales 1:1 en ambos casos (no se pierde ni se adelanta tiempo, sólo
        cambia CADA CUÁNTO se actualiza) — confirmado midiendo cuántas
        veces cambia `tick` en una ventana de 3 s real: ~21/s en idle
        (techo 30) vs ~36/s en speaking (techo 60), la proporción ~1,7×
        esperada entre 30 y 60 (los valores absolutos quedan por debajo de
        lo nominal por el propio bucle de sondeo de Python del arnés de
        prueba, no por el mecanismo en sí).

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
