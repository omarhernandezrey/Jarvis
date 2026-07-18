# 🤖 JARVIS Local

**Asistente de IA por voz, 100% local y en español, para Windows y Linux.**
Entiende lenguaje natural, decide qué herramientas usar y ejecuta acciones reales en tu PC — sin enviar tus datos a la nube.

[![Tests](https://github.com/omarhernandezrey/Jarvis/actions/workflows/tests.yml/badge.svg)](https://github.com/omarhernandezrey/Jarvis/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-455%20passing-brightgreen)
![Offline](https://img.shields.io/badge/LLM-100%25%20local-orange)
![OS](https://img.shields.io/badge/OS-Windows%20%7C%20Linux-informational)

---

## ✨ Qué lo hace distinto

No es un menú de comandos con voz: es un **agente**. El modelo de lenguaje (que corre en tu propia máquina) recibe el catálogo de herramientas y **decide cuál usar**, así que entiende frases que nadie programó:

> *"necesito saber si va a llover por allá en Cartagena"* → consulta el clima
> *"qué tal anda mi máquina de recursos"* → reporta CPU, RAM y batería
> *"me consigues unas vacantes de programador por Medellín"* → busca empleo

Y **recuerda por significado**: le dices *"soy alérgico a los mariscos"*, y semanas después, ante *"¿puedo comer camarones?"*, lo recupera aunque no compartan ni una palabra.

| | |
|---|---|
| 🔒 **Privado** | LLM (qwen2.5), voz (faster-whisper) y embeddings (bge-m3) corren offline. Nada sale de tu PC. |
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
| 1. **Respuestas instantáneas** | saludos, hora, fecha, gracias | **0 s** |
| 2. **Parser determinista** | frases conocidas: "abre whatsapp", "clima en Bogotá" | **1.6 s** |
| 3. **Agente (tool calling)** | lenguaje libre: "¿va a llover por allá?" | **19 s** |
| 4. **Chat con el LLM** | conversación, razonamiento, opinión | **~60 s** |

<sub>*Medido en el equipo de desarrollo: Intel i5-6200U, 16 GB RAM, sin GPU.</sub>

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
- **Calculadora segura** (AST, sin `eval`) con lenguaje natural, y **WolframAlpha** para ecuaciones: *"calcula x + 135 - 234 = 345"* → *x = 444*.
- **Navegador automatizado** (Selenium): JARVIS controla su propia ventana de Chrome.
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
- **Google Calendar**: *"mis próximos eventos"*.
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
# 1. Clonar (la carpeta DEBE llamarse jarvis_local: es el nombre del paquete)
mkdir workspace; cd workspace
git clone https://github.com/omarhernandezrey/Jarvis.git jarvis_local

# 2. Dependencias
pip install -r jarvis_local\requirements.txt

# 3. Modelos locales
ollama pull qwen2.5:3b        # el cerebro (1.9 GB)
ollama pull bge-m3            # memoria semántica (1.2 GB, opcional)

# 4. Arrancar (desde la carpeta padre)
$env:PYTHONIOENCODING = "utf-8"
python -m jarvis_local.cli
```

### Linux (Ubuntu/Debian)

```bash
# 1. Paquetes del sistema: portapapeles, captura de pantalla, multimedia y microfono
sudo apt install -y xclip grim playerctl libportaudio2 python3-venv

# 2. Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b        # el cerebro (1.9 GB)
ollama pull bge-m3            # memoria semantica (1.2 GB, opcional)

# 3. Clonar (la carpeta DEBE llamarse jarvis_local: es el nombre del paquete)
mkdir -p ~/workspace && cd ~/workspace
git clone https://github.com/omarhernandezrey/Jarvis.git jarvis_local

# 4. Entorno virtual y dependencias
cd jarvis_local
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 5. Arrancar (desde la carpeta padre, jarvis_local es un paquete Python)
cd ~/workspace
jarvis_local/.venv/bin/python -m jarvis_local.cli
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
jarvis_local/
├── cli.py               Punto de entrada
├── jarvis.py            Orquestador: la cascada de 4 capas
├── agent/               🆕 Tool calling
│   ├── registry.py        31 herramientas: esquema JSON + ejecutor
│   ├── selector.py        Preselección: qué herramientas ofrecer al LLM
│   └── loop.py            Bucle agéntico
├── intent/parser.py     Parser determinista (camino rápido)
├── fast_response.py     Respuestas instantáneas sin LLM
├── tools/               17 herramientas: apps, archivos, web, clima, empleo…
├── safety/              Políticas, permisos, secretos, auditoría
├── voice/               STT · TTS · wake word · streaming
├── storage/             Historial, memorias y 🆕 índice semántico
├── memory_context/      Memorias activas y 🆕 recuerdo automático
├── ui/                  Interfaz web y de escritorio
└── test/                455 tests
```

## 🧪 Tests y calidad

```bash
python -m pytest jarvis_local/test -q     # 455 tests (Windows y Linux)
ruff check jarvis_local                   # lint
```

Los tests que tocan una API exclusiva de un SO (`ctypes.windll` en Windows, `loginctl`/Wayland en Linux) se saltan solos en el SO que no les corresponde — no hace falta nada especial para correr la suite en cualquiera de los dos.

**CI en GitHub Actions**: tests en Python 3.11/3.12/3.13, lint (ruff), auditoría de seguridad (bandit + pip-audit) y verificación de que ninguna credencial esté versionada.

## 🧰 Stack

| | |
|---|---|
| **LLM** | Ollama + qwen2.5:3b (1.9 GB, CPU) con tool calling nativo |
| **Embeddings** | bge-m3 (multilingüe — elegido midiendo: 4x mejor separación que nomic en español) |
| **STT** | faster-whisper (int8) |
| **TTS** | edge-tts neural · respaldo offline (SAPI5 en Windows, espeak-ng en Linux) |
| **Automatización** | Selenium · psutil · Pillow |
| **Linux nativo** | PipeWire (`wpctl`) para volumen, `playerctl` para multimedia, `xclip` para portapapeles, `.desktop`/Snap/Flatpak para el índice de apps |

## 🗺️ Evolución

- ✅ **Fase 1–2**: Chat local, herramientas de archivos/apps/terminal, capa de seguridad
- ✅ **Fase 3**: Voz (STT/TTS), wake word, memorias, UI, índice dinámico de apps
- ✅ **Fase 4**: Web, clima, ubicaciones, Wikipedia, correo, WolframAlpha, Calendar
- ✅ **Fase 5**: Selenium + búsqueda de empleo multi-portal
- ✅ **Fase 6**: **Agente con tool calling**, memoria semántica, voz por streaming, CI
- ✅ **Fase 7**: **Soporte Linux** (Ubuntu/GNOME): terminal, energía, volumen, portapapeles y apps con su API nativa; degradado explícito de la gestión de ventanas en Wayland
- ⏳ **Siguiente**: visión (que JARVIS *vea* tu pantalla), proactividad, instalador

---

<sub>Proyecto personal de **Omar Hernández Rey**. Construido para correr en hardware real, no en una demo.</sub>
