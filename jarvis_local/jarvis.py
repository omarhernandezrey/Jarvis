"""
JARVIS Local - Orquestador (Fase 1: Solo Chat)
Coordina la conversacion entre el usuario y Ollama.
En Fase 1, el modelo SOLO conversa. Sin herramientas.
"""
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jarvis_local.config import BASE_DIR, get_config
from jarvis_local.fast_response import fast_respond
from jarvis_local.memory.history import ConversationHistory
from jarvis_local.memory_context.session import SessionMemoryContext
from jarvis_local.ollama_client.client import OllamaClient
from jarvis_local.safety.logger import logger
from jarvis_local.safety.secrets import redact_secrets
from jarvis_local.storage.history import HistoryStore

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


# =============================================================================
# TOOL REGISTRY: mapeo nombre_herramienta -> función
# =============================================================================

def _get_weather(args: dict) -> Any:
    from jarvis_local.tools.location import my_location
    from jarvis_local.tools.weather import get_weather
    city = args.get("city", "")
    if not city:
        loc = my_location()
        city = loc["city"] if loc else ""
    if not city:
        return "De que ciudad desea saber el clima, senor?"
    return get_weather(city)


def _get_calculate(args: dict) -> Any:
    from jarvis_local.safety.policy import ActionStatus
    from jarvis_local.tools.calculator import calculate
    from jarvis_local.tools.wolfram import ask_wolfram, has_app_id
    plan = calculate(args.get("expression", ""))
    if plan.status == ActionStatus.ERROR and has_app_id():
        wa = ask_wolfram(args.get("expression", ""))
        if wa.status != ActionStatus.ERROR:
            plan = wa
    return plan


# Herramientas de lectura (solo consultan, no modifican)
_READ_TOOLS: dict[str, Callable[[dict], Any]] = {
    "list_files": lambda args: __import__("jarvis_local.tools.files", fromlist=["list_files"]).list_files(args.get("path", ".")),
    "search_files": lambda args: __import__("jarvis_local.tools.files", fromlist=["search_files"]).search_files(args.get("name", ""), args.get("path", ".")),
    "file_info": lambda args: __import__("jarvis_local.tools.files", fromlist=["read_metadata"]).read_metadata(args.get("path", "")),
    "list_apps": lambda args: __import__("jarvis_local.tools.apps", fromlist=["list_apps"]).list_apps(),
    "weather": _get_weather,
    "system_status": lambda args: __import__("jarvis_local.tools.system_info", fromlist=["system_status"]).system_status(),
    "calendar_events": lambda args: __import__("jarvis_local.tools.gcalendar", fromlist=["upcoming_events"]).upcoming_events(),
    "wiki": lambda args: __import__("jarvis_local.tools.wiki", fromlist=["wiki_summary"]).wiki_summary(args.get("topic", "")),
    "news_headlines": lambda args: __import__("jarvis_local.tools.news", fromlist=["headlines"]).headlines(),
    "calculate": _get_calculate,
    "wolfram": lambda args: __import__("jarvis_local.tools.wolfram", fromlist=["ask_wolfram"]).ask_wolfram(args.get("question", "")),
    "tell_joke": lambda args: __import__("jarvis_local.tools.jokes", fromlist=["tell_joke"]).tell_joke(),
    "get_ip": lambda args: __import__("jarvis_local.tools.ip_info", fromlist=["get_ip"]).get_ip(),
    "search_jobs": lambda args: __import__("jarvis_local.tools.jobs", fromlist=["search_jobs"]).search_jobs(args.get("puesto", ""), args.get("ciudad", "")),
    "list_reminders": lambda args: __import__("jarvis_local.tools.reminders", fromlist=["list_reminders"]).list_reminders(),
    "list_contacts": lambda args: __import__("jarvis_local.tools.whatsapp", fromlist=["list_contacts"]).list_contacts(),
    "read_clipboard": lambda args: __import__("jarvis_local.tools.reader", fromlist=["read_clipboard"]).read_clipboard(),
    "read_file": lambda args: __import__("jarvis_local.tools.reader", fromlist=["read_file_aloud"]).read_file_aloud(args.get("path", "")),
    "daily_briefing": lambda args: __import__("jarvis_local.tools.briefing", fromlist=["daily_briefing"]).daily_briefing(),
}

