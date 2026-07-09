"""
JARVIS Local - Orquestador (Fase 1: Solo Chat)
Coordina la conversacion entre el usuario y Ollama.
En Fase 1, el modelo SOLO conversa. Sin herramientas.
"""
import re
from jarvis_local.ollama_client.client import OllamaClient
from jarvis_local.memory.history import ConversationHistory
from jarvis_local.safety.logger import logger
from jarvis_local.safety.secrets import redact_secrets
from jarvis_local.config import get_config

_EXACT_TRIGGERS = [
    "responde solamente",
    "responde solo",
    "di solamente",
    "di solo",
    "dime solamente",
    "dime solo",
    "contesta solamente",
    "contesta solo",
]

_QUOTE_PAIRS = [('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u2018", "\u2019"), ("\u00ab", "\u00bb")]
_TRAILING_PUNCT = ".!?\u00a1\u00bf"


def _exact_response(message: str) -> str | None:
    m = " ".join(message.strip().split())
    m_lower = m.lower()
    for trigger in _EXACT_TRIGGERS:
        idx = m_lower.find(trigger)
        if idx == -1:
            continue
        after = m[idx + len(trigger):].strip()
        if not after:
            return None
        for left, right in _QUOTE_PAIRS:
            if after.startswith(left) and after.endswith(right):
                after = after[1:-1]
                break
        while after and after[-1] in _TRAILING_PUNCT:
            after = after[:-1]
        after = after.strip()
        if after:
            return after
        return None
    return None


SYSTEM_PROMPT = """Eres JARVIS, un asistente de IA local que corre en Windows 10.
Tu trabajo es ayudar a Omar con tareas en su computadora.

REGLAS:
- Responde en espanol, en tono profesional pero amigable.
- Si no entiendes algo, pregunta. No asumas.
- No puedes ejecutar comandos, abrir archivos, ni navegar en internet.
- Solo puedes conversar y responder preguntas.
- Si Omar te pide hacer algo que no puedes (ejecutar, abrir, navegar), dile
  amablemente que en esta fase solo puedes conversar, pero que en fases
  futuras tendras esas capacidades.
- Manten tus respuestas concisas (maximo 3-4 oraciones) a menos que Omar
  te pida mas detalle.
- OBEDIENCIA ESTRICTA: Si Omar dice "responde solamente X", "di solamente X",
  "contesta solo X" o frases equivalentes, DEBES responder unicamente con X,
  sin saludos, sin explicaciones, sin puntuacion extra y sin texto adicional.
- Eres un asistente util, servicial y respetuoso."""


class Jarvis:
    def __init__(self):
        self.cfg = get_config()
        self.client = OllamaClient()
        self.history = ConversationHistory()
        self._ensure_model()

    def _ensure_model(self):
        model = self.cfg["ollama"]["model"]
        if not self.client.is_running():
            raise ConnectionError(
                "Ollama no esta corriendo.\n"
                "Ejecuta 'ollama serve' en otra terminal o inicia Ollama desde el menu de Windows."
            )
        if not self.client.model_exists(model):
            raise RuntimeError(
                f"El modelo '{model}' no esta instalado.\n"
                f"Ejecuta: ollama pull {model}"
            )

    def chat(self, user_input: str) -> str:
        instruction = user_input[:100]
        try:
            if user_input.strip() == "":
                return ""

            safe_input, secrets_found = redact_secrets(user_input)
            if secrets_found > 0:
                logger.log_action(
                    instruction="[SECRETO DETECTADO - BLOQUEADO]",
                    result="Se bloqueo el envio al modelo",
                )
                return (
                    "He detectado informacion sensible en tu mensaje "
                    "(como una contrasena, API key o token). "
                    "Por seguridad, no he enviado ese mensaje al modelo. "
                    "Por favor, elimina esa informacion y vuelve a intentarlo."
                )

            exact = _exact_response(safe_input)
            if exact is not None:
                self.history.add_user(safe_input)
                self.history.add_assistant(exact)
                logger.log_action(instruction=instruction, result=exact)
                return exact

            self.history.add_user(safe_input)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(self.history.get_messages())

            print("\r[JARVIS pensando...]", end="", flush=True)

            response = ""
            for token in self.client.chat(messages, stream=True):
                response += token

            if not response:
                response = "Lo siento, no pude generar una respuesta. Intenta de nuevo."

            response = response.strip()
            self.history.add_assistant(response)

            result_snippet = response[:150]
            logger.log_action(
                instruction=instruction, result=result_snippet
            )

            return response

        except ConnectionError as e:
            logger.log_error("chat", str(e))
            raise
        except RuntimeError as e:
            logger.log_error("chat", str(e))
            raise
        except Exception as e:
            logger.log_error("chat", str(e))
            raise RuntimeError(f"Error inesperado al comunicarse con Ollama: {e}")

    def get_status(self) -> str:
        try:
            running = self.client.is_running()
            if not running:
                return "Ollama: NO CONECTADO"
            models = self.client.list_models()
            names = [m["name"] for m in models]
            return f"Ollama: OK | Modelos: {', '.join(names[:5])}"
        except Exception as e:
            return f"Ollama: ERROR ({e})"
