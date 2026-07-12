# 🤖 JARVIS Local

**Asistente de IA por voz y texto, 100% local y en español, para Windows 10/11.**

JARVIS corre completamente en tu computador: el modelo de lenguaje (Ollama), el reconocimiento de voz (faster-whisper) y la síntesis de voz funcionan sin enviar tus datos a la nube. Entiende español natural, ejecuta acciones reales en tu PC (abrir aplicaciones, gestionar archivos, usar la terminal) y protege cada acción con un sistema de permisos y confirmaciones.

---

## ✨ ¿Qué es JARVIS?

JARVIS Local es un asistente personal estilo "Iron Man" diseñado para hardware modesto (probado en un Intel i5-6200U con 16 GB de RAM, sin GPU dedicada). Sus principios:

- **Privacidad total**: el LLM (`qwen2.5:3b` vía Ollama) y el STT (faster-whisper) corren offline. Nada sale de tu PC (el TTS con edge-tts es lo único que usa internet, con fallback offline a SAPI5).
- **Español primero**: entiende y responde en español, incluyendo comandos hablados.
- **Seguridad por diseño**: whitelists de carpetas y comandos, niveles de riesgo, plan → confirmación para acciones destructivas, redacción automática de secretos (API keys, tokens, contraseñas) y registro de todas las acciones.
- **Rapidez**: respuestas instantáneas sin pasar por el LLM para saludos, hora, fecha y comandos directos; el modelo se precalienta en segundo plano al arrancar.

## 🚀 ¿Qué hace?

### 💬 Conversación
- Chat en español por texto o por voz, con historial persistente y memoria de contexto.
- Respuestas rápidas (sin LLM) para: saludos, hora, fecha, agradecimientos, despedidas.
- Preguntas complejas van a Ollama (`qwen2.5:3b`) con contexto de la conversación.

### 🗣️ Voz
- **Dictado puntual** (`/voz`): habla y JARVIS transcribe con faster-whisper y responde.
- **Modo continuo** (`/voz continuo`): escucha permanente con *wake word* — di **"Jarvis"** seguido de tu orden, manos libres.
- **Síntesis de voz**: responde hablando con `es-CO-GonzaloNeural` (edge-tts, voz masculina colombiana) o SAPI5 offline como respaldo. Velocidad, volumen y voz configurables.
- Calibración de micrófono y diagnóstico de audio integrados (`/voz calibrar`, `/voz diagnostico`).
- Saludo hablado al arrancar según la hora del día.

### 📱 Aplicaciones — abre CUALQUIER app instalada
- **Índice dinámico**: JARVIS escanea las ~160 aplicaciones de tu menú inicio (Win32 y Microsoft Store) y las abre por nombre: *"abre WhatsApp"*, *"lanza Telegram"*, *"inicia Android Studio"*, *"abre Word"*, *"abre Docker"*...
- **Búsqueda difusa sin acentos**: "notio" encuentra Notion; si hay varias coincidencias abre la mejor y sugiere las demás.
- El índice se cachea en `data/apps_index.json` y se renueva solo cada 7 días (apps nuevas se detectan automáticamente).
- **WSL integrado**: *"abre la terminal de wsl"* / *"abre ubuntu"* abre Ubuntu directamente en `~/personalProjects`.
- Filtra automáticamente desinstaladores, manuales y enlaces web del menú inicio.

### 🌐 Web e información (Fase 4)
- **Sitios web**: *"abre youtube.com"*, *"abre la página de wikipedia"* — abre cualquier sitio en tu navegador.
- **Google**: *"busca vuelos baratos en google"*, *"googlea python 3.14"*.
- **YouTube**: *"reproduce hotel california en youtube"* — busca y reproduce canciones o videos.
- **Clima**: *"¿cómo está el clima en Medellín?"* — clima actual de cualquier ciudad del mundo vía Open-Meteo (sin API key); sin ciudad usa tu ubicación.
- **Ubicaciones**: *"¿dónde queda Tokio?"* — abre el lugar en Google Maps e indica la **distancia desde tu ubicación**.
- **Wikipedia**: *"¿quién es Gabriel García Márquez?"*, *"háblame de Shakira"* — resumen hablado de cualquier persona o tema.
- **Noticias**: *"dame las noticias"* — titulares principales vía RSS de Google News (fuente configurable).
- **WolframAlpha**: *"pregunta a wolfram ..."* — preguntas de datos/cálculo (requiere App ID gratis en `secrets.yaml`); sin configurar, responde el LLM local.

