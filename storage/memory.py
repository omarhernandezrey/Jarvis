"""
JARVIS Local - Memoria explicita del usuario (Fase 5)
Persiste notas del usuario en JSON atomico.
"""
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAX_MEMORIES = 100
MAX_MEMORY_LENGTH = 500


class MemoryStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.data_dir / "memory.json"
        self._items: list[dict] = []
        self._load()

    def _load(self):
        if not self._path.exists():
            self._items = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._items = data.get("items", [])
        except (json.JSONDecodeError, KeyError, ValueError):
            corrupted = self.data_dir / f"memory.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            shutil.move(str(self._path), str(corrupted))
            print(f"[AVISO] Memoria corrupta. Movida a {corrupted.name}. Iniciando vacia.")
            self._items = []

    def _save(self):
        data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": self._items,
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

    def add(self, text: str) -> dict | None:
        if len(self._items) >= MAX_MEMORIES:
            return None
        clean = str(text)[:MAX_MEMORY_LENGTH].strip()
        if not clean:
            return None
        item = {
            "id": str(uuid.uuid4()),
            "text": clean,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._items.append(item)
        self._save()
        return item

    def list(self) -> list[dict]:
        return list(self._items)

    def delete(self, memory_id: str) -> bool:
        for i, item in enumerate(self._items):
            if item["id"] == memory_id:
                self._items.pop(i)
                self._save()
                return True
        return False

    def clear(self):
        self._items = []
        if self._path.exists():
            self._path.unlink()
