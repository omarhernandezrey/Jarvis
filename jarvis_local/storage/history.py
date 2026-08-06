"""
JARVIS Local - Almacenamiento de historial (Fase 5)
Persiste la conversacion en JSON atomico. Sin pickle.
"""
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from jarvis_local.safety.secrets import redact_secrets

MAX_MESSAGES = 50
MAX_CONTENT_LENGTH = 2000


class HistoryStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.data_dir / "history.json"
        self._messages: list[dict] = []
        self._load()

    def _load(self):
        if not self._path.exists():
            self._messages = []
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            self._messages = data.get("messages", [])
        except (json.JSONDecodeError, KeyError, ValueError):
            corrupted = self.data_dir / f"history.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            shutil.move(str(self._path), str(corrupted))
            print(f"[AVISO] Historial corrupto. Movido a {corrupted.name}. Iniciando vacio.")
            self._messages = []

    def _save(self):
        data = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "messages": self._messages,
        }
        fd, tmp_path = tempfile.mkstemp(dir=str(self.data_dir), suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(self._path))
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise

    @staticmethod
    def sanitize(role: str, content: str) -> str:
        c = str(content)[:MAX_CONTENT_LENGTH]
        # redact_secrets() detecta secretos por FORMA (sk-..., AIza...,
        # contrasenas de app de Gmail, etc.), no por palabras clave cercanas,
        # asi que cubre casos que el filtro de keywords de abajo se perdia
        # (una API key pegada sin la palabra "token" al lado). El filtro de
        # keywords se conserva como red de respaldo mas agresiva (omite el
        # mensaje completo) para valores que no tienen una forma reconocida.
        c, _ = redact_secrets(c)
        if role == "user" and any(kw in c.lower() for kw in [
            "ejecuta ", "ejecutar ", "run ", "shutdown", "del ", "rm ", "format",
            "password", "contraseña", "token", "api_key"
        ]):
            return "[comando de terminal omitido]"
        if role == "assistant" and any(kw in c.lower() for kw in [
            "password", "contraseña", "token", "api_key", "Bearer "
        ]):
            return "[respuesta con posible secreto omitida]"
        return c

    def load(self) -> list[dict]:
        return list(self._messages)

    def append(self, role: str, content: str):
        clean = self.sanitize(role, content)
        self._messages.append({
            "role": role,
            "content": clean,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        if len(self._messages) > MAX_MESSAGES:
            self._messages = self._messages[-MAX_MESSAGES:]
        self._save()

    def clear(self):
        self._messages = []
        if self._path.exists():
            self._path.unlink()

    def to_list(self, limit: int = 10) -> list[dict]:
        return list(self._messages[-limit:])