### 🖥️ Escritorio y utilidades (Fase 4)
- **Estado del sistema**: *"estado del sistema"* — uso de CPU, RAM, disco y batería (psutil).
- **Calculadora**: *"calcula 135 menos 234 más 345"* — evaluación **segura** (AST, sin `eval`) con lenguaje natural: más, menos, por, entre, raíz cuadrada de, elevado a...
- **Notas**: *"toma nota comprar café"* — guarda la nota con hora en `Documentos\JARVIS Notas` y la abre en el Bloc de notas.
- **Capturas**: *"toma una captura de pantalla llamada factura"* — guarda PNG con nombre personalizado en `Imágenes\Capturas JARVIS`.
- **Cambiar ventana**: *"cambia de ventana"* — Alt+Tab por voz.
- **Música local**: *"pon música"* — reproduce (aleatorio o por nombre) desde tu carpeta Música.
- **IP**: *"¿cuál es mi ip?"* — IP local y pública.
- **Chistes**: *"cuéntame un chiste"* — 100% offline.
- **Ocultar archivos**: *"oculta los archivos de <carpeta>"* / *"muestra los archivos ocultos de <carpeta>"* — con plan + confirmación, solo en carpetas permitidas.

### ✉️ Correo y calendario (Fase 4, requieren configuración)
- **Enviar correos**: *"envía un correo a omar@... asunto Reunión mensaje Nos vemos mañana"* — SMTP con contraseña de aplicación en `secrets.yaml`; **siempre pide `/confirmar`** antes de enviar. Soporta contactos por nombre.
- **Google Calendar**: *"mis próximos eventos"* — lista tus eventos (OAuth opcional, ver `secrets.example.yaml`).
- Las credenciales viven en `secrets.yaml` / `credentials.json`, ambos **fuera de git** (.gitignore).

### 💼 Empleo y navegador automatizado (Fase 5)
- **Búsqueda de empleo multi-portal**: *"busca trabajo de desarrollador en Bogotá"*, *"hay vacantes de vendedor en Cali"* — JARVIS consulta **Computrabajo y LinkedIn en paralelo** (~2 s) y te lee las 8 ofertas **más recientes primero**, con fuente, empresa, ubicación, salario, modalidad y antigüedad.
- **Solo lo relevante**: filtra el ruido (buscar "desarrollador" no te trae "auxiliar de cocina") y elimina ofertas duplicadas entre portales.
- **Abrir una oferta**: *"abre la oferta 2"* — la abre en tu navegador.
- **Los tres portales**: *"muéstrame las ofertas"* — abre Computrabajo, **El Empleo** y LinkedIn, cada uno en su pestaña, con tu búsqueda ya aplicada.
- **Navegador controlado (Selenium)**: *"navega a github.com"* / *"cierra el navegador"* — JARVIS maneja su propia ventana de Chrome, que queda abierta para que sigas navegando.
- Sin API key ni credenciales: `requests` + Selenium Manager (descarga el chromedriver solo).

> **Nota sobre El Empleo**: su buscador solo filtra desde el JavaScript del propio sitio — el HTML que sirve trae siempre un listado genérico, así que no es posible leer sus resultados filtrados por scraping. Por eso El Empleo se abre en el navegador (donde sí funciona) en vez de leerse en voz alta.

### 📁 Archivos
- Listar, buscar, crear (archivos y carpetas), copiar, mover, renombrar y ver metadatos.
- Solo dentro de carpetas permitidas (Documentos, Descargas, Escritorio, Música, Imágenes, Videos, OneDrive) con validación contra escapes de ruta.
- Borrado siempre requiere plan + confirmación explícita (`/confirmar`).

### ⌨️ Terminal
- Planifica comandos de PowerShell (`/terminal plan <cmd>`) y los ejecuta solo tras confirmación.
- Bloquea patrones peligrosos: `Invoke-Expression`, `Remove-Item -Force`, scripts `.ps1/.bat/.cmd`, etc.

