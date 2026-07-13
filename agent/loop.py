"""
JARVIS Local - Bucle del agente (router de intencion)

El LLM decide que herramienta usar (tool calling nativo de Ollama) y JARVIS la
ejecuta. Este modulo es el nucleo del razonamiento: aqui se decide QUE hacer.

DISENO (cada decision viene de medir la bateria de jarvis_local/eval/, no de
suponer):

1. Las herramientas candidatas se recuperan por SIGNIFICADO (retriever.py), no
   por palabras clave. El selector lexico anterior devolvia una lista vacia
   ante lenguaje coloquial ("chamba", "pega") y entonces el agente ni se
   invocaba: el modelo nunca veia la frase. Recall@6 del retriever: 100%.

2. El LLM decide, no el retriever. El retriever solo acota el catalogo (31
   esquemas saturan a un 3B en CPU: 1-2 min y elige mal; con <=6, ~15 s y
   acierta). Cuando ninguna herramienta encaja, el modelo tiene la opcion
   explicita de no llamar ninguna y responder en texto.

3. Multi-paso real: tras ejecutar una herramienta se le devuelve el resultado al
   modelo, que puede encadenar otra ("busca trabajo y abre la primera oferta").

4. Validacion estricta con reintento: si el modelo inventa una herramienta o
   omite argumentos obligatorios, se le devuelve el error concreto y se le da
   otra oportunidad, en vez de fallar en silencio.

5. Confianza baja o argumentos incompletos -> pedir aclaracion. Nunca ejecutar
   una accion "a ver si suena".

6. Toda decision queda en un log estructurado (decisions.jsonl) para auditar.
"""
import json
import re
from dataclasses import dataclass, field

from jarvis_local.agent.decision_log import log_decision
from jarvis_local.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    CONTEXT_HINT,
    correccion_argumentos,
    correccion_herramienta_invalida,
)
from jarvis_local.agent.registry import execute, get_tool, tool_names
from jarvis_local.agent.retriever import confidence, select_tools

MAX_STEPS = 3       # herramientas encadenadas por peticion
MAX_REINTENTOS = 2  # correcciones al modelo ante salida invalida

# El modelo a veces escribe el tool call como texto en vez de usar el canal de
# tool_calls. Ese JSON no debe llegarle nunca al usuario.
_JSON_LEAK = re.compile(r'^\s*[>\s]*[{\[].*["\'](?:name|arguments|function)["\'].*[}\]]\s*$',
                        re.S)

# Referencias a turnos anteriores: activan la pista de contexto en el prompt.
_ANAFORA = re.compile(
    r'^\s*(?:y|ahora|luego|despues|entonces)\b|\b(?:eso|ese|esa|esos|esas|'
    r'lo mismo|el anterior|la anterior|la primera|la segunda|la tercera|'
    r'el primero|el segundo|ahi|alli)\b', re.IGNORECASE)


# Deicticos: palabras que senalan a algo sin nombrarlo. Una orden construida
# solo con estos no tiene objeto identificable.
_VAGO = re.compile(
    r'^\s*(?:hazlo|haz\s+eso|hazme\s+eso|dale|listo|eso|ahi|'
    r'(?:abre|abreme|cierra|busca|buscame|pon|ponme|dame|muestra|muestrame|'
    r'ejecuta|corre|borra|elimina|toma|manda|envia|reproduce|lanza|inicia)'
    r'(?:\s+(?:eso|esto|aquello|ese|esa|ahi|alli|el|la|lo|los|las|algo|'
    r'una?\s+cosa))?\s*[.!?]*)\s*$',
    re.IGNORECASE)

# "necesito ayuda con algo", "quiero hacer una cosa": peticion sin contenido.
_SIN_OBJETO = re.compile(
    r'\b(?:ayuda|ayudame|hacer|haga|necesito)\b.*\b(?:algo|una\s+cosa|eso)\b|'
    r'\b(?:algo|una\s+cosa)\b\s*[.!?]*\s*$', re.IGNORECASE)


def _es_orden_vaga(message: str) -> bool:
    """Es una ORDEN pero sin objeto: hay que preguntar, no adivinar ni callar.

    Distingue "hazlo" / "abre eso" / "busca" (ordenes incompletas -> aclarar)
    de "de que color es el cielo" (conversacion -> responder). Ambas dan
    confianza semantica baja, pero exigen respuestas opuestas: ante una orden
    incompleta, quedarse callado o divagar es el peor resultado posible.
    """
    m = message.strip()
    if not m or len(m.split()) > 6:
        return False
    return bool(_VAGO.match(m) or _SIN_OBJETO.search(m))


@dataclass
class AgentResult:
    text: str
    tools_used: list[str] = field(default_factory=list)
    pending_confirmation: bool = False
    needs_clarification: bool = False
    confidence: float = 0.0


def _arguments(call: dict) -> dict:
    """Los argumentos pueden venir como dict o como string JSON."""
    args = call.get("function", {}).get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {}
    return args if isinstance(args, dict) else {}


def _clean_text(text: str) -> str:
    """Descarta la respuesta si el modelo filtro un tool call como texto."""
    t = (text or "").strip()
    if not t or _JSON_LEAK.match(t):
        return ""
    return t


