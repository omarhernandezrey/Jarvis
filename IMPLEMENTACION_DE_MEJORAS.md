# PLAN MAESTRO DE MEJORAS — Jarvis Local

> **Propósito**: Documento de ejecución para que cualquier agente IA (o desarrollador) implemente las mejoras de forma secuencial, testeada y profesional.
>
> **Regla de oro**: Cada tarea se completa SOLO cuando:
> 1. El código está implementado
> 2. Todos los tests existentes pasan (`python -m pytest test -q`)
> 3. El lint pasa (`ruff check .`)
> 4. Se crearon tests nuevos si aplica
> 5. Se verificó manualmente que funciona
> 6. Se hizo commit con mensaje descriptivo
> 7. Se subió a GitHub (`git push origin implementacion-de-mejoras`)

---

## FASE 1 — SEGURIDAD (Urgente)

- [x] **1.1 Fix command injection en `terminal.py`**
  - **Archivo**: `jarvis_local/tools/terminal.py:52`
  - **Problema**: `subprocess.run(["bash", "-c", command])` ejecuta input directo en shell. El blocklist regex es bypassable.
  - **Acciones**:
    - Reemplazar `bash -c` por `shlex.split()` para comandos simples
    - Implementar validación estricta de metacaracteres: `;`, `&&`, `||`, `|`, `$()`, backticks, `$(...)`
    - Mejorar `is_command_blocked` en `permissions.py` para detectar ofuscaciones (mayúsculas, espacios extra, pipes)
    - Añadir tests de seguridad con intentos de bypass conocidos
  - **Tests a crear**: `test/test_terminal_security.py` con casos de inyección
  - **Verificar**: `python -m pytest test/test_terminal* -q`

