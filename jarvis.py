"""
JARVIS Local - Orquestador (Fase 1: Solo Chat)
Coordina la conversacion entre el usuario y Ollama.
En Fase 1, el modelo SOLO conversa. Sin herramientas.
"""
from jarvis_local.ollama_client.client import OllamaClient
from jarvis_local.memory.history import ConversationHistory
from jarvis_local.safety.logger import logger
from jarvis_local.safety.secrets import redact_secrets
from jarvis_local.config import get_config

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
