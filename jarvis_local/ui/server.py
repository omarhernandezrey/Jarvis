"""
JARVIS Local - Interfaz Web Ultra-Moderna (Iron Man style)
Servidor HTTP sin dependencias externas.
Uso: python -m jarvis_local.ui.server
"""
import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PORT = 8080
_jarvis_instance = None
_chat_history: list[dict] = []
_jarvis_lock = threading.Lock()
# Con HTTPServer (una conexion a la vez) el LLM pensando bloqueaba TODO,
# incluido el sondeo de /api/status cada 10s -- la UI se sentia colgada.
# ThreadingHTTPServer arregla eso, pero j.chat()/_parse_and_execute() mutan
# el historial/memoria compartidos de la MISMA instancia de Jarvis: sin este
# lock, dos chats a la vez (dos pestanas, o un doble click) corromperian esa
# conversacion en vez de solo demorarse. Solo se serializa lo que de verdad
# comparte estado (chat/comando/voz); /api/status y /api/history no lo usan.
_chat_lock = threading.Lock()

# Token de sesion generado al arrancar el servidor. El servidor solo escucha
# en 127.0.0.1, pero eso no basta: sin este token, cualquier pagina web
# abierta en el mismo navegador puede hacer fetch() a este puerto y disparar
# acciones reales (apagar el equipo, ejecutar comandos, enviar WhatsApp) sin
# que el usuario haya tocado JARVIS. El token solo lo conoce quien cargo la
# pagina desde este mismo servidor (SOP impide que un origen distinto lo lea).
_AUTH_TOKEN = secrets.token_urlsafe(24)


def _get_jarvis():
    global _jarvis_instance
    if _jarvis_instance is None:
        with _jarvis_lock:
            if _jarvis_instance is None:  # otro hilo pudo crearlo mientras esperabamos el lock
                from jarvis_local.jarvis import Jarvis
                _jarvis_instance = Jarvis()
    return _jarvis_instance


def _get_status() -> dict:
    try:
        j = _get_jarvis()
        ollama_ok = j.client.is_running()
    except Exception:
        ollama_ok = False

    try:
        from jarvis_local.voice.stt import load_voice_config
        vcfg = load_voice_config()
    except Exception:
        vcfg = {}

    try:
        from jarvis_local.voice.tts import is_available as tts_available
        tts_ok = tts_available()
    except Exception:
        tts_ok = False

    try:
        import sounddevice as sd
        mic = sd.query_devices(kind="input")
        mic_name = mic.get("name", "No detectado")[:50]
    except Exception:
        mic_name = "No detectado"

    try:
        from jarvis_local.config import get_config
        _model_name = get_config().get("ollama", {}).get("model", "llama3.2:3b")
    except Exception:
        _model_name = "llama3.2:3b"

    # CPU/RAM para la barra superior del HUD web (paridad visual con
    # hud_pro). Una sola llamada por peticion de /api/status, en un unico
    # proceso -- no aplica el bug de "varios callers pisandose" que se
    # arreglo en hud_pro/system_metrics.py (ese era multi-widget dentro del
    # MISMO proceso de escritorio; aqui es un unico handler por request).
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=None)
        ram_pct = psutil.virtual_memory().percent
    except Exception:
        cpu_pct = None
        ram_pct = None

    return {
        "ollama": ollama_ok,
        "model": _model_name if ollama_ok else "N/A",
        "stt_model": vcfg.get("stt_model", "small"),
        "mic": mic_name,
        "tts": tts_ok,
        "cpu": cpu_pct,
        "ram": ram_pct,
        "simulation": False,
        "history_count": len(_chat_history),
        "time": time.strftime("%H:%M:%S"),
    }


HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS - Interfaz de Control</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Orbitron:wght@500;700&display=swap" rel="stylesheet">
<style>
  /* Paleta y tipografia: mismos tokens que hud_pro/theme.py (HUD de
     escritorio predeterminado) -- ver _get_status()/README para como se
     eligieron. Fuentes via Google Fonts con fallback a la pila de sistema
     si no hay internet (no rompe nada, solo pierde el look exacto). */
  :root {
    --bg0: #03060D;
    --bg-panel: rgba(9,18,34,0.60);
    --bg-panel-solid: #0A1426;
    --bg-input: rgba(4,10,22,0.85);
    --line: rgba(110,190,255,0.14);
    --line-strong: rgba(110,190,255,0.32);
    --text: #E6F1FF;
    --text-dim: #93AACB;
    --text-muted: #5A7093;
    --accent: #38BDF8;
    --accent2: #22D3EE;
    --danger: #FF5A7A;
    --success: #22C55E;
    --font: 'Inter', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, 'Courier New', monospace;
    --font-display: 'Orbitron', var(--font);
    --transition: 0.25s cubic-bezier(0.4,0,0.2,1);
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: var(--font);
    background: var(--bg0);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  /* Selección de texto: el CROMO (barra, badges, consola, botones) no se
     selecciona, para que arrastrar sobre el orbe no deje rastros azules. La
     CONVERSACIÓN sí se puede seleccionar y copiar: antes esto era
     `user-select: none` en `body`, así que no había forma de llevarse ni una
     palabra de lo que JARVIS respondía (ni con el ratón ni con Ctrl+A). */
  .top-bar, .stage, .quick-cmds, .input-area,
  .stage-label, .voice-label, .toast {
    user-select: none; -webkit-user-select: none;
  }
  .chat-area, .chat-area .msg-bubble, .chat-area .msg-time,
  .chat-area .msg-avatar {
    user-select: text; -webkit-user-select: text;
  }
  .chat-area .msg-bubble { cursor: text; }

  /* ── Barra superior (hud_pro/widgets.py::TopBar) ─────────────────────── */
  .top-bar {
    display: flex; align-items: center; gap: 14px; height: 52px;
    padding: 0 18px; flex-shrink: 0; border-bottom: 1px solid var(--line);
  }
  .mini-orb {
    width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0;
    background: radial-gradient(circle at 35% 35%, #fff 0%, var(--accent2) 35%, var(--accent) 70%, transparent 100%);
    box-shadow: 0 0 10px var(--accent);
  }
  .wordmark {
    font-family: var(--font-display); font-weight: 700; font-size: 15px;
    letter-spacing: 4px; color: var(--text); white-space: nowrap;
  }
  .divider { width: 1px; height: 18px; background: var(--line); flex-shrink: 0; }
  .wordmark-sub { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
  .top-spacer { flex: 1; min-width: 12px; }
  .metric {
    font-family: var(--font-mono); font-size: 12px; color: var(--text-dim);
    white-space: nowrap;
  }
  .dot {
    width: 7px; height: 7px; border-radius: 50%; display: inline-block;
    margin-right: 6px; vertical-align: middle;
  }
  .dot.on { background: var(--success); box-shadow: 0 0 6px var(--success); }
  .dot.off { background: var(--danger); }
  .status-chip {
    background: rgba(56,189,248,0.08); border: 1px solid var(--line-strong);
    border-radius: 13px; padding: 4px 14px; font-family: var(--font-mono);
    font-size: 11px; letter-spacing: 1.5px; color: var(--accent);
    white-space: nowrap;
  }
  .clock {
    font-family: var(--font-mono); font-size: 13px; color: var(--text);
    min-width: 44px; text-align: right;
  }

  /* ── Escenario central (orbe + badges de esquina) ────────────────────── */
  .stage { flex: 1; position: relative; display: flex; flex-direction: column;
    align-items: center; justify-content: center; min-height: 0; padding: 14px; }

  .corner-badge {
    position: absolute; background: var(--bg-panel); border: 1px solid var(--line);
    border-radius: 10px; padding: 6px 10px; font-family: var(--font-mono);
  }
  .corner-badge.top-left { top: 14px; left: 14px; display: flex; gap: 10px; align-items: center; }
  .corner-badge.top-right { top: 14px; right: 14px; }
  .corner-badge.bottom-left { bottom: 14px; left: 14px; display: flex; flex-direction: column; gap: 3px; }
  .badge-title { color: var(--text-muted); font-size: 10px; letter-spacing: 1px; }
  .badge-line { color: var(--text-dim); font-size: 11px; white-space: nowrap; }

  .mini-ring { width: 34px; height: 34px; transform: rotate(-90deg); }
  .mini-ring circle.track { stroke: var(--line); stroke-width: 3; fill: none; }
  .mini-ring circle.arc { stroke: var(--accent); stroke-width: 3; fill: none;
    stroke-linecap: round; transition: stroke-dashoffset 0.4s ease; }
  .mini-ring.ram circle.arc { stroke: var(--accent2); }
  .mini-ring-wrap { position: relative; width: 34px; height: 34px; }
  .mini-ring-val {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    font-size: 8px; color: var(--text); transform: none;
  }

  canvas#orbCanvas { display: block; }
  .stage-label { text-align: center; margin-top: 6px; }
  #orbState {
    font-family: var(--font-display); font-weight: 600; font-size: 13px;
    letter-spacing: 6px; color: var(--accent); transition: color 0.4s;
  }
  #orbHint { font-size: 12px; color: var(--text-dim); margin-top: 4px; }

  /* ── Panel de consola (hud_pro QFrame#ChatPanel) ─────────────────────── */
  .console-panel {
    margin: 0 16px 14px; background: var(--bg-panel); border: 1px solid var(--line);
    border-radius: 18px; display: flex; flex-direction: column;
    max-height: 42vh; overflow: hidden; flex-shrink: 0;
  }
  .console-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px; border-bottom: 1px solid var(--line);
  }
  .console-title {
    font-family: var(--font-mono); font-size: 11px; letter-spacing: 1.5px;
    color: var(--text-dim); text-transform: uppercase;
  }

  .chat-area {
    flex: 1; overflow-y: auto; padding: 14px 16px;
    display: flex; flex-direction: column; gap: 10px;
    scroll-behavior: smooth;
  }
  .chat-area::-webkit-scrollbar { width: 4px; }
  .chat-area::-webkit-scrollbar-track { background: transparent; }
  .chat-area::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 4px; }

  .msg {
    display: flex; gap: 10px; animation: msgIn 0.3s ease;
    max-width: 85%;
  }
  @keyframes msgIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  .msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .msg.jarvis { align-self: flex-start; }

  .msg-avatar {
    width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--font-mono); font-size: 11px; font-weight: 600;
    border: 1px solid var(--line-strong);
  }
  .msg.user .msg-avatar { background: rgba(56,189,248,0.10); color: var(--text-dim); }
  .msg.jarvis .msg-avatar { background: rgba(56,189,248,0.10); color: var(--accent); }

  .msg-bubble {
    padding: 10px 14px; font-size: 14px; line-height: 1.5; word-break: break-word;
  }
  .msg.user .msg-bubble {
    background: rgba(56,189,248,0.13); border: 1px solid rgba(56,189,248,0.30);
    border-radius: 14px 14px 4px 14px;
  }
  .msg.jarvis .msg-bubble {
    background: rgba(255,255,255,0.025); border: 1px solid var(--line);
    border-left: 2px solid var(--accent); border-radius: 10px;
  }
  .msg-time {
    font-family: var(--font-mono); font-size: 10px; color: var(--text-muted);
    margin-top: 4px;
  }
  .msg.user .msg-time { text-align: right; }

  /* Copiar un turno: botón discreto dentro de la línea de tiempo, visible al
     pasar por encima (nunca estorba a la lectura) y SIEMPRE alcanzable con
     teclado (focus-visible), porque la selección con el ratón no siempre
     sirve: los mensajes largos exigen arrastrar con precisión. */
  .msg-actions {
    display: flex; align-items: center; gap: 10px; margin-top: 4px;
  }
  .msg.user .msg-actions { justify-content: flex-end; }
  .msg-copy {
    background: none; border: 1px solid var(--line); cursor: pointer;
    border-radius: 10px; padding: 2px 8px; color: var(--text-dim);
    font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.5px;
    transition: var(--transition);
  }
  .msg-copy:hover { color: var(--accent); border-color: var(--line-strong); }
  .msg-copy:focus-visible { outline: 1px solid var(--accent); color: var(--accent); }
  .status-copy {
    background: none; cursor: pointer;
    border: 1px solid var(--line); border-radius: 20px;
    padding: 4px 12px; color: var(--text-dim);
    font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.8px;
    text-transform: uppercase; transition: var(--transition);
  }
  .status-copy:hover { color: var(--accent); border-color: var(--line-strong); }
  .status-copy:focus-visible { outline: 1px solid var(--accent); color: var(--accent); }

  .typing-indicator {
    align-self: flex-start; display: flex; gap: 4px; padding: 10px 16px;
    background: rgba(255,255,255,0.025); border-radius: 10px;
    border: 1px solid var(--line);
  }
  .typing-dot {
    width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    animation: typingBounce 1.4s ease-in-out infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes typingBounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
    30% { transform: translateY(-8px); opacity: 1; }
  }

  /* Quick commands */
  .quick-cmds {
    display: flex; gap: 8px; padding: 0 16px 10px; flex-wrap: wrap;
  }
  .quick-btn {
    padding: 5px 13px; border-radius: 8px; border: 1px solid var(--line);
    background: transparent; color: var(--text-dim); cursor: pointer;
    font-size: 11px; letter-spacing: 0.3px; transition: var(--transition);
    font-family: var(--font-mono); white-space: nowrap;
  }
  .quick-btn:hover { border-color: var(--line-strong); color: var(--text); }

  /* Input */
  .input-area {
    display: flex; gap: 10px; padding: 10px 16px 14px; align-items: center;
  }
  .voice-btn {
    width: 38px; height: 38px; border-radius: 50%; border: 1px solid var(--line-strong);
    background: var(--bg-input); color: var(--accent); cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: var(--transition); flex-shrink: 0; font-size: 15px;
  }
  .voice-btn:hover { background: rgba(56,189,248,0.10); }
  .voice-btn:active { transform: scale(0.95); }
  .voice-btn.recording {
    border-color: var(--danger); background: rgba(255,90,122,0.12); color: var(--danger);
    animation: recPulse 1.5s ease-in-out infinite;
  }
  @keyframes recPulse {
    0%, 100% { box-shadow: 0 0 0 rgba(255,90,122,0.3); }
    50% { box-shadow: 0 0 14px rgba(255,90,122,0.4); }
  }
  .input-field {
    flex: 1; padding: 10px 16px; border-radius: 20px;
    border: 1px solid var(--line); background: var(--bg-input);
    color: var(--text); font-size: 13px; font-family: var(--font);
    outline: none; transition: var(--transition);
  }
  .input-field:focus { border-color: var(--accent); }
  .input-field::placeholder { color: var(--text-muted); }
  .send-btn {
    width: 38px; height: 38px; border-radius: 50%; border: none;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: var(--bg0); cursor: pointer; font-size: 15px;
    transition: var(--transition); flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  .send-btn:hover { box-shadow: 0 0 16px rgba(56,189,248,0.3); }
  .send-btn:active { transform: scale(0.95); }
  .send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .voice-label { display: none; } /* el estado ya lo dice el chip/orbe */

  /* Toast */
  .toast {
    position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
    padding: 10px 20px; border-radius: 10px; font-size: 12px; z-index: 999;
    background: var(--bg-panel-solid); border: 1px solid var(--line-strong);
    border-left: 3px solid var(--accent);
    color: var(--text); letter-spacing: 0.3px;
    animation: toastIn 0.3s ease, toastOut 0.3s ease 2.5s forwards;
    pointer-events: none;
  }
  @keyframes toastIn { from { opacity: 0; transform: translateX(-50%) translateY(-20px); } to { opacity: 1; } }
  @keyframes toastOut { from { opacity: 1; } to { opacity: 0; } }

  @media (max-width: 760px) {
    .wordmark-sub, .metric, .corner-badge.top-right { display: none; }
    .console-panel { margin: 0 8px 10px; }
  }
</style>
</head>
<body>
  <!-- Barra superior -->
  <div class="top-bar">
    <div class="mini-orb"></div>
    <div class="wordmark">J.A.R.V.I.S</div>
    <div class="divider"></div>
    <div class="wordmark-sub">Asistente local</div>
    <div class="top-spacer"></div>
    <span class="metric" id="stModel">llama3.2:3b</span>
    <span class="metric"><span class="dot on" id="stOllamaDot"></span><span id="stOllamaLabel">Ollama</span></span>
    <span class="metric" id="stMetrics">CPU --%  ·  RAM --%</span>
    <div class="divider"></div>
    <div class="status-chip" id="statusChip">● LISTO</div>
    <div class="clock" id="clock">--:--</div>
  </div>

  <!-- Escenario: orbe + badges -->
  <div class="stage">
    <div class="corner-badge top-left">
      <div class="mini-ring-wrap">
        <svg class="mini-ring cpu" viewBox="0 0 34 34">
          <circle class="track" cx="17" cy="17" r="14"></circle>
          <circle class="arc" id="cpuArc" cx="17" cy="17" r="14" stroke-dasharray="88" stroke-dashoffset="88"></circle>
        </svg>
        <div class="mini-ring-val" id="cpuVal">--</div>
      </div>
      <div class="mini-ring-wrap">
        <svg class="mini-ring ram" viewBox="0 0 34 34">
          <circle class="track" cx="17" cy="17" r="14"></circle>
          <circle class="arc" id="ramArc" cx="17" cy="17" r="14" stroke-dasharray="88" stroke-dashoffset="88"></circle>
        </svg>
        <div class="mini-ring-val" id="ramVal">--</div>
      </div>
    </div>
    <div class="corner-badge top-right">
      <div class="badge-title">HERRAMIENTA</div>
      <div class="badge-line">Sin actividad</div>
    </div>
    <div class="corner-badge bottom-left">
      <div class="badge-line"><span class="dot on" id="stMicDot"></span>Mic</div>
      <div class="badge-line"><span class="dot on" id="stTTSDot"></span>TTS</div>
    </div>

    <canvas id="orbCanvas" width="220" height="220"></canvas>
    <div class="stage-label">
      <div id="orbState">LISTO</div>
      <div id="orbHint">Di «Jarvis» o escribe abajo</div>
    </div>
  </div>

  <!-- Consola -->
  <div class="console-panel">
    <div class="console-head">
      <span class="console-title">Consola</span>
      <button class="status-copy" id="copyAllBtn" type="button"
              onclick="copiarConversacion()" title="Copiar toda la conversación">Copiar conversación</button>
    </div>
    <div class="chat-area" id="chatArea">
      <div class="msg jarvis">
        <div class="msg-avatar">J</div>
        <div>
          <div class="msg-bubble">Bienvenido, señor. JARVIS en línea. Todos los sistemas operando con normalidad. ¿En qué puedo asistirle?</div>
          <div class="msg-actions">
            <div class="msg-time" id="initTime"></div>
            <button class="msg-copy" type="button" onclick="copiarTurno(this)"
                    title="Copiar este mensaje">copiar ⧉</button>
          </div>
        </div>
      </div>
    </div>

    <div class="quick-cmds">
      <button class="quick-btn" onclick="sendQuick('Estado del sistema')">Estado</button>
      <button class="quick-btn" onclick="sendQuick('Abre Chrome')">Abrir Chrome</button>
      <button class="quick-btn" onclick="sendQuick('Abre VS Code')">Abrir VS Code</button>
      <button class="quick-btn" onclick="sendQuick('Abre el explorador de archivos')">Explorador</button>
      <button class="quick-btn" onclick="sendQuick('Lista mis archivos')">Mis Archivos</button>
      <button class="quick-btn" onclick="sendQuick('Ejecuta dir')">Terminal</button>
      <button class="quick-btn" onclick="sendQuick('¿Qué puedes hacer?')">Ayuda</button>
      <button class="quick-btn" onclick="sendQuick('Cuéntame un dato interesante')">Dato</button>
    </div>

    <div class="input-area">
      <button class="voice-btn" id="voiceBtn" onclick="toggleVoice()" title="Presiona para hablar">&#x1F399;</button>
      <input type="text" class="input-field" id="inputField"
             placeholder="Escribe un comando o mensaje..."
             onkeydown="if(event.key==='Enter') sendMessage()">
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">&#x27A4;</button>
      <div class="voice-label" id="voiceLabel">HABLAR</div>
    </div>
  </div>
<div id="toastContainer"></div>

<script>
const API = '/api';
const API_TOKEN = '%JARVIS_TOKEN%';
let isProcessing = false;
let voiceActive = false;

document.getElementById('initTime').textContent = new Date().toLocaleTimeString();
refreshStatus();
setInterval(refreshStatus, 10000);
tickClock();
setInterval(tickClock, 1000);

function $(id) { return document.getElementById(id); }

function tickClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  $('clock').textContent = hh + ':' + mm;
}