### 🧠 Memoria
- `/memoria guardar <texto>` — guarda datos que quieres que JARVIS recuerde (hasta 100).
- `/memoria usar <id>` — activa memorias como contexto de la conversación (hasta 5 a la vez).
- Listar, buscar, borrar y limpiar memorias; borrar siempre pide confirmación.
- Historial de conversación persistente entre sesiones (`/historial`).

### 🖥️ Interfaces
- **CLI** (principal): `python -m jarvis_local.cli`
- **Web** (`/ui`): interfaz en el navegador servida localmente.
- **Escritorio** (`/desktop`): ventana nativa.

### 🛡️ Seguridad
| Mecanismo | Descripción |
|---|---|
| Niveles de riesgo | READ (ejecuta directo) · EXECUTE (apps) · WRITE/DELETE (plan + confirmación) |
| Whitelist de carpetas | Solo opera dentro de tus carpetas de usuario |
| Comandos bloqueados | Patrones destructivos de PowerShell rechazados siempre |
| Redacción de secretos | API keys, tokens JWT, contraseñas y llaves privadas se censuran antes de llegar al LLM o a los logs |
| Auditoría | Toda acción queda en `logs/actions.log` |
| Planes | `/plan` muestra lo pendiente; `/confirmar` ejecuta; `/cancelar` aborta |

---

## 📦 Instalación

