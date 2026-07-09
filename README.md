# JARVIS Local

Asistente de IA local para Windows 10, offline y en espanol.

Usa **Ollama** (qwen2.5:3b), **faster-whisper** (STT) y **Piper** (TTS).

## Instalacion

```powershell
pip install -r requirements-phase3.txt
```

Instalar Ollama: https://ollama.com/download/windows

```powershell
ollama pull qwen2.5:3b
```

## Ejecucion

```powershell
python -m jarvis_local.cli
```

## Comandos

| Comando | Accion |
|---|---|
| `hola jarvis` | Saludar |
| `salir` | Salir |
| `/voz calibrar` | Calibrar microfono |
| `/voz` | Hablar por microfono |
| `/archivos listar <ruta>` | Listar archivos |
| `/apps abrir chrome` | Abrir Chrome |
| `/terminal plan <cmd>` | Preparar comando |
| `/plan` + `/confirmar` | Ejecutar plan |

## Requisitos

- Windows 10/11
- Python 3.9+
- Ollama corriendo
- Microfono (para voz)
