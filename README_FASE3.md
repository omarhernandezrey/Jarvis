# JARVIS Local - Fase 3: Voz Local Offline

## Estado: CODIGO LISTO (modelos pendientes de descarga)

---

## Paquetes instalados

| Paquete | Version | Licencia |
|---|---|---|
| faster-whisper | 1.2.1 | MIT ([SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)) |
| ctranslate2 | 4.8.1 | MIT |
| piper-tts | 1.4.2 | MIT ([rhasspy/piper-tts](https://github.com/rhasspy/piper-tts)) |
| onnxruntime | 1.27.0 | MIT |
| tokenizers | 0.23.1 | Apache 2.0 |
| huggingface-hub | 1.22.0 | Apache 2.0 |
| av | 18.0.0 | BSD |
| sounddevice | 0.5.5 (ya instalado) | MIT |
| numpy | 2.5.1 (ya instalado) | BSD |

---

## Modelos PENDIENTES de descarga (requieren confirmacion separada)

| Modelo | Tamano | Licencia | Origen |
|---|---|---|---|
| `faster-whisper-base` (STT) | ~150 MB | MIT | [huggingface.co/Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base) |
| `es_MX-ald-x_low` (voz Piper) | ~30 MB + 1.5 MB config | MIT | [huggingface.co/rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_MX/ald/x_low) |
| **Total modelos** | **~182 MB** | | |

---

## Comandos de voz

| Comando | Accion |
|---|---|
| `/voz` | Captura voz (max 8s), transcribe, envia a Ollama |
| `/voz on` | Activa lectura de respuestas con Piper |
| `/voz off` | Desactiva lectura de respuestas |
| `/voz estado` | Muestra configuracion de voz actual |

El modelo solo conversa. No invoca herramientas de Fase 2.

---

## Archivos de Fase 3

### Nuevos (5)
```
jarvis_local/
  voice/__init__.py
  voice/audio_devices.py      Deteccion de microfonos
  voice/stt.py                Captura + faster-whisper
  voice/tts.py                Piper TTS
  test/test_voice.py          10 tests con mocks
  requirements-phase3.txt
  README_FASE3.md
```

### Modificados (3)
```
  cli.py                      Comandos /voz, /voz on, /voz off, /voz estado
  config.yaml                 Seccion voice
  PLAN_JARVIS_WINDOWS.md      Fase 3 marcada
```

---

## Pruebas

```powershell
python -m jarvis_local.test.test_voice
```

10/10 tests pasan con mocks. Sin hardware real requerido.

---

## Pendiente para activacion real

1. **Descargar modelo STT** (requiere confirmacion):
   ```
   python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
   ```
   Tamano: ~150 MB. Se descarga automaticamente de HuggingFace.

2. **Descargar voz Piper** (requiere confirmacion):
   ```
   python -c "import piper_tts; piper_tts.download_voice('es_MX-ald-x_low')"
   ```
   Tamano: ~30 MB + 1.5 MB config.

---

*Fase 3 codigo listo - 8 de julio de 2026*