// Circunferencia de los anillos CPU/RAM (r=14): 2*pi*14 ~= 88.
const RING_CIRC = 88;
function setRing(arcId, valId, value) {
  const v = Math.max(0, Math.min(100, value));
  $(arcId).setAttribute('stroke-dashoffset', String(RING_CIRC * (1 - v / 100)));
  $(valId).textContent = Math.round(v);
}

async function refreshStatus() {
  try {
    const r = await fetch(API + '/status');
    const s = await r.json();
    $('stOllamaDot').className = 'dot ' + (s.ollama ? 'on' : 'off');
    $('stOllamaLabel').textContent = 'Ollama';
    $('stMicDot').className = 'dot on';
    $('stTTSDot').className = 'dot ' + (s.tts ? 'on' : 'off');
    $('stModel').textContent = s.model || 'N/A';
    if (typeof s.cpu === 'number' && typeof s.ram === 'number') {
      $('stMetrics').textContent = 'CPU ' + Math.round(s.cpu) + '%  ·  RAM ' + Math.round(s.ram) + '%';
      setRing('cpuArc', 'cpuVal', s.cpu);
      setRing('ramArc', 'ramVal', s.ram);
    }
  } catch(e) {}
}

/* ── Orbe (canvas 2D) ──────────────────────────────────────────────────────
   Replica visual de hud_pro/orb.py con Canvas2D en vez de un shader GLSL:
   nucleo con gradiente radial + anillos rotando + polvo de particulas,
   coloreado con los mismos RGB por estado que hud_pro/theme.py::STATE_STYLES.
   Solo anima mientras la pestana esta visible (document.hidden) -- cero
   costo de fondo si el usuario cambia de pestana. */
