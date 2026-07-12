"""
JARVIS Local - Logger de acciones y errores
Registra cada accion en formato JSON Lines.
"""
import json
from datetime import datetime
from pathlib import Path

from jarvis_local.config import BASE_DIR, get_config


class ActionLogger:
    def __init__(self):
        cfg = get_config()["logging"]
        self.log_dir = (BASE_DIR / cfg["dir"]).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.actions_path = self.log_dir / cfg["actions_log"]
        self.errors_path = self.log_dir / cfg["errors_log"]

    def log_action(self, instruction: str, result: str, error: str = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "instruction": instruction,
            "result": result,
            "error": error,
        }
        self._append_json(self.actions_path, entry)

    def log_error(self, source: str, error: str, details: str = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "error": error,
            "details": details,
        }
        self._append_json(self.errors_path, entry)

    def _append_json(self, path: Path, entry: dict):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_actions(self, limit: int = 50) -> list[dict]:
        return self._read_json_lines(self.actions_path, limit)

    def read_errors(self, limit: int = 50) -> list[dict]:
        return self._read_json_lines(self.errors_path, limit)

    def _read_json_lines(self, path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries[-limit:]


logger = ActionLogger()
