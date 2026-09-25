# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Spotify: blindaje total del token de autorización para que no vuelva a
  "caducar" en falso:
  - copia de seguridad del token (`data/.spotify_cache.bak`) con
    auto-restauración si el cache se borra externamente o se corrompe;
  - un 401 a mitad de operación renueva el access token con el refresh_token
    y solo pide reintentar — reautorizar únicamente si Spotify rechaza el
    refresh_token de verdad;
  - un bache de red al refrescar ya no borra la autorización ni pide
    reautorizar (mensaje de "verifique su conexión" en su lugar);
  - la causa real de cualquier fallo de token queda registrada en el log;
  - `--reauth-spotify` avisa si la autorización terminó pero el token no pudo
    guardarse en disco, y muestra un mensaje claro si el puerto 8888 está
    ocupado (antes: traceback);
  - `jarvis doctor` valida el token de verdad (refresh incluido) y distingue
    "sin red" de "token caducado";
  - `_client()` usa `_CACHE_PATH` como única fuente de la ruta del cache.
- Spotify: la reproducción y el control vuelven a funcionar de verdad:
  - `pause`/`resume`/`next`/`previous`/`volume`/`shuffle`/`repeat`/
    `add_to_queue` se mandaban SIN dispositivo, así que con la app cerrada
    fallaban con 404 — ahora van al dispositivo que está sonando (celular,
    parlante o este PC);
  - la Web API responde 204 aunque el dispositivo luego no arranque; ahora
    se comprueba que empiece a sonar de verdad y, si no, se reintenta y se
    avisa en vez de afirmar que está reproduciendo;
  - `ESPERA_APERTURA_SEGUNDOS` 15 → 25 (medido en frío: 14,8 s);
  - el 403 de `previous` ya no culpa a Premium — es el límite de Spotify
    para retroceder en los primeros segundos de la canción.

## [8.1.0] - 2026-09-22

Spotify "Pro": de buscar-y-reproducir a control completo por Web API, a
petición directa del usuario (sin fase de plan asociada).

### Added
- Control de reproducción vía Web API de Spotify (`jarvis_local/tools/spotify.py`):
  pausar/reanudar, siguiente/anterior, volumen del dispositivo Connect,
  aleatorio, repetición (canción/lista/apagado), "qué está sonando" y agregar
  a la cola. A diferencia de `controlar_musica` (MPRIS/`playerctl`), funciona
  aunque el dispositivo activo sea remoto (celular, parlante Connect).
- Playlists y descubrimiento: reproducir una playlist propia por nombre
  parcial, un álbum completo, y una "radio" por artista o canción
  (recomendaciones de Spotify si el endpoint está disponible para la cuenta,
  o el catálogo del artista/la canción buscada como respaldo honesto).
- Multi-dispositivo: listar los dispositivos Spotify Connect disponibles y
  cambiar a cuál suena la música por nombre parcial.
- Biblioteca personal: guardar la canción actual en Me Gusta, ver
  reproducido recientemente, reanudar lo último tras perder la sesión.
- 17 `ToolContract` nuevos en `jarvis_local/tools/catalog.py`, regex nuevos
  en `jarvis_local/intent/parser.py` (playlist/álbum/radio en `_parse_fase4`,
  control vía `_parse_spotify_control` nueva) y ejemplos en
  `jarvis_local/agent/retriever.py::_EJEMPLOS` para cada uno.
- 116 tests nuevos (`test/test_spotify_pro.py`, `test/test_parser_spotify.py`).

### Changed
- `SCOPES` de Spotify ampliado (`user-read-recently-played`,
  `user-library-modify`, `playlist-read-private`,
  `playlist-read-collaborative`): quien ya había autorizado la cuenta antes
  de esta versión debe correr `--reauth-spotify` de nuevo, o las funciones
  nuevas fallan con el mensaje de reautorizar.

## [8.0.0] - 2026-09-03

Plan de eficacia (`PLAN_MAESTRO.md`): auditoría funcionalidad por funcionalidad
y arreglo con test que lo blinde. Fases A–D. Base: `docs/AUDITORIA_2026-09.md`.

### Added
- `jarvis_local/doctor.py` + `python -m jarvis_local.cli doctor`: diagnóstico
  del entorno (red, Ollama y modelos, secrets, Google Calendar, Spotify,
  micrófono, navegador) con salida `OK/NO/WARN` (D1).
- Tests `live` opt-in (`-m live`, `test/test_live_integracion.py`) que pegan a
  las APIs reales (Open-Meteo, Wikipedia, Nominatim, WolframAlpha, IP, empleo)
  + job nocturno de CI que los corre (D2).
- Prueba de voz e2e (`test/test_voice_e2e.py`, marcada `live`): audio real →
  STT (faster-whisper) → router de Jarvis → herramienta correcta. Fixture
  sintético reproducible en `test/fixtures/` (D3).
- `jarvis_local/voice/stt.py::transcribe_file(path)`: transcribe un archivo de
  audio con el mismo modelo/VAD que la escucha en vivo (D3).
- Caché de decisiones del agente (`jarvis_local/agent/decision_cache.py`): una
  frase repetida no vuelve a pagar la llamada al LLM (TTL 600 s) (C6).
- Instrumentación de `run_agent`: `decisions.jsonl` registra `llm_calls` y
  `llm_secs` por turno; `scripts/bench_agente.py` (C1).
- Solver local de ecuaciones lineales de una incógnita en `calculator.py` —
  antes solo vía WolframAlpha (B3).
- `reauthorize()` + `--reauth-calendar` / `--reauth-spotify` en la CLI (B5, B6).
- Batería de cobertura del parser (`test/test_parser_coverage.py`, 114 casos) (A1).