### Requisitos
- Windows 10/11
- Python 3.9+ (probado con 3.14)
- [Ollama](https://ollama.com/download/windows) instalado y corriendo
- Micrófono (opcional, para voz)

### Pasos

> **Importante**: el paquete se importa como `jarvis_local`, así que clona el repo dentro de una carpeta con ese nombre y ejecuta desde la carpeta padre.

```powershell
# 1. Clonar el repositorio como "jarvis_local" dentro de tu carpeta de trabajo
mkdir mi-workspace; cd mi-workspace
git clone https://github.com/omarhernandezrey/Jarvis.git jarvis_local

# 2. Instalar dependencias
pip install -r jarvis_local\requirements.txt

# 3. Descargar el modelo LLM (~1.9 GB, solo CPU)
ollama pull qwen2.5:3b

# 4. Arrancar JARVIS (desde la carpeta padre)
$env:PYTHONIOENCODING = "utf-8"
python -m jarvis_local.cli
```

> **Primera ejecución**: la carga inicial del modelo puede tardar 2–5 minutos en CPU modesta. JARVIS precalienta el modelo en segundo plano, así que puedes usar los comandos rápidos de inmediato.

---

## 🎮 Uso

### Lenguaje natural (texto o voz)

| Dices... | JARVIS hace... |
|---|---|
| "abre whatsapp" / "abre word" / "lanza telegram" | Abre cualquier app instalada |
| "abre la terminal de wsl" | Ubuntu en `~/personalProjects` |
| "abre chrome" | Apps de la whitelist clásica |
| "lista los archivos de Documentos" | Lista archivos (solo lectura) |
| "busca informe.pdf en Descargas" | Busca archivos |
| "crea una carpeta llamada Proyectos en Documentos" | Plan + confirmación |
| "ejecuta dir" | Planifica comando de terminal |
| "¿qué hora es?" / "hola jarvis" | Respuesta instantánea sin LLM |
| cualquier otra pregunta | Conversación con el LLM local |

### Comandos del CLI

```
/ayuda                    Ayuda completa
/estado                   Estado de Ollama y voz
/limpiar                  Borrar historial
/historial [limpiar]      Ver o borrar historial

/voz                      Dictar una orden por micrófono
/voz continuo             Modo manos libres con wake word "Jarvis"
/voz continuo detener     Detener modo continuo
/voz on | off             Activar/desactivar respuestas habladas
/voz calibrar             Calibrar ruido del micrófono
/voz diagnostico          Diagnóstico del sistema de voz
/voz voces | voz <n>      Listar/elegir voz TTS
/voz velocidad <120-250>  Velocidad de habla
/voz volumen <0.0-1.0>    Volumen

/archivos listar|buscar|crear-archivo|crear-carpeta|copiar|mover|renombrar|borrar-plan|info
/apps listar              Apps de la whitelist con estado
/apps abrir <nombre>      Abrir app (whitelist o cualquier instalada)
/terminal plan <cmd>      Planificar comando PowerShell

/plan                     Ver plan pendiente
/confirmar                Ejecutar plan pendiente
/cancelar                 Cancelar plan pendiente

/memoria guardar|listar|usar|dejar|activas|buscar|borrar|limpiar
/ui                       Interfaz web
/desktop                  Interfaz de escritorio
salir                     Salir
```

---

## 🏗️ Arquitectura

```
jarvis_local/  (este repo)
├── cli.py                 # Punto de entrada CLI (chat + comandos /)
├── jarvis.py              # Orquestador: intents → herramientas → LLM
├── fast_response.py       # Respuestas instantáneas sin LLM
├── config.py / config.yaml# Configuración (modelo, voz, seguridad, logs)
├── ollama_client/         # Cliente HTTP de Ollama
├── intent/                # Parser de lenguaje natural en español
│   └── parser.py          #   detecta abrir apps, archivos, comandos...
├── tools/
│   ├── apps.py            # Abrir aplicaciones (whitelist + índice)
│   ├── app_index.py       # Índice dinámico de apps instaladas (Get-StartApps)
│   ├── files.py           # Operaciones de archivos con whitelist
│   └── terminal.py        # Comandos PowerShell con plan/confirmación
├── safety/
│   ├── policy.py          # ActionPlan, niveles de riesgo, confirmaciones
│   ├── permissions.py     # Whitelists de carpetas, apps y comandos
│   ├── secrets.py         # Redacción de API keys/tokens/contraseñas
│   └── logger.py          # Log de acciones y errores
├── voice/
│   ├── stt.py             # faster-whisper (español, calibración de ruido)
│   ├── tts.py             # edge-tts (es-CO-Gonzalo) + fallback SAPI5
│   ├── continuous.py      # Escucha continua con wake word "Jarvis"
│   └── audio_devices.py   # Detección de micrófonos
├── storage/               # Historial y memorias persistentes (JSON)
├── memory_context/        # Memorias activas inyectadas al contexto del LLM
├── ui/                    # Interfaz web (server.py) y escritorio (desktop.py)
└── test/                  # 237 tests (pytest)
```

**Flujo de una orden**: entrada (texto/voz) → `fast_response` (¿respuesta instantánea?) → `intent/parser` (¿es una acción?) → herramienta con `ActionPlan` según riesgo (READ ejecuta, WRITE/DELETE piden `/confirmar`) → si no es acción, chat con Ollama → respuesta por texto y opcionalmente por voz.

## 🧰 Stack

| Componente | Tecnología |
|---|---|
| LLM | Ollama + qwen2.5:3b (1.9 GB, CPU) |
| STT | faster-whisper (modelo `small`, int8) |
| TTS | edge-tts `es-CO-GonzaloNeural` · fallback pyttsx3/SAPI5 |
| Audio | sounddevice (16 kHz) |
| Lenguaje | Python 3.9+ |
| Plataforma | Windows 10/11 |

## 🧪 Tests

```powershell
# desde la carpeta padre
python -m pytest jarvis_local/test -q
```

**237 tests** cubren: configuración, cliente Ollama, parser de intents, permisos, política de seguridad, secretos, archivos, apps, índice de apps, terminal, voz, memoria y almacenamiento.

## 🗺️ Roadmap

- ✅ **Fase 1**: Chat local con Ollama + configuración + historial
- ✅ **Fase 2**: Herramientas (archivos, apps, terminal) + seguridad
- ✅ **Fase 3**: Voz (STT/TTS), modo continuo con wake word, memorias, UI web/desktop, índice dinámico de apps, WSL
- ✅ **Fase 4**: Web (sitios, Google, YouTube), clima, ubicaciones y distancias, Wikipedia, noticias, estado del sistema, calculadora segura, notas, capturas, música, correo, WolframAlpha, Google Calendar, ocultar archivos, chistes, IP, cambiar ventana
- ✅ **Fase 5**: Navegación web automatizada (Selenium) + búsqueda de empleo en Computrabajo

---

*Proyecto personal de Omar Hernández Rey.*
