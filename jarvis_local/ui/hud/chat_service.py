"""Driver de conversación — punto de contacto con el núcleo para el chat.

`ChatService` reutiliza `jarvis_local.jarvis.Jarvis` SIN modificarlo: envuelve
`jarvis.client` con un tap que emite cada token del stream tal como llega
(latencia real hasta la primera palabra, tokens/s medidos). El resto de la
cascada del núcleo (respuestas rápidas, parser, agente, memoria, persistencia,
redacción de secretos) queda intacta; sus respuestas no llegan por streaming,
simplemente se muestran completas.

Todo el trabajo pesado corre en un hilo; el modelo de conversación y el
ViewModel se tocan siempre desde el hilo de la GUI (señales en cola).
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import Property, QObject, Signal, Slot


class _TapClient:
    """Delega todo en el cliente real; en `chat(stream=True)` envuelve el
    iterador para chivar cada token vía `on_token`."""

    def __init__(self, inner, on_token) -> None:
        self._inner = inner
        self._on_token = on_token

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def chat(self, messages, model=None, stream=False):
        result = self._inner.chat(messages, model=model, stream=stream)
        if not stream:
            return result

        def _gen():
            for tok in result:
                if tok:
                    self._on_token(tok)
                yield tok

        return _gen()


class ChatService(QObject):
    # señales -> conexiones en cola al hilo de la GUI
    userTurn = Signal(str)
    assistantBegin = Signal()
    assistantToken = Signal(str)
    assistantEnd = Signal(str, str, str)   # texto, meta, kind
    errorTurn = Signal(str)
    wantState = Signal(str)
    metrics = Signal(dict)

    busyChanged = Signal(bool)

    def __init__(self, view_model, conversation, parent=None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._conv = conversation
        self._jarvis = None
        self._jarvis_err: str | None = None
        self._busy = False
        self._lock = threading.Lock()

        self.userTurn.connect(conversation.add_user)
        self.assistantBegin.connect(conversation.begin_assistant)
        self.assistantToken.connect(conversation.append_token)
        self.assistantToken.connect(view_model.push_token)     # canal `token`
        self.assistantEnd.connect(conversation.end_assistant)
        self.errorTurn.connect(conversation.add_error)
        self.errorTurn.connect(view_model.push_error)
        self.wantState.connect(view_model.set_state)
        self.metrics.connect(view_model.push_metrics)

    # ── ciclo de vida del núcleo ─────────────────────────────────────────
    def _ensure_jarvis(self):
        if self._jarvis is not None or self._jarvis_err is not None:
            return
        try:
            from jarvis_local.jarvis import Jarvis
            self._jarvis = Jarvis()
        except Exception as e:  # Ollama caído, modelo ausente, etc.
            self._jarvis_err = str(e)

    def _get_busy(self) -> bool:
        return self._busy

    busy = Property(bool, _get_busy, notify=busyChanged)

    # ── envío ───────────────────────────────────────────────────────────
    @Slot(str)
    def send(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self._busy:
            return
        self._busy = True
        self.busyChanged.emit(True)
        self.userTurn.emit(text)
        self.assistantBegin.emit()
        self.wantState.emit("thinking")
        threading.Thread(target=self._run, args=(text,),
                         name="chat", daemon=True).start()

    def _run(self, text: str) -> None:
        seen = {"n": 0, "t0": None}

        def on_token(tok: str) -> None:
            if seen["t0"] is None:
                seen["t0"] = time.monotonic()
            seen["n"] += 1
            self.assistantToken.emit(tok)
            dt = time.monotonic() - seen["t0"]
            if dt > 0.3:
                self.metrics.emit({"tokensPerSecond": round(seen["n"] / dt, 1)})

        t_start = time.monotonic()
        try:
            self._ensure_jarvis()
            if self._jarvis is None:
                raise RuntimeError(self._jarvis_err or "Núcleo no disponible")

            original = self._jarvis.client
            self._jarvis.client = _TapClient(original, on_token)
            try:
                reply = self._jarvis.chat(text)
            finally:
                self._jarvis.client = original

            latency = round((time.monotonic() - t_start) * 1000)
            tps = None
            if seen["t0"] is not None and seen["n"] > 1:
                span = time.monotonic() - seen["t0"]
                if span > 0:
                    tps = round(seen["n"] / span, 1)
            meta_bits = [f"{latency} ms"]
            if tps:
                meta_bits.append(f"{tps} tok/s")
            self.metrics.emit({"latencyMs": latency,
                               "tokensPerSecond": tps})
            self.assistantEnd.emit(reply or "", " · ".join(meta_bits), "chat")
        except Exception as e:
            self.errorTurn.emit(str(e))
            self.wantState.emit("alert")
        finally:
            self._busy = False
            self.busyChanged.emit(False)
            # sólo volver a idle si nadie cambió el estado entretanto
            if self._vm.state == "thinking":
                self.wantState.emit("idle")