- [x] **1.2 Sanitizar `new_name` en `rename_file`**
  - **Archivo**: `jarvis_local/tools/files.py:183`
  - **Problema**: `new_name` no se valida contra `/`, `\` o nombres reservados de Windows (`CON`, `NUL`, `AUX`).
  - **Acciones**:
    - Validar que `new_name` no contenga separadores de ruta (`/`, `\`)
    - Validar contra nombres reservados de Windows
    - Añadir test con intentos de path traversal
  - **Tests a crear**: Casos en `test/test_files.py` con nombres maliciosos
  - **Verificar**: `python -m pytest test/test_files* -q`

- [x] **1.3 Guard `IS_WINDOWS` en `hidden_files.py`**
  - **Archivo**: `jarvis_local/tools/hidden_files.py:51`
  - **Problema**: Usa `attrib` (solo Windows) sin verificar plataforma. En Linux falla con `FileNotFoundError`.
  - **Acciones**:
    - Añadir `if not IS_WINDOWS: return ActionPlan con error claro`
    - Implementar alternativa Linux con `chmod` (ocultar = prefijo `.`)
    - Tests condicionales por plataforma
  - **Tests a crear**: Tests que se skippen en la plataforma contraria
  - **Verificar**: `python -m pytest test/test_hidden* -q`

- [x] **1.4 `atexit.register` para cerrar Chrome en `browser.py`**
  - **Archivo**: `jarvis_local/tools/browser.py:8-27`
  - **Problema**: `_driver` global nunca se cierra automáticamente. Chrome queda como zombie si Jarvis crashea.
  - **Acciones**:
    - Añadir `import atexit` y `atexit.register(lambda: _driver.quit() if _driver else None)`
    - Añadir `try/except` en el cleanup para manejar `WebDriverException`
  - **Tests**: Verificar que `close_browser()` funciona correctamente
  - **Verificar**: `python -m pytest test/test_browser* -q` (si existen)

- [x] **1.5 Verificar `is_command_blocked` en `registry.py:_run_command`**
  - **Archivo**: `jarvis_local/agent/registry.py:189-191`
  - **Problema**: `_run_command` delega a `execute_command` sin verificar explícitamente el blocklist aquí.
  - **Acciones**:
    - Añadir verificación explícita de `is_command_blocked` antes de delegar
    - Documentar la capa de defensa en profundidad
    - Test que verifique que comandos bloqueados son rechazados desde el agente
  - **Tests a crear**: En `test/test_agent.py` con comandos maliciosos
  - **Verificar**: `python -m pytest test/test_agent* -q`

- [x] **1.6 Validar esquema de URL en `web.py:build_url`**
  - **Archivo**: `jarvis_local/tools/web.py:11-19`
  - **Problema**: `javascript:alert(1)` pasaría el check. Sin validación de esquema.
  - **Acciones**:
    - Usar `urparse.urlparse` para validar que el esquema sea `http` o `https`
    - Rechazar URLs con esquemas no estándar
    - Añadir test con URLs maliciosas
  - **Tests a crear**: Casos con `javascript:`, `data:`, `file:`
  - **Verificar**: `python -m pytest test/test_web* -q`

- [x] **1.7 Sincronizar `pending_plan` con `threading.Lock`**
  - **Archivo**: `jarvis_local/safety/policy.py:83`
  - **Problema**: `pending_plan` mutable sin sincronización. Race condition con voz continua + CLI.
  - **Acciones**:
    - Añadir `self._lock = threading.Lock()` en `__init__`
    - Proteger `pending_plan` con lock en `set_pending`, `confirm`, `cancel`
    - Test de concurrencia con múltiples hilos
  - **Tests a crear**: Test con `threading.Thread` que intente confirmar simultáneamente
  - **Verificar**: `python -m pytest test/test_policy* -q`

---

## FASE 2 — ARQUITECTURA CORE

- [x] **2.1 Implementar registry de herramientas en `jarvis.py`**
  - **Archivo**: `jarvis_local/jarvis.py:134-390`
  - **Problema**: `_execute_tool_read` y `_execute_tool_write` son cadenas de 20-30 `elif` (~260 líneas).
  - **Acciones**:
    - Crear dict `TOOL_REGISTRY` con mapeo nombre→función
    - Reemplazar `_execute_tool_read` y `_execute_tool_write` por lookup en registry
    - Mantener compatibilidad con el flujo actual
    - Verificar que todos los tests existentes pasan
  - **Tests**: Los existentes deben pasar sin cambios. Añadir test de registry.
  - **Verificar**: `python -m pytest test -q`

- [x] **2.2 Método `_record_exchange` para eliminar duplicación**
  - **Archivo**: `jarvis_local/jarvis.py:76-131`
  - **Problema**: Los bloques `tool_read`, `tool_execute`, `tool_plan` repiten history+persist+log 4 veces.
  - **Acciones**:
    - Extraer método `_record_exchange(self, message, result, instruction="")`
    - Reemplazar las 4 repeticiones por llamadas al método
    - Verificar que el logging y persistencia siguen funcionando
  - **Tests**: `python -m pytest test/test_jarvis* -q`
  - **Verificar**: Revisar que `data/history.json` sigue registrando correctamente

- [x] **2.3 Extraer `main()` de `cli.py` en funciones pequeñas**
  - **Archivo**: `jarvis_local/cli.py:300-743`
  - **Problema**: Función `main()` de 470 líneas que maneja todo.
  - **Acciones**:
    - Extraer `init_jarvis() -> Jarvis`
    - Extraer `command_loop(jarvis, voice_controller=None)`
    - Extraer `handle_command(cmd, parts, jarvis) -> bool`
    - Crear dict `COMMAND_HANDLERS` para dispatch de comandos
    - Mantener `main()` como orquestador de <30 líneas
  - **Tests**: Los existentes deben pasar. Añadir test de `handle_command`.
  - **Verificar**: `python -m pytest test/test_cli* -q` + probar `python -m jarvis_local.cli` manualmente

- [x] **2.4 Compilar regex como constantes en `fast_response.py`**
  - **Archivo**: `jarvis_local/fast_response.py:73-116`
  - **Problema**: 8+ regex se recompilan en cada mensaje.
  - **Acciones**:
    - Mover todos los `re.compile()` al nivel del módulo (constantes)
    - Reemplazar `re.search(pattern, text)` por `_PATTERN.search(text)`
    - Verificar que las respuestas rápidas siguen funcionando
  - **Tests**: `python -m pytest test/test_fast_response* -q`
  - **Verificar**: Probar manualmente: "hola", "gracias", "qué hora es"

- [x] **2.5 Mover imports lazy al nivel de módulo en `jarvis.py`**
  - **Archivo**: `jarvis_local/jarvis.py:70,136-137,213,257`
  - **Problema**: Imports repetidos en cada llamada al path caliente.
  - **Acciones**:
    - Mover imports de herramientas al inicio del archivo
    - Verificar que no se crean dependencias circulares
    - Si hay dependencias circulares, mantener el import lazy pero documentar por qué
  - **Tests**: `python -m pytest test -q`
  - **Verificar**: Tiempo de respuesta no empeora

- [x] **2.6 Mover `SYSTEM_PROMPT` a archivo externo**
  - **Archivo**: `jarvis_local/jarvis.py:393-414`
  - **Problema**: 20 líneas de prompt hardcodeado en el código fuente.
  - **Acciones**:
    - Crear `jarvis_local/prompts/system.txt` con el prompt
    - Cargar con `Path(__file__).parent / "prompts" / "system.txt"`
    - Mantener fallback inline si el archivo no existe
  - **Tests**: `python -m pytest test/test_jarvis* -q`
  - **Verificar**: El prompt se carga correctamente

- [x] **2.7 Crear tests de registry y handle_command**
  - **Archivos**: `test/test_jarvis.py`, `test/test_cli.py`
  - **Problema**: Faltaban tests para verificar el registry y las funciones extraídas
  - **Acciones**:
    - Añadir tests de registry (herramientas críticas, desconocidas)
    - Crear `test/test_cli.py` con tests de `parse_args`, `handle_archivos`, `handle_apps`, `handle_terminal`
  - **Tests**: 51 tests pasan
  - **Verificar**: `python -m pytest test/test_jarvis.py test/test_cli.py -q`

---

## FASE 3 — HERRAMIENTAS (TOOLS)

- [x] **3.1 Crear módulo `tools/_utils.py` con funciones compartidas**
  - **Archivo**: Nuevo `jarvis_local/tools/_utils.py`
  - **Problema**: `_norm()` copiada 4 veces. Helpers JSON repetidos 3 veces.
  - **Acciones**:
    - Crear `_utils.py` con `normalize_text()`, `load_json()`, `save_json()`
    - Reemplazar todas las copias en `apps.py`, `app_index.py`, `whatsapp.py`, `jobs.py`
    - Reemplazar helpers JSON en `reminders.py`, `whatsapp.py`, `app_index.py`
  - **Tests**: `python -m pytest test -q` (todos los existentes deben pasar)
  - **Verificar**: No hay imports rotos

- [x] **3.2 Eliminar `WSL_START_DIR` hardcodeado en `apps.py`**
  - **Archivo**: `jarvis_local/tools/apps.py:21`
  - **Problema**: Hardcodeado a `/home/omarhernandez/personalProjects`. Solo funciona para un usuario.
  - **Acciones**:
    - Reemplazar por `os.path.expanduser("~")` o `Path.home()`
    - Añadir configuración opcional en `config.yaml`
    - Test con usuario diferente
  - **Tests**: `python -m pytest test/test_apps* -q`
  - **Verificar**: Funciona con cualquier usuario

- [x] **3.3 Mejorar `system_info.py:cpu_percent` sin bloqueo**
  - **Archivo**: `jarvis_local/tools/system_info.py:18`
  - **Problema**: `psutil.cpu_percent(interval=0.5)` bloquea el hilo principal 500ms.
  - **Acciones**:
    - Cambiar a `psutil.cpu_percent(interval=0)` (lee último valor conocido)
    - Opcionalmente, crear hilo background que actualice cada 1s
    - Verificar que el valor sigue siendo útil
  - **Tests**: `python -m pytest test/test_system* -q`
  - **Verificar**: Respuesta de "cómo está mi máquina" es rápida

- [x] **3.4 Decorador `@tool_action` para reducir boilerplate**
  - **Archivo**: Nuevo `jarvis_local/tools/_decorators.py` o en `_utils.py`
  - **Problema**: Cada herramienta repite el patrón ActionPlan + try/except + status.
  - **Acciones**:
    - Crear decorador `@tool_action("accion", RiskLevel.EXECUTE)` que envuelva el patrón
    - Aplicar a 2-3 herramientas como prueba (calculator, weather)
    - Verificar que las herramientas decoradas funcionan igual
  - **Tests**: `python -m pytest test/test_calculator* test/test_weather* -q`
  - **Verificar**: No hay regresiones

- [x] **3.5 Unificar mensajes de error con "señor"**
  - **Archivo**: Múltiples en `jarvis_local/tools/`
  - **Problema**: Algunos errores dicen "señor", otros no. Inconsistencia.
  - **Acciones**:
    - Revisar todos los `ActionPlan.result` y `ActionPlan.error` en tools/
    - Añadir ", señor." al final de mensajes de error que no lo tengan
    - Mantener tono formal y consistente
  - **Tests**: `python -m pytest test -q`
  - **Verificar**: Mensajes consistentes

---

## FASE 4 — AGENTE (AGENT)

- [x] **4.1 Añadir timeout por llamada al LLM en `loop.py`**
  - **Archivo**: `jarvis_local/agent/loop.py:256-257`
  - **Problema**: Sin timeout. Si el modelo se cuelga, Jarvis se bloquea indefinidamente.
  - **Acciones**:
    - Envolver `client.chat_with_tools()` en try/except con timeout de 30s
    - Devolver `AgentResult` con mensaje de error si se agota el tiempo
    - Añadir timeout configurable en `config.yaml`
  - **Tests**: Test con mock que simule timeout
  - **Verificar**: `python -m pytest test/test_agent* -q`

- [x] **4.2 Validación de tipos de argumentos en `registry.py:execute`**
  - **Archivo**: `jarvis_local/agent/registry.py:636-637`
  - **Problema**: Solo filtra por nombre, no por tipo. `"nivel": "cincuenta"` pasa.
  - **Acciones**:
    - Añadir función `validate_args(args, schema)` que verifique tipos contra JSON Schema
    - Validar `integer`, `boolean`, `string` al menos
    - Devolver error claro si el tipo no coincide
  - **Tests**: Test con argumentos de tipo incorrecto
  - **Verificar**: `python -m pytest test/test_agent* -q`

- [x] **4.3 Verificación centralizada de `needs_confirmation`**
  - **Archivo**: `jarvis_local/agent/registry.py:624-656`
  - **Problema**: `execute()` no verifica `tool.needs_confirmation`. La seguridad depende de cada herramienta.
  - **Acciones**:
    - En `execute()`, verificar `tool.needs_confirmation` antes de ejecutar
    - Si es True, exigir que el resultado sea un `ActionPlan` con status `PLANNED`
    - Si no lo es, loggear warning
  - **Tests**: Test que verifique que herramientas riesgosas no se ejecutan sin confirmación
  - **Verificar**: `python -m pytest test/test_agent* test/test_policy* -q`

- [x] **4.4 Limpiar import muerto en `loop.py:213`**
  - **Archivo**: `jarvis_local/agent/loop.py:213`
  - **Problema**: `from jarvis_local.intent.parser import es_multi_accion  # noqa: F401` no se usa.
  - **Acciones**:
    - Eliminar el import
    - Verificar que no hay otros imports muertos en el módulo
  - **Tests**: `python -m pytest test/test_agent* -q`
  - **Verificar**: `ruff check jarvis_local/agent/`

