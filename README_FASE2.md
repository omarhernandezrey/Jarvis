# JARVIS Local - Fase 2: Herramientas Locales Seguras

## Estado: COMPLETADO

Herramientas de archivos, apps y terminal con politica de seguridad (simulacion + confirmacion).

---

## Novedades sobre Fase 1

- `salir` ahora funciona con o sin `/` (tambien `exit`, `quit`)
- Chat con Ollama sigue aislado: el modelo no puede llamar herramientas

---

## Herramientas disponibles

### /archivos

| Comando | Accion | Riesgo |
|---|---|---|
| `/archivos listar <ruta>` | Lista contenido de un directorio | Lectura |
| `/archivos buscar <nombre> <ruta>` | Busca archivos por nombre | Lectura |
| `/archivos info <ruta>` | Muestra metadatos | Lectura |
| `/archivos crear-archivo <ruta> [contenido]` | Plan para crear archivo | Medio |
| `/archivos crear-carpeta <ruta>` | Plan para crear carpeta | Medio |
| `/archivos copiar <origen> <destino>` | Plan para copiar archivo | Medio |
| `/archivos mover <origen> <destino>` | Plan para mover archivo | Medio |
| `/archivos renombrar <ruta> <nuevo>` | Plan para renombrar | Medio |
| `/archivos borrar-plan <ruta>` | SOLO plan de borrado | Alto (BLOQUEADO) |

### /apps

| Comando | Accion |
|---|---|
| `/apps listar` | Lista apps permitidas con estado |
| `/apps abrir <app>` | Abre chrome, vscode, explorador, powershell o terminal |

### /terminal

| Comando | Accion |
|---|---|
| `/terminal plan <comando>` | Prepara un comando sin ejecutarlo |

### Control de planes

| Comando | Accion |
|---|---|
| `/plan` | Ver el plan pendiente |
| `/confirmar` | Confirmar y ejecutar (solo apps y operaciones seguras) |
| `/cancelar` | Cancelar plan pendiente |

---

## Politica de Seguridad

- **Simulacion por defecto**: todas las operaciones muestran que harian antes de ejecutar
- **Solo lectura automatico**: listar, buscar e info funcionan sin confirmacion
- **Confirmacion requerida**: crear, copiar, mover, renombrar, abrir apps, preparar comandos
- **Borrado bloqueado**: requiere doble confirmacion (no disponible en esta fase)
- **Whitelist de carpetas**: solo Documentos, Descargas y Escritorio
- **Bloqueo de escapes**: `..`, symlinks y rutas equivalentes son detectados
- **Comandos bloqueados**: `.ps1`, `.bat`, `.exe`, pipes, redirects, del, rmdir, curl, irm, iwr, shutdown, etc.
- **Registro**: cada plan, confirmacion, rechazo y error queda en `logs/actions.log`
- **Redaccion de secretos**: API keys, tokens y passwords son redactados en logs

---

## Pruebas

```powershell
cd C:\Users\herna\Documents\open-interpreter-python
python -m jarvis_local.test.test_permissions   # 14 tests
python -m jarvis_local.test.test_policy        # 10 tests
python -m jarvis_local.test.test_files         # 10 tests
python -m jarvis_local.test.test_apps          # 3 tests
python -m jarvis_local.test.test_terminal      # 7 tests
```

**Resultado**: 44/44 tests pasan (incluyendo los 15 de Fase 1 = 59 total)

---

## Ejemplos de uso

```
[Tu]: /archivos listar Documents
[SIMULACION] Se listarian archivos en: C:\Users\herna\Documents
Estado: PENDIENTE DE CONFIRMACION

[Tu]: /apps abrir chrome
[SIMULACION] Se ejecutaria: abrir_app
  app: chrome
  path: C:\Program Files\Google\Chrome\Application\chrome.exe
Estado: PENDIENTE DE CONFIRMACION

[Tu]: /confirmar
chrome abierto correctamente

[Tu]: /terminal plan dir
[SIMULACION] Se ejecutaria en PowerShell:
  > dir
Estado: PENDIENTE DE CONFIRMACION

[Tu]: /terminal plan "del /f test.txt"
BLOQUEADO: Comando bloqueado: 'del' no esta permitido

[Tu]: /archivos borrar-plan importante.txt
[BORRADO BLOQUEADO] Se eliminaria: ...importante.txt
El borrado no esta habilitado en esta fase.

[Tu]: hola jarvis como estas?
[JARVIS]: Hola Omar, estoy bien, gracias...
```

---

## Archivos modificados/creados

### Nuevos (Fase 2)
```
jarvis_local/
  safety/permissions.py         Whitelists, bloqueo de rutas/comandos
  safety/policy.py              ActionPlan, simulacion, confirmacion
  tools/files.py                Operaciones de archivos seguras
  tools/apps.py                 Apertura de apps permitidas
  tools/terminal.py             Preparacion de comandos
  requirements-phase2.txt       (mismas deps que Fase 1)
  test/test_permissions.py      14 tests
  test/test_policy.py           10 tests
  test/test_files.py            10 tests
  test/test_apps.py             3 tests
  test/test_terminal.py         7 tests
  README_FASE2.md               Este archivo
```

### Modificados (Fase 2)
```
  cli.py                        Comandos /archivos, /apps, /terminal, /plan, /confirmar, /cancelar
  config.yaml                   Seccion safety con simulation_mode y whitelists
  PLAN_JARVIS_WINDOWS.md        Fase 2 marcada como completada
```

---

*Fase 2 completada - 8 de julio de 2026*
