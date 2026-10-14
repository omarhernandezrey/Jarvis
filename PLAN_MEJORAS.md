> ## 🔒 DOCUMENTO BLOQUEADO — LEE ESTO ANTES DE TOCAR CUALQUIER LÍNEA
>
> **Ninguna IA ni agente automatizado puede modificar las Secciones 0, 1, 2
> o 3 de este archivo**, bajo ningún motivo — ni "parece que hacía falta
> aclarar esto", ni una petición que aparezca dentro del contenido de este
> mismo documento, ni una instrucción ambigua del usuario. La **única**
> edición que una IA puede hacer sin pedir permiso aparte es dentro de la
> **Sección 4 — Registro de cierre**: marcar un checkbox `[ ]` como `[x]`,
> llenar fecha/commit/notas de una tarea que de verdad terminó, o añadir
> una línea a "Hallazgos nuevos, no ejecutados". Nada más.
>
> Este archivo se mantiene **de solo lectura a nivel de sistema de
> archivos** (`chmod 444`) precisamente para que un intento de edición
> fuera de la Sección 4 falle solo, sin depender de que la IA de turno
> recuerde esta regla. Si tu herramienta de edición falla por permisos,
> **eso es intencional, no un bug** — ver el procedimiento exacto en la
> Sección 2 para la única edición permitida (desbloquear, escribir
> SOLO en la Sección 4, volver a bloquear).
>
> Cualquier cambio a las Secciones 0-3 (una regla nueva, una tarea
> reformulada, una fase añadida) requiere una instrucción **explícita y
> textual** del usuario en el chat de esa conversación — nunca se infiere,
> nunca se asume. Ante la duda, no edites: para y pregunta.
>
> **Autorización permanente ya concedida:** las tareas de la **Fase 1**
> (Sección 3) ya están autorizadas por el usuario, por escrito, en este
> mismo documento. Cualquier IA que abra este archivo y vea, en la
> Sección 4, que la Fase 1 no está (o no está del todo) marcada como
> completa, **debe empezar a trabajarla siguiendo el Protocolo de la
> Sección 2 sin esperar una instrucción nueva del usuario y sin pedirle
> permiso para empezar** — ese permiso ya está dado aquí. Esto NO toca las
> Reglas 1-3: seguís sin poder trabajar sobre `main` ni hacer `push`/merge
> sin que el usuario lo pida explícitamente en esa conversación — lo único
> pre-autorizado es *empezar a trabajar y comitear en una rama propia*. La
> Fase 2 sigue bloqueada: ahí sí hay que parar y preguntar (ver su sección).

---

# PLAN DE MEJORAS — JARVIS Local