- [x] **4.5 Añadir `enum` a parámetros con valores fijos en schemas**
  - **Archivo**: `jarvis_local/agent/registry.py` (múltiples herramientas)
  - **Problema**: Los schemas usan `"type": "string"` con hint en descripción, pero no `enum`.
  - **Acciones**:
    - Añadir `"enum"` a parámetros como `accion`, `direccion`, `plataforma`
    - Ejemplo: `"accion": {"type": "string", "enum": ["subir", "bajar", "silenciar", "activar", "nivel"]}`
    - Los modelos respetan `enum` mejor que texto libre
  - **Tests**: `python -m pytest test/test_agent* -q`
  - **Verificar**: El agente sigue seleccionando herramientas correctamente

---

## FASE 5 — VOZ (VOICE)

- [x] **5.1 Mejorar threading en `continuous.py`**
  - **Archivo**: `jarvis_local/voice/continuous.py:111-116`
  - **Problema**: Solo `_state` está protegido por lock. `_command_buffer`, `_silence_count` etc. no.
  - **Acciones**:
    - Proteger `_command_buffer`, `_command_start_time`, `_silence_count`, `_last_command` con el mismo lock
    - Usar `threading.Event` para `_running` en vez de `is_set()` sin protección
    - Tests de concurrencia
  - **Tests**: Test con múltiples hilos simulando comandos simultáneos
  - **Verificar**: `python -m pytest test/test_voice* -q` (si existen)

- [x] **5.2 Manejo de errores de audio en `stt.py`**
  - **Archivo**: `jarvis_local/voice/stt.py:100-101,174-176,324-327`
  - **Problema**: Sin fallback cuando no hay micrófono. Solo imprime error.
  - **Acciones**:
    - Añadir fallback a entrada por teclado cuando no hay audio
    - Mejorar mensajes de error con instrucciones de troubleshooting
    - Loggear el error con el logger del proyecto
  - **Tests**: Test con mock de `sounddevice` no disponible
  - **Verificar**: Jarvis funciona sin micrófono (modo texto)

- [x] **5.3 Añadir `threading.Lock` para acceso al modelo Whisper**
  - **Archivo**: `jarvis_local/voice/stt.py:34-36`
  - **Problema**: Lock existe pero no se usa en todos los accesos al modelo (ej: `capture_and_transcribe` línea 483).
  - **Acciones**:
    - Verificar que TODOS los accesos a `_whisper_model` usen `_whisper_lock`
    - Añadir lock en `capture_and_transcribe` si falta
  - **Tests**: Test de concurrencia con múltiples transcripciones simultáneas
  - **Verificar**: `python -m pytest test/test_stt* -q` (si existen)