const ORB_STATES = {
  idle:      {primary: [40,170,255],  secondary: [46,92,230],  ringSpeed: 0.45},
  listening: {primary: [20,215,255],  secondary: [30,130,255], ringSpeed: 0.90},
  thinking:  {primary: [80,125,255],  secondary: [40,70,210],  ringSpeed: 2.60},
};
let orbState = 'idle';
const orbDust = Array.from({length: 40}, () => ({
  a: Math.random() * Math.PI * 2, r: 0.3 + Math.random() * 0.62, s: 0.3 + Math.random() * 0.7,
}));

function rgba(rgb, a) { return 'rgba(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + a + ')'; }

function drawOrb(tMs) {
  const canvas = $('orbCanvas');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2, R = w / 2 - 6;
  const st = ORB_STATES[orbState] || ORB_STATES.idle;
  const t = tMs / 1000;

  ctx.clearRect(0, 0, w, h);

  // nucleo: gradiente radial, mas intenso hacia el borde (como el vidrio del HUD)
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, R);
  grad.addColorStop(0, rgba(st.secondary, 0.10));
  grad.addColorStop(0.7, rgba(st.primary, 0.22));
  grad.addColorStop(1, rgba(st.primary, 0.05));
  ctx.beginPath();
  ctx.arc(cx, cy, R, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = rgba(st.primary, 0.35);
  ctx.stroke();

  // anillos rotando, cadencia distinta por estado (igual que ring_speed en hud_pro)
  [0.82, 0.66, 0.5].forEach((frac, i) => {
    const radius = R * frac;
    const speed = st.ringSpeed * (i % 2 === 0 ? 1 : -1);
    const start = t * speed;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, start + Math.PI * (0.5 + 0.3 * i));
    ctx.strokeStyle = rgba(st.primary, 0.30 - i * 0.07);
    ctx.lineWidth = 1.4;
    ctx.stroke();
  });

  // polvo de particulas, deriva lenta
  orbDust.forEach(p => {
    const ang = p.a + t * 0.05 * p.s;
    const rr = R * p.r;
    const x = cx + Math.cos(ang) * rr, y = cy + Math.sin(ang) * rr;
    ctx.beginPath();
    ctx.arc(x, y, 0.9, 0, Math.PI * 2);
    ctx.fillStyle = rgba(st.primary, 0.5);
    ctx.fill();
  });

  if (!document.hidden) requestAnimationFrame(drawOrb);
}
requestAnimationFrame(drawOrb);
document.addEventListener('visibilitychange', () => { if (!document.hidden) requestAnimationFrame(drawOrb); });