# Herramientas de escritura (planificación y ejecución)
_WRITE_TOOLS: dict[str, Callable[[dict], Any]] = {
    "open_app": lambda args: __import__("jarvis_local.tools.apps", fromlist=["open_app"]).open_app(args.get("app", "")),
    "create_directory": lambda args: __import__("jarvis_local.tools.files", fromlist=["create_directory"]).create_directory(args.get("path", "")),
    "create_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["create_file"]).create_file(args.get("path", ""), args.get("content", "")),
    "copy_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["copy_file"]).copy_file(args.get("src", ""), args.get("dst", "")),
    "move_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["move_file"]).move_file(args.get("src", ""), args.get("dst", "")),
    "rename_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["rename_file"]).rename_file(args.get("path", ""), args.get("new_name", "")),
    "delete_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["plan_delete"]).plan_delete(args.get("path", "")),
    "run_command": lambda args: __import__("jarvis_local.tools.terminal", fromlist=["execute_command"]).execute_command(args.get("command", "")),
    "open_website": lambda args: __import__("jarvis_local.tools.web", fromlist=["open_website"]).open_website(args.get("site", "")),
    "google_search": lambda args: __import__("jarvis_local.tools.web", fromlist=["google_search"]).google_search(args.get("query", "")),
    "youtube_play": lambda args: __import__("jarvis_local.tools.web", fromlist=["youtube_play"]).youtube_play(args.get("query", "")),
    "spotify_play": lambda args: __import__("jarvis_local.tools.spotify", fromlist=["play_song"]).play_song(args.get("song", "")),
    "play_music": lambda args: __import__("jarvis_local.tools.desktop_actions", fromlist=["play_music"]).play_music(args.get("song", "")),
    "take_note": lambda args: __import__("jarvis_local.tools.notes", fromlist=["take_note"]).take_note(args.get("text", "")),
    "switch_window": lambda args: __import__("jarvis_local.tools.desktop_actions", fromlist=["switch_window"]).switch_window(),
    "screenshot": lambda args: __import__("jarvis_local.tools.desktop_actions", fromlist=["take_screenshot"]).take_screenshot(args.get("name", "")),
    "locate": lambda args: __import__("jarvis_local.tools.location", fromlist=["locate"]).locate(args.get("place", "")),
    "open_job": lambda args: __import__("jarvis_local.tools.jobs", fromlist=["open_job"]).open_job(args.get("number", 1)),
    "show_jobs": lambda args: __import__("jarvis_local.tools.browser", fromlist=["show_jobs_in_browser"]).show_jobs_in_browser(args.get("puesto", ""), args.get("ciudad", "")),
    "browser_navigate": lambda args: __import__("jarvis_local.tools.browser", fromlist=["navigate"]).navigate(args.get("url", "")),
    "close_browser": lambda args: __import__("jarvis_local.tools.browser", fromlist=["close_browser"]).close_browser(),
    "close_app": lambda args: __import__("jarvis_local.tools.apps", fromlist=["close_app"]).close_app(args.get("app", "")),
    "close_all_apps": lambda args: __import__("jarvis_local.tools.apps", fromlist=["close_all_apps"]).close_all_apps(),
    "volume_set": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["set_volume"]).set_volume(args.get("level", 50)),
    "volume_up": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["volume_up"]).volume_up(),
    "volume_down": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["volume_down"]).volume_down(),
    "volume_mute": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["volume_mute"]).volume_mute(args.get("mute", True)),
    "media_play_pause": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["media_play_pause"]).media_play_pause(),
    "media_next": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["media_next"]).media_next(),
    "media_previous": lambda args: __import__("jarvis_local.tools.media_controls", fromlist=["media_previous"]).media_previous(),
    "set_reminder": lambda args: __import__("jarvis_local.tools.reminders", fromlist=["set_reminder"]).set_reminder(args.get("text", ""), args.get("minutes", 0), args.get("at", "")),
    "cancel_reminder": lambda args: __import__("jarvis_local.tools.reminders", fromlist=["cancel_reminder"]).cancel_reminder(args.get("which", "todos")),
    "send_whatsapp": lambda args: __import__("jarvis_local.tools.whatsapp", fromlist=["send_whatsapp"]).send_whatsapp(args.get("to", ""), args.get("message", "")),
    "add_contact": lambda args: __import__("jarvis_local.tools.whatsapp", fromlist=["add_contact"]).add_contact(args.get("name", ""), args.get("phone", "")),
    "lock_pc": lambda args: __import__("jarvis_local.tools.power", fromlist=["lock_pc"]).lock_pc(),
    "shutdown_pc": lambda args: __import__("jarvis_local.tools.power", fromlist=["shutdown_pc"]).shutdown_pc(args.get("seconds", 60)),
    "restart_pc": lambda args: __import__("jarvis_local.tools.power", fromlist=["restart_pc"]).restart_pc(args.get("seconds", 60)),
    "cancel_shutdown": lambda args: __import__("jarvis_local.tools.power", fromlist=["cancel_shutdown"]).cancel_shutdown(),
    "suspend_pc": lambda args: __import__("jarvis_local.tools.power", fromlist=["suspend_pc"]).suspend_pc(),
    "minimize_all": lambda args: __import__("jarvis_local.tools.desktop_actions", fromlist=["minimize_all"]).minimize_all(),
    "snap_window": lambda args: __import__("jarvis_local.tools.desktop_actions", fromlist=["snap_window"]).snap_window(args.get("direction", "")),
}

