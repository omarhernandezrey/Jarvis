# JARVIS Local - Fase 1: Chat Local con Ollama

## Estado: COMPLETADO

Chat local conversacional en espanol usando Ollama + qwen2.5:3b.

---

## Requisitos

- Windows 10/11
- Python 3.9+ (verificado con 3.14.6)
- Ollama instalado y corriendo

---

## Instalacion

### 1. Instalar Ollama

Descarga desde: https://ollama.com/download/windows

O con winget:
```
winget install --id Ollama.Ollama
```

Ollama se instala como servicio y arranca automaticamente.

### 2. Descargar el modelo

```
ollama pull qwen2.5:3b
```

Tamano: ~1.9 GB. Tiempo: 5-15 min.

### 3. Instalar dependencias Python

```powershell
cd C:\Users\herna\Documents\open-interpreter-python
pip install -r jarvis_local\requirements-phase1.txt
```

Dependencias: `requests`, `pyyaml`.

---

## Ejecucion

```powershell
cd C:\Users\herna\Documents\open-interpreter-python
python -m jarvis_local.cli
```

### Comandos dentro del chat

| Comando | Accion |
|---|---|
| `/ayuda` | Muestra ayuda |
| `/estado` | Muestra estado de Ollama |
| `/limpiar` | Borra historial de conversacion |
| `/salir` | Salir |

---

## Pruebas

```powershell
cd C:\Users\herna\Documents\open-interpreter-python
python -m jarvis_local.test.test_config
python -m jarvis_local.test.test_secrets
python -m jarvis_local.test.test_ollama_client
```

---

## Solucion de Errores

### "Ollama no esta corriendo"

Abre Ollama desde el menu de Windows o ejecuta:
```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

### "El modelo no esta instalado"

```powershell
ollama pull qwen2.5:3b
```

### "ModuleNotFoundError: No module named 'jarvis_local'"

Ejecuta desde la carpeta `open-interpreter-python`, no desde `jarvis_local/`.

### "Connection refused" o timeout

Ollama no esta respondiendo. Verifica:
1. Ollama esta instalado y corriendo (icono en la bandeja del sistema)
2. El puerto 11434 no esta bloqueado por firewall

### Modelo muy lento

Tu CPU (i5-6200U) es modesta. El modelo 3B deberia responder en 5-15 segundos. Si es muy lento, puedes probar:
```
ollama pull qwen2.5:1.5b
```
Y cambiar `config.yaml`: `model: "qwen2.5:1.5b"`

---

## Como Desinstalar

```powershell
# Desinstalar Ollama
winget uninstall Ollama.Ollama

# Eliminar modelos descargados
Remove-Item -Recurse -Force "$env:USERPROFILE\.ollama"

# Eliminar dependencias Python (si no las necesitas para otra cosa)
pip uninstall requests pyyaml -y

# Eliminar logs de JARVIS
Remove-Item -Recurse -Force "C:\Users\herna\Documents\open-interpreter-python\jarvis_local\logs"
```

---

## Archivos de Fase 1

```
jarvis_local/
  __init__.py
  config.py              Configuracion (YAML)
  config.yaml            Valores por defecto
  jarvis.py              Orquestador de chat
  cli.py                 Interfaz de terminal
  requirements-phase1.txt
  .env.example
  
  ollama_client/
    __init__.py
    client.py            Cliente HTTP para Ollama
  
  memory/
    __init__.py
    history.py           Historial de conversacion
  
  safety/
    __init__.py
    secrets.py           Deteccion y redaccion de secretos
    logger.py            Log de acciones (JSON Lines)
  
  logs/
    actions.log          (auto-generado)
    errors.log           (auto-generado)
  
  test/
    __init__.py
    test_config.py
    test_secrets.py
    test_ollama_client.py
```

---

*Fase 1 completada - 8 de julio de 2026*