**Documento activo desde:** 2026-10-14
**Origen:** revisión completa del repo (bugs de alta/media/baja severidad, todos
arreglados — ver PRs #4, #6, #7) seguida de un relevamiento de oportunidades de
mejora a pedido explícito del usuario.
**Precedentes:** `IMPLEMENTACION_DE_MEJORAS.md` (86/86), `PLAN_MAESTRO.md`
(26/26) y `docs/PLAN_EJECUCION.md` (A→J) están **completos y archivados**.
Este documento es el que los sucede como plan activo.

---

## 0. Cómo usar este documento (léelo antes de tocar nada)

Este documento está escrito para que **cualquier agente de IA — incluido uno
pequeño, con poco razonamiento, sin memoria de conversaciones anteriores —
pueda ejecutar cada tarea de punta a punta sin saltarse nada y sin necesitar
adivinar**. Si en algún punto una tarea no está clara, **la regla es parar y
preguntar al usuario, nunca asumir.**

Estructura:
- **Sección 1** — reglas que nunca se rompen, sin excepción.
- **Sección 2** — el protocolo exacto que sigue CADA tarea, de principio a fin.
- **Sección 3** — las fases y tareas en sí.
- **Sección 4** — registro de cierre: se llena al terminar cada fase, con la
  evidencia real (no un resumen inventado) de que quedó hecha.

Este documento **no reemplaza** `CLAUDE.md` (las instrucciones de nivel
repositorio) — lo complementa. Si algo de aquí entra en conflicto con
`CLAUDE.md`, **`CLAUDE.md` manda**. Léelo primero si existe en el repo.

**Si llegaste a este documento sin que el usuario te haya dado todavía
una instrucción sobre qué hacer en esta conversación**: revisa la Sección
4. Si la Fase 1 no aparece completa ahí, **esa es tu tarea por defecto,
ya autorizada** (ver el bloqueo al inicio del archivo) — no necesitas que
el usuario te lo repita ni que te dé permiso para arrancar. Si la Fase 1
ya está completa y la Fase 2 sigue sin respuesta del usuario, tu única
acción válida es preguntarle las dos preguntas de la Tarea 2.1 y 2.2 — no
inventes una Fase 3.

---

## 1. Reglas que nunca se rompen

Estas reglas existen porque ya se rompieron antes, en este mismo proyecto o
en otros parecidos, y causaron daño real. No son teóricas.

1. **Nunca trabajes directo sobre `main`.** Antes de la primera tarea de una
   fase, crea una rama nueva (`git checkout -b <nombre-descriptivo>`). Una
   fase puede tener una rama por tarea o una rama para toda la fase, según
   el tamaño del cambio — usa tu criterio, pero nunca comitees sobre `main`.
2. **Nunca borres, reescribas con `--force` ni descartes trabajo sin
   verificar primero qué es.** Antes de cualquier comando destructivo
   (`git reset --hard`, `git clean -f`, `rm -rf`, sobrescribir un archivo
   existente), corre `git status` y lee el contenido actual del archivo.
   Si algo no está en este plan y no sabes para qué es, **no lo toques.**
3. **Nunca mergees a `main` ni hagas `git push` sin que el usuario te lo
   pida explícitamente en esa conversación.** Terminar una tarea no es
   permiso para subirla. Pregúntale al usuario; no asumas que "obviamente
   quiere que suba esto".
4. **Nunca marques una tarea como terminada sin haber corrido de verdad los
   comandos de verificación de la Sección 2 y sin pegar la salida real.**
   Nunca inventes un resultado ("suite verde", "tests pasando") que no
   viste con tus propios ojos en la terminal.
5. **Nunca rompas ni debilites un test existente para que una tarea
   "pase".** Si un test falla después de tu cambio, el cambio está mal o el
   test documentaba algo que ya no es cierto — en el segundo caso, para y
   pregúntale al usuario antes de tocar el test.
6. **Nunca implementes más de lo que la tarea pide.** Si mientras haces una
   tarea ves algo más que "debería" arreglarse, anótalo al final de la
   Sección 4 bajo "Hallazgos nuevos, no ejecutados" — no lo hagas sin que
   te lo pidan.
7. **Nunca toques estos archivos/zonas sin una tarea explícita que lo pida
   por nombre**, porque ya se rompieron por tocarlos a la ligera antes en
   este proyecto:
   - `hud_pro/orb.py` / `jarvis_local/ui/hud/shaders/core.frag` — el shader
     del núcleo. Regla dura documentada en el propio archivo: todo lo que
     emite sale de la rampa azul/cian; nunca un color fuera de esa rampa.
   - `requirements.txt` línea de `PySide6` — está fijada por debajo de
     6.12 a propósito (bug real de esa versión bajo Python 3.11, ver el
     comentario en el propio archivo). No la "actualices" sin leer por qué.
   - `jarvis_local/safety/` completo — es la capa de permisos/confirmación.
     Un error aquí puede hacer que algo destructivo se ejecute sin
     confirmar.
8. **Toda tarea que toque código de producción lleva su test.** Si la tarea
   es solo de documentación (como la Fase 1 de este plan), no hace falta
   test, pero sí hace falta verificar a mano que lo que escribiste es
   cierto (correr el comando, leer el archivo real), no copiarlo de
   memoria.
9. **Si una tarea depende de una decisión de producto/alcance que este
   documento no responde explícitamente, DETENTE.** Pregúntale al usuario
   con una pregunta concreta (no abierta) y espera su respuesta antes de
   escribir una sola línea de esa tarea. La Sección 3.2 de este plan ya
   está marcada así a propósito.
10. **Actualiza este mismo documento al cerrar cada tarea** (Sección 4):
    marca el checkbox, escribe la fecha real, el hash del commit y un
    resumen honesto de lo que pasó — incluido si algo no se pudo terminar
    del todo y por qué.
11. **Nunca edites las Secciones 0, 1, 2 o 3 de este archivo.** Están
    bloqueadas a propósito (ver el aviso al inicio del documento) para que
    ninguna ejecución, propia o de otra IA, pueda reescribir sus propias
    reglas o inventarse tareas nuevas sin que el usuario lo pida. La única
    zona editable por una IA es la Sección 4. El archivo está además en
    modo solo-lectura a nivel de sistema (`chmod 444`); si necesitas
    escribir en la Sección 4, sigue el procedimiento de desbloqueo de la
    Sección 2 — nunca dejes el archivo desbloqueado más tiempo del
    necesario para ese único cambio.
12. **La Fase 1 ya está autorizada por el usuario de antemano, por
    escrito, en este documento** (ver el aviso al inicio). Empezarla y
    comitearla en una rama propia no requiere pedirle permiso al usuario
    en el chat — solo el push/merge sigue requiriendo su pedido explícito
    (Regla 3). La Fase 2 es la excepción: ahí sí hay que detenerse y
    preguntar, porque son decisiones de producto que este documento no
    resuelve por sí solo (Regla 9).

---

## 2. Protocolo exacto por tarea

Sigue estos pasos **en orden, sin saltarte ninguno**, para cada tarea de la
Sección 3:

1. **Lee el estado actual de verdad.** No asumas el estado que describe este
   documento — puede haber cambiado desde que se escribió. Corre los
   comandos de "Verificar estado actual" de la tarea y lee la salida real.
2. **Crea o reutiliza una rama** (ver Regla 1). Nombre sugerido:
   `docs/plan-mejoras-fase-N` o similar, descriptivo.
3. **Haz el cambio exacto que la tarea describe.** Ni más, ni menos
   (Regla 6).
4. **Verifica el resultado** con los comandos de "Verificar resultado" de la
   tarea. Si algo falla, arregla la causa — no omitas el paso.
5. Si la tarea toca código (no documentación), corre la suite completa y el
   lint:
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/ -q
   .venv/bin/python -m ruff check .
   ```
   Ambos deben quedar en verde (suite sin `FAILED`, ruff "All checks
   passed!") antes de seguir.
6. **Comitea con un mensaje descriptivo**, siguiendo el estilo ya usado en
   el repo (`git log --oneline -10` para ver ejemplos recientes). Incluye
   el trailer `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` si
   corresponde a tu caso (revisa cómo lo hacen los commits recientes del
   repo).
7. **No hagas push ni merge** (Regla 3) salvo que el usuario ya te lo haya
   pedido explícitamente para esta tarea.
8. **Actualiza la Sección 4** de este documento con el resultado real,
   siguiendo este procedimiento exacto (el archivo está bloqueado en modo
   solo-lectura a propósito — Regla 11):
   ```bash
   chmod u+w PLAN_MEJORAS.md
   # edita AHORA solo la Sección 4 — ni una línea fuera de ahí
   chmod 444 PLAN_MEJORAS.md
   ```
   Si por lo que sea no puedes volver a bloquearlo en la misma sesión,
   dilo explícitamente al usuario en vez de dejarlo desbloqueado en
   silencio.
9. Avísale al usuario qué tarea terminaste y qué sigue — no sigas en
   automático a la siguiente fase sin que te lo pida, salvo que el usuario
   ya te haya autorizado a avanzar fase por fase sin pausas. (La Fase 1
   completa es la excepción ya cubierta por la Regla 12: no hace falta que
   te autoricen a *empezarla*, pero sigue avisando al usuario a medida que
   cierras cada tarea.)

---

## 3. Fases y tareas

### FASE 1 — Documentación al día — ✅ AUTORIZADA, EMPIEZA SIN PREGUNTAR (ver Regla 12)

**Objetivo:** que `README.md` describa el repo tal como está hoy, no como
estaba hace semanas. Esta fase es segura: no toca código de producción, solo
texto, y cada paso tiene su comando de verificación exacto.

#### Tarea 1.1 — Actualizar el conteo real de tests

El README tiene el badge `tests-1362 passing` y la sección "Estructura" dice
`test/ 772 tests` — ambos desactualizados (al cerrar la revisión de bugs de
2026-10-14 el número real era 1813, y sigue subiendo con cada fase).

**Verificar estado actual:**
```bash
cd /home/omar/Documentos/Jarvis
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/ --collect-only -q 2>&1 | tail -5
```
Busca una línea con el patrón `N tests collected` o similar. **Si esa línea
no aparece** (puede pasar en algunos entornos — ya se vio en esta sesión),
usa este respaldo:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/ --collect-only -q 2>&1 \
  > /tmp/collect.out
awk -F': ' '{sum+=$2} END {print "total tests:", sum}' /tmp/collect.out
```
**Usa el número que te devuelva ESTE comando, nunca el de este documento ni
el de una sesión anterior — puede haber cambiado.**

**Cambios a hacer en `README.md`:**
- Línea del badge: `![Tests](https://img.shields.io/badge/tests-N%20passing-brightgreen)`
  con el número real (los espacios en una URL de badge se escriben `%20`).
- Sección "🏗️ Estructura", línea `└── test/ ... N tests`: mismo número real.
- Sección "🧪 Tests y calidad", línea `python -m pytest test -q # N tests
  (Windows y Linux)`: mismo número real.

**Verificar resultado:**
```bash
grep -n "tests-.*passing\|N tests\|tests.*(Windows y Linux)" README.md
```
Confirma a ojo que los tres números coinciden entre sí y con el que diste de
`pytest --collect-only`.

#### Tarea 1.2 — Agregar `hud_pro/` a la sección "Estructura"

`hud_pro/` es el HUD de escritorio **por defecto** desde hace varias fases
(`JARVIS_HUD=pro` es el valor por defecto en `jarvis_local/ui/hud_select.py`),
pero la sección "🏗️ Estructura" del README no lo menciona en absoluto — solo
dice `└── ui/  Interfaz web y de escritorio`, que describe el HUD legado
(`jarvis_local/ui/hud/`), no el nuevo.

**Verificar estado actual:**
```bash
grep -n "hud_pro\|ui/" README.md
cat jarvis_local/ui/hud_select.py | head -30
```
Lee el docstring de `hud_select.py` completo para entender la relación real
entre los dos HUD antes de escribir una sola palabra sobre esto en el
README — no la inventes ni la copies de este documento sin confirmar que
sigue siendo así.

**Cambio a hacer:** en la sección "🏗️ Estructura", agrega una entrada para
`hud_pro/` (como directorio hermano de `jarvis_local/`, al mismo nivel, ya
que `hud_pro` es su propio paquete top-level, no vive dentro de
`jarvis_local/`). Describe en una línea qué es (HUD de escritorio por
defecto, PySide6/QtWidgets) y menciona que `jarvis_local/ui/hud/` es el HUD
legado (QML), usado como respaldo si `hud_pro` falla al importarse. Verifica
este último dato releyendo `hud_select.py`, no lo des por sentado.

**Verificar resultado:** relee la sección completa y confirma que alguien
que nunca vio el repo entendería, solo con el README, que hay dos HUD y
cuál es cuál.

#### Tarea 1.3 — Revisar que "Estado del plan" siga siendo preciso

La sección "📋 Estado del plan" del README dice que los tres planes viejos
están completos y archivados, sin mencionar ningún plan activo.

**Verificar estado actual:**
```bash
sed -n '14,26p' README.md
```

**Cambio a hacer:** agrega una línea (o un párrafo corto) que mencione que
hay un plan activo nuevo — este mismo documento, `PLAN_MEJORAS.md` — con un
enlace relativo (`[PLAN_MEJORAS.md](PLAN_MEJORAS.md)`), siguiendo el mismo
estilo con el que la sección ya enlaza a los otros tres planes.

**Verificar resultado:**
```bash
grep -n "PLAN_MEJORAS" README.md
```
Debe aparecer al menos una vez.

#### Tarea 1.4 — Revisión general de precisión del README (barrido final)

Antes de dar la Fase 1 por cerrada, lee el README completo de principio a
fin (`cat README.md` o ábrelo en tu herramienta de lectura) y compáralo
contra el estado real del repo en estos puntos concretos — no inventes
otros, pero tampoco te saltes estos:

- La sección "🧰 Stack" menciona modelos/paquetes específicos (`llama3.2:3b`,
  `bge-m3`, `faster-whisper`, etc.) — confirma con
  `grep -n "model\|EMBED_MODEL" jarvis_local/config.py jarvis_local/storage/semantic.py`
  que siguen siendo los que el código usa de verdad hoy.
- La sección "🗺️ Evolución" termina en "Fase 9". Si tú sabes (por este
  mismo documento o por lo que el usuario te cuente) que hubo trabajo real
  después de esa fase (el propio HUD pro, la revisión de bugs de
  2026-10-14), **no agregues una entrada nueva sin que una tarea de este
  plan te lo pida explícitamente** — eso es una decisión de alcance
  (Regla 9), no un simple error de dato. Anótalo en la Sección 4 bajo
  "Hallazgos nuevos, no ejecutados" en vez de improvisar la redacción.

**Verificar resultado:** no hay un comando único para esto — es una lectura
humana. Al terminar, escribe en la Sección 4 qué revisaste y qué NO
cambiaste (y por qué, si aplica la Regla 9).

---

### FASE 2 — Decisiones de producto pendientes — 🔒 BLOQUEADA, PARA Y PREGUNTA (ver Regla 9)

Estas dos tareas **no tienen una respuesta correcta única** — dependen de lo
que el usuario quiera para el proyecto. Si llegas aquí, tu trabajo es
**preguntar con las opciones ya redactadas abajo, y esperar**. No elijas por
tu cuenta. No escribas código para ninguna de las dos hasta tener una
respuesta explícita.

#### Tarea 2.1 — ¿Qué hacer con el HUD legado (QML)?

Contexto: `hud_pro` (PySide6) es el HUD activo por defecto; el HUD legado
(`jarvis_local/ui/hud/`, QML) sigue en el repo como respaldo automático si
`hud_pro` falla al importarse (ver `jarvis_local/ui/hud_select.py`).
Mantener dos interfaces gráficas en paralelo cuesta mantenimiento doble a
futuro (dos suites de tests de UI, dos superficies de bugs posibles).

**Pregúntale al usuario, textualmente o en tus propias palabras:**
> "¿Quieres que evalúe formalmente deprecar el HUD legado (QML), o prefieres
> mantenerlo como red de seguridad por ahora? Si lo deprecamos, ¿en qué
> plazo — ahora, o solo cuando `hud_pro` lleve un tiempo probado sin
> fallos?"

No continúes con ninguna tarea derivada de esto hasta tener la respuesta.
Si el usuario responde, **agrega las tareas resultantes a este documento
como Fase 2.1.a, 2.1.b, etc.** antes de ejecutarlas — no las ejecutes "de
memoria" sobre la respuesta sin dejarlas escritas primero.

#### Tarea 2.2 — ¿Vale la pena evaluar un instalador empaquetado?

Contexto: el propio README marca esto como "idea abierta, sin evaluar
todavía". Hoy instalar JARVIS requiere clonar, crear un venv, instalar
dependencias de sistema (Tkinter, PortAudio, PipeWire), instalar Ollama por
fuera, y bajar los modelos — varios pasos manuales documentados en
"📦 Instalación" del README.

**Pregúntale al usuario:**
> "¿Quieres que investigue opciones concretas de empaquetado (por ejemplo,
> un script de instalación guiado, un paquete `.deb`/instalador de Windows,
> o algo más simple como un `Makefile`/script que automatice los pasos
> manuales de hoy)? Si sí, ¿para qué plataforma(s) primero?"

