"""
JARVIS Local - Bucle del agente (Fase 6)

El LLM decide que herramienta usar (tool calling nativo de Ollama) y JARVIS la
ejecuta. Cubre las frases que el parser deterministico no anticipo: "necesito
saber si va a llover por alla en Cartagena", "que tal anda mi maquina".

Decisiones de diseno, aprendidas midiendo en el equipo real (i5 sin GPU):

1. Se ofrecen solo las herramientas plausibles (ver selector.py), no las 30.
   Con las 30, el prompt supera los 4000 tokens: el modelo de 3B tardaba
   1-2 minutos y elegia mal (pedia el clima a Google).

2. Una sola llamada al LLM por defecto. Nuestras herramientas ya devuelven
   texto redactado en el tono de JARVIS ("Clima en Bogota: nublado, 13 grados"),
   asi que pedirle al modelo que lo reescriba costaria otro minuto y ademas
   lo hacia peor: filtraba el JSON del tool call dentro de la respuesta.
   Solo se encadena una segunda herramienta si el modelo lo pide explicitamente.

3. Las herramientas destructivas (borrar, correo, ocultar) devuelven un plan
   pendiente: el bucle se detiene y espera el /confirmar del usuario. El modelo
   nunca ejecuta acciones irreversibles por su cuenta.
"""
import json
import re
from dataclasses import dataclass, field

from jarvis_local.agent.registry import execute, get_tool
from jarvis_local.agent.selector import select_tools
from jarvis_local.safety.logger import logger

MAX_STEPS = 3

AGENT_SYSTEM_PROMPT = """Eres JARVIS, el asistente personal de Omar, con herramientas que actuan sobre su computador Windows.

Si la peticion del usuario se resuelve con una de las herramientas disponibles, llamala con los argumentos correctos.
Si ninguna herramienta encaja, responde brevemente en texto, tratando al usuario de "senor".
Nunca inventes datos que deba entregar una herramienta (clima, noticias, ofertas de empleo, estado del sistema).
Nunca escribas JSON en tu respuesta de texto."""

# El modelo a veces escupe el tool call como texto en vez de usar el canal
# de tool_calls. Detectamos ese JSON para no mostrarselo al usuario.
_JSON_LEAK = re.compile(r'^\s*[>\s]*\{.*"(?:name|arguments|function)".*\}\s*$',
                        re.S)


@dataclass
class AgentResult:
    text: str
    tools_used: list[str] = field(default_factory=list)
    pending_confirmation: bool = False


def _arguments(call: dict) -> dict:
    """Los argumentos pueden venir como dict o como string JSON."""
    args = call.get("function", {}).get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return args if isinstance(args, dict) else {}


def _clean_text(text: str) -> str:
    """Descarta la respuesta si el modelo filtro un tool call como texto."""
    t = (text or "").strip()
    if not t or _JSON_LEAK.match(t):
        return ""
    return t


def run_agent(client, user_message: str, history: list[dict] | None = None,
              max_steps: int = MAX_STEPS) -> AgentResult:
    """Ejecuta el bucle agentico. Si ninguna herramienta es plausible para el
    mensaje, devuelve un resultado vacio para que la peticion siga al chat."""
    tools = select_tools(user_message)
    if not tools:
        return AgentResult(text="")  # nada que hacer aqui: que responda el chat

    messages: list[dict] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-4:])  # contexto reciente, sin inflar el prompt
    messages.append({"role": "user", "content": user_message})

    usadas: list[str] = []
    resultados: list[str] = []

    for _paso in range(max_steps):
        msg = client.chat_with_tools(messages, tools)
        calls = msg.get("tool_calls") or []

        if not calls:
            texto = _clean_text(msg.get("content", ""))
            # Si ya corrimos herramientas, su salida es la respuesta buena:
            # el texto del modelo solo la empeoraria.
            if usadas:
                return AgentResult(text="\n".join(resultados), tools_used=usadas)
            return AgentResult(text=texto)

        messages.append({"role": "assistant", "content": msg.get("content", ""),
                         "tool_calls": calls})

        for call in calls:
            name = call.get("function", {}).get("name", "")
            args = _arguments(call)
            if get_tool(name) is None:
                messages.append({"role": "tool", "name": name,
                                 "content": f"La herramienta '{name}' no existe."})
                continue

            texto, pendiente = execute(name, args)
            usadas.append(name)
            resultados.append(texto)
            logger.log_action(instruction=f"agente:{name}({args})",
                              result=texto[:150])

            if pendiente:  # espera /confirmar del usuario
                return AgentResult(text=texto, tools_used=usadas,
                                   pending_confirmation=True)

            messages.append({"role": "tool", "name": name, "content": texto})

        # Con una herramienta ya ejecutada, devolvemos su resultado directo:
        # una segunda llamada al LLM solo para "redactar" cuesta ~1 minuto en
        # CPU y degrada el texto. (Ver nota 2 de la cabecera.)
        return AgentResult(text="\n".join(resultados), tools_used=usadas)

    return AgentResult(text="\n".join(resultados), tools_used=usadas)