# Herramientas que requieren planificación (confirmación)
_PLAN_TOOLS: dict[str, Callable[[dict], Any]] = {
    "open_app": lambda args: __import__("jarvis_local.tools.apps", fromlist=["open_app"]).open_app(args.get("app", "")),
    "create_directory": lambda args: __import__("jarvis_local.tools.files", fromlist=["create_directory"]).create_directory(args.get("path", "")),
    "create_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["create_file"]).create_file(args.get("path", ""), args.get("content", "")),
    "copy_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["copy_file"]).copy_file(args.get("src", ""), args.get("dst", "")),
    "move_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["move_file"]).move_file(args.get("src", ""), args.get("dst", "")),
    "rename_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["rename_file"]).rename_file(args.get("path", ""), args.get("new_name", "")),
    "delete_file": lambda args: __import__("jarvis_local.tools.files", fromlist=["plan_delete"]).plan_delete(args.get("path", "")),
    "run_command": lambda args: __import__("jarvis_local.tools.terminal", fromlist=["plan_command"]).plan_command(args.get("command", "")),
    "send_email": lambda args: __import__("jarvis_local.tools.email_sender", fromlist=["plan_email"]).plan_email(args.get("to", ""), args.get("subject", ""), args.get("body", "")),
    "hide_files": lambda args: __import__("jarvis_local.tools.hidden_files", fromlist=["plan_hide"]).plan_hide(args.get("path", ""), args.get("hide", True)),
}


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


def _record_exchange(jarvis_instance, message: str, result: str, instruction: str = ""):
    """Registra un intercambio usuario-asistente en historial, persistencia y logs."""
    jarvis_instance.history.add_user(message)
    jarvis_instance.history.add_assistant(result)
    jarvis_instance._persist_message("user", message)
    jarvis_instance._persist_message("assistant", result)
    if instruction:
        logger.log_action(instruction=instruction, result=result[:150])


def _parse_and_execute(message: str, jarvis_instance) -> str | None:
    """Parsea intencion y ejecuta herramienta si aplica. Retorna respuesta o None."""
    from jarvis_local.intent.parser import parse_intent
    intent = parse_intent(message)

    if intent.kind == "chat":
        return None

    if intent.kind == "tool_read":
        try:
            result = _execute_tool_read(intent.tool, intent.arguments)
            _record_exchange(jarvis_instance, message, result, intent.tool)
            return result
        except Exception as e:
            logger.log_error("intent_tool_read", str(e))
            return f"No pude ejecutar '{intent.tool}': {e}"

    if intent.kind == "tool_execute":
        try:
            result = _execute_tool_write(intent.tool, intent.arguments)
            _record_exchange(jarvis_instance, message, result, intent.tool)
            return result
        except Exception as e:
            logger.log_error("intent_tool_execute", str(e))
            return f"No pude ejecutar '{intent.tool}': {e}"

    if intent.kind == "tool_plan":
        try:
            plan_msg = _create_tool_plan(intent.tool, intent.arguments, intent.reason)
            _record_exchange(jarvis_instance, message, plan_msg, intent.tool)
            return plan_msg
        except Exception as e:
            logger.log_error("intent_tool_plan", str(e))
            return f"No pude planificar '{intent.tool}': {e}"

    if intent.kind == "ambiguous":
        clarification = intent.clarification or "No entendi bien. Puedes ser mas especifico?"
        _record_exchange(jarvis_instance, message, clarification)
        return clarification

    if intent.kind == "unsupported":
        reason = intent.reason or "Esa accion no esta disponible."
        _record_exchange(jarvis_instance, message, reason)
        return reason

    return None


