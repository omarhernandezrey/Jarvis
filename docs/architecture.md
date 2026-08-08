# Arquitectura de JARVIS Local

## Visión General

JARVIS es un asistente de IA local que ejecuta completamente en tu PC sin enviar datos a la nube.

## Cascada de 4 Capas

```
┌─────────────────────────────────────────────────────────────┐
│                    Usuario (texto/voz)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Capa 1: Respuestas Instantáneas (0s)                       │
│  - Saludos, hora, fecha, gracias                            │
│  - Sin LLM, sin latencia                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Capa 2: Parser Determinista (1.6s)                         │
│  - Frases conocidas: "abre whatsapp", "clima en Bogotá"    │
│  - Sin LLM, patrones exactos                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Capa 3: Agente Tool Calling (19s)                          │
│  - LLM decide qué herramienta usar                          │
│  - Soporta multi-paso y encadenamiento                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Capa 4: Chat con LLM (~60s)                                │
│  - Conversación general, razonamiento                       │
│  - Usa memorias como contexto                               │
└─────────────────────────────────────────────────────────────┘
```

## Componentes Principales

### `jarvis.py` — Orquestador
- Coordina las 4 capas
- Gestiona historial y memorias
- Conecta con el LLM (Ollama)

### `agent/` — Agente
- `registry.py`: Registro de 31 herramientas
- `selector.py`: Preselección por significado
- `loop.py`: Bucle de tool calling
- `retriever.py`: Recuperación semántica

### `tools/` — Herramientas
- 17+ herramientas organizadas por categoría
- Cada herramienta devuelve `ActionPlan`
- Niveles de riesgo: NONE → READ → CREATE → EXECUTE → DELETE → CRITICAL

### `safety/` — Seguridad
- `policy.py`: Gestión de planes y confirmaciones
- `permissions.py`: Whitelist de carpetas y apps
- `secrets.py`: Redacción de secretos
- `logger.py`: Auditoría de acciones

### `voice/` — Voz
- `stt.py`: Speech-to-Text (faster-whisper)
- `tts.py`: Text-to-Speech (edge-tts)
- `continuous.py`: Modo manos libres

### `storage/` — Persistencia
- `history.py`: Historial de conversaciones
- `memory.py`: Memorias explícitas
- `semantic.py`: Índice semántico con embeddings

### `memory_context/` — Memoria Contextual
- `session.py`: Memorias activas en sesión
- `recall.py`: Recuerdo automático por significado

## Flujo de Datos

```
Usuario → CLI → Jarvis.chat()
                    │
                    ├→ fast_respond() → Respuesta instantánea
                    │
                    ├→ parse_intent() → Parser determinista
                    │
                    ├→ run_agent() → Agente tool calling
                    │       │
                    │       ├→ select_tools() → Preselección
                    │       ├→ client.chat_with_tools() → LLM
                    │       └→ execute() → Ejecutar herramienta
                    │
                    └→ client.chat() → Chat general con LLM
```

## Decisiones de Diseño

1. **Local-first**: Todo corre en el PC del usuario
2. **Cascada de costos**: Lo barato se resuelve primero
3. **Seguridad en capas**: Nunca ejecutar sin confirmación
4. **Degradación graceful**: Si algo falla, el sistema sigue funcionando
5. **Extensibilidad**: Sistema de plugins para nuevas herramientas

## Stack Técnico

| Componente | Tecnología |
|------------|------------|
| LLM | Ollama + qwen2.5:3b |
| Embeddings | bge-m3 |
| STT | faster-whisper (int8) |
| TTS | edge-tts / pyttsx3 |
| Persistencia | JSON + FileLock |
| GUI | Tkinter |
| Web | HTTP Server nativo |

## Métricas de Rendimiento

| Operación | Latencia |
|-----------|----------|
| Respuesta instantánea | 0s |
| Parser determinista | 1.6s |
| Agente tool calling | 19s |
| Chat con LLM | ~60s |

*Medido en Intel i5-6200U, 16GB RAM, sin GPU*
