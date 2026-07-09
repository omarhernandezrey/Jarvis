"""
JARVIS Local - Historial de conversacion
Guarda las ultimas N interacciones para contexto del LLM.
"""
import json
from pathlib import Path
from jarvis_local.config import get_config


class ConversationHistory:
    def __init__(self):
        cfg = get_config()["jarvis"]
        self.max_history = cfg.get("max_history", 20)
        self.messages: list[dict] = []

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})
        self._trim()

    def _trim(self):
        max_msgs = self.max_history * 2
        if len(self.messages) > max_msgs:
            self.messages = self.messages[-max_msgs:]

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    def clear(self):
        self.messages.clear()

    def to_json(self) -> str:
        return json.dumps(self.messages, ensure_ascii=False)

    def summary(self) -> str:
        """Resumen legible de la conversacion."""
        lines = []
        for msg in self.messages:
            role = "Tu" if msg["role"] == "user" else "JARVIS"
            content = msg["content"][:80] + ("..." if len(msg["content"]) > 80 else "")
            lines.append(f"[{role}] {content}")
        return "\n".join(lines)