### Changed
- Modelo de routing del agente: `llama3.2:3b` (`ollama.agent_model`), ~18 % más
  rápido en tool calling que `qwen2.5:3b` con la misma precisión en el
  subconjunto probado. El chat sigue con `qwen2.5:3b` (C5).
- `keep_alive: 30m` y `agent_num_predict: 60` para el paso de routing: evita la
  recarga del modelo entre turnos y acota la salida (C4).
- Bucle del agente podado: `MAX_STEPS 3→2`, `MAX_REINTENTOS 2→1` (C2).
- Parser-first reforzado: frases inequívocas (mute, captura de pantalla, "lanza
  <app>") se resuelven sin bajar al agente (A6, C3).
- El saludo respeta lo que dijo el usuario ("buenas noches" a las 3 pm saluda
  de noche) en vez de mirar solo el reloj (B1).
- `README.md`: latencias medidas reales tras las Fases A–C, estado real de cada
  feature, recuento de tests (772), modelo de routing y `jarvis doctor` (D4).

### Fixed
- Parser: clima en lenguaje natural ("¿va a llover en Cartagena?") ya no cae al
  agente — de ~90 s a ~1,5 s (A3).
- Parser: "pon <canción>" → Spotify directo, de ~92 s a ~0,1 s (A2).
- Parser: estado del sistema coloquial ("¿cómo anda la máquina?") de ~25–110 s
  a ~0,02 s (A7).
- Parser: "crea/nueva nota …" → `take_note` (A4); "abre youtube y pon lofi" se
  parte en dos acciones sin LLM (A5).
- Calculadora: porcentajes, raíces y funciones en lenguaje natural ("15 % de
  80", "raíz cuadrada de 144", "5 al cubo") (B2).
- `location.locate()` no falla con lugares reales (POIs, monumentos): geocodifica
  con Nominatim (OSM) y, si no hay match, abre Maps en vez de decir "no lo
  encontré" (B4).
- Google Calendar: refresca el token solo; si hace falta re-autorizar lo dice
  con el comando exacto en vez de fallar en silencio (B5).
- Spotify: token muerto → mensaje accionable (`--reauth-spotify`) en vez de un
  403 opaco (B6).
- Apps: pedir abrir una app ya abierta (o dos veces seguidas) la enfoca en vez
  de lanzar una instancia duplicada (H2, reportado en uso real).
- `find_app`: sinónimos ES/EN y nombre corto de IDE / gestor de archivos /
  navegador (B7).
- Test flaky `test_history_performance`: reconvertido a guarda de patología
  O(n²) con techos amplios (H1).

## [7.0.0] - 2026-08-08

### Added
- Sistema de logging centralizado (`jarvis_local/logging_config.py`)
- Tests de integración básicos (`test/test_integration.py`)
- Tests para browser.py, wolfram.py, location.py
- Fixture `jarvis_mock` en conftest.py
- Timeout configurable en `config.yaml`
- `filelock` para escrituras concurrentes en stores
- Versionado y migrador de esquema en storage
- Decorador `@tool_action` para reducir boilerplate
- Módulo `tools/_utils.py` con funciones compartidas
- Verificación centralizada de `needs_confirmation` en agente
- Validación de tipos de argumentos en registry
- Timeout de 30s para llamadas al LLM en agente
- `enum` en parámetros con valores fijos en schemas

### Changed
- Migrar `print()` de error a `logger.error()` en cli.py, voice, storage
- Migrar `os.path` a `pathlib` en config.py, apps.py, hidden_files.py
- Reemplazar cadenas de `elif` por registry dict en jarvis.py
- Extraer `_record_exchange()` para eliminar duplicación
- Extraer funciones de `cli.py:main()` (init_jarvis, handle_memoria, handle_voz)
- Compilar regex como constantes en fast_response.py
- Cargar SYSTEM_PROMPT desde archivo externo
- Separar `sync()` de `search()` en semantic.py
- Eliminar `global` en browser.py y config.py (BrowserManager, ConfigManager)
- Mejorar threading en continuous.py con `_buffer_lock`
- Cambiar `cpu_percent(interval=0)` para no bloquear

### Fixed
- Command injection en terminal.py
- Path traversal en rename_file
- Guard IS_WINDOWS en hidden_files.py
- atexit.register para cerrar Chrome automáticamente
- URLs maliciosas (javascript:, data:) bloqueadas en web.py
- Race condition en pending_plan con threading.Lock

### Security
- Bloqueo de metacaracteres de shell (; ` && || $())
- Validación de nombres de archivo contra reservados Windows
- Validación de esquema de URL (solo http/https)
- Verificación de is_command_blocked en registry.py

## [6.0.0] - 2026-07-15

### Added
- Soporte Linux (Ubuntu/GNOME)
- Agente con tool calling
- Memoria semántica con embeddings
- Voz por streaming
- CI en GitHub Actions

## [5.0.0] - 2026-06-01

### Added
- Selenium + búsqueda de empleo multi-portal
- Búsqueda en Computrabajo, LinkedIn, El Empleo

## [4.0.0] - 2026-05-01

### Added
- Web, clima, ubicaciones, Wikipedia, correo
- WolframAlpha, Google Calendar

## [3.0.0] - 2026-04-01

### Added
- Voz (STT/TTS), wake word
- Memorias, UI, índice dinámico de apps

## [2.0.0] - 2026-03-01

### Added
- Herramientas de archivos/apps/terminal
- Capa de seguridad

## [1.0.0] - 2026-02-01

### Added
- Chat local con Ollama
- Parser determinista
- Respuestas instantáneas
