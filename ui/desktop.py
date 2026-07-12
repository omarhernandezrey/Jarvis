"""
JARVIS Local — Interfaz de Escritorio Holográfica Ultra-Moderna
GUI tkinter con estética HUD / arc-reactor / "tecnología de otro mundo".
Sin dependencias externas.
"""
import math
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ═══════════════════════════════════════════════════════════
# PALETA — HOLOGRAMA / ARC REACTOR
# ═══════════════════════════════════════════════════════════
C = {
    "bg":           "#02040a",
    "bg2":          "#040a16",
    "surface":      "#08111f",
    "surface2":     "#0d1a2e",
    "primary":      "#00e5ff",
    "primary_dim":  "#04202f",
    "accent":       "#8b5cf6",   # violeta "alien"
    "accent_dim":   "#170a2e",
    "gold":         "#ffb020",
    "gold_dim":     "#241503",
    "text":         "#e6f4ff",
    "text_dim":     "#4d6a86",
    "danger":       "#ff2d55",
    "success":      "#00ffa3",
    "white":        "#ffffff",
    "border":       "#132038",
    "grid":         "#0a1728",
    "input_bg":     "#050d1a",
    "titlebar":     "#03070f",
    "term_bg":      "#00060d",
    "term_border":  "#0f4a63",
    "term_glow":    "#0a2e40",
}

MONO = "Consolas"
UI_FONT = "Segoe UI"
GLITCH_CHARS = "!<>-_\\/[]{}—=+*^?#$%~01アイウエオカキクケコ"


def spaced(s):
    return " ".join(list(s))


def _rand_hex(n=4):
    return "".join(random.choice("0123456789ABCDEF") for _ in range(n))


# ═══════════════════════════════════════════════════════════
# BACKEND
# ═══════════════════════════════════════════════════════════
_jarvis = None
_result_queue = queue.Queue()
_voice_buffer, _voice_stream, _voice_lock = [], None, threading.Lock()


def _get_jarvis():
    global _jarvis
    if _jarvis is None:
        from jarvis_local.jarvis import Jarvis
        _jarvis = Jarvis()
    return _jarvis


def _chat_async(message: str):
    try:
        resp = _get_jarvis().chat(message)
        _result_queue.put(("ok", resp))
    except Exception as e:
        _result_queue.put(("error", str(e)))


def _voice_start(sr=16000):
    global _voice_buffer, _voice_stream
    with _voice_lock:
        _voice_buffer = []
        import sounddevice as sd
        def _cb(indata, frames, time_info, status):
            _voice_buffer.append(indata.copy())
        _voice_stream = sd.InputStream(samplerate=sr, channels=1, dtype="int16", callback=_cb, blocksize=1024)
        _voice_stream.start()


def _voice_stop():
    global _voice_buffer, _voice_stream
    with _voice_lock:
        if _voice_stream is None:
            return None
        _voice_stream.stop(); _voice_stream.close(); _voice_stream = None
        if not _voice_buffer:
            return None
        import numpy as np
        audio = np.concatenate(_voice_buffer, axis=0).flatten().astype("float32") / 32768.0
        _voice_buffer = []
    if len(audio) < 8000:
        return None
    try:
        from jarvis_local.voice.stt import _get_whisper_model, load_voice_config
        cfg = load_voice_config()
        m = _get_whisper_model(cfg.get("stt_model","small"), cfg.get("stt_compute_type","int8"))
        segs, _ = m.transcribe(audio, language="es", beam_size=5, vad_filter=True,
                                vad_parameters={"min_silence_duration_ms":500})
        t = " ".join(s.text.strip() for s in segs).strip()
        return t if len(t) >= 2 else None
    except Exception:
        return None


def _tts_speak(text: str):
    try:
        from jarvis_local.voice.tts import is_speaking, speak
        while is_speaking():
            time.sleep(0.05)
        speak(text)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ═══════════════════════════════════════════════════════════
