"""
JARVIS Local - Orquestador (Fase 1: Solo Chat)
Coordina la conversacion entre el usuario y Ollama.
En Fase 1, el modelo SOLO conversa. Sin herramientas.
"""
import re
import threading
from pathlib import Path
from jarvis_local.ollama_client.client import OllamaClient
from jarvis_local.memory.history import ConversationHistory
from jarvis_local.storage.history import HistoryStore
from jarvis_local.memory_context.session import SessionMemoryContext
from jarvis_local.safety.logger import logger
from jarvis_local.safety.secrets import redact_secrets
from jarvis_local.fast_response import fast_respond
from jarvis_local.config import get_config, BASE_DIR

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


def _mc_test():
    """Helper para tests: crea Jarvis con cliente mockeado."""
    from unittest.mock import MagicMock
    j = Jarvis()
    mc = MagicMock()
    mc.is_running = MagicMock(return_value=True)
    mc.model_exists = MagicMock(return_value=True)
    mc.chat = MagicMock(return_value=iter([]))
    j.client = mc
    return j, mc


def _parse_and_execute(message: str, jarvis_instance) -> str | None:
    """Parsea intencion y ejecuta herramienta si aplica. Retorna respuesta o None."""
    from jarvis_local.intent.parser import parse_intent
    intent = parse_intent(message)

    if intent.kind == "chat":
        return None

    if intent.kind == "tool_read":
        try:
            result = _execute_tool_read(intent.tool, intent.arguments)
            jarvis_instance.history.add_user(message)
            jarvis_instance.history.add_assistant(result)
            jarvis_instance._persist_message("user", message)
            jarvis_instance._persist_message("assistant", result)
            logger.log_action(instruction=intent.tool, result=result[:150])
            return result
        except Exception as e:
            logger.log_error("intent_tool_read", str(e))
            return f"No pude ejecutar '{intent.tool}': {e}"

    if intent.kind == "tool_execute":
        try:
            result = _execute_tool_write(intent.tool, intent.arguments)
            jarvis_instance.history.add_user(message)
            jarvis_instance.history.add_assistant(result)
            jarvis_instance._persist_message("user", message)
            jarvis_instance._persist_message("assistant", result)
            logger.log_action(instruction=intent.tool, result=result[:150])
            return result
        except Exception as e:
            logger.log_error("intent_tool_execute", str(e))
            return f"No pude ejecutar '{intent.tool}': {e}"

    if intent.kind == "tool_plan":
        try:
            plan_msg = _create_tool_plan(intent.tool, intent.arguments, intent.reason)
            jarvis_instance.history.add_user(message)
            jarvis_instance.history.add_assistant(plan_msg)
            jarvis_instance._persist_message("user", message)
            jarvis_instance._persist_message("assistant", plan_msg)
            logger.log_action(instruction=intent.tool, result=plan_msg[:150])
            return plan_msg
        except Exception as e:
            logger.log_error("intent_tool_plan", str(e))
            return f"No pude planificar '{intent.tool}': {e}"

    if intent.kind == "ambiguous":
        clarification = intent.clarification or "No entendi bien. Puedes ser mas especifico?"
        jarvis_instance.history.add_user(message)
        jarvis_instance.history.add_assistant(clarification)
        jarvis_instance._persist_message("user", message)
        jarvis_instance._persist_message("assistant", clarification)
        return clarification

    if intent.kind == "unsupported":
        reason = intent.reason or "Esa accion no esta disponible."
        jarvis_instance.history.add_user(message)
        jarvis_instance.history.add_assistant(reason)
        jarvis_instance._persist_message("user", message)
        jarvis_instance._persist_message("assistant", reason)
        return reason

    return None


