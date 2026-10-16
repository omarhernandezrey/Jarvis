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
> **Autorización total ya concedida — lee esto con cuidado, cambia el modo
> de trabajar de cualquier IA que ejecute este documento.** El usuario,
> dueño de este proyecto, ya tomó por escrito **todas** las decisiones de
> producto que esta versión del documento necesita. Toda tarea de **toda
> fase escrita en la Sección 3** (Fase 1, Fase 2 — ya resuelta — y Fase 3)
> está **pre-autorizada de punta a punta**: ninguna IA necesita pedir
> permiso para empezar una tarea, para pasar de una tarea a la siguiente,
> ni para pasar de una fase a la siguiente. El criterio por defecto es
> **seguir hasta terminar TODAS las tareas de TODAS las fases escritas**,
> encadenadas, sin pausas para preguntar "¿sigo?" o "¿quieres que
> continúe?" — eso ya se respondió que sí, aquí, de antemano.
>
> Esto tiene exactamente **dos excepciones**, ninguna más, y ninguna IA
> puede inventarse una tercera:
> 1. **Push/merge a un remoto compartido sigue requiriendo que el usuario
>    lo pida explícitamente, cada vez** (Regla 3). No es una decisión de
>    producto de este plan — es una regla dura de `CLAUDE.md`, el archivo
>    de gobierno del repositorio, sobre visibilidad compartida y CI. Este
>    documento no tiene autoridad para levantarla.
> 2. **Una situación genuinamente nueva, no anticipada en ninguna tarea
>    ya escrita** (Regla 9, ahora de último recurso — ver su texto). Si lo
>    que encontraste SÍ está cubierto, aunque sea parcialmente, por una
>    tarea existente, no es una excepción: seguí la tarea.
>
> Fuera de esas dos, **nunca te detengas a pedir permiso de producto**: si
> hace falta una decisión de arquitectura, diseño o alcance dentro de una
> tarea que no está ya resuelta en el texto, tomala vos con el mejor
> criterio de ingeniería senior, documentá por qué en el commit y en la
> Sección 4, y seguí. Las Reglas 1, 2, 4, 5, 6, 7, 8 y 10 (rama propia, no
> destruir sin verificar, no fingir verificación, no debilitar tests, no
> implementar de más, zonas protegidas, test obligatorio, registro al
> cerrar) **siguen plenas** — no son permisos, son disciplina de
> ingeniería, y no se negocian ni se saltan bajo ningún motivo.

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
4 y encontrá la primera tarea, en orden (Fase 1 → Fase 2 → Fase 3 → ...),
que no esté marcada como completa. **Esa es tu tarea por defecto, ya
autorizada — empezala ahora, sin esperar instrucción nueva ni pedir
permiso.** Seguí encadenando tareas y fases hasta que la Sección 4 no
tenga ningún checkbox sin marcar. Solo te detenés en las dos excepciones
del aviso de bloqueo al inicio del archivo (push/merge, o algo
genuinamente no anticipado) — nunca por costumbre, nunca "para
confirmar".

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
9. **Última instancia, no la regla por defecto:** las decisiones de
   producto/alcance conocidas al escribir esta versión del documento ya
   están tomadas (ver el aviso de bloqueo al inicio y las tareas de la
   Sección 3 — incluida la Fase 2, ya resuelta). Esta regla se invoca
   **solo** ante una situación genuinamente nueva que ninguna tarea
   existente cubre ni remotamente — no para evitar un juicio de
   ingeniería que podés tomar vos mismo con criterio senior y documentar
   después. Si de verdad aplica, pregúntale al usuario con una pregunta
   concreta (no abierta) y esperá su respuesta antes de escribir una sola
   línea de esa parte específica de la tarea — el resto de la tarea que sí
   esté claro, seguí ejecutándolo.
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
12. **Todas las fases y tareas de la Sección 3 ya están autorizadas por
    el usuario de antemano, por escrito, en este documento** (ver el
    aviso al inicio). Empezar, continuar y terminar cualquiera de ellas
    —y encadenar la siguiente sin pausa— no requiere pedirle permiso al
    usuario en el chat. Las únicas dos excepciones son las del aviso
    inicial: push/merge (Regla 3) y una situación realmente no anticipada
    (Regla 9, último recurso). Nada más amerita detenerse a preguntar.

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
9. Avísale al usuario qué tarea terminaste (un mensaje breve basta: qué
   cambió, qué commit) y **seguí de inmediato con la siguiente tarea de
   la siguiente fase**, sin esperar respuesta — la Regla 12 ya te
   autorizó a encadenar todo. Solo te detenés de verdad ante las dos
   excepciones de la Regla 12 (push/merge, o Regla 9 genuina). El aviso
   es para que el usuario tenga visibilidad, no un punto de pausa.

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