def _execute_tool_read(tool: str, args: dict) -> str:
    """Ejecuta una herramienta de lectura usando el registry."""
    fn = _READ_TOOLS.get(tool)
    if fn is None:
        return f"Herramienta de lectura no encontrada: {tool}"
    plan = fn(args)
    if plan and hasattr(plan, "result") and plan.result:
        return plan.result
    if isinstance(plan, str):
        return plan
    return "Operacion completada."


def _create_tool_plan(tool: str, args: dict, reason: str) -> str:
    """Crea un plan de ejecución para una herramienta de escritura."""
    from jarvis_local.safety.policy import policy
    fn = _PLAN_TOOLS.get(tool)
    if fn is None:
        return f"No pude planificar '{tool}'."
    plan = fn(args)
    if plan:
        policy.pending_plan = plan
        return str(plan) + "\n\nEscribe /confirmar para ejecutar o /cancelar."
    return f"No pude planificar '{tool}'."


def _execute_tool_write(tool: str, args: dict) -> str:
    """Ejecuta una herramienta de escritura usando el registry."""
    fn = _WRITE_TOOLS.get(tool)
    if fn is None:
        return f"No pude ejecutar '{tool}': herramienta no encontrada."
    plan = fn(args)
    if plan is None:
        return f"No pude ejecutar '{tool}': herramienta no encontrada."
    if hasattr(plan, "error") and plan.error:
        safe_error, _ = redact_secrets(plan.error)
        return f"Error: {safe_error}"
    if hasattr(plan, "result") and plan.result:
        return plan.result
    if isinstance(plan, str):
        return plan
    return "Operacion completada."


def _load_system_prompt() -> str:
    """Carga el system prompt desde archivo externo, con fallback inline."""
    try:
        prompt_path = Path(__file__).parent / "prompts" / "system.txt"
        return prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        # Fallback si el archivo no existe
        return """Eres JARVIS, el asistente de IA personal de Omar.
Hablas formalmente, llamando al usuario "senor" o "senor Omar".
Respuestas concisas (2-3 oraciones maximo).
Si no puedes hacer algo, dilo con calma y ofrece alternativas."""


SYSTEM_PROMPT = _load_system_prompt()


