# 🤖 JARVIS Local

**Asistente de IA por voz, 100% local y en español, para Windows y Linux.**
Entiende lenguaje natural, decide qué herramientas usar y ejecuta acciones reales en tu PC — sin enviar tus datos a la nube.

[![Tests](https://github.com/omarhernandezrey/Jarvis/actions/workflows/tests.yml/badge.svg)](https://github.com/omarhernandezrey/Jarvis/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-772%20passing-brightgreen)
![Offline](https://img.shields.io/badge/LLM-100%25%20local-orange)
![OS](https://img.shields.io/badge/OS-Windows%20%7C%20Linux-informational)

---

## 📋 Plan de Mejoras en Curso

> **Si eres un agente IA o desarrollador**, lee obligatoriamente [`PLAN_MAESTRO.md`](PLAN_MAESTRO.md) antes de hacer cualquier cambio. Es el plan maestro activo (eficacia de cada funcionalidad), con tareas en orden estricto: una rama por tarea, batería de pruebas completa hasta verde, y merge a `main`.
>
> [`IMPLEMENTACION_DE_MEJORAS.md`](IMPLEMENTACION_DE_MEJORAS.md) está archivado (86/86 tareas completadas).

Plan activo: **PLAN_MAESTRO** | Tareas: 26 | Fases: 5 (0, A, B, C, D) | Base: [`docs/AUDITORIA_2026-09.md`](docs/AUDITORIA_2026-09.md)

---

## ✨ Qué lo hace distinto

No es un menú de comandos con voz: es un **agente**. El modelo de lenguaje (que corre en tu propia máquina) recibe el catálogo de herramientas y **decide cuál usar**, así que entiende frases que nadie programó:

> *"necesito saber si va a llover por allá en Cartagena"* → consulta el clima
> *"qué tal anda mi máquina de recursos"* → reporta CPU, RAM y batería
> *"me consigues unas vacantes de programador por Medellín"* → busca empleo

Y **recuerda por significado**: le dices *"soy alérgico a los mariscos"*, y semanas después, ante *"¿puedo comer camarones?"*, lo recupera aunque no compartan ni una palabra.

| | |
|---|---|
| 🔒 **Privado** | LLM (llama3.2:3b), voz (faster-whisper) y embeddings (bge-m3) corren offline. Nada sale de tu PC. |
| 🇪🇸 **En español** | Pensado en español, no traducido. Voz masculina neural latina. |
| 🛡️ **Seguro** | Whitelists, niveles de riesgo y plan→confirmación. El modelo **nunca** borra ni envía nada por su cuenta. |
| ⚡ **Rápido donde importa** | Cascada de 4 capas: lo trivial responde en 0 s; solo lo complejo llega al LLM. |
| 💪 **Modesto** | Diseñado para un i5-6200U sin GPU. Si corre ahí, corre en cualquier lado. |
| 🐧 **Multiplataforma** | Mismo código en Windows 10/11 y Linux (probado en Ubuntu/GNOME): terminal, apps, volumen, energía y portapapeles usan la API nativa de cada SO. |

---

## 🧠 Arquitectura: cascada de 4 capas

Cada mensaje baja por esta cascada y se detiene en la primera capa que lo resuelve. El costo sube en cada escalón, así que lo barato se resuelve barato:

| Capa | Qué resuelve | Latencia real* |
|---|---|---|
| 1. **Respuestas instantáneas** | saludos, hora, fecha, gracias | **~0 s** (<1 ms) |
| 2. **Parser determinista** | frases conocidas: "abre whatsapp" (~0,2 ms de enrutado); "clima en Bogotá" incluye la llamada HTTP | **~1,6 s** |
| 3. **Agente (tool calling)** | lenguaje libre que ningún patrón cubre: "búscame un chiste de programadores" | **35–70 s** |
| 4. **Chat con el LLM** | conversación, razonamiento, opinión | **~1,5 s** con modelo caliente, **~60 s** en frío |

<sub>*Medido en el equipo de desarrollo (Intel i5-6200U, 16 GB RAM, sin GPU) con Ollama caliente, tras las Fases A–C. La capa 3 depende del hardware: un modelo 3B haciendo *tool calling* en una CPU de 2 núcleos es lento y variable. El plan de mejora ataca esto **sacando frases del agente**: "va a llover en Cartagena" pasó de ~90 s (agente) a **1,5 s** (parser→clima); "cómo anda la máquina" de ~110 s a **0,02 s** (parser→tool). Detalle en [`docs/AUDITORIA_2026-09.md`](docs/AUDITORIA_2026-09.md).</sub>

```
                                    ┌─ tools/ ─────────────────┐
  Voz ──► STT ──┐                   │ apps · archivos · web    │
                ├──► ¿Instantánea?  │ clima · empleo · correo  │
  Texto ────────┘         │ no      │ sistema · notas · ...    │
                          ▼         └──────────▲───────────────┘
                   ¿Parser la reconoce? ───────┤
                          │ no                 │
                          ▼                    │
                   Agente: el LLM elige ───────┤
                          │ ninguna encaja     │
                          ▼                    │
                   Chat + memorias recordadas ─┘
                          │
                          ▼
                   TTS por frases (habla mientras genera)
```

---

## 🚀 Todo lo que hace

<details open>
<summary><b>💬 Conversación y memoria</b></summary>

- Chat en español por texto o voz, con historial persistente entre sesiones.
- **Memoria semántica**: recuerda por significado, no por palabras. *"¿en qué trabajo?"* recupera *"soy desarrollador frontend en Bogotá"*.
- Recuerdo automático: las memorias relevantes entran solas al contexto (`/memoria guardar <dato>` para enseñarle algo).
- Respuestas instantáneas sin gastar el LLM: saludos, hora, fecha, agradecimientos.
</details>

<details open>
<summary><b>🗣️ Voz</b></summary>

- **Modo manos libres** (`/voz continuo`): di **"Jarvis"** y luego tu orden.
- **Habla mientras piensa**: pronuncia la primera frase mientras el modelo sigue escribiendo. La espera hasta la primera palabra bajó de **93 s a 38 s**.
- Dictado puntual (`/voz`), calibración de micrófono y diagnóstico de audio.
- TTS: voz neural masculina latina (edge-tts) con respaldo offline (SAPI5 en Windows, espeak-ng en Linux).
</details>

<details open>
<summary><b>📱 Aplicaciones y sistema</b></summary>

- Abre **cualquiera de las apps instaladas** por nombre, con búsqueda difusa: *"abre whatsapp"*, *"lanza android studio"*, *"abre notion"* — en Windows via `Get-StartApps`, en Linux escaneando `.desktop` (incluye Snap y Flatpak).
- **WSL** (solo Windows): *"abre la terminal de wsl"* → Ubuntu directamente en `~/personalProjects`.
- Estado del sistema: CPU, RAM, disco, batería.
- Comandos de terminal: PowerShell en Windows, bash en Linux — con patrones destructivos bloqueados en ambos.
- Capturas de pantalla con nombre, Alt+Tab por voz, música local.

> **Nota honesta sobre Linux/Wayland**: minimizar todas las ventanas, "encajar" la ventana activa y Alt+Tab por comando dependen de la API de ventanas de Windows, que Wayland no expone por diseño sin una extensión de GNOME instalada. En Linux, JARVIS lo dice claramente en vez de fingir que lo hizo — todo lo demás (apps, volumen, energía, portapapeles, capturas) funciona igual que en Windows.
</details>

<details open>
<summary><b>🌐 Web e información</b></summary>

- Sitios web, búsquedas en Google, reproducir en YouTube.
- **Clima** de cualquier ciudad (Open-Meteo, sin API key).
- **Ubicaciones**: abre el lugar en Maps y calcula la **distancia desde donde estás**.
- **Wikipedia**: *"¿quién es Gabriel García Márquez?"*.
- **Noticias**: titulares del día.
- **Calculadora segura** (AST, sin `eval`) con lenguaje natural (*"raíz cuadrada de 144"*, *"15% de 80"*, *"5 al cubo"*) y **ecuaciones lineales resueltas en local**: *"resuelve x + 135 - 234 = 345"* → *x = 444*. **WolframAlpha** para lo que no se puede en local (derivadas, sistemas).
- **Navegador automatizado** (Selenium): JARVIS controla su propia ventana de Chrome.
- **Spotify**: *"pon bohemian rhapsody"* → la busca y reproduce con tu cuenta (Premium) en cualquier dispositivo Spotify Connect activo. Setup en [`docs/spotify.md`](docs/spotify.md). Si el token caduca, lo dice claro y te da el comando exacto (`--reauth-spotify`) en vez de fallar en silencio.
</details>

<details open>
<summary><b>💼 Búsqueda de empleo</b></summary>

- *"busca trabajo de desarrollador en Bogotá"* → consulta **Computrabajo y LinkedIn en paralelo** (~2 s) y lee las 8 ofertas **más recientes primero**, con empresa, salario, ubicación y antigüedad.
- Filtra el ruido (buscar "desarrollador" no trae "auxiliar de cocina") y deduplica entre portales.
- *"abre la oferta 2"* la abre; *"muéstrame las ofertas"* abre los 3 portales en pestañas (incluido **El Empleo**).

> **Nota honesta sobre El Empleo**: su buscador solo filtra desde el JavaScript del sitio — el HTML que sirve trae siempre un listado genérico, así que sus resultados no se pueden leer por scraping. Por eso se abre en el navegador, donde sí funciona.
</details>

<details open>
<summary><b>📁 Archivos, correo y calendario</b></summary>

- Listar, buscar, crear, copiar, mover, renombrar y borrar (solo en carpetas permitidas).
- Ocultar/mostrar archivos de una carpeta.
- **Correo**: *"envía un correo a Omar asunto Reunión mensaje Nos vemos mañana"* — SMTP, **siempre pide confirmación**.
- **Google Calendar**: *"mis próximos eventos"*. Refresca el token solo; si hace falta re-autorizar, lo indica con el comando exacto (`--reauth-calendar`).
- Notas rápidas con fecha y hora, en el Bloc de notas.
</details>

---

## 🛡️ Seguridad

Un agente que puede ejecutar acciones en tu PC necesita límites reales, no buenas intenciones:

| Mecanismo | Qué garantiza |
|---|---|
| **Plan → confirmación** | Borrar, enviar correos u ocultar archivos **siempre** requiere `/confirmar`. El modelo *nunca* ejecuta acciones irreversibles por su cuenta. |
| **Whitelist de carpetas** | Solo opera en tus carpetas de usuario, con validación contra escapes de ruta. |
| **Comandos bloqueados** | Windows: `Invoke-Expression`, `Remove-Item -Force`, scripts `.ps1/.bat`. Linux: `sudo`, `dd`, `mkfs`, bombas fork, pipe a un shell (`curl \| sh`). Rechazados siempre, sin importar el orden de los argumentos. |
| **Redacción de secretos** | API keys, tokens y contraseñas se censuran *antes* de llegar al modelo o a los logs. |
| **Memorias como contexto** | Lo recordado entra marcado como datos, nunca como instrucciones (defensa contra inyección de prompt). |
| **Credenciales fuera de git** | `secrets.yaml`, `credentials.json` y `token.json` están en `.gitignore`, y el **CI falla** si alguien intenta versionarlos. |
| **Auditoría** | Toda acción queda registrada en `logs/actions.log`. |

---

## 📦 Instalación

**Requisitos**: Windows 10/11 o Linux (probado en Ubuntu/GNOME) · Python 3.11+ · [Ollama](https://ollama.com/download) · micrófono (opcional)

### Windows

```powershell
# 1. Clonar (la carpeta puede llamarse como quieras)
git clone https://github.com/omarhernandezrey/Jarvis.git
cd Jarvis

# 2. Dependencias
pip install -r requirements.txt

# 3. Modelos locales
ollama pull llama3.2:3b       # el cerebro: chat + routing del agente (2.0 GB)
ollama pull bge-m3            # memoria semántica (1.2 GB, opcional)
ollama pull qwen2.5:3b        # fallback opcional del router (1.9 GB)

# 4. Arrancar (desde la raíz del proyecto)
$env:PYTHONIOENCODING = "utf-8"
python -m jarvis_local.cli
```

### Linux (Ubuntu/Debian)

```bash
# 1. Paquetes del sistema: portapapeles, multimedia, microfono, interfaz de
#    escritorio (Tkinter) y captura de pantalla (via el portal de GNOME)
sudo apt install -y xclip playerctl libportaudio2 python3-venv python3-tk python3-gi gir1.2-glib-2.0

# 2. Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b       # el cerebro: chat + routing del agente (2.0 GB)
ollama pull bge-m3            # memoria semantica (1.2 GB, opcional)
ollama pull qwen2.5:3b        # fallback opcional del router (1.9 GB)

# 3. Clonar (la carpeta puede llamarse como quieras)
git clone https://github.com/omarhernandezrey/Jarvis.git
cd Jarvis

# 4. Entorno virtual (con acceso a los paquetes de sistema: Tkinter y
#    PyGObject no se pueden instalar con pip, vienen del SO) y dependencias
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

# 5. Arrancar (desde la raíz del proyecto)
.venv/bin/python -m jarvis_local.cli          # consola
.venv/bin/python -m jarvis_local.ui.hud       # interfaz de escritorio (Qt/QML)
```

> La primera carga del modelo tarda 2–5 min en CPU modesta. JARVIS lo precalienta en segundo plano, así que puedes usar los comandos rápidos de inmediato.

### 🔑 Credenciales opcionales

Todo funciona sin configurar nada, salvo tres funciones. Copia `secrets.example.yaml` a `secrets.yaml` y completa solo lo que uses:

| Función | Qué necesitas |
|---|---|
| **Correo** | Contraseña de aplicación de Gmail ([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)) |
| **WolframAlpha** | App ID gratis ([developer.wolframalpha.com](https://developer.wolframalpha.com/)) |
| **Google Calendar** | OAuth: `credentials.json` de [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

---

## 🎮 Uso

Habla o escribe con naturalidad — o usa comandos directos:

```
/ayuda                    Ayuda completa
/voz on | off             Respuestas habladas (habla mientras genera)
/voz continuo             Manos libres con wake word "Jarvis"
/memoria guardar <dato>   Enseñarle algo permanente
/memoria buscar <pregunta>  Búsqueda semántica en lo recordado
/apps abrir <nombre>      Abrir cualquier app instalada
/plan · /confirmar · /cancelar   Control de acciones de riesgo
/ui · /desktop            Interfaz web o de escritorio
salir
```

---

## 🏗️ Estructura

```
Jarvis/                      (raíz del proyecto: config.yaml, secrets.yaml, data/, logs/)
├── jarvis_local/            El paquete Python
│   ├── cli.py               Punto de entrada
│   ├── jarvis.py            Orquestador: la cascada de 4 capas
│   ├── agent/               🆕 Tool calling
│   │   ├── registry.py        32 herramientas: esquema JSON + ejecutor
│   │   ├── selector.py        Preselección: qué herramientas ofrecer al LLM
│   │   └── loop.py            Bucle agéntico
│   ├── intent/parser.py     Parser determinista (camino rápido)
│   ├── fast_response.py     Respuestas instantáneas sin LLM
│   ├── tools/               17 herramientas: apps, archivos, web, clima, empleo…
│   ├── safety/              Políticas, permisos, secretos, auditoría
│   ├── voice/               STT · TTS · wake word · streaming
│   ├── storage/             Historial, memorias y 🆕 índice semántico
│   ├── memory_context/      Memorias activas y 🆕 recuerdo automático
│   └── ui/                  Interfaz web y de escritorio
└── test/                    772 tests
```

## 🧪 Tests y calidad

```bash
python -m pytest test -q            # 772 tests (Windows y Linux)
python -m pytest -m live            # 9 tests que pegan a APIs reales (nocturno en CI)
ruff check .                        # lint
python -m jarvis_local.cli doctor   # diagnóstico del entorno (Ollama, red, credenciales, micro)
```

Los tests que tocan una API exclusiva de un SO (`ctypes.windll` en Windows, `loginctl`/Wayland en Linux) se saltan solos en el SO que no les corresponde — no hace falta nada especial para correr la suite en cualquiera de los dos. Los tests `live` no corren por defecto (`-m 'not live'`); se ejecutan a mano o en el job nocturno de CI.

**CI en GitHub Actions**: tests en Python 3.11/3.12/3.13, lint (ruff), auditoría de seguridad (bandit + pip-audit), verificación de que ninguna credencial esté versionada, y un job nocturno que corre los tests `live` contra las APIs reales.

## 🧰 Stack

| | |
|---|---|
| **LLM** | Ollama + **llama3.2:3b** (2.0 GB, CPU): chat y routing del agente, un solo modelo. Tool calling nativo. qwen2.5:3b opcional como fallback del router. hermes3:3b evaluado y descartado (1/12 en la batería de routing — ver `docs/AUDITORIA_2026-09.md` §7) |
| **Embeddings** | bge-m3 (multilingüe — elegido midiendo: 4x mejor separación que nomic en español) |
| **STT** | faster-whisper (int8) |
| **TTS** | edge-tts neural · respaldo offline (SAPI5 en Windows, espeak-ng en Linux) |
| **Automatización** | Selenium · psutil · Pillow |
| **Linux nativo** | PipeWire (`wpctl`) para volumen, `playerctl` para multimedia, `xclip` para portapapeles, `.desktop`/Snap/Flatpak para el índice de apps, portal de escritorio (`org.freedesktop.portal.Screenshot`) para capturas |

## 🗺️ Evolución

- ✅ **Fase 1–2**: Chat local, herramientas de archivos/apps/terminal, capa de seguridad
- ✅ **Fase 3**: Voz (STT/TTS), wake word, memorias, UI, índice dinámico de apps
- ✅ **Fase 4**: Web, clima, ubicaciones, Wikipedia, correo, WolframAlpha, Calendar
- ✅ **Fase 5**: Selenium + búsqueda de empleo multi-portal
- ✅ **Fase 6**: **Agente con tool calling**, memoria semántica, voz por streaming, CI
- ✅ **Fase 7**: **Soporte Linux** (Ubuntu/GNOME): terminal, energía, volumen, portapapeles y apps con su API nativa; degradado explícito de la gestión de ventanas en Wayland
- 🔄 **Fase 8 — eficacia** ([`PLAN_MAESTRO.md`](PLAN_MAESTRO.md)): auditoría funcionalidad por funcionalidad y arreglo con test que lo blinde. Fases A–D: huecos del parser (clima, notas, cálculo, ubicaciones), re-autorización accionable de Calendar/Spotify, apps que no se abren dos veces, instrumentación y poda de la latencia del agente, `jarvis doctor`, tests `live` + nocturno, prueba de voz e2e
- ⏳ **Siguiente**: visión (que JARVIS *vea* tu pantalla), proactividad, instalador

---

<sub>Proyecto personal de **Omar Hernández Rey**. Construido para correr en hardware real, no en una demo.</sub>