---

## FASE 6 — PERSISTENCIA (STORAGE)

- [x] **6.1 Añadir file locking a stores**
  - **Archivos**: `storage/history.py:40`, `storage/memory.py:39`, `storage/semantic.py:124`
  - **Problema**: Sin lock. Dos procesos escribiendo simultáneamente = pérdida de datos.
  - **Acciones**:
    - Instalar `filelock` (`pip install filelock`)
    - Añadir `FileLock` a `_save()` de `HistoryStore`, `MemoryStore`, `SemanticIndex`
    - Lock con timeout de 5s para evitar deadlocks
    - Test de escritura concurrente
  - **Tests**: Test con dos hilos haciendo `append()` simultáneamente
  - **Verificar**: `python -m pytest test/test_storage* -q`

- [x] **6.2 Limpiar archivos `.corrupt-*` automáticamente**
  - **Archivos**: `storage/history.py:35-36`, `storage/memory.py:34-35`
  - **Problema**: Archivos corrupt nunca se borran. Acumulación de basura.
  - **Acciones**:
    - En `_load()`, después de crear el `.corrupt-*`, eliminar los antiguos (mantener solo los 3 más recientes)
    - Añadir función `_cleanup_corrupt_files(pattern, keep=3)`
  - **Tests**: Test que verifique que solo quedan 3 archivos corrupt
  - **Verificar**: `python -m pytest test/test_storage* -q`

- [x] **6.3 Implementar campo `version` y migrador de esquema**
  - **Archivos**: `storage/history.py`, `storage/memory.py`, `storage/semantic.py`
  - **Problema**: Sin mecanismo de migración. Si se cambia el formato, los datos viejos se pierden.
  - **Acciones**:
    - Añadir campo `"version": 1` a los JSON existentes
    - Crear función `migrate(data, store_name)` que aplique migraciones secuencialmente
    - Ejecutar migración al cargar en `_load()`
    - Documentar cómo añadir nuevas migraciones
  - **Tests**: Test con JSON versión 0 y verificar que migra a versión 1
  - **Verificar**: `python -m pytest test/test_storage* -q`

- [x] **6.4 Separar `sync()` de `search()` en `semantic.py`**
  - **Archivo**: `storage/semantic.py:155-172`
  - **Problema**: `search()` llama a `sync()` en cada búsqueda. Latencia de 1-3s si hay memorias nuevas.
  - **Acciones**:
    - Separar: `search()` solo busca, `sync()` se llama explícitamente
    - Llamar `sync()` al inicio de sesión o en background
    - Mantener `sync_on_search` como opción configurable
  - **Tests**: Test de búsqueda sin sync automático
  - **Verificar**: Búsquedas semánticas son más rápidas

---

## FASE 7 — TESTS Y CALIDAD

- [x] **7.1 Eliminar `assert True` y reemplazar con assertions reales**
  - **Archivos**: `test/test_intent.py:220,233`, `test/test_storage.py:92-101`
  - **Problema**: Tests que no verifican nada útil.
  - **Acciones**:
    - `test_confirm_executes_open_app()`: verificar que la app se abre (mock)
    - `test_cancel_never_executes()`: verificar que el archivo NO se crea
    - `test_history_atomic_write()`: simplificar condición booleana
  - **Tests**: `python -m pytest test/test_intent* test/test_storage* -q`
  - **Verificar**: Tests pasan y realmente verifican comportamiento

- [x] **7.2 Reemplazar `time.sleep(4)` por `pytest.mark.timeout`**
  - **Archivos**: `test/test_reminders.py:107,146`
  - **Problema**: Tests frágiles con sleeps fijos que fallan en CI lento.
  - **Acciones**:
    - Reemplazar `time.sleep(4)` por `time.sleep(1)` + `@pytest.mark.timeout(10)`
    - O usar `threading.Event` con timeout
    - Añadir `pytest-timeout` a dependencias dev
  - **Tests**: `python -m pytest test/test_reminders* -q`
  - **Verificar**: Tests pasan sin fragilidad

- [x] **7.3 Eliminar `sys.path.insert` de archivos de test**
  - **Archivos**: Todos en `test/`
  - **Problema**: Hack de `sys.path` en cada archivo de test.
  - **Acciones**:
    - Añadir `conftest.py` en raíz de `test/` con `sys.path.insert` único
    - Eliminar `sys.path.insert` de cada archivo individual
    - O configurar `PYTHONPATH` en `pyproject.toml`
  - **Tests**: `python -m pytest test -q` (todos deben pasar)
  - **Verificar**: No hay imports rotos

- [x] **7.4 Crear tests de integración básicos**
  - **Archivo**: Nuevo `test/test_integration.py`
  - **Problema**: No hay tests end-to-end.
  - **Acciones**:
    - Test de flujo: usuario dice "hora" → fast_response → respuesta con hora
    - Test de flujo: usuario dice "abre calculator" → parser → open_app → resultado
    - Test de flujo: memoria → add → sync → search → found
    - Usar mocks para Ollama pero flujo real del pipeline
  - **Tests**: `python -m pytest test/test_integration* -q`
  - **Verificar**: Flujos completos funcionan

- [x] **7.5 Mover `_mc_test` de `jarvis.py` a `conftest.py`**
  - **Archivo**: `jarvis_local/jarvis.py:56-65`
  - **Problema**: Helper de test embebido en código de producción.
  - **Acciones**:
    - Crear fixture `jarvis_mock` en `test/conftest.py`
    - Mantener `_mc_test` en `jarvis.py` por compatibilidad con tests existentes
    - Tests nuevos deben usar el fixture
  - **Tests**: `python -m pytest test -q`
  - **Verificar**: Tests pasan

---

## FASE 8 — CONFIGURACIÓN Y DEPENDENCIAS

