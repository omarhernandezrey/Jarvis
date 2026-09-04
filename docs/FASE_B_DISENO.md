# FASE B — Catálogo único de herramientas + contrato de herramienta (diseño)

> Estado: **IMPLEMENTADO** (2026-09-03, rama `feat/catalogo-unico-herramientas`).
> Resumen y evidencia en `docs/PLAN_EJECUCION.md § FASE B`. Este documento se
> conserva como registro del diseño y de las decisiones.
>
> Desviaciones respecto al plan de abajo, decididas durante la implementación:
> - `ToolContract` tiene además `plan_run` (ejecutor de la variante plan cuando
>   difiere del `run`) e `in_legacy_write` (marca a `delete_file`, que
>   históricamente estaba en `_WRITE_TOOLS` **y** `_PLAN_TOOLS`).
> - `parser_argmap`/`parser_fixed` se validan contra la **firma del ejecutor**
>   (`inspect.signature`), no contra las `properties` del schema — los intents
>   finos (`volume_up`…) tienen schema vacío pero pasan `accion` al ejecutor.
> - `verify`/`revert` son **strings** (declarativos); se vuelven ejecutables en
>   FASE D.
> - CRITICAL (sistema: `energia_del_equipo`, `ejecutar_comando`) **no** fuerza
>   `needs_confirmation` (su guardia es otra: 60 s cancelables / blocklist);
>   endurecerlo es FASE E. Sólo DELETE lo fuerza.
> - Se añadió `listar_aplicaciones` (intent `list_apps`, sólo-parser) para
>   paridad exacta con `_READ_TOOLS`.
> - `test_paridad_*` usa un snapshot JSON congelado
>   (`test/_fixtures_catalogo_baseline.json`) en vez de leer git HEAD~.

## Decisiones tomadas (no re-litigar)

1. **Idioma canónico: español.** `abrir_aplicacion`, `clima`, `tomar_nota` son
   los nombres de verdad — es lo que ya ve el LLM y lo que valida
   `jarvis_local/eval/cases.py`. Los nombres del parser (`open_app`, `weather`,
   `take_note`…) pasan a ser **alias** que siguen resolviendo.
2. **Migración: catálogo como fuente + adaptadores.** El módulo nuevo es la
   única fuente de verdad. `jarvis.py::_READ_TOOLS/_WRITE_TOOLS/_PLAN_TOOLS` y
   `agent/registry.py::TOOLS` se **derivan** de él en tiempo de import, sin
   borrar las rutas de ejecución. Diff acotado, revert limpio.

## Estado actual (lo que se fusiona)

| | `jarvis.py` (ruta parser) | `agent/registry.py` (ruta agente) |
|---|---|---|
| Forma | 3 dicts `nombre→lambda(args)`: `_READ_TOOLS` 19, `_WRITE_TOOLS` 41, `_PLAN_TOOLS` 10 | `TOOLS: list[Tool]` 46 (nombre, descripción, JSON Schema, `run(**kw)`, `needs_confirmation`, `aliases`) |
| Idioma | inglés | español (visto por el LLM y `eval/`) |
| Granularidad | fina: `volume_up/down/set/mute`, `media_*`, `lock_pc/shutdown_pc/restart_pc/suspend_pc/cancel_shutdown`, `minimize_all/snap_window/switch_window` sueltos | agrupada: `controlar_volumen(accion)`, `controlar_musica(accion)`, `energia_del_equipo(accion)`, `organizar_ventanas(accion)`, `cambiar_ventana` |
| Args divergentes | `set_reminder`→`text/minutes/at` · `send_whatsapp`→`to/message` | `crear_recordatorio`→`texto/minutos/hora` · `enviar_whatsapp`→`para/mensaje` |
| Solo en un lado | `add_contact`, `list_contacts` (parser; no en registry) | `recordar` (agente; sin intent de parser) |
| Puente hoy | `eval/harness.py:141` mapea `open_app→abrir_aplicacion` a mano | |

61 intents distintos emitidos por el parser (`grep 'tool="'` en `parser.py`).

## Módulo nuevo: `jarvis_local/tools/catalog.py`

Contiene, en este orden:

1. **Ejecutores perezosos** — se **mueven aquí** los ~46 `_open_app`, `_weather`,
   … que hoy viven en `registry.py` (evita import circular: hoy
   `retriever.py → registry.TOOLS`; si `registry` importara `catalog` y
   `catalog` importara `registry`, ciclo). `registry.py` pasa a importarlos de
   aquí.
2. **`RiskLevel`** — se **reutiliza** el de `safety/policy.py`
   (`NONE/READ/CREATE/EXECUTE/DELETE/CRITICAL`). Mapeo al 4-way del plan:
   lectura→`READ` · escritura→`CREATE` (archivos) / `EXECUTE` (acciones) ·
   destructivo→`DELETE` · sistema→`CRITICAL`.