const ORB_STATE_META = {
  idle:      {label: 'LISTO',      hint: 'Di «Jarvis» o escribe abajo', color: '#38BDF8'},
  listening: {label: 'ESCUCHANDO', hint: 'Te escucho…',                 color: '#22D3EE'},
  thinking:  {label: 'PROCESANDO', hint: 'Analizando tu solicitud…',    color: '#507DFF'},
};

function setOrbState(state) {
  const key = (state === 'listening') ? 'listening' : (state === 'thinking') ? 'thinking' : 'idle';
  orbState = key;
  const meta = ORB_STATE_META[key];
  $('orbState').textContent = meta.label;
  $('orbState').style.color = meta.color;
  $('orbHint').textContent = meta.hint;
  $('statusChip').textContent = '● ' + meta.label;
  $('statusChip').style.color = meta.color;
}

function addMessage(role, text) {
  const area = $('chatArea');
  const div = document.createElement('div');
  div.className = 'msg ' + role;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? 'Tú' : 'J';

  const wrap = document.createElement('div');
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = text;
  // el pie del mensaje lleva la hora y, al lado, el botón de copiar: pulsarlo
  // pega en el portapapeles este turno exacto (sin la decoración).
  const actions = document.createElement('div');
  actions.className = 'msg-actions';
  const time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = new Date().toLocaleTimeString();
  const copyBtn = document.createElement('button');
  copyBtn.className = 'msg-copy';
  copyBtn.type = 'button';
  copyBtn.title = 'Copiar este mensaje';
  copyBtn.textContent = 'copiar ⧉';
  copyBtn.onclick = function () { copiarTurno(copyBtn); };
  actions.appendChild(time);
  actions.appendChild(copyBtn);

  wrap.appendChild(bubble);
  wrap.appendChild(actions);
  div.appendChild(avatar);
  div.appendChild(wrap);
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return bubble;
}

