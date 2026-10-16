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

### FASE 4 — (sin definir todavía)

Esta fase depende de qué priorice el usuario después de cerrar las Fases
1-3. **No la rellenes por tu cuenta ni inventes tareas acá.** Si llegaste
hasta este punto con las Fases 1, 2 y 3 completas en la Sección 4, avísale
al usuario que el plan conocido está terminado y pregúntale qué quiere que
entre en la Fase 4 — este es el único punto de parada legítimo que queda
una vez cerrada la Fase 3, porque no hay ninguna tarea escrita todavía que
seguir.

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

### Hallazgos nuevos, no ejecutados

(Cosas que notaste mientras trabajabas en una tarea, que no pedía esa
tarea — anótalas aquí, con el archivo/línea exacto, para que el usuario
decida después si entran a una fase futura. No las ejecutes sin que te lo
pidan — Regla 6.)

- README.md § "🗺️ Evolución": termina en Fase 9, pero existieron trabajos posteriores reales (HUD pro por defecto en jarvis_local/ui/hud_select.py; revisión de bugs 2026-10-14). No se agregó entrada por Regla 9 (decisión de alcance, no simple error de dato). Decidir si extender Evolución para registrar Fase 10/bug review o dejarlo. Detectado en Tarea 1.4 (2026-10-14).
-