3. **`@dataclass(frozen=True) ToolContract`**:

   | campo | tipo | qué es |
   |---|---|---|
   | `name` | `str` | canónico español |
   | `description` | `str` | para el LLM (≥ 30 chars; obligatoria si `llm_visible`) |
   | `parameters` | `dict` | JSON Schema (`_obj/_str/_int`) |
   | `run` | `Callable[..., ActionPlan\|str]` | ejecutor (estilo `**kwargs` con las props del schema) |
   | `risk` | `RiskLevel` | — |
   | `needs_confirmation` | `bool` | default `risk.value >= DELETE.value`; explícito si difiere |
   | `verify` | `str` | **declarativo en FASE B** (cómo se comprueba el efecto). Callable en FASE D. `"n/a (lectura)"` para reads |
   | `revert` | `str` | cómo se revierte, o `"irreversible"` / `"n/a"` |
   | `parser_intents` | `tuple[str, ...]` | nombres que emite `parser.py` y que caen aquí (`()` = inalcanzable por parser) |
   | `parser_argmap` | `dict[str,str]` | `{clave_parser: clave_schema}` sólo si difieren |
   | `parser_fixed` | `dict[str,object]` | args fijos al venir del parser (ej. `volume_up` → `{"accion": "subir"}`) |
   | `aliases` | `tuple[str, ...]` | otros nombres |
   | `llm_visible` | `bool` | `True` = el agente lo ofrece al LLM (los 46); `False` = entrada fina sólo-parser |

4. **`validate_contract(c) -> list[str]`** — devuelve lista de problemas
   (vacía = OK): nombre no vacío y `snake_case`; si `llm_visible`,
   `len(description) >= 30`; `parameters` es objeto JSON Schema válido
   (`type=="object"`, `properties` dict, `required ⊆ properties`); `run` es
   callable; `risk` es `RiskLevel`; `verify` y `revert` no vacíos;
   `needs_confirmation is True` si `risk.value >= DELETE.value`; toda clave de
   `parser_argmap`/`parser_fixed` existe en `properties`; `parser_intents` y
   `aliases` sin colisiones con otros contratos. Se ejecuta en el import del
   módulo con `assert not problemas` → un contrato a medias **rompe el arranque**
   (y el test lo fija).

5. **`CONTRACTS: list[ToolContract]`** — la tabla (≈ 65 entradas, ver mapeo
   abajo).

6. **Adaptadores** (funciones puras que derivan las vistas viejas):
   - `by_name(n) -> ToolContract | None` — resuelve `name`, `aliases` y
     `parser_intents`.
   - `agent_contracts() -> list[ToolContract]` — los `llm_visible`.
   - `read_tools() / write_tools() / plan_tools() -> dict[str, Callable[[dict], object]]`
     — clave = cada `parser_intent` **y** el `name` canónico; valor = lambda que
     traduce el dict del parser (`parser_argmap` + `parser_fixed`) y llama a
     `run(**kw)`. Partición por `risk`: `READ`→read; `DELETE`/con plan→plan;
     resto→write. (Réplica exacta de las 3 dicts actuales.)
   - `slow_path_only() -> list[str]` — `llm_visible and not parser_intents`.
     Es el "informe de herramientas sólo alcanzables por el camino lento" que
     pide el plan.

## Mapeo de contratos (una fila = un `ToolContract`)

**Grupos LLM-visibles con intents finos de parser** (`llm_visible=True`):

