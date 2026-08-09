"""
JARVIS Local - Cliente HTTP para Ollama
Comunicacion pura con la API de Ollama.
Soporte para httpx (mejor rendimiento) con fallback a requests.
"""
import json
from collections.abc import Iterator

from jarvis_local.config import get_config
from jarvis_local.logging_config import get_logger

logger = get_logger("ollama_client")

# Intentar importar httpx para mejor rendimiento
try:
    import httpx
    HAS_HTTPX = True
    logger.debug("Usando httpx para HTTP")
except ImportError:
    import requests
    HAS_HTTPX = False
    logger.debug("Usando requests para HTTP")


class OllamaClient:
    """Cliente HTTP para la API de Ollama."""

    def __init__(self, host: str | None = None, timeout: int | None = None):
        cfg = get_config()["ollama"]
        self.host = host or cfg["host"]
        self.timeout = timeout or cfg.get("timeout", 120)
        self._client = None

    def _get_client(self):
        """Obtiene o crea el cliente HTTP."""
        if self._client is None:
            if HAS_HTTPX:
                self._client = httpx.Client(
                    base_url=self.host,
                    timeout=httpx.Timeout(self.timeout, connect=15.0)
                )
            else:
                self._client = requests.Session()
        return self._client

    def _url(self, path: str) -> str:
        return f"{self.host}{path}"

    def is_running(self) -> bool:
        """Verifica si el servidor de Ollama esta corriendo."""
        try:
            client = self._get_client()
            if HAS_HTTPX:
                r = client.get("/api/tags", timeout=5.0)
            else:
                r = client.get(self._url("/api/tags"), timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[dict]:
        """Lista los modelos instalados en Ollama."""
        client = self._get_client()
        if HAS_HTTPX:
            r = client.get("/api/tags")
        else:
            r = client.get(self._url("/api/tags"), timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("models", [])

    def model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo especifico esta instalado."""
        models = self.list_models()
        return any(m.get("name", "").startswith(model_name) for m in models)

    def pull_model(self, model_name: str) -> bool:
        """Descarga un modelo de Ollama. Bloquea hasta terminar."""
        client = self._get_client()
        if HAS_HTTPX:
            with client.stream("POST", "/api/pull",
                              json={"name": model_name, "stream": True},
                              timeout=httpx.Timeout(self.timeout, connect=15.0)) as r:
                r.raise_for_status()
                last_status = ""
                for line in r.iter_lines():
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
        else:
            r = client.post(
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
        model: str | None = None,
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
                "num_ctx": cfg.get("num_ctx", 2048),
                "num_predict": cfg.get("num_predict", 120),
                "temperature": 0.7,
            },
        }

        client = self._get_client()
        if HAS_HTTPX:
            r = client.post(
                "/api/chat",
                json=payload,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
            )
            r.raise_for_status()
            if stream:
                return self._stream_response_httpx(r)
            else:
                return self._collect_response(r)
        else:
            r = client.post(
                self._url("/api/chat"),
                json=payload,
                timeout=(15, self.timeout),
                stream=True,
            )
            r.raise_for_status()
            if stream:
                return self._stream_response(r)
            else:
                return self._collect_response(r)

    def _stream_response(self, response) -> Iterator[str]:
        """Stream de respuesta con requests."""
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

    def _stream_response_httpx(self, response) -> Iterator[str]:
        """Stream de respuesta con httpx."""
        for line in response.iter_lines():
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
        """Recopila toda la respuesta."""
        full = ""
        for token in self._stream_response(response):
            full += token
        return full

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
    ) -> dict:
        """
        Chat con herramientas (tool calling nativo de Ollama).

        Returns:
            El mensaje del modelo: {"role": "assistant", "content": str,
            "tool_calls": [{"function": {"name": str, "arguments": dict}}]}
            La clave "tool_calls" solo aparece si el modelo decide usar una herramienta.
        """
        cfg = get_config()["ollama"]
        payload = {
            "model": model or cfg["model"],
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {
                "num_ctx": cfg.get("agent_num_ctx", 2048),
                "num_predict": cfg.get("agent_num_predict", 120),
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }
        client = self._get_client()
        if HAS_HTTPX:
            r = client.post(
                "/api/chat",
                json=payload,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
            )
        else:
            r = client.post(
                self._url("/api/chat"),
                json=payload,
                timeout=(15, self.timeout),
            )
        r.raise_for_status()
        return r.json().get("message", {})

    def get_model_info(self, model_name: str) -> dict:
        """Obtiene informacion de un modelo (tamano, parametros, etc.)."""
        client = self._get_client()
        if HAS_HTTPX:
            r = client.post(
                "/api/show",
                json={"name": model_name},
                timeout=httpx.Timeout(self.timeout, connect=15.0),
            )
        else:
            r = client.post(
                self._url("/api/show"),
                json={"name": model_name},
                timeout=self.timeout,
            )
        r.raise_for_status()
        return r.json()

    def get_running_models(self) -> list[dict]:
        """Lista modelos actualmente cargados en memoria."""
        try:
            client = self._get_client()
            if HAS_HTTPX:
                r = client.get("/api/ps", timeout=5.0)
            else:
                r = client.get(self._url("/api/ps"), timeout=5)
            r.raise_for_status()
            return r.json().get("models", [])
        except Exception:
            return []

    def close(self):
        """Cierra el cliente HTTP."""
        if self._client is not None:
            if HAS_HTTPX:
                self._client.close()
            self._client = None
