"""Voz — captura de micrófono (con espectro real para el visualizador) y salida
hablada (con envolvente de energía real).

No reimplementa el núcleo de voz: la transcripción usa
`jarvis_local.voice.stt` y el audio hablado usa la generación/decodificación de
`jarvis_local.voice.tts`. Sólo la reproducción final se hace con un
`OutputStream` con callback para poder medir la envolvente que alimenta el
estado SPEAKING.

Estados de micrófono (reales, no asumidos): `inactive`, `listening`, `denied`.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

_SR = 16000
_BLOCK = 1024
_BINS = 64


class VoiceService(QObject):
    micStateChanged = Signal(str)              # inactive | listening | denied
    transcribed = Signal(str)                  # texto reconocido, listo para chat
    audio = Signal(float, list)                # -> Vm.push_audio (nivel, espectro)
    wantState = Signal(str)
    speakingChanged = Signal(bool)

    def __init__(self, view_model, parent=None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._mic_state = "inactive"
        self._stream = None
        self._frames: list = []
        self._lock = threading.Lock()
        self._speaking = False
        self._stop_speech = threading.Event()

        self.audio.connect(view_model.push_audio)
        self.wantState.connect(view_model.set_state)

    # ── propiedades para QML ────────────────────────────────────────────
    def _get_mic_state(self):
        return self._mic_state

    micState = Property(str, _get_mic_state, notify=micStateChanged)

    def _get_speaking(self):
        return self._speaking

    speaking = Property(bool, _get_speaking, notify=speakingChanged)

    def _set_mic_state(self, s: str) -> None:
        if s != self._mic_state:
            self._mic_state = s
            self.micStateChanged.emit(s)

    # ── captura ────────────────────────────────────────────────────────
    @Slot()
    def start_recording(self) -> None:
        if self._mic_state == "listening":
            return
        try:
            import numpy as np
            import sounddevice as sd
        except Exception:
            self._set_mic_state("denied")
            return

        win = np.hanning(_BLOCK).astype("float32")

        def _cb(indata, frames, time_info, status):  # hilo de PortAudio
            with self._lock:
                self._frames.append(indata.copy())
            mono = indata[:, 0].astype("float32")
            rms = float(np.sqrt(np.mean(mono ** 2))) / 32768.0
            level = min(1.0, rms * 6.0)
            if len(mono) >= _BLOCK:
                mag = np.abs(np.fft.rfft(mono[:_BLOCK] / 32768.0 * win))
                usable = mag[:256]                      # ~0-4 kHz (banda de voz)
                binned = usable.reshape(_BINS, -1).mean(axis=1)
                peak = float(binned.max()) or 1.0
                spec = np.clip(binned / (peak * 0.7), 0.0, 1.0)
                spec = np.sqrt(spec)                    # realza lo bajo
                self.audio.emit(level, spec.tolist())
            else:
                self.audio.emit(level, [])

        try:
            with self._lock:
                self._frames = []
            self._stream = sd.InputStream(
                samplerate=_SR, channels=1, dtype="int16",
                blocksize=_BLOCK, callback=_cb)
            self._stream.start()
        except Exception:
            self._stream = None
            self._set_mic_state("denied")
            return

        self._set_mic_state("listening")
        self.wantState.emit("listening")

    @Slot()
    def stop_recording(self) -> None:
        if self._mic_state != "listening":
            return
        self._set_mic_state("inactive")
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop(); stream.close()
            except Exception:
                pass
        self.audio.emit(0.0, [])
        if self._vm.state == "listening":
            self.wantState.emit("idle")
        threading.Thread(target=self._transcribe, name="stt", daemon=True).start()

    def _transcribe(self) -> None:
        try:
            import numpy as np
            with self._lock:
                frames = self._frames
                self._frames = []
            if not frames:
                return
            audio = np.concatenate(frames, axis=0).flatten().astype("float32") / 32768.0
            if len(audio) < 8000:
                return
            from jarvis_local.voice.stt import _get_whisper_model, load_voice_config
            cfg = load_voice_config()
            model = _get_whisper_model(cfg.get("stt_model", "small"),
                                      cfg.get("stt_compute_type", "int8"))
            segs, _ = model.transcribe(audio, language="es", beam_size=5,
                                       vad_filter=True,
                                       vad_parameters={"min_silence_duration_ms": 500})
            text = " ".join(s.text.strip() for s in segs).strip()
            if len(text) >= 2:
                self.transcribed.emit(text)
        except Exception:
            pass

    # ── salida hablada con envolvente real ─────────────────────────────
    @Slot(str)
    def speak(self, text: str) -> None:
        if not text:
            return
        self._stop_speech.clear()
        threading.Thread(target=self._speak, args=(text,),
                         name="tts", daemon=True).start()

    @Slot()
    def stop_speech(self) -> None:
        self._stop_speech.set()

    def _speak(self, text: str) -> None:
        try:
            import numpy as np
            import sounddevice as sd

            from jarvis_local.voice import tts

            mp3 = tts._cache_get(text)
            from_cache = bool(mp3)
            if not mp3:
                for _ in range(2):
                    mp3 = tts._run_async(tts._edge_generate_async(text))
                    if mp3:
                        break
            if not mp3:
                return
            samples, sr = tts._mp3_bytes_to_numpy(mp3)
            if samples is None or sr <= 0:
                return
            if not from_cache:
                tts._cache_put(text, mp3)

            self._speaking = True
            self.speakingChanged.emit(True)
            self.wantState.emit("speaking")

            pos = {"i": 0}
            n = len(samples)

            def _out_cb(outdata, frames, time_info, status):
                i = pos["i"]
                chunk = samples[i:i + frames]
                if len(chunk) < frames:
                    outdata[:len(chunk), 0] = chunk
                    outdata[len(chunk):, 0] = 0.0
                    raise sd.CallbackStop
                outdata[:, 0] = chunk
                pos["i"] = i + frames
                env = float(np.sqrt(np.mean(chunk ** 2)))
                lvl = min(1.0, env * 3.5)
                bins = np.abs(chunk[:_BLOCK])
                if len(bins) >= _BINS:
                    b = bins[:_BINS * (len(bins) // _BINS)].reshape(_BINS, -1).mean(axis=1)
                    b = np.clip(b / (float(b.max()) or 1.0), 0, 1)
                else:
                    b = np.full(_BINS, lvl)
                self.audio.emit(lvl, (np.sqrt(b)).tolist())

            with sd.OutputStream(samplerate=sr, channels=1, dtype="float32",
                                 blocksize=_BLOCK, callback=_out_cb):
                while pos["i"] < n and not self._stop_speech.is_set():
                    sd.sleep(50)
        except Exception:
            pass
        finally:
            self._speaking = False
            self.speakingChanged.emit(False)
            self.audio.emit(0.0, [])
            if self._vm.state == "speaking":
                self.wantState.emit("idle")