| contrato | parser_intents | risk | conf | notas |
|---|---|---|---|---|
| `abrir_aplicacion` | `open_app` | EXECUTE | no | |
| `cerrar_aplicacion` | `close_app` | EXECUTE | no | |
| `cerrar_todas_aplicaciones` | `close_all_apps` | EXECUTE | no | |
| `controlar_volumen` | — (los finos abajo) | EXECUTE | no | |
| `controlar_musica` | — | EXECUTE | no | |
| `crear_recordatorio` | `set_reminder` | CREATE | no | argmap `text→texto, minutes→minutos, at→hora` |
| `listar_recordatorios` | `list_reminders` | READ | no | |
| `cancelar_recordatorio` | `cancel_reminder` | EXECUTE | no | argmap `which→cual` |
| `enviar_whatsapp` | `send_whatsapp` | EXECUTE | no | argmap `to→para, message→mensaje` |
| `organizar_ventanas` | — (finos abajo) | EXECUTE | no | |
| `resumen_del_dia` | `daily_briefing` | READ | no | |
| `leer_portapapeles` | `read_clipboard` | READ | no | |
| `leer_archivo` | `read_file` | READ | no | argmap `path→ruta` |
| `energia_del_equipo` | — (finos abajo) | CRITICAL | no¹ | ¹apagar/reiniciar dan 60 s cancelables, no `/confirmar` |
| `estado_del_sistema` | `system_status` | READ | no | |
| `ejecutar_comando` | `run_command` | CRITICAL | no² | ²blocklist en `safety.permissions`; plan sólo por parser (`_PLAN_TOOLS`) |
| `listar_archivos` | `list_files` | READ | no | |
| `buscar_archivo` | `search_files` | READ | no | |
| `crear_carpeta` | `create_directory` | CREATE | no | |
| `crear_archivo` | `create_file` | CREATE | no | |
| `borrar_archivo` | `delete_file` | DELETE | **sí** | |
| `ocultar_archivos` | `hide_files` | DELETE | **sí** | |
| `clima` | `weather` | READ | no | |
| `ubicar_lugar` | `locate` | EXECUTE | no | argmap `place→place` (abre Maps) |
| `wikipedia` | `wiki` | READ | no | argmap `topic→topic` |
| `noticias` | `news_headlines` | READ | no | |
| `calcular` | `calculate` | READ | no | |
| `preguntar_wolframalpha` | `wolfram` | READ | no | argmap `question` / parser usa `question` |
| `mi_direccion_ip` | `get_ip` | READ | no | |
| `proximos_eventos` | `calendar_events` | READ | no | |
| `contar_chiste` | `tell_joke` | READ | no | |
| `abrir_sitio_web` | `open_website` | EXECUTE | no | argmap `site→site` |
| `buscar_en_google` | `google_search` | EXECUTE | no | argmap `query→query` |
| `reproducir_en_spotify` | `spotify_play` | EXECUTE | no | argmap `song→song` |
| `reproducir_en_youtube` | `youtube_play` | EXECUTE | no | argmap `query→query` |
| `reproducir_musica_local` | `play_music` | EXECUTE | no | |
| `navegar_con_selenium` | `browser_navigate` | EXECUTE | no | |
| `cerrar_navegador` | `close_browser` | EXECUTE | no | |
| `buscar_empleo` | `search_jobs` | READ | no | |
| `abrir_oferta_empleo` | `open_job` | EXECUTE | no | |
| `mostrar_ofertas_empleo` | `show_jobs` | EXECUTE | no | |
| `tomar_nota` | `take_note` | CREATE | no | |
| `captura_de_pantalla` | `screenshot` | CREATE | no | |
| `cambiar_ventana` | `switch_window` | EXECUTE | no | |
| `enviar_correo` | `send_email` | DELETE | **sí** | |
| `recordar` | — | CREATE | no | **sólo-agente** (sin intent de parser) |

**Contratos finos sólo-parser** (`llm_visible=False`, `parser_fixed`):

| contrato | parser_intent | `run` | fixed |
|---|---|---|---|
| `volume_up` | `volume_up` | `_volume_control` | `accion=subir` |
| `volume_down` | `volume_down` | `_volume_control` | `accion=bajar` |
| `volume_set` | `volume_set` | `_volume_control` | `accion=nivel` (+ `level→nivel`) |
| `volume_mute` | `volume_mute` | `_volume_control` | `accion=silenciar`/`activar` según `mute` |
| `media_play_pause` | `media_play_pause` | `_media_control` | `accion=pausar` |
| `media_next` | `media_next` | `_media_control` | `accion=siguiente` |
| `media_previous` | `media_previous` | `_media_control` | `accion=anterior` |
| `lock_pc` | `lock_pc` | `_power_control` | `accion=bloquear` |
| `shutdown_pc` | `shutdown_pc` | `_power_control` | `accion=apagar` |
| `restart_pc` | `restart_pc` | `_power_control` | `accion=reiniciar` |
| `suspend_pc` | `suspend_pc` | `_power_control` | `accion=suspender` |
| `cancel_shutdown` | `cancel_shutdown` | `_power_control` | `accion=cancelar` |
| `minimize_all` | `minimize_all` | `_window_control` | `accion=minimizar_todo` |
| `snap_window` | `snap_window` | `_window_control` | `accion=<direction>` |
| `add_contact` | `add_contact` | `whatsapp.add_contact` | — (no llega al LLM) |
| `list_contacts` | `list_contacts` | `whatsapp.list_contacts` | READ |
| `file_info` | `file_info` | `files.read_metadata` | READ |

> `volume_set` necesita `level` (int) en el schema fino; `snap_window` necesita
> `direction`. `volume_mute` mapea `mute: bool` → `accion`. Estos 3 llevan
> `parameters` propios; el resto van con `_obj({}, [])`.

## Cambios en archivos existentes (mínimos)

