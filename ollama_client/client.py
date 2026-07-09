"""
JARVIS Local - Cliente HTTP para Ollama
Comunicacion pura con la API de Ollama, sin dependencias externas.
"""
import json
import time
import requests
from typing import Optional, Iterator

from jarvis_local.config import get_config


class OllamaClient:
    """Cliente HTTP para la API de Ollama."""

    def __init__(self, host: Optional[str] = None, timeout: Optional[int] = None):
        cfg = get_config()["ollama"]
        self.host = host or cfg["host"]
        self.timeout = timeout or cfg.get("timeout", 120)

    def _url(self, path: str) -> str:
        return f"{self.host}{path}"

    def is_running(self) -> bool:
        """Verifica si el servidor de Ollama esta corriendo."""
        try:
            r = requests.get(self._url("/api/tags"), timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[dict]:
        """Lista los modelos instalados en Ollama."""
        r = requests.get(self._url("/api/tags"), timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("models", [])

    def model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo especifico esta instalado."""
        models = self.list_models()
        for m in models:
            if m.get("name", "").startswith(model_name):
                return True
        return False

    def pull_model(self, model_name: str) -> bool:
        """Descarga un modelo de Ollama. Bloquea hasta terminar."""
        r = requests.post(
            self._url("/api/pull"),
            json={"name": model_name, "stream": True},
            timeout=self.timeout,
            stream=True,
        )
        r.raise_for_status()
        last_status = ""
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                status = data.get("status", "")
                if status and status != last_status:
                    if "completed" in data or "success" in status.lower():
                        print(f"\r[OK] {status}")
                    elif "error" in status.lower():
                        print(f"\r[ERROR] {status}")
                        return False
                    else:
                        pct = data.get("completed", 0) if "total" in data else 0
                        bar = "=" * int(pct / 5) if isinstance(pct, (int, float)) else ""
                        print(f"\r[{status}] {bar}", end="", flush=True)
                    last_status = status
            except json.JSONDecodeError:
                pass
        print()
        return self.model_exists(model_name)

    def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        stream: bool = False,
    ) -> str | Iterator[str]:
        """
        Envia mensajes al modelo y recibe la respuesta.

        Args:
            messages: Lista de mensajes en formato [{"role": "...", "content": "..."}]
            model: Nombre del modelo (usa el de config si es None)
            stream: Si True, devuelve un iterador de tokens.

        Returns:
            Respuesta completa (str) o iterador de tokens si stream=True.
        """
        cfg = get_config()["ollama"]
        payload = {
            "model": model or cfg["model"],
            "messages": messages,
            "stream": stream,
            "options": {
                "num_ctx": cfg.get("num_ctx", 4096),
                "temperature": 0.7,
            },
        }

        r = requests.post(
            self._url("/api/chat"),
            json=payload,
            timeout=self.timeout,
            stream=True,
        )
        r.raise_for_status()

        if stream:
            return self._stream_response(r)
        else:
            return self._collect_response(r)

    def _stream_response(self, response) -> Iterator[str]:
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("done"):
                    break
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
            except json.JSONDecodeError:
                continue

    def _collect_response(self, response) -> str:
        full = ""
        for token in self._stream_response(response):
            full += token
        return full

    def get_model_info(self, model_name: str) -> dict:
        """Obtiene informacion de un modelo (tamano, parametros, etc.)."""
        r = requests.post(
            self._url("/api/show"),
            json={"name": model_name},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_running_models(self) -> list[dict]:
        """Lista modelos actualmente cargados en memoria."""
        try:
            r = requests.get(self._url("/api/ps"), timeout=5)
            r.raise_for_status()
            return r.json().get("models", [])
        except requests.RequestException:
            return []