def _validar(name: str, args: dict) -> tuple[bool, str]:
    """Valida la llamada contra el esquema. (valida, mensaje_de_correccion)."""
    tool = get_tool(name)
    if tool is None:
        return False, correccion_herramienta_invalida(name, tool_names())

    props = tool.parameters.get("properties", {})
    requeridos = tool.parameters.get("required", [])
    faltantes = [r for r in requeridos
                 if r not in args or args[r] in (None, "", [])]
    if faltantes:
        return False, correccion_argumentos(name, faltantes)
    return True, ""


def _limpiar_args(name: str, args: dict) -> dict:
    """Descarta argumentos que el modelo se invento y no existen en el esquema."""
    tool = get_tool(name)
    if tool is None:
        return {}
    validos = set(tool.parameters.get("properties", {}))
    return {k: v for k, v in args.items() if k in validos}


def run_agent(client, user_message: str, history: list[dict] | None = None,
              max_steps: int = MAX_STEPS) -> AgentResult:
    """Decide y ejecuta. Texto vacio y sin herramientas = que responda el chat."""
    from jarvis_local.intent.parser import es_multi_accion

    conf = confidence(user_message)

    # Orden sin objeto ("hazlo", "abre eso", "busca") y sin conversacion previa
    # de donde deducirlo: preguntar. Se comprueba ANTES de mirar la confianza,
    # porque el retriever puede estar muy seguro de la ACCION ("abre") y aun asi
    # no haber ningun objeto que abrir. Ejecutar aqui seria adivinar.
    # Con historial no se corta: "abreme la segunda" SI es resoluble con contexto.
    if _es_orden_vaga(user_message) and not history:
        texto = ("Que desea que haga exactamente, senor? Necesito que me "
                 "precise la accion o el objeto.")
        log_decision(user_message, conf, [], [texto], "aclaracion_orden_vaga")
        return AgentResult(text=texto, needs_clarification=True, confidence=conf)

    tools = select_tools(user_message)
    if not tools:
        # Nada plausible ni semanticamente: es conversacion. No se gasta una
        # llamada al LLM con el catalogo de herramientas.
        log_decision(user_message, conf, [], [], "sin_herramientas_plausibles")
        return AgentResult(text="", confidence=conf)

    multi = es_multi_accion(user_message)

    system = AGENT_SYSTEM_PROMPT
    if history and _ANAFORA.search(user_message):
        # "y en Bogota?", "abreme la segunda": sin esta pista el modelo pierde
        # el referente y llama a la herramienta con argumentos vacios.
        system += "\n\n" + CONTEXT_HINT

    messages: list[dict] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

    usadas: list[str] = []
    resultados: list[str] = []
    reintentos = 0

    for _paso in range(max_steps + MAX_REINTENTOS):
        msg = client.chat_with_tools(messages, tools)
        calls = msg.get("tool_calls") or []

        # --- El modelo no llamo a ninguna herramienta ---
        if not calls:
            texto = _clean_text(msg.get("content", ""))
            if usadas:
                # Ya hicimos el trabajo: la salida de las herramientas ES la
                # respuesta. El texto del modelo solo la diluiria.
                log_decision(user_message, conf, usadas, resultados, "ok")
                return AgentResult(text="\n".join(resultados), tools_used=usadas,
                                   confidence=conf)

            # Sin herramientas y sin texto util: no sabemos que quiere.
            if not texto:
                log_decision(user_message, conf, [], [], "sin_respuesta")
                return AgentResult(text="", confidence=conf)

            # Texto sin herramientas: puede ser una negativa honesta, una
            # pregunta de aclaracion o conversacion. Todas son validas.
            aclara = texto.rstrip().endswith("?")
            log_decision(user_message, conf, [], [texto],
                         "aclaracion" if aclara else "respuesta_en_texto")
            return AgentResult(text=texto, needs_clarification=aclara,
                               confidence=conf)

        messages.append({"role": "assistant", "content": msg.get("content", ""),
                         "tool_calls": calls})

        detener = False
        for call in calls:
            name = call.get("function", {}).get("name", "")
            args = _arguments(call)

            # --- Validacion estricta + reintento ---
            valida, correccion = _validar(name, args)
            if not valida:
                reintentos += 1
                if reintentos > MAX_REINTENTOS:
                    log_decision(user_message, conf, usadas, resultados,
                                 f"invalida_tras_reintentos:{name}")
                    return AgentResult(
                        text=("No consegui entender que necesita exactamente, "
                              "senor. Puede reformularlo?"),
                        needs_clarification=True, confidence=conf)
                messages.append({"role": "tool", "name": name,
                                 "content": correccion})
                detener = True  # volver a preguntarle al modelo
                break

            args = _limpiar_args(name, args)
            texto, pendiente = execute(name, args)
            usadas.append(name)
            resultados.append(texto)

            if pendiente:  # accion de riesgo: espera /confirmar
                log_decision(user_message, conf, usadas, resultados,
                             "pendiente_confirmacion")
                return AgentResult(text=texto, tools_used=usadas,
                                   pending_confirmation=True, confidence=conf)

            messages.append({"role": "tool", "name": name, "content": texto})

        if detener:
            continue

        # Peticion de una sola accion: ya esta hecha. Volver a llamar al modelo
        # solo para que "redacte" cuesta otros ~15 s en CPU y no aporta: la
        # salida de la herramienta ya viene redactada. Solo se sigue iterando
        # cuando el usuario pidio varias acciones encadenadas.
        if not multi or len(usadas) >= max_steps:
            break

    log_decision(user_message, conf, usadas, resultados,
                 "ok" if usadas else "limite_de_pasos")
    return AgentResult(text="\n".join(resultados), tools_used=usadas,
                       confidence=conf)
