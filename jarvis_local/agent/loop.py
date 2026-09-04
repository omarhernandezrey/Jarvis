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

7. Timeout de 30s por llamada al LLM: si el modelo se cuelga, el agente
   devuelve un error claro en vez de bloquear Jarvis indefinidamente.
"""
import json
import re
from dataclasses import dataclass, field

from jarvis_local.agent import decision_cache
from jarvis_local.agent.decision_log import log_decision
from jarvis_local.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    CONTEXT_HINT,
    correccion_argumentos,
    correccion_herramienta_invalida,
)
from jarvis_local.agent.registry import execute, get_tool, tool_names
from jarvis_local.agent.retriever import confidence, select_tools

# TAREA C2: cada llamada al modelo cuesta 20-70 s en CPU (medido, C1). Se
# poda el bucle a lo minimo util:
#   - 1 accion simple = 1 llamada (el modelo elige la herramienta y listo).
#   - 1 reintento como maximo si la salida es invalida (antes 2).
#   - las peticiones multi-accion NO pasan por aqui: las divide
#     dividir_acciones() y cada clausula entra por su cuenta, con su propio
#     presupuesto (MAX_STEPS_ENCADENADO).
MAX_STEPS = 2               # pasos (herramientas encadenadas) por clausula
MAX_STEPS_ENCADENADO = 4    # nº maximo de clausulas de una peticion multi-accion
MAX_REINTENTOS = 1          # correcciones al modelo ante salida invalida
AGENT_TIMEOUT = 30          # timeout en segundos para llamadas al LLM

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
# El espanol pega el cliticо al verbo ("hazlo", "buscalo", "mandalo", "ponlo"):
# esas formas tambien son ordenes sin objeto y hay que pedir aclaracion.
_MULETILLA = r'(?:\s+(?:ya|pues|porfa|porfis|parce|hermano|man|vale|si|de\s+una))*'
_VAGO = re.compile(
    r'^\s*(?:'
    r'hazlo|hazlo\s+ya|haz\s+eso|hazme\s+eso|hacelo|dale|dele|listo|eso|ahi|'
    r'(?:abre|abreme|cierra|cierralo|busca|buscalo|buscame|pon|ponlo|ponme|'
    r'dame|damelo|muestra|muestralo|muestrame|ejecuta|ejecutalo|corre|borra|'
    r'borralo|elimina|eliminalo|toma|tomalo|manda|mandalo|mandelo|envia|envialo|'
    r'reproduce|reproducelo|lanza|lanzalo|inicia|trae|traelo|dilo|dimelo|hazme)'
    r'(?:\s+(?:eso|esto|aquello|ese|esa|ahi|alli|el|la|lo|los|las|algo|'
    r'una?\s+cosa))?'
    r')' + _MULETILLA + r'\s*[.!?]*\s*$',
    re.IGNORECASE)

# "necesito ayuda con algo", "quiero hacer una cosa": peticion sin contenido.
_SIN_OBJETO = re.compile(
    r'\b(?:ayuda|ayudame|hacer|haga|necesito)\b.*\b(?:algo|una\s+cosa|eso)\b|'
    r'\b(?:algo|una\s+cosa)\b\s*[.!?]*\s*$', re.IGNORECASE)


def _consulta_de_recuperacion(message: str, history: list[dict] | None) -> str:
    """Texto con el que se BUSCAN las herramientas (no el que ve el LLM).

    Una frase anaforica no tiene contenido propio: "y en Bogota?" no se parece
    a la descripcion de ninguna herramienta, asi que el retriever no devolvia
    nada y la peticion se perdia. Se le pega el ultimo mensaje del usuario, que
    es donde esta el tema ("clima en Cali"), y asi la recuperacion funciona.
    """
    from jarvis_local.intent.parser import es_anaforica

    if not history or not es_anaforica(message):
        return message
    ultimo = next((m["content"] for m in reversed(history)
                   if m.get("role") == "user" and m.get("content")), "")
    return f"{ultimo} {message}".strip() if ultimo else message


def _es_orden_vaga(message: str) -> bool:
    """Es una ORDEN pero sin objeto: hay que preguntar, no adivinar ni callar.

    Distingue "hazlo" / "abre eso" / "mándalo pues" (ordenes incompletas ->
    aclarar) de "de que color es el cielo" (conversacion -> responder). Ambas
    dan confianza semantica baja, pero exigen respuestas opuestas: ante una
    orden incompleta, quedarse callado o divagar es el peor resultado posible.
    """
    from jarvis_local.intent.parser import _sin_tildes
    m = _sin_tildes(message.strip())  # "mándalo" -> "mandalo": el patron es ASCII
    if not m or len(m.split()) > 6:
        return False
    return bool(_VAGO.match(m) or _SIN_OBJETO.search(m))


# ─────────────────────────────────────────────────────────────────────────────
# PLAN_EJECUCION FASE C · C2 — puerta de conversación (causa raíz 1 del banco)
#
# Medido (BANCO_PRUEBAS_BASELINE §12): la confianza del retriever para charla
# ("vos sí sos bacano", "cuál es tu color favorito") va de 0,40 a 0,54; para
# una petición legítima de herramienta ("necesito sombrilla en Cali",
# "vacantes de electricista"), de 0,46 a 0,66. Los rangos SE SOLAPAN de 0,46 a
# 0,54: ningún umbral de un solo escalar los separa (subir el umbral mata
# peticiones reales; bajarlo deja pasar charla). No es un problema de
# calibración, es un problema de forma de la señal.
#
# En vez de un umbral de similitud, se reconoce la FORMA de la charla dirigida
# a JARVIS (pregunta sobre sí mismo, piropo, hipotético, pedir una sugerencia
# u opinión sin tema factual) — no el tema. Determinista, 0 ms: se decide
# ANTES de tocar el retriever, así una charla nunca paga ni el embedding de
# selección de herramientas ni, mucho menos, una llamada al LLM.
_CHARLA_DIRIGIDA_A_JARVIS = re.compile(
    r'\b(?:sos|eres)\s+(?:bacano|bacana|genial|el\s+mejor|la\s+mejor|un\s+crack|'
    r'una\s+verraquera|verraco|verraca)\b'                                  # piropo
    r'|\bcual\s+es\s+tu\b[^.?!]{0,25}\bfavorit[oa]s?\b'                     # "tu X favorito/a"
    r'|\bcomo\s+te\s+(?:sientes|sentis|va|encuentras|estas)\b'              # "cómo te sientes/sentís"
    r'|\bque\s+tal\s+(?:estas|te\s+va|andas)\b'
    r'|\bsi\s+fueras\s+(?:humano|persona|de\s+carne\s+y\s+hueso)\b'         # hipotético
    r'|\b(?:cuentame|dime|dame)\s+(?:un\s+|una\s+)?(?:dato|cosa)\s+'
    r'(?:curios[oa]|interesante|random|rar[oa])\b'                          # "dato curioso" (no "chiste": ese sí es tool)
    r'|\bque\s+se\s+te\s+ocurre\b|\bque\s+me\s+recomiendas\s+para\b'        # pedir sugerencia
    r'|\b(?:opin\w+|piens\w+|cre[eé]s?)\b.{0,30}\b(?:de\s+el|del|sobre)\s+'
    r'(?:este\s+|el\s+|ese\s+)?(?:clima|tiempo|calor|frio)\b',              # opinión sobre el clima
    re.IGNORECASE)


def _es_conversacion_directa(message: str) -> bool:
    """Charla dirigida a JARVIS (piropo, pregunta sobre sí mismo, hipotético,
    pedir sugerencia/dato sin tema factual) que no necesita ni el catálogo ni
    el retriever: va derecho a generación de chat."""
    from jarvis_local.intent.parser import _sin_tildes
    m = _sin_tildes(message.strip())
    if not m or len(m.split()) > 20:
        return False
    return bool(_CHARLA_DIRIGIDA_A_JARVIS.search(m))


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


# Un modelo debil a veces "llama" a la herramienta escribiendo el JSON en el
# texto en vez de usar el canal nativo de tool_calls de Ollama. Formatos vistos:
#   <tool_call>{"name": "clima", "arguments": {"city": "Cali"}}</tool_call>
#   {"name": "clima", "arguments": {"city": "Cali"}}
#   {"function": {"name": "clima", "arguments": {...}}}
# Se rescata SOLO si el nombre extraido es una herramienta realmente ofrecida.


def _objetos_json(texto: str) -> list[str]:
    """Subcadenas `{...}` con llaves balanceadas (ignora llaves dentro de
    strings). Las expresiones regulares no cuentan anidamiento; esto si."""
    objetos: list[str] = []
    profundidad = 0
    inicio = -1
    en_string = False
    escape = False
    for i, ch in enumerate(texto):
        if en_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                en_string = False
            continue
        if ch == '"':
            en_string = True
        elif ch == "{":
            if profundidad == 0:
                inicio = i
            profundidad += 1
        elif ch == "}" and profundidad > 0:
            profundidad -= 1
            if profundidad == 0 and inicio >= 0:
                objetos.append(texto[inicio:i + 1])
    return objetos


def _salvage_tool_calls(content: str, ofrecidas: list[dict]) -> list[dict]:
    """Extrae una llamada a herramienta escrita como texto. [] si no hay una
    valida. Devuelve el mismo formato que Ollama: [{"function": {name, arguments}}]."""
    if not content or "{" not in content:
        return []
    nombres = {t.get("function", {}).get("name") for t in ofrecidas}

    for blob in _objetos_json(content):
        try:
            data = json.loads(blob)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        fn = data.get("function") if isinstance(data.get("function"), dict) else data
        name = fn.get("name") if isinstance(fn, dict) else None
        if name not in nombres:
            continue
        args = fn.get("arguments", fn.get("parameters", {}))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                args = {}
        return [{"function": {"name": name,
                              "arguments": args if isinstance(args, dict) else {}}}]
    return []


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
    """Decide y ejecuta. Texto vacio y sin herramientas = que responda el chat.

    Si la peticion pide varias acciones, se resuelve clausula por clausula: el
    modelo de 3B no encadena por su cuenta (medido: 0/2), asi que confiar en que
    pida la segunda herramienta tras la primera perderia la mitad de la orden.
    """
    from jarvis_local.intent.parser import dividir_acciones

    clausulas = dividir_acciones(user_message)
    if len(clausulas) > 1:
        return _run_encadenado(client, clausulas, history)
    return _run_simple(client, user_message, history, max_steps)


def _run_encadenado(client, clausulas: list[str],
                    history: list[dict] | None) -> AgentResult:
    """Ejecuta cada accion de la peticion, en orden."""
    from jarvis_local.intent.parser import es_anaforica

    usadas: list[str] = []
    textos: list[str] = []
    ctx = list(history or [])

    for clausula in clausulas[:MAX_STEPS_ENCADENADO]:
        # El contexto acumulado solo se le pasa a la clausula si lo NECESITA
        # ("abre la primera oferta" -> hay que saber de que lista). Una clausula
        # autonoma ("abre Chrome") no lo necesita, y darselo empeora las cosas:
        # el modelo pequeno se distrae con el resultado anterior (el parte del
        # clima) y deja de llamar a la herramienta.
        necesita_ctx = es_anaforica(clausula)
        r = _run_simple(client, clausula, ctx if necesita_ctx else None, MAX_STEPS)

        if r.pending_confirmation:
            # Una accion de riesgo corta la cadena: el usuario debe decidir
            # antes de que sigamos actuando en su nombre.
            return AgentResult(text="\n".join([*textos, r.text]),
                               tools_used=usadas + r.tools_used,
                               pending_confirmation=True, confidence=r.confidence)

        usadas.extend(r.tools_used)
        if r.text:
            textos.append(r.text)
            ctx = [*ctx, {"role": "user", "content": clausula},
                   {"role": "assistant", "content": r.text}]

    return AgentResult(text="\n".join(textos), tools_used=usadas,
                       confidence=confidence(clausulas[0]))


def _run_simple(client, user_message: str, history: list[dict] | None,
                max_steps: int) -> AgentResult:
    # Para RECUPERAR herramientas, una frase anaforica no se sostiene sola:
    # "y en Bogota?" no se parece a ninguna herramienta, asi que el retriever
    # devolvia lista vacia y la peticion moria en conversacion. Se recupera con
    # el turno anterior pegado ("clima en Cali" + "y en Bogota?"), que si tiene
    # el contenido semantico. El LLM sigue recibiendo el mensaje original.
    consulta = _consulta_de_recuperacion(user_message, history)

    # PLAN_EJECUCION FASE C · C2 — puerta de conversación: se decide ANTES de
    # tocar el retriever (ni siquiera se calcula su `confidence`, que también
    # es un embedding). Charla dirigida a JARVIS -> generación de chat directa.
    if _es_conversacion_directa(user_message):
        log_decision(user_message, 0.0, [], [], "conversacion_directa")
        return AgentResult(text="", confidence=0.0)

    conf = confidence(consulta)

    # Orden sin objeto ("hazlo", "buscalo", "mandalo pues"): preguntar, nunca
    # adivinar ni fabricar. Antes solo se cortaba SIN historial; el banco de
    # pruebas encontro que basta un turno previo ("hola") para saltarse el
    # guardia y que el chat invente ("hazlo" -> "la respuesta es 45").
    # Una orden puramente deictica no gana nada con el historial: no hay
    # antecedente accion+objeto. Solo se deja pasar cuando HAY historial Y la
    # frase es anaforica ("abreme la segunda", "abre eso" tras "muestrame las
    # fotos"): ahi el contexto si puede resolverla. Sin historial, cualquier
    # orden vaga -> aclarar.
    from jarvis_local.intent.parser import es_anaforica
    if _es_orden_vaga(user_message) and not (history and es_anaforica(user_message)):
        texto = ("Que desea que haga exactamente, senor? Necesito que me "
                 "precise la accion o el objeto.")
        log_decision(user_message, conf, [], [texto], "aclaracion_orden_vaga")
        return AgentResult(text=texto, needs_clarification=True, confidence=conf)

    tools = select_tools(consulta)
    if not tools:
        # Nada plausible ni semanticamente: es conversacion. No se gasta una
        # llamada al LLM con el catalogo de herramientas.
        log_decision(user_message, conf, [], [], "sin_herramientas_plausibles")
        return AgentResult(text="", confidence=conf)

    # --- CACHE DE DECISIONES (C6) ---
    # Frase repetida en poco tiempo -> reusar la herramienta elegida la ultima
    # vez y saltarse los 20-70 s de tool-calling. La EJECUCION siempre se
    # rehace (datos frescos). No aplica a frases anaforicas (el referente
    # cambia) ni a ordenes vagas.
    _anafora = bool(history and _ANAFORA.search(user_message))
    if not _anafora:
        cacheado = decision_cache.get(user_message)
        if cacheado is not None:
            c_tool, c_args = cacheado
            nombres = {t.get("function", {}).get("name") for t in tools}
            if c_tool in nombres:
                texto, pendiente = execute(c_tool, c_args)
                log_decision(user_message, conf, [c_tool], [texto],
                             "cache_hit", llm_calls=0, llm_secs=0.0)
                return AgentResult(
                    text=texto, tools_used=[c_tool],
                    pending_confirmation=pendiente, confidence=conf)

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

    # Instrumentacion (C1): nº de llamadas al LLM y tiempo total en ellas.
    # Un turno de 1 accion deberia hacer 1 sola llamada; mas de 2-3 indica un
    # bucle de reintentos o multi-paso que no termina.
    import time as _time
    _llm_calls = 0
    _llm_secs = 0.0

    for _paso in range(max_steps + MAX_REINTENTOS):
        try:
            _t0 = _time.perf_counter()
            msg = client.chat_with_tools(messages, tools)
            _llm_calls += 1
            _llm_secs += _time.perf_counter() - _t0
        except Exception as e:
            # Timeout o error de conexión: devolver error claro
            error_msg = str(e).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                log_decision(user_message, conf, usadas, resultados, "timeout_llm", llm_calls=_llm_calls, llm_secs=_llm_secs)
                return AgentResult(
                    text="El modelo tardo demasiado en responder, senor. Intente de nuevo.",
                    confidence=conf)
            log_decision(user_message, conf, usadas, resultados, f"error_llm:{e}", llm_calls=_llm_calls, llm_secs=_llm_secs)
            return AgentResult(
                text="Tuve un inconveniente al comunicarme con el modelo, senor.",
                confidence=conf)
        calls = msg.get("tool_calls") or []
        contenido = msg.get("content", "")

        # El modelo escribio el tool call como texto en vez de usar el canal
        # nativo: rescatarlo si es una herramienta valida (modelos debiles lo
        # hacen; sin esto se perderia la accion y caeria a conversacion).
        if not calls:
            rescatadas = _salvage_tool_calls(contenido, tools)
            if rescatadas:
                calls = rescatadas
                contenido = ""   # el JSON crudo no debe quedar en el historial
                log_decision(user_message, conf, usadas, resultados,
                             "tool_call_rescatado", llm_calls=_llm_calls,
                             llm_secs=_llm_secs)

        # --- El modelo no llamo a ninguna herramienta ---
        if not calls:
            texto = _clean_text(contenido)
            if usadas:
                # Ya hicimos el trabajo: la salida de las herramientas ES la
                # respuesta. El texto del modelo solo la diluiria.
                log_decision(user_message, conf, usadas, resultados, "ok", llm_calls=_llm_calls, llm_secs=_llm_secs)
                return AgentResult(text="\n".join(resultados), tools_used=usadas,
                                   confidence=conf)

            # Sin herramientas y sin texto util: no sabemos que quiere.
            if not texto:
                log_decision(user_message, conf, [], [], "sin_respuesta", llm_calls=_llm_calls, llm_secs=_llm_secs)
                return AgentResult(text="", confidence=conf)

            # Texto sin herramientas: puede ser una negativa honesta, una
            # pregunta de aclaracion o conversacion. Todas son validas.
            aclara = texto.rstrip().endswith("?")
            log_decision(user_message, conf, [], [texto],
                         "aclaracion" if aclara else "respuesta_en_texto")
            return AgentResult(text=texto, needs_clarification=aclara,
                               confidence=conf)

        messages.append({"role": "assistant", "content": contenido,
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

            # C6: recordar la ELECCION (no el resultado) para la proxima vez
            # que se pida esto mismo. Las anaforicas no se cachean.
            if not _anafora:
                decision_cache.put(user_message, name, args)

            messages.append({"role": "tool", "name": name, "content": texto})

        if detener:
            continue

        # Ya se ejecuto la herramienta: la peticion esta resuelta. Volver a
        # llamar al modelo solo para que "redacte" cuesta otros ~15 s en CPU y
        # no aporta, porque la salida de la herramienta ya viene redactada.
        # Las peticiones de varias acciones no llegan aqui: las divide
        # dividir_acciones() y cada clausula entra por su cuenta.
        break

    log_decision(user_message, conf, usadas, resultados,
                 "ok" if usadas else "limite_de_pasos",
                 llm_calls=_llm_calls, llm_secs=_llm_secs)
    return AgentResult(text="\n".join(resultados), tools_used=usadas,
                       confidence=conf)