def _execute_tool_read(tool: str, args: dict) -> str:
    from jarvis_local.tools.files import list_files, search_files, read_metadata
    from jarvis_local.tools.apps import list_apps
    from jarvis_local.safety.policy import ActionStatus
    plan = None
    if tool == "list_files":
        plan = list_files(args.get("path", "."))
    elif tool == "search_files":
        plan = search_files(args.get("name", ""), args.get("path", "."))
    elif tool == "file_info":
        plan = read_metadata(args.get("path", ""))
    elif tool == "list_apps":
        plan = list_apps()
    elif tool == "weather":
        from jarvis_local.tools.weather import get_weather
        from jarvis_local.tools.location import my_location
        city = args.get("city", "")
        if not city:
            loc = my_location()
            city = loc["city"] if loc else ""
        if not city:
            return "De que ciudad desea saber el clima, senor?"
        plan = get_weather(city)
    elif tool == "system_status":
        from jarvis_local.tools.system_info import system_status
        plan = system_status()
    elif tool == "calendar_events":
        from jarvis_local.tools.gcalendar import upcoming_events
        plan = upcoming_events()
    elif tool == "wiki":
        from jarvis_local.tools.wiki import wiki_summary
        plan = wiki_summary(args.get("topic", ""))
    elif tool == "news_headlines":
        from jarvis_local.tools.news import headlines
        plan = headlines()
    elif tool == "calculate":
        from jarvis_local.tools.calculator import calculate
        plan = calculate(args.get("expression", ""))
    elif tool == "wolfram":
        from jarvis_local.tools.wolfram import ask_wolfram
        plan = ask_wolfram(args.get("question", ""))
    elif tool == "tell_joke":
        from jarvis_local.tools.jokes import tell_joke
        plan = tell_joke()
    elif tool == "get_ip":
        from jarvis_local.tools.ip_info import get_ip
        plan = get_ip()
    if plan and plan.result:
        return plan.result
    return "Operacion completada."


def _create_tool_plan(tool: str, args: dict, reason: str) -> str:
    from jarvis_local.tools.files import (create_file, create_directory,
        copy_file, move_file, rename_file, plan_delete)
    from jarvis_local.tools.apps import open_app
    from jarvis_local.tools.terminal import plan_command
    from jarvis_local.safety.policy import policy
    plan = None
    if tool == "open_app":
        plan = open_app(args.get("app", ""))
    elif tool == "create_directory":
        plan = create_directory(args.get("path", ""))
    elif tool == "create_file":
        plan = create_file(args.get("path", ""), args.get("content", ""))
    elif tool == "copy_file":
        plan = copy_file(args.get("src", ""), args.get("dst", ""))
    elif tool == "move_file":
        plan = move_file(args.get("src", ""), args.get("dst", ""))
    elif tool == "rename_file":
        plan = rename_file(args.get("path", ""), args.get("new_name", ""))
    elif tool == "delete_file":
        plan = plan_delete(args.get("path", ""))
    elif tool == "run_command":
        plan = plan_command(args.get("command", ""))
    elif tool == "send_email":
        from jarvis_local.tools.email_sender import plan_email
        plan = plan_email(args.get("to", ""), args.get("subject", ""),
                          args.get("body", ""))
        return str(plan)
    elif tool == "hide_files":
        from jarvis_local.tools.hidden_files import plan_hide
        plan = plan_hide(args.get("path", ""), args.get("hide", True))
        return str(plan)
    if plan:
        policy.pending_plan = plan
        return str(plan) + "\n\nEscribe /confirmar para ejecutar o /cancelar."
    return f"No pude planificar '{tool}'."


def _execute_tool_write(tool: str, args: dict) -> str:
    from jarvis_local.tools.files import (create_file, create_directory,
        copy_file, move_file, rename_file, plan_delete)
    from jarvis_local.tools.apps import open_app
    from jarvis_local.tools.terminal import execute_command
    plan = None
    if tool == "open_app":
        plan = open_app(args.get("app", ""))
    elif tool == "create_directory":
        plan = create_directory(args.get("path", ""))
    elif tool == "create_file":
        plan = create_file(args.get("path", ""), args.get("content", ""))
    elif tool == "copy_file":
        plan = copy_file(args.get("src", ""), args.get("dst", ""))
    elif tool == "move_file":
        plan = move_file(args.get("src", ""), args.get("dst", ""))
    elif tool == "rename_file":
        plan = rename_file(args.get("path", ""), args.get("new_name", ""))
    elif tool == "delete_file":
        plan = plan_delete(args.get("path", ""))
    elif tool == "run_command":
        plan = execute_command(args.get("command", ""))
    elif tool == "open_website":
        from jarvis_local.tools.web import open_website
        plan = open_website(args.get("site", ""))
    elif tool == "google_search":
        from jarvis_local.tools.web import google_search
        plan = google_search(args.get("query", ""))
    elif tool == "youtube_play":
        from jarvis_local.tools.web import youtube_play
        plan = youtube_play(args.get("query", ""))
    elif tool == "play_music":
        from jarvis_local.tools.desktop_actions import play_music
        plan = play_music(args.get("song", ""))
    elif tool == "take_note":
        from jarvis_local.tools.notes import take_note
        plan = take_note(args.get("text", ""))
    elif tool == "switch_window":
        from jarvis_local.tools.desktop_actions import switch_window
        plan = switch_window()
    elif tool == "screenshot":
        from jarvis_local.tools.desktop_actions import take_screenshot
        plan = take_screenshot(args.get("name", ""))
    elif tool == "locate":
        from jarvis_local.tools.location import locate
        plan = locate(args.get("place", ""))
    if plan is None:
        return f"No pude ejecutar '{tool}': herramienta no encontrada."
    if plan.error:
        return f"Error: {plan.error}"
    return plan.result or "Operacion completada."