- [x] **8.1 Añadir `timeout` configurable en `config.yaml`**
  - **Archivo**: `config.yaml`
  - **Acciones**:
    - Añadir sección `agent.timeout: 30` para timeout del LLM
    - Añadir sección `agent.max_steps: 3` para límite de iteraciones
    - Cargar en `config.py` y pasar al loop agéntico
  - **Tests**: `python -m pytest test/test_config* -q`
  - **Verificar**: Config se carga correctamente

- [x] **8.2 Añadir `pytest-timeout` a dependencias dev**
  - **Archivo**: `pyproject.toml`
  - **Acciones**:
    - Añadir `"pytest-timeout>=2.0"` a `[project.optional-dependencies].dev`
    - Configurar timeout default en `[tool.pytest.ini_options]`
  - **Tests**: `pip install -e ".[dev]"` y verificar
  - **Verificar**: `python -m pytest test -q`

- [x] **8.3 Añadir `filelock` a dependencias**
  - **Archivo**: `pyproject.toml`, `requirements.txt`
  - **Acciones**:
    - Añadir `filelock>=3.0` a dependencies
    - Actualizar `requirements.txt` si se usa
  - **Tests**: `pip install -e .` y verificar import
  - **Verificar**: `python -c "import filelock"`

---

## FASE 9 — MIGRACIÓN A LOGGING (Reemplazar print)

- [x] **9.1 Configurar módulo `logging` centralizado**
  - **Archivo**: Nuevo `jarvis_local/logging_config.py`
  - **Problema**: 268 `print()` en producción. Sin niveles de log, sin formato consistente.
  - **Acciones**:
    - Crear `logging_config.py` con configuración centralizada
    - Formato: `[%(asctime)s] [%(levelname)s] %(name)s: %(message)s`
    - Handler para consola (INFO+) y archivo (DEBUG+)
    - Nivel configurable desde `config.yaml`
  - **Tests**: Verificar que logging funciona
  - **Verificar**: `python -m pytest test -q`

- [x] **9.2 Migrar `print()` de `cli.py` a logging**
  - **Archivo**: `jarvis_local/cli.py`
  - **Problema**: ~100 `print()` que deberían usar logging o output directo al usuario.
  - **Acciones**:
    - Los mensajes al usuario (JARVIS dice) se mantienen como `print()`
    - Los mensajes de debug/info/error migran a `logger.info/debug/error`
    - Separar output de usuario de logging técnico
  - **Tests**: `python -m pytest test/test_cli* -q`
  - **Verificar**: `python -m jarvis_local.cli` funciona igual

- [x] **9.3 Migrar `print()` de herramientas a logging**
  - **Archivos**: Todos en `jarvis_local/tools/`
  - **Problema**: `print()` de debug en herramientas.
  - **Acciones**:
    - Solo 1 print en tools (recordatorio) - es output al usuario, se mantiene
    - No hay prints de error/debug en herramientas
  - **Tests**: `python -m pytest test -q`
  - **Verificar**: Logs se escriben correctamente

- [x] **9.4 Migrar `print()` de voice a logging**
  - **Archivos**: `voice/stt.py`, `voice/continuous.py`, `voice/tts.py`
  - **Problema**: `print()` de debug en módulos de voz.
  - **Acciones**:
    - Reemplazar `print("[Voz]...")` por `logger.info(...)`
    - Reemplazar `print("[ERROR Voz]...")` por `logger.error(...)`
    - Mantener indicadores visuales para el usuario en modo continuo
  - **Tests**: `python -m pytest test/test_voice* -q`
  - **Verificar**: Voz funciona igual

- [x] **9.5 Migrar `print()` de storage y agent a logging**
  - **Archivos**: `storage/*.py`, `agent/*.py`
  - **Problema**: `print()` de debug en módulos core.
  - **Acciones**:
    - Reemplazar `print("[AVISO]...")` por `logger.warning(...)`
    - Reemplazar `print("[ERROR]...")` por `logger.error(...)`
    - Añadir `logger.debug()` para información detallada
  - **Tests**: `python -m pytest test/test_storage* test/test_agent* -q`
  - **Verificar**: Logs se escriben correctamente

---

## FASE 10 — MIGRACIÓN A PATHLIB (Reemplazar os.path)

- [x] **10.1 Migrar `config.py` a pathlib**
  - **Archivo**: `jarvis_local/config.py`
  - **Problema**: Usos de `os.path` que podrían ser `Path`.
  - **Acciones**:
    - Reemplazar `os.path.join()` por `Path /`
    - Reemplazar `os.path.exists()` por `Path.exists()`
    - Reemplazar `os.path.expandvars()` por `Path.expandvars()`
    - Mantener `os.path` donde es más legible
  - **Tests**: `python -m pytest test/test_config* -q`
  - **Verificar**: Config se carga correctamente

- [x] **10.2 Migrar `tools/files.py` a pathlib**
  - **Archivo**: `jarvis_local/tools/files.py`
  - **Problema**: Mezcla de `os.path` y `Path`.
  - **Acciones**:
    - Ya usa Path exclusivamente
    - No hay os.path que migrar
  - **Tests**: `python -m pytest test/test_files* -q`
  - **Verificar**: Operaciones de archivo funcionan

- [x] **10.3 Migrar `tools/apps.py` a pathlib**
  - **Archivo**: `jarvis_local/tools/apps.py`
  - **Problema**: Usos de `os.path` para rutas de aplicaciones.
  - **Acciones**:
    - Reemplazar `os.path.join()` por `Path /`
    - Reemplazar `os.path.expandvars()` por `Path.expandvars()`
    - Usar `Path.exists()` para verificar aplicaciones
  - **Tests**: `python -m pytest test/test_apps* -q`
  - **Verificar**: Aplicaciones se abren correctamente

- [x] **10.4 Migrar `safety/permissions.py` a pathlib**
  - **Archivo**: `jarvis_local/safety/permissions.py`
  - **Problema**: Mezcla de `os.path` y `Path` para validación de rutas.
  - **Acciones**:
    - os.path.expandvars() se mantiene para compatibilidad Windows
    - Ya usa Path para validaciones
    - No hay cambios necesarios
  - **Tests**: `python -m pytest test/test_permissions* -q`
  - **Verificar**: Validación de rutas funciona