### FASE 2 — Decisiones de producto — ✅ RESUELTA, AUTORIZADA, SIGUE SIN PREGUNTAR

Estas dos preguntas **ya fueron respondidas por el usuario el 2026-10-14**
(ver las respuestas bajo cada tarea y en la Sección 4). Quedan en el
documento como registro de por qué se decidió lo que se decidió — no como
preguntas abiertas. Ninguna IA debe volver a preguntarlas ni reabrirlas sin
una instrucción nueva y explícita del usuario que lo pida por nombre.

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

**✅ Respondida (2026-10-14):** el usuario eligió "mantenerlo como red de
seguridad" — el HUD legado (QML) sigue como respaldo automático, sin
evaluar deprecación por ahora. **No hay tarea derivada que ejecutar.** No
reabras esta decisión sin una instrucción nueva y explícita del usuario.

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

**✅ Respondida (2026-10-14):** el usuario eligió "sí, investigar ahora",
con **Linux primero** (es la única plataforma con CI activo hoy; Windows
no tiene CI propio desde hace varias fases — ver J6 en
`docs/PLAN_EJECUCION.md`). Tarea derivada, ya autorizada a continuación:

##### Tarea 2.2.a — Investigar opciones de empaquetado para Linux (solo investigación, NO implementar nada todavía)

**Alcance exacto — lee esto dos veces antes de empezar:** esta tarea
produce un **documento de comparación**, no código. No crees ningún
script de instalación, `Makefile`, paquete `.deb` ni nada ejecutable en
esta tarea — eso es una implementación, y requeriría su propia tarea con
su propia autorización explícita (Regla 6: no implementes más de lo que
la tarea pide).

**Verificar estado actual (contexto que necesitas antes de investigar):**
```bash
cd /home/omar/Documentos/Jarvis
sed -n '/## 📦 Instalación/,/^## /p' README.md | head -60
cat requirements.txt
```
Lee completos los pasos manuales de instalación que el README describe
hoy (clonar, venv, dependencias de sistema, Ollama aparte, descarga de
modelos) — tu comparación debe partir de ahí, no de una idea genérica de
"cómo se empaqueta software en Linux".

**Qué investigar (mínimo estas 3 opciones, todas para Linux):**
1. **Script de instalación guiado** (`install.sh` o similar) que
   automatice los pasos manuales de hoy: crear venv, instalar
   `requirements.txt`, verificar/instalar dependencias de sistema
   (Tkinter, PortAudio, PipeWire), verificar si Ollama está instalado y
   guiar su instalación si no, descargar los modelos (`llama3.2:3b`,
   `bge-m3`) vía `ollama pull`.
2. **Paquete `.deb`** (Debian/Ubuntu) usando una herramienta estándar
   (por ejemplo `dpkg-deb`, `fpm`, o `debhelper`) que instale el paquete
   Python y sus dependencias de sistema vía `apt`.
3. **`Makefile`/script simple** (`make install`, `make run`) que no
   empaqueta nada — solo encadena los comandos manuales de hoy en un
   único comando, sin resolver dependencias de sistema automáticamente.

Para cada opción, documenta (en una tabla o en texto corto, a tu
criterio): qué problemas de los que el README describe hoy resuelve,
qué esfuerzo de implementación y mantenimiento estimas, qué limitaciones
tiene (por ejemplo: un `.deb` no resuelve instalar Ollama, que no se
distribuye por `apt`), y si existe algún precedente conocido en proyectos
similares (asistentes de voz locales, herramientas con backend LLM local)
que puedas citar sin inventar nada — si no encuentras ninguno, dilo
explícitamente, no inventes uno.

