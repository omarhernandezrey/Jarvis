# Auditoría del router de intención — diagnóstico y corrección

Problema reportado: *"el asistente no interpreta correctamente lo que el usuario
pide"*. No fallaban las herramientas, fallaba el **razonamiento sobre qué
ejecutar**.

Todo lo que sigue está medido en el equipo real (Intel i5-6200U, 16 GB, sin GPU)
con la batería de `jarvis_local/eval/` (63 casos). Ningún número es estimado.

---

## Fase 1 — Auditoría

### Mapa del flujo de decisión (antes)

```
mensaje
  ├─ 1. fast_response.py   regex de cortesía          (0 s)
  ├─ 2. intent/parser.py   regex por intención        (0 s)
  ├─ 3. agent/             selector léxico → LLM      (~20 s)
  └─ 4. chat               LLM sin herramientas       (~60 s)
```

| Aspecto | Estado encontrado |
|---|---|
| Tool calling | **Sí, nativo** (`/api/chat` con `tools`). No era parsing de texto libre. |
| Modelo | `qwen2.5:3b`, temperatura 0.1 para decisión. Correcto. |
| Esquemas | JSON Schema por herramienta, bien formados. |
| Few-shot | **Ausentes**. El prompt eran reglas abstractas sin un solo ejemplo. |
| Contexto conversacional | Se pasaba historial al LLM, pero **el parser no lo veía**. |
| Validación de salida | Parcial: se filtraban argumentos, pero **sin reintento**. |
| Baja confianza | **No existía**. Ante duda, ejecutaba o callaba. |
| Logging de decisiones | **No existía**. Imposible auditar un fallo. |

### Causa raíz

**No era el tool calling ni el modelo. Era que el LLM casi nunca llegaba a
razonar sobre la frase**: dos capas anteriores la interceptaban.

**1. El portón léxico (causa principal).** `agent/selector.py` decidía qué
herramientas ofrecerle al modelo con un diccionario de palabras clave. Si
ninguna coincidía, devolvía **cero herramientas y el agente ni se invocaba**.
Fallo silencioso:

```
"estoy buscando chamba de contador"  → 0 herramientas → el LLM nunca vio la frase
"estoy buscando pega de diseñador"   → 0 herramientas → el LLM nunca vio la frase
"y en Bogotá?"                       → 0 herramientas → el LLM nunca vio la frase
```

Añadir sinónimos ("chamba", "pega", "camello"…) no arregla esto: siempre faltará
una palabra. Es fragilidad disfrazada de cobertura.

**2. Falsos positivos del parser.** Regex laxas secuestraban frases y las
enrutaban mal, con el LLM fuera del circuito:

```python
r'(?:lista|listar|muestra|mostrar|ver?)\s+...(?:archivos|...)?\s*(?:de|en)?\s+(.*)'
#                                ^^^^ sin \b            ^ objeto opcional
```
`"va a llover en Medellín"` → la sílaba **-ver-** de "llo**ver**" hacía match →
`listar_archivos(path="Medellín")`. Igual `"busca"` a secas → `buscar_archivo`.

**3. Sin manejo de negación, ambigüedad ni multi-acción.**
`"no abras Chrome"` → abría Chrome. `"hazlo"` → silencio.
`"dime el clima y luego abre Chrome"` → solo el clima; la segunda mitad se perdía.

---

## Fase 2 — Batería de pruebas

`jarvis_local/eval/cases.py`: 63 casos en 11 categorías (directos, coloquiales,
ambiguos, encadenados, negación, fuera de alcance, 5-6 variantes por función
crítica, y contextuales con anáfora).

El arnés (`eval/harness.py`) recorre la cascada real pero **sustituye el ejecutor
por un doble**: mide qué *decide* el sistema sin abrir aplicaciones.

---

## Fase 3 — Correcciones

### 1. Recuperación semántica de herramientas (`agent/retriever.py`)

Reemplaza el portón léxico. Embebe la descripción + ejemplos de uso de cada
herramienta (bge-m3, local) y recupera las k más cercanas al mensaje por
similitud coseno. *"Chamba"* y *"empleo"* quedan próximos en el espacio
vectorial aunque no compartan una letra.

**Recall@6 medido: 100%** — la herramienta correcta siempre llega al LLM.

Un hallazgo importante de la calibración: **no existe un umbral que separe
limpiamente peticiones de charla** (peticiones bajan a 0.44; charla sube a 0.50).
Conclusión de diseño: *el retriever no decide si hay acción, solo recupera
candidatas*. **La decisión la toma el LLM**, que tiene la opción explícita de no
llamar ninguna herramienta.

### 2. Parser de alta precisión

Las regex ahora exigen delimitadores de palabra (`\b`) y el objeto explícito.
Y cede al agente lo que estructuralmente no puede resolver:

- **multi-acción** (`es_multi_accion`): resuelve una sola intención; ante dos,
  ejecutaba la primera y descartaba la otra en silencio.
- **anáforas** (`es_anaforica`): no tiene historial, así que inventaba los
  argumentos ("la segunda" lo tomaba por el nombre de una aplicación).

### 3. Prompt con few-shot (`agent/prompts.py`)

Ocho ejemplos, uno por cada categoría que fallaba: negación, orden vaga, fuera
de alcance, coloquial, doble negación con acción real.