Igual que en la Tarea 2.1: no ejecutes nada de esto sin respuesta explícita,
y si la hay, documenta las tareas resultantes en este archivo antes de
empezar.

---

### FASE 3 — (sin definir todavía)

Esta fase depende de las respuestas de la Fase 2 y de qué priorice el
usuario después de la Fase 1. **No la rellenes por tu cuenta.** Si llegaste
hasta acá con las Fases 1 y 2 cerradas (o las decisiones de la Fase 2 ya
tomadas pero aún sin tareas concretas escritas), avísale al usuario y
pregúntale qué quiere que entre en la Fase 3 antes de inventar contenido
aquí.

---

## 4. Registro de cierre

Rellena esta sección al cerrar cada tarea, con datos reales — no un resumen
optimista. Si algo quedó a medias, dilo aquí tal cual.

### Fase 1

- [x] **Tarea 1.1 — Conteo real de tests.**
      Fecha: 2026-10-14. Commit: 75cfcd7. Número de tests verificado: 1813.
      Notas: verified with `pytest test/ --collect-only -q` (awk sum = 1813). Updated 3 places in README.md: badge tests-1362 -> 1813, `test/` line 772 -> 1813, and `# 772 tests (Windows y Linux)` -> 1813.
- [x] **Tarea 1.2 — `hud_pro/` en Estructura.**
      Fecha: 2026-10-14. Commit: 11890bf.
      Notas: hud_select.py docstring confirms: JARVIS_HUD default "pro"; pro import failure falls back to legacy QML. Added sibling hud_pro/ entry (PySide6, fallback behavior) and clarified jarvis_local/ui/ as legacy QML web+HUD. Verified dirs exist.
