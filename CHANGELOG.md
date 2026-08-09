# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