/* ── Portapapeles ────────────────────────────────────────────────────────── */
// El texto de la conversación se puede seleccionar con el ratón (ver CSS:
// `user-select: text` en `.chat-area`), pero con mensajes largos arrastrar la
// selección exacta es un suplicio, y Ctrl+C sobre un mensaje con markdown se
// puede llevar trozos de burbuja. Estos dos botones copian limpio.
function etiquetaCopiado(btn) {
  if (!btn.dataset.label) btn.dataset.label = btn.textContent;
  btn.textContent = 'copiado ✓';
  setTimeout(function () { btn.textContent = btn.dataset.label; }, 1400);
}

async function ponerEnPortapapeles(texto, btn) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(texto);
    } else {
      // Fallback: el servidor se sirve en http://localhost, que NO es contexto
      // seguro, así que `navigator.clipboard` suele faltar. Textarea oculto +
      // execCommand sigue funcionando ahí.
      const ta = document.createElement('textarea');
      ta.value = texto;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-1000px';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    if (btn) etiquetaCopiado(btn);
    toast('Copiado al portapapeles');
  } catch (e) {
    toast('No se pudo copiar: ' + e);
  }
}

async function copiarTurno(btn) {
  const msg = btn.closest('.msg');
  if (!msg) return;
  const bubble = msg.querySelector('.msg-bubble');
  const texto = bubble ? bubble.innerText.trim() : '';
  if (!texto) { toast('Nada que copiar'); return; }
  await ponerEnPortapapeles(texto, btn);
}

