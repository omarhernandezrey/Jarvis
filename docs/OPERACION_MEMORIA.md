# Hallazgo operativo — degradación por memoria (FASE D · D3)

## El modo de fallo por defecto de este equipo

Con **bge-m3** (embeddings, ~1,3 GB) y **llama3.2:3b** (router/chat, ~2,3 GB)
cargados a la vez, más sus KV-cache (`num_ctx` 4096 del chat + 2048 del
agente) y un escritorio ya pesado (~9 GB de base: navegador, GNOME, etc.), la
RAM útil se agota y el sistema entra en **swap**. A partir de ahí, cada turno
del agente —que hace 1 embed para `confidence()` + 1 embed para
`select_tools()` + 1 llamada a llama— toca los dos modelos y **pasa de
segundos a minutos** (medido: una repetición de 18 peticiones tardó 40+ min;
con los modelos descargados y ~7,5 GB libres, la misma carga baja a minutos).

Esto **no** es un problema de la salida estructurada ni del router: es la
máquina. Y va a volver a pasar en las oleadas **E, F y G**, que añaden más
trabajo por turno (procesos, systemd, ventanas).

### Por qué ocurre (números)

| Componente | RAM aprox. |
| --- | --- |
| Base del escritorio (navegador incluido) | ~9 GB |
| bge-m3 residente | ~1,3 GB |
| llama3.2:3b residente | ~2,3 GB |
| KV-cache (4096 + 2048) + runtime Ollama | ~0,8–1,2 GB |
| **Total** | **~13,5–14 GB de 15,4 GB** |

Cabe con ~1,5 GB de holgura — y cualquier cosa que la consuma (una pestaña
más, el propio Python de un script, un `apt` en E) tumba el margen y arranca
el thrashing. Es un equilibrio inestable, no un fallo puntual.

C4/C5 fijaron `keep_alive: 30m` a propósito (evitar ~10 s de recarga por
turno). En un equipo con RAM de sobra es correcto; en éste, ese pin es justo
lo que provoca la degradación.

## Política para no caer ahí

### 1. Cuándo se descarga bge-m3

bge-m3 solo se usa **al principio del turno** (recuperación + confianza),
antes de la llamada a llama. Después no se vuelve a tocar en ese turno. Luego:

- **Equipo con RAM holgada** (`MemAvailable` > ~3 GB tras cargar ambos):
  mantener el pin de 30 min de ambos. Es lo que hay hoy.
- **Equipo ajustado** (este): tras `select_tools()`, soltar bge-m3 de RAM
  (`keep_alive: 0` en la última llamada a `/api/embed` del turno, o
  `ollama stop bge-m3`). Coste: el turno siguiente paga ~2–3 s de recarga del
  embedding. Barato comparado con 5 min de swap.
- **Nunca durante una batería/medición**: `jarvis_local/eval/` debe correr con
  bge-m3 **descargado desde el principio** si va a hacer >10 turnos seguidos
  (el propio medidor lo hace ahora al desactivar la caché de decisiones; para
  el banco completo, hacer `ollama stop bge-m3` antes).

### 2. ¿Pueden convivir el embedding y el router?

Sí, técnicamente (3,6 GB de modelos en 15 GB). **No** de forma estable junto a
un escritorio de ~9 GB de base. La regla operativa:

- Si `MemAvailable` tras cargar el router baja de **~800 MB**, NO mantener
  bge-m3 residente: hacer retrieval, soltar, y dejar la RAM para llama.
- El respaldo léxico de `retriever.py` (Jaccard de palabras) ya existe para
  cuando bge-m3 no está: es peor recall pero no thrashea. En degradación
  aguda es preferible caer a léxico que quedarse en swap.

### 3. Comprobación barata de que ya estamos en swap

Una sola lectura de `/proc/meminfo` (sin `psutil`, sin fork):

- `MemAvailable` (KB) — si < ~800 MB, no hay sitio para un modelo más.
- `SwapTotal` vs `SwapFree` — si `SwapTotal - SwapFree` > ~200 MB **y** sube
  entre turnos, se está paginando.

Para detectar thrashing **activo** (no solo swap ocupado): `/proc/vmstat`
`pgmajfault` — si el delta en 1 s es > unos cientos, el proceso está
esperando disco por páginas de código/modelo. Eso es lo que convierte un
turno de 20 s en uno de 5 min.

```
mem_available_kb  = int(línea "MemAvailable:" de /proc/meminfo)
swap_usado_kb     = SwapTotal - SwapFree
degradado         = mem_available_kb < 800_000 or swap_usado_kb > 200_000
```

### 4. Que JARVIS avise en vez de solo tardar

Recomendación para **FASE E** (que ya toca procesos y systemd, donde encaja
un monitor de recursos):

- Al arrancar un turno del agente, `_check_memoria()` lee `/proc/meminfo`.
  Si `degradado`, se antepone **una línea** a la respuesta:
  *"Voy a ir lento, señor: la RAM está al límite y el modelo está en swap.
  Cierre alguna aplicación o pídame que quite el modelo de embeddings de
  memoria (`ollama stop bge-m3`)."*
- Opcional: si `degradado` y el turno no necesita recuerdo semántico nuevo,
  saltarse el embed y usar el respaldo léxico ese turno.
- `estado_del_sistema` ya reporta RAM; añadir ahí una señal explícita de
  "modelos en RAM" y "en swap: sí/no" para que el aviso sea consultable.

Nada de esto entra en FASE D (cierra con D5). Queda anotado como entrada de E.

---

## Operativa de permisos y demonios (hallazgos de FASE F, entrada para G)

### 5. Un cambio de grupo/permisos exige reiniciar Claude Code (particularidad de esta máquina)

El proceso de Claude Code **hereda los grupos de cuando arrancó** y no los
recarga. En FASE F, `sudo usermod -aG video omar` (necesario para que
`brightnessctl` escriba sin sudo) no tuvo efecto hasta **reiniciar el propio
proceso** de Claude Code — reiniciar la sesión de escritorio no basta, y
`newgrp`/`sg` no están instalados en este equipo para forzar la recarga.

Regla: cualquier `usermod -aG`, cambio de `sudoers`, o ajuste de permisos que
afecte a lo que JARVIS/Claude Code puede hacer → **salir y volver a entrar en
Claude Code** (`claude --continue`) antes de dar por buena la verificación en
vivo. Comprobación: `id -nG` debe incluir el grupo nuevo.

Va a repetirse en **FASE G**: `ydotool` necesita el grupo `input` (ver §6).
Mismo procedimiento: `usermod -aG input omar` → reiniciar Claude Code →
comprobar `id -nG`.

### 6. FASE G — `ydotool` necesita `ydotoold` + grupo `input` ANTES de codificar

`ydotool` (teclado/ratón sintéticos de G) no funciona a secas:

- requiere el demonio **`ydotoold`** corriendo (normalmente como servicio de
  usuario o de sistema; sin él, todo comando de `ydotool` falla);
- el usuario debe pertenecer al grupo **`input`** (acceso a `/dev/uinput`),
  o hace falta una udev rule que lo conceda.

Resolver esto **antes** de escribir el código de G (instalar, arrancar
`ydotoold`, `usermod -aG input omar`, reiniciar Claude Code por el punto 5),
no a mitad de la implementación. Si no se puede dejar operativo, G se
implementa igual pero se marca NO VERIFICABLE en vivo desde el principio, como
F2/F3.