class Jarvis:
    def __init__(self):
        self.cfg = get_config()
        self.client = OllamaClient()
        self.history = ConversationHistory()
        self.store = HistoryStore(BASE_DIR / "data")
        self.memory_context = SessionMemoryContext()
        # Agente con tool calling (Fase 6). Se puede apagar en config.yaml
        # (agent.enabled: false) para volver al comportamiento por parser.
        self.agent_enabled = self.cfg.get("agent", {}).get("enabled", True)
        self.auto_recall = self._build_recall()
        # Si se asigna una funcion de TTS, las respuestas del chat se hablan
        # por frases mientras el modelo genera (ver voice/streaming.py).
        # El CLI la conecta cuando /voz esta en ON.
        self.speak_fn: Callable[[str], None] | None = None
        # True si la ultima respuesta ya se hablo durante el streaming: evita
        # que la interfaz la vuelva a pronunciar al terminar.
        self.spoke_last_response = False
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
        import contextlib

        import requests as _requests

        def _do_warm():
            with contextlib.suppress(Exception):
                _requests.post(
                    self.client._url("/api/generate"),
                    json={"model": model, "prompt": "", "stream": False,
                          "options": {"num_predict": 1}},
                    timeout=(10, 300),
                )

        t = threading.Thread(target=_do_warm, daemon=True)
        t.start()

    def _build_recall(self):
        """Recuerdo automatico por significado. Si falla, JARVIS sigue sin el."""
        try:
            from jarvis_local.memory_context.recall import AutoRecall
            from jarvis_local.storage.memory import MemoryStore
            from jarvis_local.storage.semantic import SemanticIndex
            store = MemoryStore(BASE_DIR / "data")
            index = SemanticIndex(BASE_DIR / "data")
            recall = AutoRecall(store, index)
            recall.enabled = self.cfg.get("memory", {}).get("auto_recall", True)
            return recall
        except Exception as e:
            logger.log_error("auto_recall_init", str(e))
            return None

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
        self.spoke_last_response = False
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

            # Peticion de varias acciones ("dime el clima y luego abre Chrome"):
            # se parte y cada clausula baja por la cascada completa. Antes esto
            # lo resolvia el agente por dentro, y la segunda clausula ("abre
            # Chrome") iba directa al LLM, saltandose el parser que la resolvia
            # perfecto: el modelo pequeno a veces no la ejecutaba.
            encadenada = self._chat_encadenado(safe_input, instruction)
            if encadenada is not None:
                return encadenada

            # Camino rapido: el parser deterministico reconoce la frase
            # (instantaneo, sin gastar el LLM)
            intent = _parse_and_execute(safe_input, self)
            if intent is not None:
                self._persist_message("user", safe_input)
                self._persist_message("assistant", intent)
                return intent

            # Camino agentico: el LLM decide que herramientas usar.
            # Cubre las frases que el parser no anticipo y encadena acciones.
            agent_reply = self._try_agent(safe_input, instruction)
            if agent_reply is not None:
                return agent_reply

            self.history.add_user(safe_input)
            self._persist_message("user", safe_input)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            partes = [SYSTEM_PROMPT]
            # Memorias activadas a mano (/memoria usar)
            ctx = self.memory_context.build_context()
            if ctx:
                partes.append(ctx)
            # Memorias recuperadas por significado (automatico)
            if self.auto_recall is not None:
                auto = self.auto_recall.build_context(safe_input)
                if auto:
                    partes.append(auto)
            if len(partes) > 1:
                messages[0]["content"] = "\n\n".join(partes)
            messages.extend(self.history.get_messages())

            print("\r[JARVIS pensando...]", end="", flush=True)

            tokens = self.client.chat(messages, stream=True)
            if self.speak_fn is not None:
                # Habla por frases mientras el modelo sigue generando: la
                # primera palabra suena a los ~5 s en vez de a los ~40 s.
                from jarvis_local.voice.streaming import speak_stream
                response = speak_stream(tokens, self.speak_fn)
                self.spoke_last_response = True
            else:
                response = "".join(tokens)

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
            raise RuntimeError(
                f"Error inesperado al comunicarse con Ollama: {e}") from e

    def _chat_encadenado(self, safe_input: str, instruction: str) -> str | None:
        """Resuelve una peticion de varias acciones, clausula por clausula.

        Cada clausula baja por la MISMA cascada que un mensaje suelto: primero
        el parser (instantaneo y fiable para "abre Chrome") y solo si no la
        reconoce, el agente. Devuelve None si la peticion es de una sola accion.
        """
        from jarvis_local.intent.parser import dividir_acciones

        clausulas = dividir_acciones(safe_input)
        if len(clausulas) < 2:
            return None

        partes: list[str] = []
        for clausula in clausulas:
            respuesta = _parse_and_execute(clausula, self)
            if respuesta is None:
                r = self._try_agent(clausula, clausula[:100])
                respuesta = r if r else None
            if respuesta:
                partes.append(respuesta)

        if not partes:
            return None  # no se resolvio nada: que lo intente el chat

        texto = "\n".join(partes)
        logger.log_action(instruction=instruction,
                          result=f"[encadenado x{len(partes)}] {texto[:120]}")
        return texto

    def _try_agent(self, safe_input: str, instruction: str) -> str | None:
        """Deja que el LLM elija herramientas (tool calling).

        Devuelve la respuesta si el agente uso alguna herramienta; None si no
        uso ninguna, para que la peticion siga al chat normal (mas barato y
        con la personalidad y el contexto de memoria completos).
        """
        if not self.agent_enabled:
            return None
        try:
            from jarvis_local.agent.loop import run_agent
            result = run_agent(self.client, safe_input,
                               history=self.history.get_messages())
        except Exception as e:
            logger.log_error("agente", str(e))
            return None  # si el agente falla, seguimos con el chat normal

        # El agente pide aclaracion: esa ES la respuesta correcta. Mandarla al
        # chat haria que el modelo divague o invente en vez de preguntar.
        if result.needs_clarification and result.text:
            self.history.add_user(safe_input)
            self.history.add_assistant(result.text)
            self._persist_message("user", safe_input)
            self._persist_message("assistant", result.text)
            logger.log_action(instruction=instruction,
                              result=f"[aclaracion] {result.text[:120]}")
            return result.text

        if not result.tools_used or not result.text:
            return None

        self.history.add_user(safe_input)
        self.history.add_assistant(result.text)
        self._persist_message("user", safe_input)
        self._persist_message("assistant", result.text)
        logger.log_action(instruction=instruction,
                          result=f"[agente:{','.join(result.tools_used)}] "
                                 f"{result.text[:120]}")
        return result.text

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