class JarvisDesktop:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S — Sistema Inteligente")
        self.root.configure(bg=C["bg"])

        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        w, h = int(sw * 0.64), int(sh * 0.70)
        x, y = (sw - w) // 2, (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(600, 380)

        self.is_processing = False
        self.tts_enabled = True
        self._voice_active = False
        self._speaking = False
        self.orb_angle = 0.0
        self.orb_state = "idle"          # idle | processing | listening | speaking
        self._pulse_phase = 0.0
        self._electrons = []
        self._particles = []
        self._scan_y = 0
        self._wave_phase = 0.0
        self._resize_after = None
        self._quick_cols = 0
        self._typewriter_job = None

        self.root.bind("<KeyPress-space>", self._on_space_press)
        self.root.bind("<KeyRelease-space>", self._on_space_release)
        self.root.bind("<KeyRelease-Control_L>", self._on_ctrl_release)
        self.root.bind("<KeyRelease-Control_R>", self._on_ctrl_release)
        self.root.bind("<Control-l>", lambda e: self.input_field.focus_set())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._boot_sequence()

    # ═══════════════════════════════════════════════════════
    # SECUENCIA DE ARRANQUE
    # ═══════════════════════════════════════════════════════
    def _boot_sequence(self):
        boot = tk.Canvas(self.root, bg=C["bg"], highlightthickness=0)
        boot.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.root.update_idletasks()
        w = self.root.winfo_width(); h = self.root.winfo_height()
        cx, cy = w // 2, h // 2

        lines = [
            "INICIALIZANDO NÚCLEO COGNITIVO...",
            "CALIBRANDO MATRICES NEURONALES...",
            "ENLAZANDO MODELO qwen2.5:3b...",
            "SISTEMAS EN LÍNEA.",
        ]
        state = {"i": 0, "ring": 0}

        def draw(step):
            boot.delete("all")
            for k in range(3):
                r = 20 + k * 26 + (step * 3) % 26
                a = max(0, 0.55 - k * 0.15 - (step % 26) / 26 * 0.3)
                if a <= 0: continue
                col = self._dim(C["primary"], a)
                boot.create_oval(cx-r, cy-r, cx+r, cy+r, outline=col, width=1)
            core_r = 10 + 3 * math.sin(step / 6)
            boot.create_oval(cx-core_r, cy-core_r, cx+core_r, cy+core_r,
                              fill=C["primary"], outline="")
            idx = min(state["i"], len(lines) - 1)
            boot.create_text(cx, cy + 90, text=spaced(lines[idx]),
                              fill=C["primary"], font=(MONO, 10))
            bw = 260
            boot.create_rectangle(cx-bw/2, cy+115, cx+bw/2, cy+119, outline=C["border"])
            prog = min(1.0, step / 90)
            boot.create_rectangle(cx-bw/2, cy+115, cx-bw/2+bw*prog, cy+119,
                                   fill=C["primary"], outline="")
            boot.create_text(cx, cy-120, text="J . A . R . V . I . S",
                              fill=C["text"], font=(UI_FONT, 22, "bold"))

        def tick(step=0):
            if step > 95:
                boot.destroy()
                self._start_animations()
                self._poll_results()
                self._update_status()
                self._sys("JARVIS en línea. Todos los sistemas operando con normalidad.")
                return
            if step % 24 == 0 and step > 0:
                state["i"] += 1
            draw(step)
            self.root.after(16, tick, step + 1)

        tick()

    # ═══════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════
    def _build_ui(self):
        self.bg_canvas = tk.Canvas(self.root, bg=C["bg"], highlightthickness=0)
        self.bg_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Barra de estado
        self.status_bar = tk.Frame(self.root, bg=C["titlebar"], height=38)
        self.status_bar.pack(fill=tk.X, side=tk.TOP)
        self.status_bar.pack_propagate(False)
        sep = tk.Canvas(self.status_bar, height=1, bg=C["titlebar"], highlightthickness=0)
        sep.pack(side=tk.BOTTOM, fill=tk.X)
        self._sep_canvas = sep

        left_sb = tk.Frame(self.status_bar, bg=C["titlebar"]); left_sb.pack(side=tk.LEFT, fill=tk.Y, padx=(14,0))
        tk.Label(left_sb, text="◉", font=(UI_FONT, 10), bg=C["titlebar"], fg=C["primary"]).pack(side=tk.LEFT)
        tk.Label(left_sb, text=" " + spaced("JARVIS"), font=(UI_FONT, 9, "bold"),
                 bg=C["titlebar"], fg=C["primary"]).pack(side=tk.LEFT)
        self.sb_status = tk.Label(left_sb, text="   │  Sistema operativo", font=(MONO, 8),
                                   bg=C["titlebar"], fg=C["text_dim"]); self.sb_status.pack(side=tk.LEFT)

        # Visualizador de onda (vida ambiental)
        self.wave_canvas = tk.Canvas(left_sb, width=110, height=26, bg=C["titlebar"], highlightthickness=0)
        self.wave_canvas.pack(side=tk.LEFT, padx=(10, 0))

        right_sb = tk.Frame(self.status_bar, bg=C["titlebar"]); right_sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,12))
        self._dot(right_sb, "OLLAMA", True).pack(side=tk.LEFT, padx=(0,10))
        self._dot(right_sb, "MIC", True).pack(side=tk.LEFT, padx=(0,10))
        self.st_tts = self._dot(right_sb, "VOZ", True); self.st_tts.pack(side=tk.LEFT, padx=(0,10))
        tk.Label(right_sb, text="qwen2.5:3b", font=(MONO, 8),
                 bg=C["titlebar"], fg=C["text_dim"]).pack(side=tk.LEFT, padx=(0,12))
        self.tts_btn = tk.Button(right_sb, text="\U0001F50A VOZ ON", font=(UI_FONT, 8, "bold"),
                                  bg=C["primary_dim"], fg=C["primary"], activebackground=C["primary_dim"],
                                  activeforeground=C["white"], relief=tk.FLAT, borderwidth=1, cursor="hand2",
                                  command=self._toggle_tts, padx=8, pady=1)
        self.tts_btn.pack(side=tk.LEFT)
        self._hover(self.tts_btn, C["primary_dim"], "#0e3348")

        # PanedWindow
        self.pane = tk.PanedWindow(self.root, bg=C["border"], sashwidth=2, sashrelief=tk.FLAT, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6,8))

        # ——— Panel izquierdo ———
        self.left_panel = tk.Frame(self.pane, bg=C["bg"]); self.pane.add(self.left_panel, width=290, minsize=170)
        self.left_hud = tk.Canvas(self.left_panel, bg=C["bg"], highlightthickness=0)
        self.left_hud.place(relx=0, rely=0, relwidth=1, relheight=1)
        left_inner = tk.Frame(self.left_panel, bg=C["bg"]); left_inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        tf = tk.Frame(left_inner, bg=C["bg"]); tf.pack(fill=tk.X, pady=(10,0))
        self.left_title = tk.Label(tf, text=spaced("JARVIS"), font=(UI_FONT, 19, "bold"), bg=C["bg"], fg=C["text"])
        self.left_title.pack()
        self.left_sub = tk.Label(tf, text=spaced("SISTEMA AUTONOMO"), font=(MONO, 7),
                                  bg=C["bg"], fg=C["text_dim"]); self.left_sub.pack(pady=(2,0))

        self.orb_canvas = tk.Canvas(left_inner, bg=C["bg"], highlightthickness=0)
        self.orb_canvas.pack(expand=True, pady=(10,4))

        self.orb_label = tk.Label(left_inner, text=spaced("LISTO"), font=(MONO, 9, "bold"),
                                   bg=C["bg"], fg=C["primary"]); self.orb_label.pack()

        self.voice_btn = tk.Button(left_inner, text="\U0001F399  HABLAR", font=(UI_FONT, 9, "bold"),
                                    bg=C["primary_dim"], fg=C["primary"], activebackground=C["primary_dim"],
                                    activeforeground=C["white"], relief=tk.FLAT, borderwidth=1, cursor="hand2",
                                    padx=16, pady=8)
        self.voice_btn.pack(pady=(12,3))
        self.voice_btn.bind("<ButtonPress-1>", lambda e: self._voice_start_recording())
        self.voice_btn.bind("<ButtonRelease-1>", lambda e: self._voice_stop_recording())
        self._hover(self.voice_btn, C["primary_dim"], "#0e3348")
        self.voice_hint = tk.Label(left_inner, text="Mantén  •  Ctrl+Espacio", font=(MONO, 7),
                                    bg=C["bg"], fg=C["text_dim"]); self.voice_hint.pack(pady=(0,6))

        # Telemetría decorativa (sensación "viva")
        self.telemetry = tk.Label(left_inner, text="", font=(MONO, 7), bg=C["bg"], fg=C["text_dim"], justify=tk.LEFT)
        self.telemetry.pack(side=tk.BOTTOM, pady=(4,0))

        # ——— Panel derecho ———
        self.right_panel = tk.Frame(self.pane, bg=C["surface"]); self.pane.add(self.right_panel, minsize=300)
        self.right_hud = tk.Canvas(self.right_panel, bg=C["surface"], highlightthickness=0)
        self.right_hud.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Input — estilo prompt de terminal, siempre visible abajo
        inf_wrap = tk.Frame(self.right_panel, bg=C["term_border"])
        inf_wrap.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(4,10))
        inf = tk.Frame(inf_wrap, bg=C["term_bg"])
        inf.pack(fill=tk.X, padx=1, pady=1)

        self.input_prompt = tk.Label(inf, text=" ❯", font=(MONO, 13, "bold"),
                                      bg=C["term_bg"], fg=C["primary"])
        self.input_prompt.pack(side=tk.LEFT, padx=(8,0))

        self.input_field = tk.Text(inf, bg=C["term_bg"], fg=C["text"], font=(MONO, 11),
                                    wrap=tk.WORD, relief=tk.FLAT, borderwidth=0, padx=8, pady=9,
                                    insertbackground=C["primary"], height=2,
                                    highlightthickness=0)
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2,4))
        self.input_field.bind("<Return>", self._on_enter)
        self.input_field.bind("<Shift-Return>", lambda e: None)

        self.send_btn = tk.Button(inf, text="➤", font=(UI_FONT, 14, "bold"),
                                   bg=C["term_bg"], fg=C["primary"], activebackground=C["term_bg"],
                                   activeforeground=C["accent"], relief=tk.FLAT, borderwidth=0,
                                   cursor="hand2", command=self._send_from_input, padx=12, pady=6)
        self.send_btn.pack(side=tk.RIGHT)
        self._hover(self.send_btn, C["term_bg"], C["term_bg"])

        # Quick buttons
        self.quick_frame = tk.Frame(self.right_panel, bg=C["surface"])
        self.quick_frame.pack(fill=tk.X, padx=10, pady=(8,3))
        self.quick_commands = [
            ("Estado", "Estado del sistema"), ("Chrome", "Abre Chrome"),
            ("VS Code", "Abre VS Code"), ("Archivos", "Lista mis archivos"),
            ("Explorador", "Abre el explorador"), ("Terminal", "Ejecuta dir"),
        ]
        self._build_quick_buttons()

        # ═══ TERMINAL — enlace neural (chat) ═══
        term_wrap = tk.Frame(self.right_panel, bg=C["term_border"])
        term_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2,2))
        term_inner = tk.Frame(term_wrap, bg=C["term_bg"])
        term_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        header = tk.Frame(term_inner, bg=C["titlebar"], height=32)
        header.pack(fill=tk.X, side=tk.TOP); header.pack_propagate(False)
        self._live_dot = tk.Label(header, text="●", font=(MONO, 9), bg=C["titlebar"], fg=C["danger"])
        self._live_dot.pack(side=tk.LEFT, padx=(10,3))
        tk.Label(header, text="ENLACE NEURAL", font=(MONO, 8, "bold"),
                 bg=C["titlebar"], fg=C["text_dim"]).pack(side=tk.LEFT)
        tk.Label(header, text="root@jarvis :: /neural-link", font=(MONO, 8),
                 bg=C["titlebar"], fg=C["text_dim"]).pack(side=tk.LEFT, padx=(10,0))
        self.term_bar = tk.Canvas(header, width=130, height=22, bg=C["titlebar"], highlightthickness=0)
        self.term_bar.pack(side=tk.RIGHT, padx=(0,10))

        cf = tk.Frame(term_inner, bg=C["term_bg"]); cf.pack(fill=tk.BOTH, expand=True)
        self.chat = tk.Text(cf, bg=C["term_bg"], fg=C["text"], font=(MONO, 10),
                             wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT, borderwidth=0,
                             padx=14, pady=10, insertbackground=C["primary"], cursor="arrow",
                             spacing1=1, spacing3=1)
        self.chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(cf, bg=C["term_bg"], troughcolor=C["bg"]); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat.config(yscrollcommand=sb.set); sb.config(command=self.chat.yview)

        for tag, fg, bg, font in [
            ("prompt_user", C["gold"], None, (MONO, 10, "bold")),
            ("prompt_jarvis", C["primary"], None, (MONO, 10, "bold")),
            ("id_tag", C["accent"], None, (MONO, 8)),
            ("msg_user", C["text"], None, (MONO, 10)),
            ("msg_jarvis", C["text"], None, (MONO, 10)),
            ("glitch_user", C["gold"], None, (MONO, 10)),
            ("glitch_jarvis", C["primary"], None, (MONO, 10)),
            ("time", C["text_dim"], None, (MONO, 7)),
            ("sep", C["term_glow"], None, (MONO, 8)),
            ("sys", C["accent"], None, (MONO, 8, "italic")),
            ("typing", C["primary"], None, (MONO, 9, "italic")),
            ("cursor", C["primary"], None, (MONO, 10, "bold")),
        ]:
            opts = {"foreground": fg, "font": font}
            if bg: opts["background"] = bg
            if "msg" in tag or "glitch" in tag: opts.update({"lmargin1": 22, "lmargin2": 22, "rmargin": 12})
            self.chat.tag_config(tag, **opts)

        self._cursor_shown = False
        self._cursor_on = True

        # Bindings responsive
        self.left_panel.bind("<Configure>", self._on_left_resize)
        self.right_panel.bind("<Configure>", self._on_right_resize)

        self._draw_orb(160)
        self.input_field.focus_set()

    def _dot(self, parent, text, on):
        f = tk.Frame(parent, bg=C["titlebar"])
        c = C["success"] if on else C["danger"]
        d = tk.Canvas(f, width=8, height=8, bg=C["titlebar"], highlightthickness=0)
        d.create_oval(1, 1, 7, 7, fill=c, outline=""); d.pack(side=tk.LEFT, padx=(0,4))
        tk.Label(f, text=text, font=(MONO, 8), bg=C["titlebar"], fg=C["text_dim"]).pack(side=tk.LEFT)
        return f

    def _hover(self, widget, normal_bg, hover_bg):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))

    # ═══════════════════════════════════════════════════════
    # FONDO — grid + constelación de partículas
    # ═══════════════════════════════════════════════════════
    def _init_particles(self):
        w = self.root.winfo_width(); h = self.root.winfo_height()
        self._particles = []
        for _ in range(52):
            self._particles.append({
                "x": random.uniform(0, w), "y": random.uniform(0, h),
                "r": random.uniform(0.6, 1.8),
                "vx": random.uniform(-0.18, 0.18), "vy": random.uniform(-0.22, -0.05),
                "alpha": random.uniform(0.15, 0.5),
            })

    def _draw_grid(self, w, h):
        self.bg_canvas.delete("grid")
        step = 42
        for gx in range(0, w, step):
            self.bg_canvas.create_line(gx, 0, gx, h, fill=C["grid"], tags="grid")
        for gy in range(0, h, step):
            self.bg_canvas.create_line(0, gy, w, gy, fill=C["grid"], tags="grid")
        self.bg_canvas.tag_lower("grid")

    def _animate_particles(self):
        if not hasattr(self, 'bg_canvas'):
            return
        w = self.root.winfo_width(); h = self.root.winfo_height()
        if not self._particles:
            self._init_particles()
            self._draw_grid(w, h)
        self.bg_canvas.delete("particle")
        pts = self._particles
        for p in pts:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["y"] < 0: p["y"] = h; p["x"] = random.uniform(0, w)
            if p["x"] < 0: p["x"] = w
            if p["x"] > w: p["x"] = 0

        # Conexiones tipo constelación entre partículas cercanas
        n = len(pts)
        for i in range(n):
            for j in range(i+1, n):
                dx = pts[i]["x"]-pts[j]["x"]; dy = pts[i]["y"]-pts[j]["y"]
                d2 = dx*dx + dy*dy
                if d2 < 130*130:
                    a = max(0.0, 0.12 * (1 - (d2 ** 0.5) / 130))
                    if a > 0.01:
                        col = self._dim(C["primary"], a)
                        self.bg_canvas.create_line(pts[i]["x"], pts[i]["y"], pts[j]["x"], pts[j]["y"],
                                                    fill=col, tags="particle")
        for p in pts:
            a = p["alpha"]
            color = self._dim(C["primary"], a)
            r2 = p["r"]
            self.bg_canvas.create_oval(p["x"]-r2, p["y"]-r2, p["x"]+r2, p["y"]+r2,
                                        fill=color, outline="", tags="particle")

        # Línea de escaneo vertical descendente, con estela
        self._scan_y = (self._scan_y + 1.4) % h
        self.bg_canvas.delete("scan")
        self.bg_canvas.create_line(0, self._scan_y, w, self._scan_y,
                                    fill=self._dim(C["primary"], 0.10), tags="scan")
        self.bg_canvas.tag_lower("scan")
        self.bg_canvas.tag_lower("grid")

        self.root.after(45, self._animate_particles)

    # ═══════════════════════════════════════════════════════
    # HUD — corner brackets tipo mira táctica
    # ═══════════════════════════════════════════════════════
    def _draw_hud_frame(self, canvas, w, h, color, size=16, pad=4):
        canvas.delete("hud")
        pts = [
            (pad, pad, pad+size, pad, pad, pad+size),
            (w-pad, pad, w-pad-size, pad, w-pad, pad+size),
            (pad, h-pad, pad+size, h-pad, pad, h-pad-size),
            (w-pad, h-pad, w-pad-size, h-pad, w-pad, h-pad-size),
        ]
        for x, y, x2, y2, x3, y3 in pts:
            canvas.create_line(x, y, x2, y2, fill=color, width=2, tags="hud")
            canvas.create_line(x, y, x3, y3, fill=color, width=2, tags="hud")
        canvas.tag_lower("hud")

    def _redraw_huds(self):
        try:
            lw = self.left_panel.winfo_width(); lh = self.left_panel.winfo_height()
            if lw > 2 and lh > 2:
                self._draw_hud_frame(self.left_hud, lw, lh, self._dim(C["primary"], 0.35))
            rw = self.right_panel.winfo_width(); rh = self.right_panel.winfo_height()
            if rw > 2 and rh > 2:
                self._draw_hud_frame(self.right_hud, rw, rh, self._dim(C["accent"], 0.30))
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════
    # ORB — Reactor Arc vivo (radar + electrones + estado por color)
    # ═══════════════════════════════════════════════════════
    def _draw_orb(self, size=160):
        self.orb_canvas.config(width=size, height=size)
        self._orb_size = size
        cx, cy = size//2, size//2
        self._orb_cx, self._orb_cy, self._orb_r = cx, cy, int(size*0.48)
        self._electrons = []
        for k in range(3):
            self._electrons.append({
                "r": self._orb_r * (0.62 + k*0.14),
                "a": random.uniform(0, 360),
                "speed": random.choice([-1, 1]) * (1.4 + k*0.5),
            })

    def _state_color(self):
        return {
            "idle": C["primary"],
            "processing": C["gold"],
            "listening": C["danger"],
            "speaking": C["success"],
        }.get(self.orb_state, C["primary"])

    def _start_animations(self):
        self._init_particles()
        self._animate_particles()
        self._animate_orb()
        self._animate_wave()
        self._animate_telemetry()
        self._animate_termbar()
        self._animate_live_dot()
        self._cursor_blink()
        self._redraw_huds()

    def _animate_orb(self):
        self.orb_angle = (self.orb_angle + 1.6) % 360
        self._pulse_phase += 0.09
        oc = self.orb_canvas
        oc.delete("live")
        cx, cy, R = self._orb_cx, self._orb_cy, self._orb_r
        base = self._state_color()

        # Halo exterior (glow simulado por capas)
        for i, f in enumerate([0.22, 0.14, 0.07]):
            rr = R * (1.28 + i*0.16)
            oc.create_oval(cx-rr, cy-rr, cx+rr, cy+rr, outline=self._dim(base, f), tags="live")

        # Anillos fijos ya dibujados en _draw_orb persisten; aquí solo arcos móviles
        r1, r2, r3 = int(R*0.98), int(R*0.80), int(R*0.60)
        for r, color, offset, ext in [(r1, base, 0, 60), (r2, C["accent"], 130, 45), (r3, base, 250, 70)]:
            start = (self.orb_angle + offset) % 360
            oc.create_arc(cx-r, cy-r, cx+r, cy+r, start=start, extent=ext,
                           outline=color, width=2, style="arc", tags="live")

        # Radar sweep (cuña giratoria con estela)
        sweep_r = int(R*0.98)
        for k, extent in [(0, 26), (1, 14), (2, 6)]:
            a = max(0.05, 0.32 - k*0.10)
            start = (self.orb_angle*1.4 - k*10) % 360
            oc.create_arc(cx-sweep_r, cy-sweep_r, cx+sweep_r, cy+sweep_r, start=start, extent=extent,
                           fill=self._dim(base, a), outline="", style="pieslice", tags="live")

        # Ticks perimetrales
        for t in range(24):
            ang = math.radians(t * 15)
            r_out = R * 1.02
            r_in = R * (0.94 if t % 6 else 0.88)
            x1, y1 = cx + r_out*math.cos(ang), cy + r_out*math.sin(ang)
            x2, y2 = cx + r_in*math.cos(ang), cy + r_in*math.sin(ang)
            oc.create_line(x1, y1, x2, y2, fill=self._dim(base, 0.25), tags="live")

        # Electrones orbitando
        for e in self._electrons:
            e["a"] = (e["a"] + e["speed"]) % 360
            ang = math.radians(e["a"])
            ex, ey = cx + e["r"]*math.cos(ang), cy + e["r"]*math.sin(ang)
            oc.create_oval(ex-2.4, ey-2.4, ex+2.4, ey+2.4, fill=C["white"], outline="", tags="live")
            oc.create_oval(ex-4.5, ey-4.5, ex+4.5, ey+4.5, outline=self._dim(base,0.4), tags="live")

        # Núcleo con respiración (breathing)
        breathe = 1.0 + 0.10*math.sin(self._pulse_phase)
        r4 = R * 0.22 * breathe
        oc.create_oval(cx-r4*1.7, cy-r4*1.7, cx+r4*1.7, cy+r4*1.7,
                        outline=self._dim(base, 0.25), tags="live")
        oc.create_oval(cx-r4, cy-r4, cx+r4, cy+r4,
                        fill=self._dim(base, 0.85), outline=base, width=1, tags="live")
        oc.create_oval(cx-r4*0.45, cy-r4*0.45, cx+r4*0.45, cy+r4*0.45,
                        fill=C["white"], outline="", tags="live")

        self.root.after(33, self._animate_orb)

    def _pulse_orb(self, color):
        cx, cy, r = self._orb_cx, self._orb_cy, int(self._orb_r*0.30)
        def frame(i=0):
            if i > 5:
                self.orb_canvas.delete("pulse"); return
            self.orb_canvas.delete("pulse")
            rr = r + i*10
            f = max(0.04, 0.5 - i*0.09)
            self.orb_canvas.create_oval(cx-rr, cy-rr, cx+rr, cy+rr, outline=self._dim(color, f),
                                         width=2, tags="pulse")
            self.root.after(45, frame, i+1)
        frame()

    def _dim(self, hx, f):
        f = max(0.0, min(1.0, f))
        r, g, b = int(hx[1:3],16), int(hx[3:5],16), int(hx[5:7],16)
        br, bg_, bb = int(C["bg"][1:3],16), int(C["bg"][3:5],16), int(C["bg"][5:7],16)
        r = int(br + (r-br)*f); g = int(bg_ + (g-bg_)*f); b = int(bb + (b-bb)*f)
        return f'#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}'

    # ═══════════════════════════════════════════════════════
    # VISUALIZADOR DE VOZ (barras animadas — sensación de vida)
    # ═══════════════════════════════════════════════════════
    def _animate_wave(self):
        wc = self.wave_canvas
        wc.delete("all")
        w, h = 110, 26
        bars = 13
        # Escala de amplitud por estado: JARVIS hablando > escuchándote > procesando > reposo
        state = self.orb_state
        if state == "listening":       # tú hablas — el más grande y agitado
            color, scale, speed, jitter = C["danger"], 0.98, 7.5, 4.0
        elif state == "speaking":      # JARVIS habla — grande y fluido
            color, scale, speed, jitter = C["success"], 0.88, 5.2, 1.8
        elif state == "processing":
            color, scale, speed, jitter = C["gold"], 0.5, 3.0, 1.0
        else:
            color, scale, speed, jitter = C["text_dim"], 0.14, 1.4, 0.3
        for i in range(bars):
            self._wave_phase += 0.0016
            amp = abs(math.sin(self._wave_phase*speed + i*0.85)) * (h*scale) + random.uniform(0, jitter)
            amp = min(amp, h - 2)
            x = i * (w/bars) + 3
            wc.create_line(x, h/2 - amp/2, x, h/2 + amp/2, fill=color, width=3, capstyle=tk.ROUND)
        self.root.after(55, self._animate_wave)

    # ═══════════════════════════════════════════════════════
    # TELEMETRÍA DECORATIVA (ambiente "sci-fi vivo")
    # ═══════════════════════════════════════════════════════
    def _animate_telemetry(self):
        cpu = random.randint(4, 18) if not self.is_processing else random.randint(35, 78)
        mem = random.randint(28, 41)
        lat = random.randint(8, 46)
        txt = f"CPU {cpu:>2}%   MEM {mem:>2}%   LAT {lat:>3}ms"
        try:
            self.telemetry.config(text=txt)
        except Exception:
            pass
        self.root.after(1400, self._animate_telemetry)

    # ═══════════════════════════════════════════════════════
    # TERMINAL — enlace neural (chat estilo consola holográfica)
    # ═══════════════════════════════════════════════════════
    def _append(self, sender, text):
        self._cursor_remove()
        self.chat.config(state=tk.NORMAL)
        now = time.strftime("%H:%M:%S")
        self.chat.insert(tk.END, f"\n[{now}] ", "time")
        if sender == "user":
            self.chat.insert("end-1c", "OMAR ❯ ", "prompt_user")
            self.chat.insert("end-1c", text + "\n", "msg_user")
            self.chat.config(state=tk.DISABLED)
            self.chat.see(tk.END)
            self._cursor_add()
        else:
            self.chat.insert("end-1c", f"JARVIS #{_rand_hex()} ❯ ", "prompt_jarvis")
            self.chat.config(state=tk.DISABLED)
            self.chat.see(tk.END)
            self._typewrite(text, "msg_jarvis", "glitch_jarvis", chunk=2, delay=12,
                             on_done=self._append_separator)

    def _append_separator(self):
        self.chat.config(state=tk.NORMAL)
        self.chat.insert("end-1c", "\n " + "╌" * 44 + "\n", "sep")
        self.chat.config(state=tk.DISABLED)
        self.chat.see(tk.END)

    def _typewrite(self, text, tag, glitch_tag, i=0, chunk=2, delay=12, on_done=None):
        if self._typewriter_job:
            self.root.after_cancel(self._typewriter_job)
        self.chat.config(state=tk.NORMAL)
        end = min(len(text), i + chunk)
        real = text[i:end]
        glitch = "".join(random.choice(GLITCH_CHARS) for _ in real)
        self.chat.insert("end-1c", glitch, glitch_tag)
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)
        self._typewriter_job = self.root.after(
            delay, self._settle_glitch, text, tag, glitch_tag, i, end, chunk, delay, on_done)

    def _settle_glitch(self, text, tag, glitch_tag, i, end, chunk, delay, on_done):
        self.chat.config(state=tk.NORMAL)
        n = end - i
        if n > 0:
            self.chat.delete(f"end-{n+1}c", "end-1c")
            self.chat.insert("end-1c", text[i:end], tag)
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)
        if end < len(text):
            self._typewriter_job = self.root.after(
                delay, self._typewrite, text, tag, glitch_tag, end, chunk, delay, on_done)
        else:
            self.chat.config(state=tk.NORMAL)
            self.chat.insert("end-1c", "\n", tag)
            self.chat.config(state=tk.DISABLED)
            self._typewriter_job = None
            if on_done: on_done()
            self._cursor_add()

    def _sys(self, text):
        self._cursor_remove()
        self.chat.config(state=tk.NORMAL)
        self.chat.insert(tk.END, f"\n[SYS] ▸ {text}\n", "sys")
        self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)
        self._cursor_add()

    def _typing_show(self):
        self._cursor_remove()
        self.chat.config(state=tk.NORMAL)
        self.chat.mark_set("typing_start", "end-1c")
        self.chat.mark_gravity("typing_start", tk.LEFT)
        self.chat.insert("end-1c", "\nJARVIS ▸ analizando", "typing")
        self.chat.mark_set("typing_end", "end-1c")
        self.chat.mark_gravity("typing_end", tk.LEFT)
        self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)
        self._typing_dot_count = 0
        self._typing_anim()

    def _typing_anim(self):
        if not self.is_processing:
            return
        try:
            self.chat.config(state=tk.NORMAL)
            self.chat.delete("typing_end", "end-1c")
            self._typing_dot_count = (self._typing_dot_count + 1) % 4
            self.chat.insert("typing_end", "." * self._typing_dot_count, "typing")
            self.chat.config(state=tk.DISABLED)
            self.chat.see(tk.END)
        except tk.TclError:
            return
        self.root.after(350, self._typing_anim)

    def _typing_hide(self):
        self.chat.config(state=tk.NORMAL)
        try:
            self.chat.delete("typing_start", "end-1c")
        except tk.TclError:
            pass
        self.chat.config(state=tk.DISABLED)

    def _cursor_add(self):
        if self._cursor_shown: return
        self.chat.config(state=tk.NORMAL)
        self.chat.insert("end-1c", "▌", "cursor")
        self.chat.config(state=tk.DISABLED)
        self._cursor_shown = True

    def _cursor_remove(self):
        if not self._cursor_shown: return
        self.chat.config(state=tk.NORMAL)
        self.chat.delete("end-2c", "end-1c")
        self.chat.config(state=tk.DISABLED)
        self._cursor_shown = False

    def _cursor_blink(self):
        if self._cursor_shown:
            self._cursor_on = not self._cursor_on
            self.chat.tag_config("cursor", foreground=C["primary"] if self._cursor_on else C["term_bg"])
        self.root.after(500, self._cursor_blink)

    def _animate_termbar(self):
        tb = self.term_bar
        tb.delete("all")
        w, h, n = 130, 22, 20
        state = self.orb_state
        if state == "listening":       # tú hablas
            base, scale, speed, jitter = C["danger"], 1.0, 0.55, 0.18
        elif state == "speaking":      # JARVIS habla
            base, scale, speed, jitter = C["success"], 0.9, 0.42, 0.1
        elif state == "processing":
            base, scale, speed, jitter = C["gold"], 0.55, 0.28, 0.05
        else:
            base, scale, speed, jitter = C["term_glow"], 0.14, 0.06, 0.0
        self._term_bar_phase = getattr(self, '_term_bar_phase', 0.0) + speed
        for k in range(n):
            amp = abs(math.sin(self._term_bar_phase + k * 0.5)) * scale + random.uniform(0, jitter)
            amp = min(amp, 1.0)
            hgt = 2 + amp * (h - 2)
            x = k * (w / n) + 1
            tb.create_line(x, h - hgt, x, h, fill=base, width=3)
        self.root.after(70, self._animate_termbar)

    def _animate_live_dot(self):
        self._live_on = not getattr(self, '_live_on', True)
        col = C["danger"] if self._live_on else self._dim(C["danger"], 0.2)
        try:
            self._live_dot.config(fg=col)
        except Exception:
            pass
        self.root.after(650, self._animate_live_dot)

    # ═══════════════════════════════════════════════════════
    # RESPONSIVE
    # ═══════════════════════════════════════════════════════
    def _on_left_resize(self, event):
        if self._resize_after: self.root.after_cancel(self._resize_after)
        self._resize_after = self.root.after(150, self._resize_left, event.width)
        self.root.after(10, self._redraw_huds)

    def _resize_left(self, w):
        sz = max(46, min(w - 40, 190)); self._draw_orb(sz)
        if w < 210:
            self.left_title.config(font=(UI_FONT, 12, "bold"))
            self.voice_btn.config(text="\U0001F399", font=(UI_FONT, 10), padx=8, pady=5)
            self.voice_hint.config(text="Ctrl+Esp")
        else:
            self.left_title.config(font=(UI_FONT, 19, "bold"))
            self.voice_btn.config(text="\U0001F399  HABLAR", font=(UI_FONT, 9, "bold"), padx=16, pady=8)
            self.voice_hint.config(text="Mantén  •  Ctrl+Espacio")

    def _on_right_resize(self, event):
        w = self.right_panel.winfo_width()
        self.root.after(10, self._redraw_huds)
        if w < 20: return
        cols = max(2, (w - 20) // 100)
        if cols != self._quick_cols: self._quick_cols = cols; self._build_quick_buttons()

    def _build_quick_buttons(self):
        for w in self.quick_frame.winfo_children(): w.destroy()
        if self._quick_cols == 0: return
        row = tk.Frame(self.quick_frame, bg=C["surface"]); row.pack(fill=tk.X)
        for i, (label, cmd) in enumerate(self.quick_commands):
            if i > 0 and i % self._quick_cols == 0:
                row = tk.Frame(self.quick_frame, bg=C["surface"]); row.pack(fill=tk.X)
            btn = tk.Button(row, text=label, font=(UI_FONT, 8, "bold"), bg=C["primary_dim"], fg=C["primary"],
                            activebackground=C["accent_dim"], activeforeground=C["white"],
                            relief=tk.FLAT, borderwidth=1, cursor="hand2", padx=10, pady=3,
                            command=lambda c=cmd: self._send_message(c))
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self._hover(btn, C["primary_dim"], C["accent_dim"])

    # ═══════════════════════════════════════════════════════
    # ACCIONES
    # ═══════════════════════════════════════════════════════
    def _send_from_input(self):
        text = self.input_field.get("1.0", tk.END).strip()
        if text: self.input_field.delete("1.0", tk.END); self._send_message(text)

    def _on_enter(self, event):
        if not event.state & 0x1: self._send_from_input(); return "break"

    def _send_message(self, text):
        if self.is_processing or not text.strip(): return
        self.is_processing = True
        self.orb_state = "processing"
        self.send_btn.config(state=tk.DISABLED, bg=C["text_dim"])
        self.voice_btn.config(state=tk.DISABLED, text="\U0001F399  ESPERE...")
        self._append("user", text); self._typing_show()
        self._pulse_orb(C["gold"])
        self.orb_label.config(text=spaced("PROCESANDO"), fg=C["gold"])
        self.sb_status.config(text="   │  Procesando...", fg=C["gold"])
        threading.Thread(target=_chat_async, args=(text,), daemon=True).start()

    def _on_space_press(self, event):
        if self.is_processing or getattr(self, '_voice_active', False): return
        if not (event.state & 0x4): return
        self._voice_start_recording()

    def _on_space_release(self, event):
        if getattr(self, '_voice_active', False): self._voice_stop_recording()

    def _on_ctrl_release(self, event):
        if getattr(self, '_voice_active', False): self._voice_stop_recording()

    def _voice_start_recording(self):
        self._voice_active = True
        self.orb_state = "listening"
        self.voice_btn.config(text="\U0001F399  GRABANDO...", fg=C["danger"], bg="#240613")
        self.orb_label.config(text=spaced("ESCUCHANDO"), fg=C["danger"])
        self.sb_status.config(text="   │  Escuchando...", fg=C["danger"])
        self._pulse_orb(C["danger"])
        threading.Thread(target=_voice_start, daemon=True).start()

    def _voice_stop_recording(self):
        self._voice_active = False
        self.orb_state = "processing"
        self.voice_btn.config(text="\U0001F399  ...", fg=C["gold"], bg=C["gold_dim"])
        self.orb_label.config(text=spaced("PROCESANDO"), fg=C["gold"])
        self.sb_status.config(text="   │  Transcribiendo...", fg=C["gold"])

        def _finish():
            text = _voice_stop()
            _result_queue.put(("voice", text))
        threading.Thread(target=_finish, daemon=True).start()

    def _toggle_tts(self):
        self.tts_enabled = not self.tts_enabled
        if self.tts_enabled:
            self.tts_btn.config(text="\U0001F50A VOZ ON", fg=C["primary"], bg=C["primary_dim"])
            self._hover(self.tts_btn, C["primary_dim"], "#0e3348")
        else:
            self.tts_btn.config(text="\U0001F507 VOZ OFF", fg=C["text_dim"], bg=C["surface2"])
            self._hover(self.tts_btn, C["surface2"], C["border"])

    def _update_status(self):
        try:
            from jarvis_local.voice.tts import is_available as tts_ok
            ok = tts_ok(); color = C["success"] if ok else C["danger"]
            c = self.st_tts.winfo_children()[0]; c.delete("all")
            c.create_oval(1, 1, 7, 7, fill=color, outline="")
            self.st_tts.winfo_children()[1].config(text="VOZ" if ok else "VOZ OFF")
        except Exception: pass
        self.root.after(15000, self._update_status)

    def _poll_results(self):
        try:
            while True:
                kind, data = _result_queue.get_nowait()
                if kind == "ok":
                    self._typing_hide()
                    self.orb_state = "speaking"; self._speaking = True
                    self._append("jarvis", data); self._reset_ui()
                    if self.tts_enabled and data:
                        # 'texto' se fija como argumento por defecto: si el bucle
                        # sigue iterando, el hilo hablaria el mensaje siguiente
                        # en vez del suyo (la clausura veria el 'data' nuevo).
                        def _speak_then_reset(texto=data):
                            _tts_speak(texto)
                            self._speaking = False
                            if self.orb_state == "speaking":
                                self.orb_state = "idle"
                        threading.Thread(target=_speak_then_reset, daemon=True).start()
                    else:
                        self._speaking = False
                        self.orb_state = "idle"
                elif kind == "error":
                    self._typing_hide(); self._sys(f"Error: {data}"); self._reset_ui()
                elif kind == "voice":
                    self._reset_voice()
                    if data: self._send_message(data)
                    else:
                        self._sys("No se detectó voz.")
                        self.orb_state = "idle"
                        self.orb_label.config(text=spaced("LISTO"), fg=C["primary"])
        except queue.Empty: pass
        self.root.after(100, self._poll_results)

    def _reset_ui(self):
        self.is_processing = False
        self.send_btn.config(state=tk.NORMAL, bg=C["primary"])
        self.voice_btn.config(state=tk.NORMAL, text="\U0001F399  HABLAR", fg=C["primary"], bg=C["primary_dim"])
        self._voice_active = False
        if self.orb_state not in ("speaking",):
            self.orb_state = "idle"
        self.orb_label.config(text=spaced("LISTO"), fg=C["primary"])
        self.sb_status.config(text="   │  Sistema operativo", fg=C["text_dim"])

    def _reset_voice(self):
        self._voice_active = False
        self.voice_btn.config(state=tk.NORMAL, text="\U0001F399  HABLAR", fg=C["primary"], bg=C["primary_dim"])
        self.orb_label.config(text=spaced("LISTO"), fg=C["primary"])
        self.sb_status.config(text="   │  Sistema operativo", fg=C["text_dim"])

    def _on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    print("Iniciando JARVIS Desktop...")
    try:
        _get_jarvis()
        print("  Ollama: CONECTADO")
    except Exception as e:
        print(f"  [WARN] {e}")
    JarvisDesktop().run()


if __name__ == "__main__":
    main()
