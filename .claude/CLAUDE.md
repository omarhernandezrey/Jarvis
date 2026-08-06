# CLAUDE.md — Instrucciones para Claude y agentes similares

## Primera acción obligatoria

Lee `IMPLEMENTACION_DE_MEJORAS.md` antes de cualquier trabajo. Contiene el plan maestro con tareas en orden específico.

## Flujo de trabajo

1. Leer `IMPLEMENTACION_DE_MEJORAS.md`
2. Identificar la siguiente tarea pendiente (`- [ ]`)
3. Implementar según instrucciones
4. Ejecutar: `python -m pytest test -q`
5. Ejecutar: `ruff check .`
6. Marcar como completada (`- [x]`)
7. Commit descriptivo
8. Push: `git push origin implementacion-de-mejoras`

## Comandos clave

- Tests: `python -m pytest test -q`
- Lint: `ruff check .`
- Ejecutar: `python -m jarvis_local.cli`
- Rama: `git branch --show-current`

## Reglas

- No saltes tareas
- No marques completada sin testear
- No rompas tests existentes
- No implementes mejoras fuera del documento sin preguntar
