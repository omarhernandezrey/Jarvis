# AGENTS.md — Instrucciones para Agentes IA

> **Este archivo es obligatorio de leer al inicio de cualquier sesión de trabajo en este proyecto.**

---

## REGLA PRINCIPAL

**ANTES de hacer cualquier cambio en el código, DEBES leer el archivo:**

```
IMPLEMENTACION_DE_MEJORAS.md
```

Este documento contiene el plan maestro de mejoras con tareas en orden específico. No lo ignores, no lo asumas, no lo resumas. **Léelo completo cada vez.**

---

## Flujo de trabajo obligatorio

1. **Leer** `IMPLEMENTACION_DE_MEJORAS.md` al inicio de la sesión
2. **Identificar** la siguiente tarea pendiente (checkbox `- [ ]`)
3. **Implementar** la tarea según las instrucciones del documento
4. **Ejecutar** tests: `python -m pytest test -q`
5. **Ejecutar** lint: `ruff check .`
6. **Verificar** que funciona manualmente si es necesario
7. **Marcar** la tarea como completada en el documento (`- [x]`)
8. **Hacer commit** con mensaje descriptivo
9. **Subir a GitHub**: `git push origin implementacion-de-mejoras`
10. **Repetir** desde el paso 1

---

## No hagas esto

- No implementes mejoras que no estén en el documento sin preguntar
- No saltes tareas aunque parezcan simples
- No marques una tarea como completada sin haberla testeado
- No hagas commit de código que rompa tests existentes
- No cambies de fase sin completar todas las tareas de la fase actual

---

## Comandos útiles

```bash
# Tests
python -m pytest test -q

# Lint
ruff check .

# Ejecutar Jarvis
python -m jarvis_local.cli

# Verificar rama actual
git branch --show-current
```

---

## Estructura del proyecto

```
jarvis_local/          # Paquete principal
├── agent/             # Tool calling, loop agéntico
├── intent/            # Parser determinista
├── tools/             # 17+ herramientas
├── safety/            # Permisos, secretos, auditoría
├── voice/             # STT, TTS, wake word
├── storage/           # Historial, memorias, índice semántico
├── memory_context/    # Recuerdo automático
├── ui/                # Interfaz web y escritorio
├── cli.py             # Punto de entrada
├── jarvis.py          # Orquestador principal
└── config.py          # Configuración
```

---

## Documentación de referencia

| Archivo | Propósito |
|---------|-----------|
| `IMPLEMENTACION_DE_MEJORAS.md` | **Plan maestro de mejoras (OBLIGATORIO)** |
| `README.md` | Documentación del proyecto |
| `config.yaml` | Configuración en runtime |
| `pyproject.toml` | Dependencias y configuración de herramientas |