- **`agent/registry.py`**: borra los ejecutores (movidos) y la lista `TOOLS`
  literal. `from jarvis_local.tools import catalog`. `Tool` se mantiene.
  `TOOLS = [_to_tool(c) for c in catalog.agent_contracts()]` donde `_to_tool`
  copia `name/description/parameters/run/needs_confirmation/aliases`. `get_tool`,
  `all_schemas`, `tool_names`, `execute`, `_validate_arg_type`,
  `_coerce_arg_type` intactos. `_obj/_str/_int` se mueven a `catalog` y se
  re-exportan aquí para no romper imports.
- **`jarvis.py`**: `_READ_TOOLS = catalog.read_tools()` ·
  `_WRITE_TOOLS = catalog.write_tools()` · `_PLAN_TOOLS = catalog.plan_tools()`.
  Se borran las lambdas y los helpers `_get_weather`/`_get_calculate` (su lógica
  ya vive en los ejecutores `_weather`/`_calculate` del catálogo).
- **`agent/retriever.py`**: `from jarvis_local.agent.registry import TOOLS` sigue
  valiendo (registry re-exporta). Sin cambios.
- **`eval/harness.py`**: el dict manual `open_app→abrir_aplicacion` se puede
  sustituir por `catalog.by_name(x).name`, pero **no en FASE B** (no romper el
  eval); se anota como limpieza para FASE C.

## Tests nuevos: `test/test_catalog.py`

1. `test_todos_los_contratos_validos` — `validate_contract` vacía para las ~65.
2. `test_contrato_a_medias_se_rechaza` — construir contratos rotos (sin
   descripción con `llm_visible`, `required` fuera de `properties`, `risk` no
   enum, `DELETE` sin `needs_confirmation`, argmap a clave inexistente) → cada
   uno produce ≥ 1 problema.
3. `test_alta_toca_un_solo_archivo` — añadir un `ToolContract` de prueba a una
   lista copia y pasar por `read_tools()/write_tools()/agent_contracts()`
   derivadas de esa copia: aparece en las 3 vistas **sin tocar más código**.
   (Demuestra el criterio de aceptación 1 del plan.)
4. `test_paridad_con_dicts_viejos` — para cada clave de los `_READ_TOOLS`/
   `_WRITE_TOOLS`/`_PLAN_TOOLS` **de git HEAD~** (lista fijada en el test):
   `catalog.by_name(clave)` no es None y cae en la misma partición.
5. `test_paridad_registry` — `{t.name for t in registry.TOOLS}` == set de los 46
   nombres español de HEAD~; cada `schema()` idéntico al anterior (fixture).
6. `test_informe_camino_lento` — `catalog.slow_path_only()` == `{"recordar"}`
   (o la lista real que salga; se fija explícita para que un cambio la delate).
7. `test_needs_confirmation_coherente` — todo contrato `DELETE`/`CRITICAL`
   destructivo tiene `needs_confirmation` y devuelve `ActionPlan` pendiente
   (mock del ejecutor).

## Protocolo de pruebas (del PLAN_MAESTRO, entero, hasta verde)

1. `ruff check .` → limpio.
2. `pytest test/test_catalog.py -q` → verde.
3. `QT_QPA_PLATFORM=offscreen pytest test -q` → **0 FAILED/ERROR** (772 tests).
   Vigilar `test_agent.py`, `test_router.py`, `test_jarvis.py`,
   `test_parser_coverage.py`, `test_banco_seguridad.py`.
4. Cobertura de `catalog.py` ≥ 90 %.
5. e2e con Ollama vivo: `Jarvis.chat("abre la calculadora")` → `open_app`;
   `Jarvis.chat("pon bohemian rhapsody")` → `spotify_play`;
   `Jarvis.chat("borra el archivo notas.txt de documentos")` → plan + `/confirmar`;
   una frase que va al agente (`"cuéntame un chiste"`) → `contar_chiste`.
6. `python -m scripts.banco_pruebas` → comparar contra
   `BANCO_PRUEBAS_BASELINE.md`: **sin retrocesos** (grupo A ≥ 19/20, E igual o
   mejor). El catálogo no debe cambiar el enrutado — sólo unifica la definición.
7. Seguridad: `test_banco_seguridad.py` intacto; `run_command` destructivo sigue
   BLOQUEADO por el mismo guardia.
9. CI verde en la rama.

## Riesgo y plan de reversión

Si la suite completa o el banco muestran regresión de enrutado que no se corrige
en la misma sesión: `git checkout main` y descartar la rama entera (el ROADMAP
§4 FASE 1 lo autoriza explícitamente). Re-planificar en 3 pasos separados:
(a) sólo el `ToolContract` + validador + tests, sin tocar rutas; (b) derivar
`registry.TOOLS`; (c) derivar los dicts de `jarvis.py`.

## Al cerrar

Commit en la rama, **sin push** (lo sube el usuario). Marcar FASE B `✅` en
`docs/PLAN_EJECUCION.md` con resumen de 10 líneas. STOP (no encadenar FASE C).