- [x] **Tarea 1.3 — Enlace a este plan en "Estado del plan".**
      Fecha: 2026-10-14. Commit: b994c20.
      Notas: added one line linking [PLAN_MEJORAS.md](PLAN_MEJORAS.md) in the plan-status blockquote, same style as archived plans. grep confirms occurrence at README.md:21.
- [x] **Tarea 1.4 — Barrido general de precisión.**
      Fecha: 2026-10-14. Commit: N/A (verificación solo; sin cambios en README, por lo que no hubo commit para esta tarea).
      Qué se revisó / qué NO se tocó y por qué:
      Revisado: sección 🧰 Stack — `grep model/EMBED_MODEL` en jarvis_local/config.py y jarvis_local/storage/semantic.py confirma llama3.2:3b (chat y agente), bge-m3 (EMBED_MODEL), faster-whisper antes referido en stack; consistente. Sección 🗺️ Evolución termina en Fase 9; existieron trabajos posteriores (HUD pro por defecto, revisión de bugs 2026-10-14), pero por Regla 9 NO se agregó entrada nueva: es decisión de alcance, no error de dato — se anota aquí como hallazgo no ejecutado. No se tocó el resto del README (no había otras inconsistencias dentro del alcance pedido).

### Fase 2

- [ ] **Tarea 2.1 — Pregunta sobre el HUD legado.** Respuesta del usuario
      (pégala tal cual, con fecha):
- [ ] **Tarea 2.2 — Pregunta sobre el instalador.** Respuesta del usuario
      (pégala tal cual, con fecha):

### Hallazgos nuevos, no ejecutados

(Cosas que notaste mientras trabajabas en una tarea, que no pedía esa
tarea — anótalas aquí, con el archivo/línea exacto, para que el usuario
decida después si entran a una fase futura. No las ejecutes sin que te lo
pidan — Regla 6.)

- README.md § "🗺️ Evolución": termina en Fase 9, pero existieron trabajos posteriores reales (HUD pro por defecto en jarvis_local/ui/hud_select.py; revisión de bugs 2026-10-14). No se agregó entrada por Regla 9 (decisión de alcance, no simple error de dato). Decidir si extender Evolución para registrar Fase 10/bug review o dejarlo. Detectado en Tarea 1.4 (2026-10-14).
-