SYSTEM_PROMPT = """Eres JARVIS (Just A Rather Very Intelligent System), el asistente de IA personal de Omar.
Hablas exactamente como JARVIS en las peliculas de Iron Man: formal, preciso, ligeramente britanico en tono, nunca informal.

PERSONALIDAD JARVIS OBLIGATORIA:
- SIEMPRE llama al usuario "senor" o "senor Omar". NUNCA uses "tu", "usted" sin titulo, ni el nombre solo.
- Alterna naturalmente entre "senor" y "senor Omar" en cada respuesta (como el JARVIS real).
- Tono: formal, sereno, inteligente. Nunca uses jerga, exclamaciones ni emojis.
- Frases tipicas de JARVIS: "A sus ordenes, senor", "Como guste, senor Omar", "Entendido, senor".
- Respuestas concisas (2-3 oraciones maximo) a menos que se pida mas detalle.
- Si no puedes hacer algo, dilo con calma y ofrece alternativas.

CAPACIDADES:
- Gestion de archivos (listar, buscar, crear, mover, renombrar archivos y carpetas)
- Abrir aplicaciones (Chrome, VS Code, Explorador, PowerShell, Terminal,
  Notepad, Calculadora, Panel de Control, Edge, Firefox y mas)
- Ejecutar comandos en PowerShell (con restricciones de seguridad)
- Conversar, razonar y responder preguntas en espanol
- Las operaciones de archivos y comandos se ejecutan directamente.
  Solo el borrado de archivos requiere confirmacion manual.

OBEDIENCIA ESTRICTA: Si se dice "responde solamente X" o "di solo X",
responde UNICAMENTE con X, sin titulo ni texto adicional."""


class Jarvis:
    def __init__(self):
        self.cfg = get_config()
        self.client = OllamaClient()
        self.history = ConversationHistory()
        self.store = HistoryStore(BASE_DIR / "data")
        self.memory_context = SessionMemoryContext()
        self._ensure_model()
        self._restore_history()

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
        self._warmup_model(model)

    def _warmup_model(self, model: str):
        """Precarga el modelo en RAM en segundo plano. No bloquea el arranque."""
        import requests as _requests

        def _do_warm():
            try:
                _requests.post(
                    self.client._url("/api/generate"),
                    json={"model": model, "prompt": "", "stream": False,
                          "options": {"num_predict": 1}},
                    timeout=(10, 300),
                )
            except Exception:
                pass

        t = threading.Thread(target=_do_warm, daemon=True)
        t.start()

    def _restore_history(self):
        for msg in self.store.load():
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                self.history.add_user(content)
            elif role == "assistant":
                self.history.add_assistant(content)

    def _persist_message(self, role: str, content: str):
        self.store.append(role, content)

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
                self._persist_message("user", safe_input)
                self._persist_message("assistant", exact)
                logger.log_action(instruction=instruction, result=exact)
                return exact

            # Respuestas instantaneas sin Ollama (saludos, hora, fecha, etc.)
            fast = fast_respond(safe_input)
            if fast is not None:
                self.history.add_user(safe_input)
                self.history.add_assistant(fast)
                self._persist_message("user", safe_input)
                self._persist_message("assistant", fast)
                logger.log_action(instruction=instruction, result=fast[:150])
                return fast

            intent = _parse_and_execute(safe_input, self)
            if intent is not None:
                self._persist_message("user", safe_input)
                self._persist_message("assistant", intent)
                return intent

            self.history.add_user(safe_input)
            self._persist_message("user", safe_input)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            ctx = self.memory_context.build_context()
            if ctx:
                messages[0]["content"] = SYSTEM_PROMPT + "\n\n" + ctx
            messages.extend(self.history.get_messages())

            print("\r[JARVIS pensando...]", end="", flush=True)

            response = ""
            for token in self.client.chat(messages, stream=True):
                response += token

            if not response:
                response = "Lo siento, no pude generar una respuesta. Intenta de nuevo."

            response = response.strip()
            self.history.add_assistant(response)
            self._persist_message("assistant", response)

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