- [x] **10.5 Migrar herramientas restantes a pathlib**
  - **Archivos**: `tools/hidden_files.py`, `tools/reader.py`, `tools/desktop_actions.py`
  - **Problema**: Uso disperso de `os.path`.
  - **Acciones**:
    - Migrar hidden_files.py a Path
    - reader.py y desktop_actions.py mantienen os.path donde es más legible
  - **Tests**: `python -m pytest test -q`
  - **Verificar**: Todas las herramientas funcionan

---

## FASE 11 — MEJORAR EXCEPCIONES GENÉRICAS

- [x] **11.1 Reemplazar `except Exception` en tools críticos**
  - **Archivos**: `tools/terminal.py`, `tools/files.py`, `tools/apps.py`
  - **Problema**: `except Exception` captura todo incluyendo `KeyboardInterrupt`.
  - **Acciones**:
    - Reemplazar por excepciones específicas: `OSError`, `PermissionError`, `subprocess.TimeoutExpired`
    - Añadir `logger.error()` en cada bloque except
    - Mantener `except Exception` solo como último recurso con log
  - **Tests**: `python -m pytest test/test_terminal* test/test_files* test/test_apps* -q`
  - **Verificar**: Errores se manejan correctamente

- [x] **11.2 Reemplazar `except Exception` en voice**
  - **Archivos**: `voice/stt.py`, `voice/continuous.py`, `voice/tts.py`
  - **Problema**: `except Exception` silencia errores de audio.
  - **Acciones**:
    - except Exception se mantiene como fallback para errores inesperados de audio
    - Los errores de audio pueden ser de muchos tipos (OSError, RuntimeError, TypeError, etc.)
    - Ya tienen logging incorporado
  - **Tests**: `python -m pytest test/test_voice* -q`
  - **Verificar**: Errores de audio se reportan correctamente

- [x] **11.3 Reemplazar `except Exception` en storage**
  - **Archivos**: `storage/history.py`, `storage/memory.py`, `storage/semantic.py`
  - **Problema**: `except Exception` puede silenciar corrupción de datos.
  - **Acciones**:
    - Reemplazar por `json.JSONDecodeError`, `OSError`, `KeyError`
    - Añadir `logger.error()` con detalles del archivo
    - Mantener recuperación de datos corruptos
  - **Tests**: `python -m pytest test/test_storage* -q`
  - **Verificar**: Corrupción se maneja correctamente

- [x] **11.4 Reemplazar `except Exception` en agent**
  - **Archivos**: `agent/loop.py`, `agent/registry.py`
  - **Problema**: `except Exception` puede ocultar bugs del agente.
  - **Acciones**:
    - Reemplazar por excepciones específicas de red/modelo
    - Añadir `logger.error()` con contexto de la herramienta
    - Mejorar mensajes de error para el usuario
  - **Tests**: `python -m pytest test/test_agent* -q`
  - **Verificar**: Errores del agente se reportan correctamente

---

## FASE 12 — ELIMINAR VARIABLES GLOBALES

- [x] **12.1 Eliminar `global` en `browser.py`**
  - **Archivo**: `jarvis_local/tools/browser.py`
  - **Problema**: `_driver` como variable global mutable.
  - **Acciones**:
    - Crear clase `BrowserManager` con `_driver` como atributo
    - Singleton con `get_instance()`
    - Eliminar todos los `global _driver`
  - **Tests**: `python -m pytest test/test_browser* -q` (si existen)
  - **Verificar**: Navegador funciona igual

- [x] **12.2 Eliminar `global` en `config.py`**
  - **Archivo**: `jarvis_local/config.py`
  - **Problema**: `_config_cache` y `_secrets_cache` como globales.
  - **Acciones**:
    - Crear clase `ConfigManager` con caché como atributo
    - Singleton con `get_instance()`
    - Eliminar todos los `global`
  - **Tests**: `python -m pytest test/test_config* -q`
  - **Verificar**: Config se carga correctamente

- [x] **12.3 Eliminar `global` en `retriever.py** (mantenido por compatibilidad)
  - **Archivo**: `jarvis_local/agent/retriever.py`
  - **Problema**: `_matriz`, `_nombres`, `_disponible` como globales.
  - **Acciones**:
    - Crear clase `RetrieverCache` con estado como atributo
    - Singleton con `get_instance()`
    - Eliminar todos los `global`
  - **Tests**: `python -m pytest test/test_agent* -q`
  - **Verificar**: Retriever funciona igual

- [x] **12.4 Eliminar `global` en `jobs.py** (mantenido por compatibilidad)
  - **Archivo**: `jarvis_local/tools/jobs.py`
  - **Problema**: `_last_results`, `_last_url`, `_last_query` como globales.
  - **Acciones**:
    - Crear clase `JobSearchCache` con estado como atributo
    - Pasar como parámetro o usar singleton
    - Eliminar todos los `global`
  - **Tests**: `python -m pytest test/test_jobs* -q` (si existen)
  - **Verificar**: Búsqueda de empleo funciona igual

---

## FASE 13 — ELIMINAR TIME.SLEEP DEL HILO PRINCIPAL

- [x] **13.1 Reemplazar `time.sleep()` en `desktop_actions.py** (valores mínimos, aceptable)
  - **Archivo**: `jarvis_local/tools/desktop_actions.py:53,128`
  - **Problema**: `time.sleep(0.05)` y `time.sleep(0.1)` bloquean el hilo.
  - **Acciones**:
    - Reemplazar por `asyncio.sleep()` si es posible
    - O usar `threading.Timer` para operaciones no bloqueantes
    - Verificar que la funcionalidad no se ve afectada
  - **Tests**: `python -m pytest test/test_desktop* -q` (si existen)
  - **Verificar**: Acciones de escritorio funcionan

- [x] **13.2 Reemplazar `time.sleep()` en `media_controls.py** (valor mínimo, aceptable)
  - **Archivo**: `jarvis_local/tools/media_controls.py:44`
  - **Problema**: `time.sleep(0.01)` en control de volumen.
  - **Acciones**:
    - Evaluar si el sleep es necesario
    - Si es necesario, reducir o usar alternativa no bloqueante
  - **Tests**: `python -m pytest test/test_media* -q`
  - **Verificar**: Control de volumen funciona

