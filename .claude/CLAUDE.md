# CLAUDE.md — Instrucciones para Claude y agentes similares

## Primera acción obligatoria

Lee `PLAN_MAESTRO.md` (en la raíz) antes de cualquier trabajo. Es EL plan
maestro activo, con tareas en orden estricto. `IMPLEMENTACION_DE_MEJORAS.md`
está archivado (completado al 100%): no se ejecuta.

## Flujo de trabajo (una rama por tarea → merge a `main`)

1. Leer `PLAN_MAESTRO.md` y sus "Reglas de oro" + "Protocolo de pruebas".
2. Identificar la siguiente tarea pendiente (`- [ ]`). **No se salta ninguna.**
3. `git checkout main && git pull origin main`
4. `git checkout -b <rama-de-la-tarea>` (nunca se trabaja directo sobre `main`).
5. Implementar según las instrucciones de la tarea + añadir sus tests.
6. Correr el **Protocolo de pruebas completo** del `PLAN_MAESTRO.md` (lint, unit
   nuevos, suite completa sin regresiones, cobertura, e2e con Ollama vivo,
   latencia si aplica, seguridad si aplica, CI). Si algo falla → corregir →
   **repetir la batería entera** hasta que TODO esté verde a la vez.
7. Commit descriptivo con evidencia e2e y trailers.
8. `git push origin <rama-de-la-tarea>`; esperar CI verde.
9. `git checkout main && git merge --no-ff <rama> && git push origin main`.
10. Borrar la rama (local y remota).
11. Marcar la tarea `- [x]` en `PLAN_MAESTRO.md` en el commit de merge.

## Comandos clave

- Tests (suite): `QT_QPA_PLATFORM=offscreen python -m pytest test -q`
- Lint: `ruff check .`
- Cobertura: `python -m pytest test/<...> --cov=jarvis_local.<módulo> --cov-report=term-missing`
- Ejecutar: `python -m jarvis_local.cli`
- Rama: `git branch --show-current`

## Reglas

- No saltes tareas. Secuencial estricto.
- No marques completada sin correr TODO el protocolo de pruebas hasta verde.
- No rompas ni debilites tests existentes. Cero regresiones.
- Cada arreglo lleva su test que lo blinde.
- No implementes mejoras fuera del documento sin preguntar.
- Si algo no se puede arreglar del todo (red, cuenta externa, hardware):
  documenta el límite y deja el error accionable. Nunca finjas que funciona.
