# CLAUDE.md — Instrucciones para Claude y agentes similares

## Estado del proyecto

**No hay un plan maestro activo.** Los tres documentos de plan que ha tenido
este repo están completos y archivados — ninguno se ejecuta:

- `IMPLEMENTACION_DE_MEJORAS.md` (86/86 tareas).
- `PLAN_MAESTRO.md` (26/26 tareas, eficacia funcional).
- `docs/PLAN_EJECUCION.md` (fases A→J: VERIFY/auditoría, control de máquina,
  HUD, endurecimiento — mergeado a `main` el 2026-09-14, `2017ec3`).

Antes de tocar código, lee la sección **J6 — Cierre** al final de
`docs/PLAN_EJECUCION.md`: es la evaluación honesta más reciente de dónde
sigue frágil el proyecto, qué deuda queda abierta (residuo verde del shader
del orbe, F4.3 sin instalar, CI de Windows eliminado por indiagnosticable,
lo no verificable por hardware) y qué se haría a continuación. `README.md`
tiene la descripción funcional completa y el roadmap.

De aquí en adelante, el trabajo llega **por petición explícita del usuario**,
no de una lista de tareas preexistente. Cuando el usuario pida algo:

1. Entender qué pide exactamente. Si un plan nuevo (varias tareas
   encadenadas) tiene sentido para lo pedido, proponerlo antes de escribir
   código — no asumir alcance no pedido.
2. Si el trabajo lo justifica (más de un cambio trivial), abrir su propia
   rama; nunca trabajar directo sobre `main`.
3. Implementar + añadir los tests que blindan el cambio.
4. Correr el protocolo de pruebas completo (ver abajo) hasta que todo esté
   verde a la vez.
5. Commit descriptivo, con trailers.
6. El usuario dirige push y merge — ver "Reglas" abajo. No asumas permiso
   para ninguno de los dos por haber hecho el anterior.

## Comandos clave

- Tests (suite): `QT_QPA_PLATFORM=offscreen python -m pytest test -q`
- Lint: `ruff check .`
- Cobertura: `python -m pytest test/<...> --cov=jarvis_local.<módulo> --cov-report=term-missing`
- Ejecutar: `python -m jarvis_local.cli`
- Rama: `git branch --show-current`
- Estado de CI sin `gh auth` (no está logueado en este entorno): API pública
  de GitHub — `curl -s https://api.github.com/repos/omarhernandezrey/Jarvis/commits/<sha>/check-runs`.
  Los LOGS de un job sí requieren admin (403); el resultado (`conclusion`)
  de cada check no.

## Reglas

- No implementes más de lo pedido. Si algo fuera de alcance parece necesario,
  pregunta antes de tocarlo.
- No rompas ni debilites tests existentes. Cero regresiones — la suite
  completa sigue 100% verde siempre.
- Cada arreglo o funcionalidad lleva su test que lo blinda. Un test que
  falla a veces (flaky) no se acepta como "pasa": se arregla la causa
  (inyectar el reloj/las dependencias externas) o se documenta por qué no
  se puede.
- No marques nada como terminado sin haberlo ejercitado de verdad (CLI o
  `Jarvis.chat()` con Ollama vivo cuando aplique) — "los tests pasan" no es
  evidencia de que funcione en uso real.
- Si algo no se puede arreglar del todo (red, cuenta externa sin permisos,
  hardware que no está en esta máquina): documenta el límite exacto y deja
  un error accionable. Nunca finjas que funciona ni inventes un resultado.
- **El usuario dirige push y merge, con instrucción explícita — no por
  defecto tras terminar una tarea:**
  - Push de una rama de trabajo: solo cuando el usuario lo pide.
  - Merge a `main`: solo cuando el CI de `Tests (Linux, ...)` está **verde
    en las 3 versiones** (3.11/3.12/3.13) para el commit a mergear, Y el
    usuario lo ha pedido. El usuario veta el merge si el CI está rojo.
  - Al mergear: `--no-ff`; si el trabajo tenía su propio documento de
    seguimiento (como pasaba con `PLAN_EJECUCION.md`), rellenar ahí el hash
    real del merge en un commit aparte sobre `main`; borrar la rama, local
    y remota.