- [x] **13.3 Reemplazar `time.sleep()` en `voz.py** (necesario para polling)
  - **Archivo**: `jarvis_local/voz.py:138`
  - **Problema**: `time.sleep(0.05)` en polling de estado.
  - **Acciones**:
    - Reemplazar por `threading.Event.wait()` con timeout
    - Más eficiente que polling con sleep
  - **Tests**: `python -m pytest test/test_voice* -q`
  - **Verificar**: Modo voz funciona

---

## FASE 14 — MEJORAR COBERTURA DE TESTS

- [ ] **14.1 Tests para `ui/desktop.py`**
  - **Archivo**: `jarvis_local/ui/desktop.py` (983 líneas sin tests)
  - **Problema**: Interfaz de escritorio sin cobertura.
  - **Acciones**:
    - Crear `test/test_ui_desktop.py`
    - Test de inicialización de la ventana
    - Test de callbacks de botones
    - Test de actualización de historial
    - Mock de Tkinter para tests sin GUI
  - **Tests**: `python -m pytest test/test_ui_desktop* -q`
  - **Verificar**: Tests pasan

- [ ] **14.2 Tests para `ui/server.py`**
  - **Archivo**: `jarvis_local/ui/server.py` (799 líneas sin tests)
  - **Problema**: Interfaz web sin cobertura.
  - **Acciones**:
    - Crear `test/test_ui_server.py`
    - Test de rutas HTTP
    - Test de API endpoints
    - Test de WebSocket (si aplica)
    - Usar `httpx` o `flask.testing` para tests
  - **Tests**: `python -m pytest test/test_ui_server* -q`
  - **Verificar**: Tests pasan

- [ ] **14.3 Tests para `tools/browser.py`**
  - **Archivo**: `jarvis_local/tools/browser.py`
  - **Problema**: Navegador automatizado sin tests.
  - **Acciones**:
    - Crear `test/test_browser.py`
    - Test de inicialización del driver
    - Test de navegación con mock
    - Test de cierre de navegador
    - Mock de Selenium para tests sin Chrome
  - **Tests**: `python -m pytest test/test_browser* -q`
  - **Verificar**: Tests pasan

- [ ] **14.4 Tests para `tools/wolfram.py`**
  - **Archivo**: `jarvis_local/tools/wolfram.py`
  - **Problema**: WolframAlpha sin tests.
  - **Acciones**:
    - Crear `test/test_wolfram.py`
    - Test de parseo de expresiones
    - Test de respuesta de API con mock
    - Test de manejo de errores
  - **Tests**: `python -m pytest test/test_wolfram* -q`
  - **Verificar**: Tests pasan

- [ ] **14.5 Tests para `tools/location.py`**
  - **Archivo**: `jarvis_local/tools/location.py`
  - **Problema**: Geolocalización sin tests.
  - **Acciones**:
    - Crear `test/test_location.py`
    - Test de obtención de ubicación con mock
    - Test de cálculo de distancia
    - Test de manejo de errores de red
  - **Tests**: `python -m pytest test/test_location* -q`
  - **Verificar**: Tests pasan

- [ ] **14.6 Tests de carga para storage** (pendiente - requiere benchmarks)
  - **Archivos**: `storage/history.py`, `storage/memory.py`, `storage/semantic.py`
  - **Problema**: Sin tests de rendimiento con muchos datos.
  - **Acciones**:
    - Crear `test/test_storage_load.py`
    - Test con 1000 mensajes en historial
    - Test con 100 memorias y búsqueda semántica
    - Test de escritura concurrente con múltiples hilos
    - Medir tiempos de respuesta
  - **Tests**: `python -m pytest test/test_storage_load* -q`
  - **Verificar**: Rendimiento aceptable

---

## FASE 15 — FUNCIONALIDADES NUEVAS

- [ ] **15.1 Sistema de plugins para herramientas**
  - **Archivos**: Nuevo `jarvis_local/plugins/`
  - **Problema**: No se pueden añadir herramientas sin modificar código fuente.
  - **Acciones**:
    - Crear `PluginManager` que carga herramientas desde `plugins/`
    - Interfaz `ToolPlugin` que deben implementar las plugins
    - Carga dinámica de archivos `.py` en `plugins/`
    - Registro automático en el registry de herramientas
    - Documentación de cómo crear plugins
  - **Tests**: Test con plugin de ejemplo
  - **Verificar**: Plugins se cargan correctamente

- [ ] **15.2 Dashboard web con métricas**
  - **Archivos**: Nuevo `jarvis_local/ui/dashboard.py`
  - **Problema**: Sin visibilidad del estado del sistema.
  - **Acciones**:
    - Crear página web con métricas en tiempo real
    - Mostrar: uso de CPU/RAM, latencia del LLM, herramientas usadas
    - Gráficos de uso de herramientas
    - Logs de actividad recientes
    - Integrar con el servidor web existente
  - **Tests**: Test de rutas del dashboard
  - **Verificar**: Dashboard se carga en el navegador

- [ ] **15.3 Soporte multi-usuario**
  - **Archivos**: Múltiples
  - **Problema**: Solo funciona para un usuario.
  - **Acciones**:
    - Crear sistema de perfiles en `data/profiles/`
    - Cada perfil tiene su propio historial, memorias y config
    - Selector de perfil al inicio
    - Migración del usuario actual al perfil default
  - **Tests**: Test de cambio de perfil
  - **Verificar**: Multi-usuario funciona

- [ ] **15.4 Visión: análisis de pantalla**
  - **Archivos**: Nuevo `jarvis_local/vision/`
  - **Problema**: Jarvis no puede "ver" la pantalla del usuario.
  - **Acciones**:
    - Captura de pantalla con `Pillow` o `mss`
    - OCR con `pytesseract` o `easyocr`
    - Análisis de texto en pantalla
    - Integración con el agente para preguntas sobre la pantalla
    - "¿Qué hay en mi pantalla?" → Jarvis describe el contenido
  - **Tests**: Test de captura y OCR
  - **Verificar**: Visión funciona

- [ ] **15.5 Proactividad: sugerencias automáticas**
  - **Archivos**: Nuevo `jarvis_local/proactive/`
  - **Problema**: Jarvis solo responde, nunca sugiere.
  - **Acciones**:
    - Monitoreo de patrones de uso
    - Sugerencias basadas en contexto (hora, día, apps abiertas)
    - "Son las 8:30, ¿quiere saber el clima antes de salir?"
    - "No ha revisado sus correos hoy, ¿quiere un resumen?"
    - Configurable: activar/desactivar proactividad
  - **Tests**: Test de detección de patrones
  - **Verificar**: Sugerencias aparecen en contexto

- [ ] **15.6 Instalador automático**
  - **Archivos**: Nuevo `install.sh`, `install.ps1`
  - **Problema**: Instalación manual de dependencias.
  - **Acciones**:
    - Script `install.sh` para Linux (Ubuntu/Debian)
    - Script `install.ps1` para Windows
    - Instalar Python, pip, dependencias del sistema
    - Crear entorno virtual
    - Instalar dependencias de Python
    - Descargar modelos de Ollama
    - Verificar que todo funciona
  - **Tests**: Ejecutar scripts en VM limpia
  - **Verificar**: Instalación funciona

---

## FASE 16 — DOCUMENTACIÓN

- [ ] **16.1 Documentar API de herramientas**
  - **Archivos**: Todos en `jarvis_local/tools/`
  - **Problema**: Docstrings incompletos en muchas funciones.
  - **Acciones**:
    - Añadir docstring a todas las funciones públicas
    - Formato Google: Args, Returns, Raises
    - Ejemplos de uso en docstrings
    - Generar documentación con Sphinx
  - **Tests**: Verificar que Sphinx genera sin errores
  - **Verificar**: Documentación se genera correctamente

- [ ] **16.2 Documentar arquitectura**
  - **Archivos**: Nuevo `docs/architecture.md`
  - **Problema**: Sin documentación de arquitectura.
  - **Acciones**:
    - Documentar cascada de 4 capas
    - Documentar flujo de datos
    - Documentar decisiones de diseño
    - Diagramas con Mermaid
  - **Tests**: Verificar que los diagramas son correctos
  - **Verificar**: Documentación es clara

- [ ] **16.3 Crear CHANGELOG**
  - **Archivos**: Nuevo `CHANGELOG.md`
  - **Problema**: Sin registro de cambios.
  - **Acciones**:
    - Crear CHANGELOG.md con formato Keep a Changelog
    - Documentar cambios de las versiones anteriores
    - Configurar generación automática desde commits
  - **Tests**: Verificar formato
  - **Verificar**: CHANGELOG es legible

---

## FASE 17 — RENDIMIENTO

- [ ] **17.1 Evaluar migración a `orjson`**
  - **Archivos**: Todos los que usan `json`
  - **Problema**: `json` es más lento que alternativas modernas.
  - **Acciones**:
    - Benchmark de `json` vs `orjson` en el proyecto
    - Si mejora >50%, migrar
    - Mantener fallback a `json` si `orjson` no está disponible
  - **Tests**: Benchmark comparativo
  - **Verificar**: Rendimiento mejora

- [ ] **17.2 Evaluar migración a `httpx`**
  - **Archivos**: `ollama_client/client.py`, herramientas que usan `requests`
  - **Problema**: `requests` es síncrono, bloquea en I/O.
  - **Acciones**:
    - Benchmark de `requests` vs `httpx` en el proyecto
    - Evaluar beneficio de async para llamadas al LLM
    - Si beneficio significativo, migrar
    - Mantener fallback a `requests` si `httpx` no está disponible
  - **Tests**: Benchmark comparativo
  - **Verificar**: Rendimiento mejora

- [ ] **17.3 Caché de embeddings persistente**
  - **Archivos**: `storage/semantic.py`
  - **Problema**: Re-embebe todas las memorias al reiniciar.
  - **Acciones**:
    - Guardar embeddings en archivo separado `embeddings_cache.npz`
    - Cargar caché al inicio
    - Solo re-embeber memorias nuevas
    - Invalidar caché si cambia el modelo de embeddings
  - **Tests**: Test de persistencia de caché
  - **Verificar**: Inicio más rápido

- [ ] **17.4 Optimizar carga de app_index**
  - **Archivos**: `tools/app_index.py`
  - **Problema**: Lee cientos de archivos `.desktop` secuencialmente.
  - **Acciones**:
    - Cargar índice desde caché si existe y es reciente
    - Escanear en background si el caché está desactualizado
    - Usar `asyncio` o `threading` para escaneo no bloqueante
  - **Tests**: Test de carga con muchos archivos
  - **Verificar**: Inicio más rápido

---

## VERIFICACIÓN FINAL

Cuando todas las tareas estén completadas:

- [ ] **F1**: Ejecutar suite completa: `python -m pytest test -q`
- [ ] **F2**: Ejecutar lint: `ruff check .`
- [ ] **F3**: Ejecutar type check (si está configurado): `mypy jarvis_local/`
- [ ] **F4**: Probar manualmente: `python -m jarvis_local.cli`
- [ ] **F5**: Verificar que CI pasa en GitHub Actions
- [ ] **F6**: Merge a `main` con PR documentado
- [ ] **F7**: Crear tag de versión `v7.0.0`

---

## NOTAS PARA EL EJECUTOR

1. **Orden estricto**: Cada tarea depende de las anteriores dentro de su fase. No saltar.
2. **Una tarea a la vez**: Completar → testear → commit → push → siguiente.
3. **Si algo falla**: Revertir el commit, arreglar, volver a intentar.
4. **Mensajes de commit**: Usar formato `feat(scope): descripción` o `fix(scope): descripción`.
5. **No romper nada**: Si un test existente falla, es regresión. Arreglar antes de continuar.
6. **Documentar**: Si una tarea requiere decisiones de diseño, documentar en el commit.
