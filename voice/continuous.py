"""
JARVIS Local - Escucha continua con palabra de activacion (Fase 8)
Usa faster-whisper compartido. Maquina de estados real.
Detecta "Jarvis" y variantes STT.
"""
import enum
import re
import threading
import time
import unicodedata
from collections.abc import Callable

_WAKE_VARIANTS = [
    "jarvis", "yarbis", "yarvis", "garbis", "gerbis",
    "jarbis", "harvis", "carvis", "yarbi", "garbi", "arbis",
    "jarbees", "jarvises", "garvis", "jervis", "jarbez",
    "jarbes", "jarves", "charvis", "charbis",
]
_WAKE_PATTERN = "|".join(re.escape(v) for v in sorted(_WAKE_VARIANTS, key=len, reverse=True))
_WAKE_REGEX = re.compile(
    rf'^(?:[a-z]{{1,5}}[,.]?\s+){{0,3}}\b({_WAKE_PATTERN})\b\s*[,.!?\u2026]*\s*(.*)',
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    t = text.lower().strip()
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return " ".join(t.split())


def find_wake_word(text: str) -> tuple[bool, str]:
    n = _normalize(text)
    m = _WAKE_REGEX.match(n)
    if not m:
        return False, ""
    wake_word = m.group(1)
    cmd_normalized = m.group(2)
    if not cmd_normalized:
        return True, ""

    # Buscar la posicion del comando en el texto original
    first_word = cmd_normalized.split()[0]
    t_lower = text.lower()
    pos = t_lower.find(first_word)
    if pos >= 0:
        remaining = text[pos:].strip()
        if len(remaining.split()) > len(cmd_normalized.split()):
            # Tomar hasta la ultima palabra del comando detectado
            last_word = cmd_normalized.split()[-1]
            lp = remaining.lower().rfind(last_word)
            if lp >= 0:
                remaining = remaining[:lp + len(last_word)]
        return True, " ".join(remaining.split())

    return True, cmd_normalized


def extract_command_after_wake_word(text: str) -> str | None:
    detected, cmd = find_wake_word(text)
    if not detected:
        return None
    return cmd


class VoiceState(enum.Enum):
    LISTENING_WAKE_WORD = "listening"
    COLLECTING_COMMAND = "collecting"
    PROCESSING = "processing"
    STOPPED = "stopped"


def _merge_fragments(fragments: list[str]) -> str:
    """Concatena fragmentos evitando duplicados obvios entre consecutivos."""
    parts = [p.strip() for p in fragments if p.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    merged = [parts[0]]
    for i in range(1, len(parts)):
        prev = merged[-1]
        curr = parts[i]
        prev_words = prev.split()
        curr_words = curr.split()
        if not prev_words or not curr_words:
            merged.append(curr)
            continue
        # Si la ultima palabra de prev == primera de curr, remover solapamiento
        if prev_words[-1].lower() == curr_words[0].lower():
            combined = prev_words[:-1] + curr_words
            merged[-1] = " ".join(combined)
        else:
            merged.append(curr)
    return " ".join(merged)


class ContinuousVoiceController:
    def __init__(self, stt_fn: Callable, chat_fn: Callable,
                 tts_speak_fn=None, tts_speaking_fn=None):
        self._stt = stt_fn
        self._chat = chat_fn
        self._tts_speak = tts_speak_fn
        self._tts_speaking = tts_speaking_fn
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._fragment_duration = 2
        self._tts_pause_ms = 500
        self._command_timeout_s = 8
        self._silence_to_end = 2

        self._command_buffer: list[str] = []
        self._command_start_time = 0.0
        self._silence_count = 0
        self._last_command = ""
        self._state = VoiceState.STOPPED
        self._state_lock = threading.Lock()

    # -- state helpers --

    def _set_state(self, new_state: VoiceState):
        with self._state_lock:
            self._state = new_state

    def _get_state(self) -> VoiceState:
        with self._state_lock:
            return self._state

    @property
    def state(self):
        return self._get_state()

    # -- public API --

    def start(self):
        if self._running.is_set():
            return
        self._running.set()
        self._set_state(VoiceState.LISTENING_WAKE_WORD)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running.clear()
        self._set_state(VoiceState.STOPPED)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=4)

    def is_running(self) -> bool:
        return self._running.is_set()

    def get_state(self) -> dict:
        st = self._get_state()
        return {
            "active": self.is_running(),
            "state": st.value,
            "wake_word": "Jarvis (tolerante: " + ", ".join(_WAKE_VARIANTS[:4]) + "...)",
            "fragment_duration_s": self._fragment_duration,
            "tts_pause_ms": self._tts_pause_ms,
            "buffer": " | ".join(self._command_buffer) if self._command_buffer else "",
            "last_command": self._last_command,
            "silence_count": self._silence_count,
            "command_timeout_s": self._command_timeout_s,
        }

    # -- TTS guard --

    def _pause_for_tts(self):
        if self._tts_speaking and self._tts_speaking():
            time.sleep(self._tts_pause_ms / 1000)

    def _is_tts_speaking(self) -> bool:
        if self._tts_speaking:
            return self._tts_speaking()
        return False

    # -- fragment capture helper --

    def _capture_fragment(self) -> str | None:
        """Captura un fragmento. Retorna texto transcrito o None."""
        try:
            result = self._stt(self._fragment_duration, show_stats=True)
            if isinstance(result, dict):
                return result.get("text")
            return result
        except Exception as e:
            print(f"[Voz continua] Error STT: {e}")
            return None

    # -- main loop --

    def _loop(self):
        while self._running.is_set():
            self._pause_for_tts()
            if not self._running.is_set():
                break

            current_state = self._get_state()

            if current_state == VoiceState.LISTENING_WAKE_WORD:
                self._handle_listening()
            elif current_state == VoiceState.COLLECTING_COMMAND:
                self._handle_collecting()
            elif current_state == VoiceState.PROCESSING:
                # Nunca deberia ocurrir: PROCESSING es sincrono y se resuelve
                # dentro de _handle_collecting. Si llega aqui, restaurar.
                self._set_state(VoiceState.LISTENING_WAKE_WORD)
            elif current_state == VoiceState.STOPPED:
                break

    def _handle_listening(self):
        text = self._capture_fragment()
        if text is None:
            return

        cmd = extract_command_after_wake_word(text)
        if cmd is None:
            return

        # Wake word detectada.
        print("[Voz continua] Wake word detectada.")
        self._command_buffer = [cmd] if cmd else []
        self._command_start_time = time.time()
        self._silence_count = 0
        self._set_state(VoiceState.COLLECTING_COMMAND)

    def _handle_collecting(self):
        # Si el buffer inicial esta vacio (solo "Jarvis"):
        # decir "Te escucho." y captura unica de 8s.
        if not self._command_buffer or not any(p.strip() for p in self._command_buffer):
            if self._tts_speak:
                try:
                    self._tts_speak("Te escucho.")
                except Exception as e:
                    print(f"[Voz continua] Error TTS: {e}")
            if not self._running.is_set():
                self._set_state(VoiceState.LISTENING_WAKE_WORD)
                return
            text = self._stt(8, show_stats=True)
            if isinstance(text, dict):
                text = text.get("text")
            if text and text.strip() and self._running.is_set():
                self._command_buffer.append(text)
            else:
                print("[Voz continua] Sin comando detectado.")
                print("[Voz continua] Escucha reanudada.")
                self._set_state(VoiceState.LISTENING_WAKE_WORD)
                return

        # Capturar fragmentos hasta silencio o timeout
        while self._running.is_set() and self._get_state() == VoiceState.COLLECTING_COMMAND:
            elapsed = time.time() - self._command_start_time
            timed_out = elapsed >= self._command_timeout_s
            silent_enough = self._silence_count >= self._silence_to_end

            if timed_out or silent_enough:
                break

            self._pause_for_tts()
            if not self._running.is_set():
                return

            text = self._capture_fragment()
            if text:
                self._command_buffer.append(text)
                self._silence_count = 0
            else:
                self._silence_count += 1

            elapsed = time.time() - self._command_start_time

        # Construir comando final
        command = _merge_fragments(self._command_buffer)
        self._command_buffer = []
        self._silence_count = 0

        if not command or not command.strip():
            print("[Voz continua] Sin comando detectado.")
            print("[Voz continua] Escucha reanudada.")
            self._set_state(VoiceState.LISTENING_WAKE_WORD)
            return

        # Procesar
        self._set_state(VoiceState.PROCESSING)
        print(f"[Voz continua] Comando completo: {command}")
        self._last_command = command

        try:
            response = self._chat(command)
            if response:
                print(f"[JARVIS]: {response}")
            if response and self._tts_speak:
                if self._running.is_set():
                    try:
                        self._tts_speak(response)
                    except Exception as e:
                        print(f"[Voz continua] Error TTS: {e}")
        except Exception as e:
            print(f"[Voz continua] Error: {e}")

        self._set_state(VoiceState.LISTENING_WAKE_WORD)
        print("[Voz continua] Escucha reanudada.")

    # -- single-shot methods (mantenidos para compatibilidad) --

    def process_transcription(self, text: str) -> str | None:
        cmd = extract_command_after_wake_word(text)
        if cmd is None:
            return None
        if cmd == "":
            if self._tts_speak:
                self._tts_speak("Te escucho.")
            return ""
        return self._chat(cmd)

    def _loop_step(self, text: str) -> str | None:
        return self.process_transcription(text)