### 4. Validación estricta con reintento (`agent/loop.py`)

Si el modelo inventa una herramienta u omite argumentos obligatorios, se le
devuelve el error concreto y se reintenta (máx. 2). Antes: fallo silencioso.

### 5. Desambiguación explícita

Una **orden sin objeto** ("hazlo", "abre eso") no es charla: se pregunta, en vez
de adivinar o quedarse mudo. Se distingue de la conversación real, que sí va al
chat.

### 6. Log estructurado (`agent/decision_log.py`)

Cada decisión → `logs/decisions.jsonl` (entrada, confianza, herramientas,
resultado). `python -m jarvis_local.agent.decision_log` da el resumen.

### 7. Encadenado por división de cláusulas

Primer intento: devolverle al modelo el resultado de la primera herramienta para
que pidiera la segunda. **Medido: 0/2.** El 3B no encadena, ni siquiera con el
resultado delante.

Solución: `dividir_acciones()` parte la petición por el conector y el agente
resuelve cada cláusula, pasándole el resultado de la anterior como contexto.
Determinista, y no depende de una capacidad que el modelo local no tiene.

```
"dime el clima de Cali y después abre Chrome"
  → ["dime el clima de Cali", "abre Chrome"]
```

### 8. Menos opciones, mejores decisiones (TOP_K 6 → 4)

Contraintuitivo pero medido: con 6 herramientas ofrecidas, en *"ando aburrido,
dime algo divertido"* el retriever ponía `contar_chiste` primero (0.73) y el
modelo elegía `wikipedia` (0.45), que solo estaba ahí de relleno. Menos opciones
= menos formas de equivocarse.

### 9. Anáfora solo cuando falta el objeto

Primera versión: toda frase que empezara por conector iba al agente. Eso mandó
*"ahora abre whatsapp"* (que nombra su objeto y se resolvía sola en el parser) al
camino lento, y el modelo pequeño fallaba. Ahora solo son anáforicas las que
apuntan a algo **sin nombrarlo**: *"ábreme la segunda"*, *"y en Bogotá?"*.

---

## Fase 4 — Resultados

### Precisión del enrutamiento (63 casos, mismo hardware, mismo modelo)

| Categoría | Antes | Después |
|---|---|---|
| Directos | 100% | 100% |
| Coloquiales | 80% | **87%** |
| **Ambiguos** | **25%** | **100%** |
| **Negación** | **67%** | **100%** |
| **Encadenados** | **0%** | **100%** |
| Fuera de alcance | 100% | 100% |
| Variantes de clima | 83% | **100%** |
| Variantes de empleo | 80% | **100%** |
| Variantes de app / sistema | 100% | 100% |
| Contextuales | 33% | 33%¹ |
| **TOTAL** | **79%** | **94%** |

<sub>¹ Inestable entre corridas (33–67%): el 3B a veces resuelve la anáfora y a
veces no, con la misma entrada y temperatura 0.1.</sub>

El salto no viene de un modelo mejor: es **el mismo qwen2.5:3b**. Viene de que
ahora el modelo *llega a ver* la petición y decide sobre un catálogo limpio.

### Los 4 fallos que quedan

| Caso | Diagnóstico |
|---|---|
| *"necesito revisar mis correos"* | **Límite del modelo.** Se le ofrece la herramienta correcta y no la llama. **Falla igual en el 7B.** |
| *"se me antoja escuchar algo de música"* | Ídem: **falla igual en el 7B.** |
| *"ábreme la segunda"*, *"y en Bogotá?"* | Anáfora: el 3B resuelve el referente de forma inconsistente entre corridas. |

Ninguno es ya un fallo de arquitectura: en los cuatro, **el sistema le entrega al
modelo la herramienta correcta y el contexto necesario**. Lo que falla es la
decisión del modelo. Ese es el techo real del 3B.

### ¿Es el modelo de 3B el techo? (medido, 12 casos difíciles)

| Modelo | Aciertos | Latencia media |
|---|---|---|
| qwen2.5:3b | 75% | **39.6 s** |
| qwen2.5:7b | 83% | **77.6 s** |

**+8 puntos de precisión a cambio de 2x de latencia.**

**Recomendación honesta**: en este hardware (CPU, sin GPU), **mantener el 3B**.
78 segundos para decidir una acción es inusable. El 7B es la opción correcta *si
se añade una GPU*; con una gama media, su latencia bajaría a pocos segundos y los
+8 puntos serían gratis. Cambiar el modelo es una decisión de hardware, no de
software.

Y el dato que importa: **las causas raíz eran arquitectónicas, no de capacidad**.
Arreglarlas subió la precisión sin tocar el modelo. El 3B tiene un techo real,
pero no era el cuello de botella principal.

---

## Recomendaciones pendientes

1. **GPU + qwen2.5:7b**: el salto de calidad está medido y disponible.
2. **Dos casos fallan en ambos modelos** ("se me antoja escuchar algo de música",
   "necesito revisar mis correos"): el modelo recibe la herramienta correcta y
   aun así no la llama. Se mitiga con few-shot específicos.
3. **Curar el log de decisiones**: `decisions.jsonl` con uso real es el mejor
   material para ampliar los ejemplos del retriever.