async function copiarConversacion() {
  const msgs = $('chatArea').querySelectorAll('.msg');
  const lineas = [];
  msgs.forEach(function (msg) {
    const bubble = msg.querySelector('.msg-bubble');
    if (!bubble) return;
    const texto = bubble.innerText.trim();
    if (!texto) return;
    const rol = msg.classList.contains('user') ? 'TÚ' : 'JARVIS';
    const hora = msg.querySelector('.msg-time');
    const marca = hora && hora.textContent.trim() ? '[' + hora.textContent.trim() + '] ' : '';
    lineas.push(marca + rol + ' ❯ ' + texto);
  });
  if (!lineas.length) { toast('Nada que copiar'); return; }
  await ponerEnPortapapeles(lineas.join('\n'), $('copyAllBtn'));
}

function showTyping() {
  const area = $('chatArea');
  const div = document.createElement('div');
  div.className = 'typing-indicator';
  div.id = 'typingDots';
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement('div');
    dot.className = 'typing-dot';
    div.appendChild(dot);
  }
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}

function hideTyping() {
  const el = $('typingDots');
  if (el) el.remove();
}

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  $('toastContainer').appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

async function sendMessage() {
  const input = $('inputField');
  const text = input.value.trim();
  if (!text || isProcessing) return;
  input.value = '';
  await processMessage(text);
}

async function sendQuick(text) {
  if (isProcessing) return;
  $('inputField').value = text;
  await processMessage(text);
}

async function processMessage(text) {
  isProcessing = true;
  $('sendBtn').disabled = true;
  setOrbState('thinking');
  addMessage('user', text);
  showTyping();

  try {
    const r = await fetch(API + '/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Jarvis-Token': API_TOKEN},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();
    hideTyping();

    if (data.error) {
      addMessage('jarvis', 'Error: ' + data.error);
    } else {
      addMessage('jarvis', data.response || 'Sin respuesta.');
    }
  } catch(e) {
    hideTyping();
    addMessage('jarvis', 'Error de conexión con el servidor.');
  }

  setOrbState('ready');
  isProcessing = false;
  $('sendBtn').disabled = false;
  $('inputField').focus();
}

let voiceInFlight = false;  // true mientras la petición POST /voice está en curso