**Dónde escribir el resultado:** crea `docs/INSTALADOR_OPCIONES.md` nuevo,
con la comparación de las 3 opciones y, al final, la **decisión ya
tomada** en este documento (Fase 3): script guiado (`install.sh`) +
`Makefile`, descartando el `.deb` por el sobrecosto de mantenimiento de
empaquetado nativo que no resuelve el problema real (los pasos manuales
de hoy), frente a un proyecto de un solo mantenedor en desarrollo activo.
Redáctalo como decisión documentada, no como pregunta abierta. Enlaza ese
archivo nuevo desde la sección "📦 Instalación" del README (una línea:
"Ver docs/INSTALADOR_OPCIONES.md para la comparación de opciones de
empaquetado y por qué se eligió el script guiado").

**Verificar resultado:**
```bash
test -f docs/INSTALADOR_OPCIONES.md && echo "existe"
grep -n "INSTALADOR_OPCIONES" README.md
```
Ambos deben confirmar.

**Al terminar esta tarea, NO te detengas.** La elección entre las 3
opciones ya está decidida en este documento, en la Fase 3 (es una
decisión de arquitectura ya tomada con criterio senior, no una pregunta
abierta): continúa de inmediato con la Tarea 3.1 en la misma rama.

---

### FASE 3 — Instalador guiado para Linux — ✅ AUTORIZADA, EJECUTAR DE PUNTA A PUNTA

**Decisión de arquitectura ya tomada** (criterio senior, no una pregunta
abierta): se implementa un **script de instalación guiado** (`install.sh`)
más un **`Makefile`** envolvente. Se descarta el `.deb`: construir y
mantener un paquete Debian (firma, repo, versión en lockstep con
`requirements.txt` que cambia cada pocas fases) es sobrecosto de
empaquetado que no resuelve el problema real — los pasos manuales de hoy
— para un proyecto de desarrollo activo con un solo mantenedor. Un script
+ `Makefile` resuelve el 100% del dolor real (clonar → `make install` →
`make run`) con una fracción del mantenimiento.

**Objetivo:** después de esta fase, `README.md` § "📦 Instalación" debe
poder decir "clona el repo y corre `make install`" como primera opción,
manteniendo los pasos manuales de hoy como alternativa/diagnóstico.

#### Tarea 3.1 — Crear `install.sh`

**Verificar estado actual:**
```bash
cd /home/omar/Documentos/Jarvis
ls install.sh 2>/dev/null || echo "no existe todavía"
sed -n '/## 📦 Instalación/,/^## /p' README.md
cat requirements.txt
```

**Cambio a hacer:** crea `install.sh` en la raíz del repo (`chmod +x`),
en bash, con `set -euo pipefail`, que haga en orden:
1. Verifica la versión de Python disponible (`python3 --version`); si es
   menor a 3.11, imprime un error claro y sale con código ≠ 0 — no
   continúa a medias.
2. Si no existe `.venv/`, lo crea (`python3 -m venv .venv`).
3. Activa el venv dentro del script (`source .venv/bin/activate`) e
   instala `pip install -r requirements.txt`.
4. Verifica dependencias de sistema que `requirements.txt` no cubre
   (Tkinter, PortAudio, PipeWire — las que ya documenta el README en
   "📦 Instalación"): intenta detectarlas (por ejemplo,
   `python3 -c "import tkinter"` para Tkinter; `pkg-config --exists
   libportaudio2` o similar para PortAudio — usa el método que
   `README.md` ya documenta como forma de verificarlas, no inventes uno
   nuevo). Si falta alguna, **imprime** el comando `apt install` exacto
   que el README ya documenta para instalarla y sale con código ≠ 0 —
   **nunca ejecutes `sudo` ni `apt install` automáticamente dentro del
   script**: es una decisión del usuario final que corre el instalador
   más adelante, no de la IA que escribe el script ni de quien lo
   ejecuta sin supervisión.
5. Verifica si el binario `ollama` existe en `PATH`
   (`command -v ollama`). Si no existe, imprime las instrucciones de
   instalación que el README ya documenta y sale con código ≠ 0 (mismo
   criterio que el punto 4: nunca instala Ollama por su cuenta).
6. Si `ollama` existe, intenta `ollama pull llama3.2:3b` y
   `ollama pull bge-m3` (los modelos que `jarvis_local/config.py` usa
   hoy — confirma los nombres exactos ahí antes de escribir el script,
   no los copies de memoria de este documento). Si el pull falla
   (Ollama no está corriendo, sin red), imprime un aviso claro pero NO
   hace fallar el script entero — el usuario puede bajar los modelos
   después.
7. Al final, imprime un mensaje de éxito con el comando exacto para
   arrancar JARVIS (`python -m jarvis_local.cli`, recordando activar el
   venv si la shell del usuario no quedó con `.venv` activo).

**Verificar resultado:**
```bash
bash -n install.sh && echo "sintaxis OK"
test -x install.sh && echo "es ejecutable"
shellcheck install.sh || true
```
(`shellcheck` es best-effort — si no está instalado en el entorno, omite
ese chequeo y dilo en la Sección 4, no bloquees la tarea por eso.)

#### Tarea 3.2 — Crear `Makefile`

**Verificar estado actual:**
```bash
ls Makefile 2>/dev/null || echo "no existe todavía"
```

**Cambio a hacer:** crea un `Makefile` en la raíz con, como mínimo, estos
targets:
- `install`: corre `./install.sh`.
- `run`: corre `.venv/bin/python -m jarvis_local.cli` (si `.venv` no
  existe, imprime un error pidiendo correr `make install` primero, no
  crea el venv silenciosamente ahí).
- `test`: corre
  `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/ -q`.
- `lint`: corre `.venv/bin/python -m ruff check .`.
- `clean`: borra `.venv/` (con un `rm -rf .venv` acotado a esa ruta
  exacta, nunca un `clean` más amplio).
- `.PHONY` declarado para los targets de arriba (ninguno produce un
  archivo con ese nombre).

**Verificar resultado:**
```bash
make -n install && make -n run && make -n test && make -n lint && make -n clean
```
Los 5 deben imprimir el comando que ejecutarían (dry-run), sin error de
"No rule to make target".

#### Tarea 3.3 — Test de humo para `install.sh` y `Makefile`

Por Regla 8 (toda tarea de código lleva su test) — aquí el "código" es un
script de shell y un Makefile, así que el test verifica forma y
contrato, no ejecuta de verdad `apt`/`ollama pull`/instalación real (eso
requeriría red y privilegios que un test no debe asumir).

**Cambio a hacer:** crea `test/test_install_script.py` con, como mínimo:
- Test que `install.sh` existe, es ejecutable, y `bash -n install.sh`
  (vía `subprocess.run`) termina con código 0 (sintaxis válida).
- Test que `install.sh` contiene las verificaciones esperadas (grep de
  cadenas clave como `"3.11"` o la comprobación de versión, `"ollama"`,
  `"requirements.txt"`) — no ejecuta el script, solo confirma que el
  contrato mínimo está presente en el texto.
- Test que `Makefile` existe y contiene los 5 targets (`install:`,
  `run:`, `test:`, `lint:`, `clean:`).
- Test que `make -n install`, `make -n run`, `make -n test`,
  `make -n lint` (vía `subprocess.run(["make", "-n", target], ...)`)
  cada uno termina con código 0.

**Verificar resultado:**
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/test_install_script.py -q
```
Debe quedar en verde. Corre además la suite completa (paso 5 del
Protocolo de la Sección 2) antes de comitear — esta tarea no debe romper
nada existente.

#### Tarea 3.4 — Actualizar `README.md` § "📦 Instalación"

**Verificar estado actual:**
```bash
sed -n '/## 📦 Instalación/,/^## /p' README.md
```

**Cambio a hacer:** al principio de esa sección, agrega la opción rápida
(`git clone ... && cd Jarvis && make install && make run`) como primera
opción recomendada. Conserva los pasos manuales de hoy completos debajo,
bajo un subtítulo como "Instalación manual / diagnóstico" — no los
borres: siguen siendo la referencia si `install.sh` falla en un entorno
no probado. Agrega el enlace a `docs/INSTALADOR_OPCIONES.md` (de la
Tarea 2.2.a) explicando por qué se eligió este enfoque.

**Verificar resultado:**
```bash
grep -n "make install\|INSTALADOR_OPCIONES" README.md
```
Ambos deben aparecer.

#### Tarea 3.5 — Cierre de Fase 3: barrido de consistencia

Antes de marcar la Fase 3 completa en la Sección 4:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/ -q
.venv/bin/python -m ruff check .
bash -n install.sh
make -n install && make -n run && make -n test && make -n lint && make -n clean
```
Todo debe salir en verde/sin error antes de comitear el cierre de fase.

---

### FASE 4 — Instalador Windows + README al día — ✅ AUTORIZADA POR EL USUARIO (2026-10-16), EJECUTAR DE PUNTA A PUNTA

**Origen:** el usuario eligió explícitamente estos dos temas para la Fase 4,
en el chat, el 2026-10-16, respondiendo a una pregunta directa (dos
opciones del menú, ambas marcadas): "Instalador para Windows" y
"Actualizar 'Evolución' del README". Quedan autorizadas de punta a punta
igual que las fases anteriores (Regla 12) — no hace falta volver a
preguntar para empezar, continuar o encadenar estas dos tareas.

#### Tarea 4.1 — Script de instalación guiado para Windows (`install.ps1`)

**Contexto importante, léelo antes de escribir una línea:** este entorno
de desarrollo es Linux — **no hay máquina Windows disponible para probar
el script de verdad**, y no hay `pwsh`/`powershell` instalado aquí para
siquiera validar sintaxis. El CI de Windows de este repo fue **eliminado**
(no arreglado) en el pasado por indiagnosticable sin logs ni máquina — ver
`docs/PLAN_EJECUCION.md` sección J6. Esta tarea tiene la misma limitación
de fondo: se puede escribir el script con cuidado, a partir de los pasos
manuales ya documentados en `README.md` § "📦 Instalación" → "### Windows",
pero **no se puede verificar que corra de verdad en Windows real**. Eso no
es motivo para no hacerla (Regla de `CLAUDE.md`: "si algo no se puede
arreglar del todo... documenta el límite exacto y deja un error
accionable. Nunca finjas que funciona ni inventes un resultado") — se hace
la tarea completa, y se documenta el límite exacto en la Sección 4 y en un
comentario al inicio del propio script, en vez de fingir una verificación
que no ocurrió.

**Verificar estado actual:**
```bash
cd /home/omar/Documentos/Jarvis
ls install.ps1 2>/dev/null || echo "no existe todavía"
sed -n '/### Windows/,/### Linux/p' README.md
which pwsh powershell 2>/dev/null || echo "no hay intérprete de PowerShell en este entorno"
```

**Cambio a hacer:** crea `install.ps1` en la raíz del repo, en PowerShell,
con el mismo contrato y espíritu que `install.sh` (Tarea 3.1) adaptado a
Windows — mismo orden de pasos, mismas reglas duras:
1. Verifica la versión de Python (`python --version` o `py --version`); si
   es menor a 3.11, imprime un error claro y termina con código ≠ 0
   (`exit 1`).
2. Si no existe `.venv\`, lo crea (`python -m venv .venv`).
3. Instala dependencias con el `pip` del venv
   (`.venv\Scripts\pip.exe install -r requirements.txt`) — no asumas que
   el venv quedó "activado" en la sesión de quien llama al script, usa la
   ruta explícita como ya hace `install.sh` en Linux.
4. Verifica si el comando `ollama` existe en `PATH`
   (`Get-Command ollama -ErrorAction SilentlyContinue`). Si no existe,
   imprime el enlace de descarga que el README ya documenta
   (`https://ollama.com/download`) y termina con código ≠ 0. **Nunca
   descarga ni instala Ollama por su cuenta** — mismo criterio que
   `install.sh` (Regla de `install.sh`, punto 5 de la Tarea 3.1): es
   decisión del usuario final.
5. Si `ollama` existe, intenta `ollama pull llama3.2:3b` y
   `ollama pull bge-m3` (mismos modelos que Linux, confirmados en
   `jarvis_local/config.py` y `jarvis_local/storage/semantic.py` — no los
   copies de memoria de este documento, confírmalos de nuevo si cambiaron
   desde la Fase 3). Si el pull falla, imprime un aviso pero no aborta el
   script.
6. Al final, imprime el comando exacto para arrancar JARVIS
   (`.venv\Scripts\python.exe -m jarvis_local.cli`), recordando que hay
   que fijar `$env:PYTHONIOENCODING = "utf-8"` antes (ver el bloque
   Windows actual del README).
7. **Al principio del archivo**, como comentario, deja escrito tal cual:
   que este script no se ha podido ejecutar ni probar en una máquina
   Windows real durante su creación (sin máquina disponible en este
   entorno de desarrollo), que se escribió por análogia exacta con
   `install.sh` (ya probado en Linux) y a partir de los pasos manuales
   documentados en el README, y que agradece un reporte de issue si falla
   en un caso real.

**Verificar resultado:**
```bash
test -f install.ps1 && echo "existe"
grep -n "3.11\|ollama\|requirements.txt\|no se ha podido ejecutar" install.ps1
```
No hay comando de sintaxis real disponible en este entorno (no hay
`pwsh`) — dilo explícitamente en la Sección 4 en vez de omitir el paso en
silencio. Pide al usuario, si tiene acceso a una máquina Windows, que
confirme que corre antes de considerar la tarea "probada en uso real" (no
solo "escrita") — hasta entonces, el estado honesto es "escrito y
razonado, no verificado en Windows real".

#### Tarea 4.2 — README § "📦 Instalación": documentar `install.ps1`

**Verificar estado actual:**
```bash
sed -n '/### Windows/,/### Linux/p' README.md
```

**Cambio a hacer:** en el bloque "### Windows" del README, agrega la
opción rápida con `install.ps1` (análoga a `make install` en Linux —
```powershell
git clone https://github.com/omarhernandezrey/Jarvis.git
cd Jarvis
.\install.ps1
```
) antes de los pasos manuales actuales, que se conservan debajo como
"instalación manual / diagnóstico" (mismo patrón que la Tarea 3.4 en
Linux). Agrega una nota explícita y visible (no escondida en una sola
palabra) de que `install.ps1` no se ha probado en una máquina Windows
real todavía y que los pasos manuales son la vía confirmada mientras
tanto.

**Verificar resultado:**
```bash
grep -n "install.ps1\|no se ha probado" README.md
```

#### Tarea 4.3 — Actualizar "🗺️ Evolución" del README

**Contexto:** la Tarea 1.4 (Fase 1) encontró que esta sección termina en
"Fase 9" sin mencionar trabajo real posterior (el HUD pro como
predeterminado, la revisión de bugs de 2026-10-14) y lo dejó anotado como
hallazgo sin ejecutar (Regla 9 — decisión de alcance). El usuario ya
decidió ahora, explícitamente, que esto se ejecute.

**Verificar estado actual:**
```bash
sed -n '/## 🗺️ Evolución/,/## 📄 Licencia/p' README.md
git log --oneline --diff-filter=A -- hud_pro/__init__.py | tail -3
git log --oneline | grep -iE "severidad|revision-bugs" | head -5
```

**Cambio a hacer:** agrega una entrada nueva "✅ **Fase 10**" (después de
la Fase 9 existente, antes de la línea "💡 Ideas evaluadas y
descartadas") que mencione, en una o dos líneas: el HUD pro (PySide6)
integrado como HUD de escritorio predeterminado (con el legado QML como
respaldo automático — commit `2d61cb0`, 2026-09-25) y la revisión completa
de bugs de 2026-10-13/14 (PRs #4, #6, #7 — alta/media/baja severidad,
todos arreglados). Confirma las fechas y hashes reales con los comandos
de arriba antes de escribirlos — no los copies de memoria de este
documento ni de conversaciones previas sin re-verificar.

**Verificar resultado:**
```bash
grep -n "Fase 10" README.md
```

---

### FASE 5 — Mantenimiento: CHANGELOG y scrapers de empleo — ✅ AUTORIZADA POR EL USUARIO (2026-10-16), EJECUTAR DE PUNTA A PUNTA

**Origen:** a pedido del usuario ("busca cómo podemos mejorar más la
app"), se investigó el repo (deuda J6 de `docs/PLAN_EJECUCION.md`, TODOs
reales, cobertura de tests, dependencias desactualizadas) y se propusieron
4 oportunidades con impacto estimado. El usuario respondió explícitamente,
en el chat (2026-10-16): "soluciona todas prioridad nivel alto" — las dos
de impacto alto quedan autorizadas de punta a punta como esta fase. Las de
impacto medio/bajo (actualizar ~20 dependencias desactualizadas; agregar
`pip-audit` a CI) **no están autorizadas** — no se ejecutan sin que el
usuario las pida explícitamente.

#### Tarea 5.1 — `CHANGELOG.md` desactualizado desde v8.1.0 (2026-09-22)

**Contexto:** el archivo no registraba nada de: Fase 9 — endurecimiento
(`docs/PLAN_EJECUCION.md`, A→J, mergeado `2017ec3` el 2026-09-14), el HUD
pro como predeterminado (commit `2d61cb0`, 2026-09-25), la revisión de
bugs de severidad alta/media/baja (PRs #4, #6, #7, 2026-10-13/14) ni el
instalador guiado de las Fases 1-4 de este mismo documento.

**Verificar estado actual:**
```bash
cd /home/omar/Documentos/Jarvis
cat CHANGELOG.md
git show -s --format="%H %ad %s" 2017ec3 2d61cb0 21ed8b0 b96db46 fa1e6c4
```
Confirma hashes y fechas reales antes de escribir — no los copies de este
documento sin re-verificar, pueden cambiar si la historia de git se
reescribe (no debería, pero confirmá).

**Cambio a hacer:** agrega entradas nuevas entre `[Unreleased]` y
`[8.1.0]`, siguiendo el estilo Keep a Changelog ya usado en el archivo
(Added/Changed/Fixed/Removed, un número de versión semántico por release),
cubriendo en orden cronológico inverso: el instalador guiado (Fases 1-4 de
este plan), la revisión de bugs (PRs #4/#6/#7, con el conteo real de bugs
de los títulos de los PRs, no un número de memoria), el HUD pro como
predeterminado, y la Fase 9 de endurecimiento (resumen de alto nivel,
citando `docs/PLAN_EJECUCION.md` en vez de reescribir sus 1800 líneas).

**Verificar resultado:**
```bash
grep -n "^## \[" CHANGELOG.md
```
Confirma que los números de versión quedan en orden descendente y que no
hay un hueco de fechas obviamente falso.

#### Tarea 5.2 — Verificar en vivo si los scrapers de empleo siguen funcionando

**Contexto:** `jarvis_local/tools/jobs.py` (Selenium contra Computrabajo,
LinkedIn, El Empleo) no se tocó desde agosto; los tests que lo cubren se
saltan en CI por necesitar red/navegador real, así que un cambio de
layout en cualquiera de los 3 portales rompería la función en silencio,
sin que ningún pipeline lo detecte.

**Verificar estado actual:**
```bash
cd /home/omar/Documentos/Jarvis
cat jarvis_local/tools/jobs.py | head -40
grep -rn "live\|@pytest.mark.live" test/test_live_integracion.py | grep -i "job\|empleo\|computrabajo\|linkedin"
```

**Cambio a hacer — esto es una verificación, no necesariamente una
implementación:**
1. Corre los tests `live` de empleo contra los portales reales (requieren
   red real y navegador — confirmar que el entorno lo permite):
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest test/test_live_integracion.py -m live -k "job or empleo or computrabajo or linkedin" -v
   ```
2. **Si pasan de verdad** (resultados reales de los 3 portales, no un
   mock): documenta en la Sección 4 que se confirmó funcionando en vivo
   en esta fecha, con la salida real pegada. No hace falta tocar código.
3. **Si alguno falla** (selector roto, cambio de layout, bloqueo
   anti-bot): arregla la causa raíz en `jobs.py` para ese portal
   específico, con su test actualizado si el test mismo quedó
   desactualizado — no debilites el test para que "pase" (Regla 5). Si
   el bloqueo es anti-bot/CAPTCHA y no hay arreglo razonable sin
   credenciales o infraestructura que no existe en este entorno,
   documenta el límite exacto (qué portal, qué error exacto, por qué no
   se puede arreglar aquí) en vez de fingir que se arregló — regla dura
   de `CLAUDE.md`.
4. Si la tarea toca código (paso 3), corre el protocolo completo de la
   Sección 2 (suite + ruff) antes de comitear.

**Verificar resultado:** la salida real de los tests `live` pegada en la
Sección 4 — nunca un "debería funcionar" sin haberlo corrido de verdad.

---

### FASE 6 — (sin definir todavía)

Esta fase depende de qué priorice el usuario después de cerrar la Fase 5.
**No la rellenes por tu cuenta ni inventes tareas acá.** Si llegaste hasta
este punto con las Fases 1-5 completas en la Sección 4, avísale al usuario
que el plan conocido está terminado y pregúntale qué quiere que entre en
la Fase 6 — este es el único punto de parada legítimo que queda una vez
cerrada la Fase 5, porque no hay ninguna tarea escrita todavía que seguir.

Recordatorio de lo que quedó explícitamente NO autorizado en la Fase 5
(impacto medio/bajo, detectado pero no ejecutado a pedido del usuario):
actualizar ~20 dependencias de `requirements.txt` con versiones más
nuevas disponibles (incluida `cryptography`); agregar `pip-audit` u
otro escaneo de vulnerabilidades a CI. Candidatos naturales para una
Fase 6 si el usuario quiere seguir en la misma línea de mantenimiento.

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

- [x] **Tarea 2.1 — Pregunta sobre el HUD legado.** Respuesta del usuario
      (2026-10-14): "Mantenerlo como red de seguridad" — no se evalúa
      deprecación por ahora. Sin tarea derivada.
- [x] **Tarea 2.2 — Pregunta sobre el instalador.** Respuesta del usuario
      (2026-10-14): "Sí, investigar ahora", con Linux primero. Tarea
      derivada escrita como **Tarea 2.2.a** en la Sección 3 — pendiente
      de ejecutar.
- [x] **Tarea 2.2.a — Investigar opciones de empaquetado (Linux).**
      Fecha: 2026-10-14. Commit: d79e1ee.
      Notas: creado `docs/INSTALADOR_OPCIONES.md` comparando las 3 opciones (script guiado, `.deb`, Makefile/script simple); decisión documentada: script guiado (`install.sh`) + `Makefile`, descartando `.deb` por sobrecosto de mantenimiento. Enlazado desde README.md:169. Verificado con `test -f` y `grep` según protocolo.

### Fase 3

- [x] **Tarea 3.1 — `install.sh`.**
      Fecha: 2026-10-16. Commit: 3c6e6ce.
      Notas: ya existía un `install.sh` viejo (commit 07be29e, agosto) que no cumplía el contrato nuevo — ejecutaba `sudo apt install` y `curl | sh` de Ollama automáticamente. Se reescribió por completo: valida Python >=3.11, crea `.venv`, instala `requirements.txt`, detecta Tkinter/PortAudio/PipeWire y Ollama solo con `command -v`/`pkg-config`/import (nunca instala nada de sistema), imprime el comando `apt install` exacto y sale con error si falta algo, y descarga `llama3.2:3b` + `bge-m3` (confirmados en `jarvis_local/config.py` y `jarvis_local/storage/semantic.py`) como paso best-effort. `bash -n install.sh` y permiso ejecutable verificados.
- [x] **Tarea 3.2 — `Makefile`.**
      Fecha: 2026-10-16. Commit: faca0a5.
      Notas: targets `install`, `run`, `test`, `lint`, `clean` con `.PHONY`. `run` falla con mensaje claro si `.venv` no existe (no lo crea). `make -n` en los 5 targets confirmado sin error.
- [x] **Tarea 3.3 — Test de humo.**
      Fecha: 2026-10-16. Commit: 63cfe66.
      Notas: `test/test_install_script.py` verifica existencia/permiso ejecutable, sintaxis (`bash -n` vía subprocess), presencia de las verificaciones clave (3.11, ollama, requirements.txt), que ninguna línea de código (fuera de echo/printf) ejecute `sudo`/`apt` directamente, los 5 targets del Makefile presentes, y `make -n` en los 4 targets ejecutables. `pytest test/test_install_script.py -q`: 9 passed.
- [x] **Tarea 3.4 — README § Instalación.**
      Fecha: 2026-10-16. Commit: f8ef212.
      Notas: agregada sección "Linux — instalación rápida (recomendada)" con `make install && make run` antes de "### Windows"; pasos manuales de Linux conservados completos bajo "Linux (Ubuntu/Debian) — instalación manual / diagnóstico"; enlace a `docs/INSTALADOR_OPCIONES.md` agregado explicando la elección. `grep` confirma ambas cadenas.
- [x] **Tarea 3.5 — Barrido de cierre de Fase 3.**
      Fecha: 2026-10-16. Commit: (este commit de cierre de Sección 4).
      Notas: suite completa (`pytest test/ -q`) sin FAILED; `ruff check .` → "All checks passed!"; `bash -n install.sh` → OK; `make -n` en los 5 targets sin error. Todo verificado en la misma sesión, salida real pegada arriba en cada tarea.

### Fase 4

- [x] **Tarea 4.1 — `install.ps1` (Windows).**
      Fecha: 2026-10-16. Commit: 1b60023 (+ f56195f para su test de humo).
      Notas: ya existía un `install.ps1` viejo (commit 07be29e, agosto) que no validaba versión de Python numéricamente y bajaba el modelo equivocado (qwen2.5:3b en vez de llama3.2:3b). Se reescribió por analogía exacta con `install.sh`: valida Python >=3.11, crea `.venv`, instala `requirements.txt` con ruta explícita del venv, detecta Ollama solo con `Get-Command` (nunca lo instala), y descarga `llama3.2:3b` + `bge-m3` best-effort. **Límite documentado, no se oculta**: este entorno de desarrollo es Linux, sin máquina Windows ni `pwsh`/`powershell` disponibles — no se pudo ejecutar ni validar sintaxis real del script. El aviso queda escrito al inicio del propio `install.ps1` y repetido en el README (Tarea 4.2). Extendí además `test/test_install_script.py` (Regla 8) para blindar forma/contrato de `install.ps1` igual que `install.sh` — 14 tests, verdes.
- [x] **Tarea 4.2 — README § Instalación (Windows).**
      Fecha: 2026-10-16. Commit: 33cfffd.
      Notas: agregada sección "Windows — instalación rápida" con `.\install.ps1`, con aviso visible (⚠️) de que no está probado en Windows real; pasos manuales conservados debajo como "Windows — instalación manual / diagnóstico". `grep` confirma ambas cadenas.
- [x] **Tarea 4.3 — README § Evolución (Fase 10).**
      Fecha: 2026-10-16. Commit: e6e8461.
      Notas: agregada entrada "✅ Fase 10" después de Fase 9: HUD pro (PySide6) como HUD predeterminado desde el commit `2d61cb0` (2026-09-25, confirmado con `git log --diff-filter=A`) con el legado QML como respaldo, y la revisión de bugs 2026-10-13/14 (PRs #4, #6, #7, confirmados con `git log --merges`). `grep -n "Fase 10"` confirma.
      Hallazgo NO corregido (fuera de alcance exacto de esta tarea, Regla 6): la línea "💡 Ideas evaluadas y descartadas" de esa misma sección todavía dice "Un instalador empaquetado sigue siendo una idea abierta, sin evaluar todavía" — desactualizado desde la Fase 2/3 de este mismo plan. Anotado abajo en "Hallazgos nuevos, no ejecutados".

### Fase 5

- [ ] **Tarea 5.1 — `CHANGELOG.md` al día.** Fecha: ____. Commit: ____. Notas:
- [ ] **Tarea 5.2 — Scrapers de empleo verificados en vivo.** Fecha: ____. Commit: ____. Notas:

### Hallazgos nuevos, no ejecutados

(Cosas que notaste mientras trabajabas en una tarea, que no pedía esa
tarea — anótalas aquí, con el archivo/línea exacto, para que el usuario
decida después si entran a una fase futura. No las ejecutes sin que te lo
pidan — Regla 6.)

- ~~README.md § "🗺️ Evolución": termina en Fase 9...~~ **RESUELTO en Tarea 4.3 (2026-10-16, commit e6e8461)**: se agregó la entrada "Fase 10" con HUD pro y revisión de bugs. Detectado originalmente en Tarea 1.4 (2026-10-14).
- README.md § "🗺️ Evolución", línea "💡 Ideas evaluadas y descartadas": todavía dice "Un instalador empaquetado sigue siendo una idea abierta, sin evaluar todavía" — desactualizado desde que la Fase 2 (Tarea 2.2) y la Fase 3 de este mismo plan evaluaron e implementaron el instalador guiado (`install.sh`/`install.ps1` + `Makefile`). No se corrigió en la Tarea 4.3 porque esa tarea pedía exactamente agregar la entrada de Fase 10, no tocar esta otra línea (Regla 6). Detectado en Tarea 4.3 (2026-10-16).
-
