"""
JARVIS Local - Interfaz Web Ultra-Moderna (Iron Man style)
Servidor HTTP sin dependencias externas.
Uso: python -m jarvis_local.ui.server
"""
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PORT = 8080
_jarvis_instance = None
_chat_history: list[dict] = []


def _get_jarvis():
    global _jarvis_instance
    if _jarvis_instance is None:
        from jarvis_local.jarvis import Jarvis
        _jarvis_instance = Jarvis()
    return _jarvis_instance


def _get_status() -> dict:
    try:
        j = _get_jarvis()
        ollama_ok = j.client.is_running()
        models = j.client.list_models() if ollama_ok else []
    except Exception:
        ollama_ok = False
        models = []

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

    return {
        "ollama": ollama_ok,
        "model": "qwen2.5:3b" if ollama_ok else "N/A",
        "stt_model": vcfg.get("stt_model", "small"),
        "mic": mic_name,
        "tts": tts_ok,
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
<style>
  :root {
    --bg: #060b14;
    --surface: rgba(10,20,40,0.85);
    --surface2: rgba(15,30,55,0.7);
    --primary: #00c6ff;
    --primary-dim: rgba(0,198,255,0.15);
    --gold: #f0a500;
    --gold-dim: rgba(240,165,0,0.2);
    --text: #dce6f0;
    --text-dim: #6b7d95;
    --danger: #ff3b5c;
    --success: #00e676;
    --radius: 14px;
    --radius-sm: 8px;
    --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
    --transition: 0.25s cubic-bezier(0.4,0,0.2,1);
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
    display: flex;
    user-select: none;
    -webkit-user-select: none;
  }

  /* Background animation */
  .bg-grid {
    position: fixed; inset: 0; z-index: 0; opacity: 0.04;
    background-image:
      linear-gradient(rgba(0,198,255,0.3) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,198,255,0.3) 1px, transparent 1px);
    background-size: 60px 60px;
  }
  .bg-glow {
    position: fixed; width: 600px; height: 600px; border-radius: 50%;
    background: radial-gradient(circle, rgba(0,198,255,0.06) 0%, transparent 70%);
    top: 50%; left: 50%; transform: translate(-50%,-50%);
    z-index: 0; pointer-events: none; animation: glowPulse 4s ease-in-out infinite;
  }
  .bg-glow2 {
    position: fixed; width: 400px; height: 400px; border-radius: 50%;
    background: radial-gradient(circle, rgba(240,165,0,0.04) 0%, transparent 70%);
    top: 30%; left: 30%; z-index: 0; pointer-events: none;
    animation: glowPulse 6s ease-in-out infinite reverse;
  }
  @keyframes glowPulse {
    0%, 100% { opacity: 0.5; transform: translate(-50%,-50%) scale(1); }
    50% { opacity: 1; transform: translate(-50%,-50%) scale(1.2); }
  }

  /* Main layout */
  .app { position: relative; z-index: 1; display: flex; width: 100%; height: 100%; }

  /* Left panel - Orb + Controls */
  .left-panel {
    width: 380px; min-width: 380px;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 24px; padding: 40px 20px;
    background: linear-gradient(180deg, rgba(10,20,40,0.6) 0%, rgba(10,20,40,0.9) 100%);
    border-right: 1px solid rgba(0,198,255,0.08);
  }

  /* JARVIS Orb */
  .orb-container { position: relative; width: 200px; height: 200px; }
  .orb-ring {
    position: absolute; inset: 0; border-radius: 50%;
    border: 2px solid transparent;
    animation: orbSpin 8s linear infinite;
  }
  .orb-ring:nth-child(1) {
    inset: 0px; border-top-color: var(--primary);
    border-right-color: rgba(0,198,255,0.3);
    animation-duration: 8s;
  }
  .orb-ring:nth-child(2) {
    inset: 12px; border-bottom-color: var(--gold);
    border-left-color: rgba(240,165,0,0.3);
    animation-duration: 12s; animation-direction: reverse;
  }
  .orb-ring:nth-child(3) {
    inset: 24px; border-left-color: rgba(0,198,255,0.5);
    border-bottom-color: rgba(0,198,255,0.15);
    animation-duration: 16s;
  }
  @keyframes orbSpin { to { transform: rotate(360deg); } }

  .orb-core {
    position: absolute; inset: 36px; border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, rgba(0,198,255,0.25), rgba(0,198,255,0.05) 60%, transparent);
    display: flex; align-items: center; justify-content: center;
    border: 1px solid rgba(0,198,255,0.15);
    box-shadow: 0 0 40px rgba(0,198,255,0.1), inset 0 0 40px rgba(0,198,255,0.05);
    transition: all 0.6s ease;
  }
  .orb-core.listening {
    box-shadow: 0 0 80px rgba(0,198,255,0.3), inset 0 0 60px rgba(0,198,255,0.15);
    animation: corePulse 1s ease-in-out infinite;
  }
  .orb-core.thinking {
    box-shadow: 0 0 80px rgba(240,165,0,0.3), inset 0 0 60px rgba(240,165,0,0.15);
    animation: corePulse 0.5s ease-in-out infinite;
  }
  @keyframes corePulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
  }
  .orb-text {
    font-size: 11px; font-weight: 600; letter-spacing: 3px;
    color: var(--primary); text-transform: uppercase; text-align: center;
    transition: color 0.6s;
  }
  .orb-core.thinking .orb-text { color: var(--gold); }

  .orb-title {
    font-size: 20px; font-weight: 300; letter-spacing: 8px;
    color: var(--text); margin-top: 20px; text-align: center;
  }
  .orb-subtitle {
    font-size: 11px; color: var(--text-dim); letter-spacing: 4px;
    text-align: center; margin-top: 4px;
  }

  /* Voice button */
  .voice-btn {
    width: 64px; height: 64px; border-radius: 50%; border: 2px solid var(--primary);
    background: var(--primary-dim); color: var(--primary); cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: var(--transition); position: relative; font-size: 22px;
  }
  .voice-btn:hover { background: rgba(0,198,255,0.25); box-shadow: 0 0 30px rgba(0,198,255,0.2); }
  .voice-btn:active { transform: scale(0.95); }
  .voice-btn.recording {
    border-color: var(--danger); background: rgba(255,59,92,0.2); color: var(--danger);
    box-shadow: 0 0 30px rgba(255,59,92,0.3); animation: recPulse 1.5s ease-in-out infinite;
  }
  @keyframes recPulse {
    0%, 100% { box-shadow: 0 0 20px rgba(255,59,92,0.3); }
    50% { box-shadow: 0 0 50px rgba(255,59,92,0.5); }
  }
  .voice-label { font-size: 11px; color: var(--text-dim); margin-top: 6px; letter-spacing: 2px; text-transform: uppercase; }

  /* Right panel - Chat */
  .right-panel {
    flex: 1; display: flex; flex-direction: column; min-width: 0;
  }

  /* Status bar */
  .status-bar {
    display: flex; gap: 16px; padding: 14px 24px;
    background: var(--surface); border-bottom: 1px solid rgba(0,198,255,0.06);
    flex-wrap: wrap;
  }
  .status-dot {
    display: flex; align-items: center; gap: 7px; font-size: 11px; letter-spacing: 0.5px;
  }
  .status-dot::before {
    content: ''; width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  }
  .status-dot.on::before { background: var(--success); box-shadow: 0 0 6px var(--success); }
  .status-dot.off::before { background: var(--danger); }

  /* Chat */
  .chat-area {
    flex: 1; overflow-y: auto; padding: 20px 24px;
    display: flex; flex-direction: column; gap: 12px;
    scroll-behavior: smooth;
  }
  .chat-area::-webkit-scrollbar { width: 4px; }
  .chat-area::-webkit-scrollbar-track { background: transparent; }
  .chat-area::-webkit-scrollbar-thumb { background: rgba(0,198,255,0.1); border-radius: 4px; }

  .msg {
    display: flex; gap: 10px; animation: msgIn 0.3s ease;
    max-width: 85%;
  }
  @keyframes msgIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  .msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .msg.jarvis { align-self: flex-start; }

  .msg-avatar {
    width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
  }
  .msg.user .msg-avatar { background: var(--gold-dim); color: var(--gold); }
  .msg.jarvis .msg-avatar { background: var(--primary-dim); color: var(--primary); }

  .msg-bubble {
    padding: 10px 16px; border-radius: var(--radius-sm);
    font-size: 13px; line-height: 1.5; word-break: break-word;
  }
  .msg.user .msg-bubble {
    background: linear-gradient(135deg, rgba(0,198,255,0.15), rgba(0,198,255,0.05));
    border: 1px solid rgba(0,198,255,0.1); border-radius: var(--radius-sm) var(--radius-sm) 4px var(--radius-sm);
  }
  .msg.jarvis .msg-bubble {
    background: var(--surface2); border: 1px solid rgba(255,255,255,0.04);
    border-radius: var(--radius-sm) var(--radius-sm) var(--radius-sm) 4px;
  }
  .msg-time { font-size: 10px; color: var(--text-dim); margin-top: 4px; }
  .msg.user .msg-time { text-align: right; }

  .typing-indicator {
    align-self: flex-start; display: flex; gap: 4px; padding: 10px 16px;
    background: var(--surface2); border-radius: var(--radius-sm);
    border: 1px solid rgba(255,255,255,0.04);
  }
  .typing-dot {
    width: 6px; height: 6px; border-radius: 50%; background: var(--primary);
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
    display: flex; gap: 8px; padding: 10px 24px; flex-wrap: wrap;
    border-top: 1px solid rgba(0,198,255,0.06);
    background: rgba(10,20,40,0.4);
  }
  .quick-btn {
    padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(0,198,255,0.15);
    background: var(--primary-dim); color: var(--primary); cursor: pointer;
    font-size: 11px; letter-spacing: 0.5px; transition: var(--transition);
    font-family: var(--font); white-space: nowrap;
  }
  .quick-btn:hover { background: rgba(0,198,255,0.25); border-color: rgba(0,198,255,0.3); }

  /* Input */
  .input-area {
    display: flex; gap: 10px; padding: 14px 24px; border-top: 1px solid rgba(0,198,255,0.06);
    background: var(--surface);
  }
  .input-field {
    flex: 1; padding: 12px 18px; border-radius: 28px;
    border: 1px solid rgba(0,198,255,0.12); background: rgba(0,10,30,0.6);
    color: var(--text); font-size: 13px; font-family: var(--font);
    outline: none; transition: var(--transition);
  }
  .input-field:focus { border-color: var(--primary); box-shadow: 0 0 20px rgba(0,198,255,0.08); }
  .input-field::placeholder { color: var(--text-dim); }
  .send-btn {
    width: 46px; height: 46px; border-radius: 50%; border: none;
    background: linear-gradient(135deg, var(--primary), #0088cc);
    color: white; cursor: pointer; font-size: 16px;
    transition: var(--transition); flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
  }
  .send-btn:hover { box-shadow: 0 0 25px rgba(0,198,255,0.3); transform: scale(1.05); }
  .send-btn:active { transform: scale(0.95); }
  .send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* Toast */
  .toast {
    position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
    padding: 10px 24px; border-radius: 28px; font-size: 12px; z-index: 999;
    background: var(--surface); border: 1px solid rgba(0,198,255,0.2);
    color: var(--text); letter-spacing: 0.5px;
    animation: toastIn 0.3s ease, toastOut 0.3s ease 2.5s forwards;
    pointer-events: none;
  }
  @keyframes toastIn { from { opacity: 0; transform: translateX(-50%) translateY(-20px); } to { opacity: 1; } }
  @keyframes toastOut { from { opacity: 1; } to { opacity: 0; } }

  @media (max-width: 800px) {
    .left-panel { width: 100%; min-width: 100%; padding: 24px; }
    .app { flex-direction: column; }
    .orb-container { width: 120px; height: 120px; }
    .orb-core { inset: 22px; }
    .right-panel { flex: 1; }
  }
</style>
</head>
<body>
<div class="bg-grid"></div>
<div class="bg-glow"></div>
<div class="bg-glow2"></div>

<div class="app">
  <!-- Left Panel -->
  <div class="left-panel">
    <div class="orb-title">J A R V I S</div>
    <div class="orb-container" id="orbContainer">
      <div class="orb-ring"></div>
      <div class="orb-ring"></div>
      <div class="orb-ring"></div>
      <div class="orb-core" id="orbCore">
        <span class="orb-text" id="orbText">LISTO</span>
      </div>
    </div>
    <div class="orb-subtitle">SISTEMA OPERATIVO</div>

    <button class="voice-btn" id="voiceBtn" onclick="toggleVoice()" title="Presiona para hablar">
      &#x1F399;
    </button>
    <div class="voice-label" id="voiceLabel">HABLAR</div>
  </div>

  <!-- Right Panel -->
  <div class="right-panel">
    <!-- Status -->
    <div class="status-bar" id="statusBar">
      <div class="status-dot on" id="stOllama">Ollama</div>
      <div class="status-dot on" id="stMic">Micrófono</div>
      <div class="status-dot on" id="stTTS">Voz</div>
      <div class="status-dot on" id="stModel">qwen2.5:3b</div>
    </div>

    <!-- Chat -->
    <div class="chat-area" id="chatArea">
      <div class="msg jarvis">
        <div class="msg-avatar">J</div>
        <div>
          <div class="msg-bubble">Bienvenido, señor. JARVIS en línea. Todos los sistemas operando con normalidad. ¿En qué puedo asistirle?</div>
          <div class="msg-time" id="initTime"></div>
        </div>
      </div>
    </div>

    <!-- Quick commands -->
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

    <!-- Input -->
    <div class="input-area">
      <input type="text" class="input-field" id="inputField"
             placeholder="Escribe un comando o mensaje..."
             onkeydown="if(event.key==='Enter') sendMessage()">
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">&#x27A4;</button>
    </div>
  </div>
</div>
<div id="toastContainer"></div>

<script>
const API = '/api';
let isProcessing = false;
let voiceActive = false;

document.getElementById('initTime').textContent = new Date().toLocaleTimeString();
refreshStatus();
setInterval(refreshStatus, 10000);

function $(id) { return document.getElementById(id); }

async function refreshStatus() {
  try {
    const r = await fetch(API + '/status');
    const s = await r.json();
    updateDot('stOllama', 'Ollama', s.ollama);
    updateDot('stMic', 'Micrófono', true);
    updateDot('stTTS', 'Voz', s.tts);
    $('stModel').textContent = s.model || 'N/A';
  } catch(e) {}
}

function updateDot(id, label, on) {
  const el = $(id);
  el.className = 'status-dot ' + (on ? 'on' : 'off');
  el.childNodes[0] && (el.childNodes[0].textContent = '');
  el.textContent = label;
}

function setOrbState(state) {
  const core = $('orbCore');
  const text = $('orbText');
  core.classList.remove('listening', 'thinking');
  if (state === 'listening') {
    core.classList.add('listening'); text.textContent = 'ESCUCHANDO';
  } else if (state === 'thinking') {
    core.classList.add('thinking'); text.textContent = 'PROCESANDO';
  } else {
    text.textContent = 'LISTO';
  }
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
  const time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = new Date().toLocaleTimeString();

  wrap.appendChild(bubble);
  wrap.appendChild(time);
  div.appendChild(avatar);
  div.appendChild(wrap);
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return bubble;
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
      headers: {'Content-Type': 'application/json'},
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

async function toggleVoice() {
  if (isProcessing) {
    toast('JARVIS está procesando. Espere por favor.');
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

    try {
      const r = await fetch(API + '/voice', {method: 'POST'});
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

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
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
            self._send_html(HTML)
        elif path == "/api/status":
            self._send_json(_get_status())
        elif path == "/api/history":
            self._send_json({"history": _chat_history[-50:]})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
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
                response = j.chat(msg)
                _chat_history.append({"role": "user", "content": msg})
                _chat_history.append({"role": "assistant", "content": response})
                self._send_json({"response": response})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/voice":
            try:
                from jarvis_local.voice.stt import capture_and_transcribe
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
                result = _parse_and_execute(cmd, j)
                if result:
                    self._send_json({"response": result})
                else:
                    response = j.chat(cmd)
                    self._send_json({"response": response})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

    server = HTTPServer(("127.0.0.1", PORT), JarvisHandler)
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