async function toggleVoice() {
  if (isProcessing) {
    toast('JARVIS está procesando. Espere por favor.');
    return;
  }
  // Bug real encontrado en revisión: nada impedía pulsar el botón otra vez
  // mientras el fetch(API + '/voice') seguía en curso -- un segundo clic
  // re-entraba aquí, apagaba `voiceActive` y reseteaba la UI a "listo"
  // mientras la petición original todavía estaba en el aire; cuando esa
  // petición por fin resolvía, volvía a tocar la UI (y podía disparar
  // processMessage) por encima de un estado que el usuario ya creía
  // cancelado. `voiceInFlight` es un guardia propio para la voz, igual que
  // `isProcessing` ya protege el envío de texto.
  if (voiceInFlight) {
    toast('Ya estoy escuchando, espere un momento.');
    return;
  }
  voiceActive = !voiceActive;
  const btn = $('voiceBtn');
  const label = $('voiceLabel');

  if (voiceActive) {
    btn.classList.add('recording');
    label.textContent = 'GRABANDO';
    setOrbState('listening');
    toast('Escuchando... Hable ahora.');
    voiceInFlight = true;

    try {
      const r = await fetch(API + '/voice', {method: 'POST', headers: {'X-Jarvis-Token': API_TOKEN}});
      const data = await r.json();
      btn.classList.remove('recording');
      label.textContent = 'HABLAR';
      voiceActive = false;

      if (data.text) {
        $('inputField').value = data.text;
        await processMessage(data.text);
      } else {
        setOrbState('ready');
        toast('No se detectó voz.');
      }
    } catch(e) {
      btn.classList.remove('recording');
      label.textContent = 'HABLAR';
      voiceActive = false;
      setOrbState('ready');
      toast('Error al capturar voz.');
    } finally {
      voiceInFlight = false;
    }
  } else {
    btn.classList.remove('recording');
    label.textContent = 'HABLAR';
    setOrbState('ready');
  }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    if (voiceActive) toggleVoice();
    $('inputField').blur();
  }
  if (e.ctrlKey && e.key === 'v') {
    e.preventDefault();
    toggleVoice();
  }
});
</script>
</body>
</html>"""


class JarvisHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silenciar logs HTTP

    def _authorized(self) -> bool:
        return secrets.compare_digest(
            self.headers.get("X-Jarvis-Token", ""), _AUTH_TOKEN)

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        # Sin CORS: esta pagina solo se sirve a si misma. Permitir origenes
        # cruzados aqui es lo que dejaba que cualquier pestana maliciosa
        # abierta en el navegador leyera las respuestas de este servidor.
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_html(self, html, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send_html(HTML.replace("%JARVIS_TOKEN%", _AUTH_TOKEN))
        elif path == "/api/status":
            self._send_json(_get_status())
        elif path == "/api/history":
            if not self._authorized():
                self._send_json({"error": "No autorizado"}, 401)
                return
            self._send_json({"history": _chat_history[-50:]})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        # Todo POST ejecuta una accion real (chat, voz, o un comando directo
        # via /api/command que puede apagar el equipo). Sin este chequeo,
        # cualquier pagina abierta en el navegador podia dispararlas.
        if not self._authorized():
            self._send_json({"error": "No autorizado"}, 401)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == "/api/chat":
            msg = data.get("message", "").strip()
            if not msg:
                self._send_json({"error": "Mensaje vacío"}, 400)
                return
            try:
                j = _get_jarvis()
            except Exception as e:
                self._send_json({"error": f"No se pudo conectar con Ollama: {e}"}, 500)
                return
            try:
                with _chat_lock:
                    response = j.chat(msg)
                    _chat_history.append({"role": "user", "content": msg})
                    _chat_history.append({"role": "assistant", "content": response})
                self._send_json({"response": response})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/voice":
            try:
                from jarvis_local.voice.stt import capture_and_transcribe
                with _chat_lock:
                    text = capture_and_transcribe(8, show_stats=False)
                self._send_json({"text": text})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/command":
            cmd = data.get("command", "").strip()
            if not cmd:
                self._send_json({"error": "Comando vacío"}, 400)
                return
            try:
                from jarvis_local.jarvis import _parse_and_execute
                j = _get_jarvis()
                with _chat_lock:
                    result = _parse_and_execute(cmd, j)
                    if not result:
                        result = j.chat(cmd)
                self._send_json({"response": result})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        # Sin cabeceras Access-Control-Allow-*: no se admite ningun origen
        # cruzado. La pagina solo se usa desde si misma (mismo origen).
        self.send_response(204)
        self.end_headers()


def main():
    print("=" * 60)
    print("  JARVIS - Interfaz Web")
    print("  Iniciando servidor...")
    print("=" * 60)

    # Precargar JARVIS
    try:
        j = _get_jarvis()
        print(f"  Ollama: CONECTADO ({j.cfg['ollama']['model']})")
    except Exception as e:
        print(f"  [WARN] Ollama no disponible: {e}")
        print("  La interfaz abrira pero el chat no funcionara.")

    try:
        import sounddevice as sd
        mic = sd.query_devices(kind="input")
        print(f"  Microfono: {mic.get('name','?')[:50]}")
    except Exception:
        print("  [WARN] Microfono no detectado")

    try:
        from jarvis_local.voice.tts import is_available
        if is_available():
            print("  TTS: DISPONIBLE")
    except Exception:
        pass

    server = ThreadingHTTPServer(("127.0.0.1", PORT), JarvisHandler)
    print(f"\n  Servidor: http://127.0.0.1:{PORT}")
    print("  Ctrl+C para detener\n")

    threading.Thread(target=lambda: time.sleep(0.8) or webbrowser.open(f"http://127.0.0.1:{PORT}"), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.shutdown()


if __name__ == "__main__":
    main()
