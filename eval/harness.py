"""
Arnes de evaluacion del router de intencion.

Reproduce la cascada real de decision de JARVIS pero SIN ejecutar las acciones
(no abre apps ni navegadores): sustituye el ejecutor de herramientas por un
doble que solo registra que herramienta se habria llamado y con que argumentos.
Asi se mide la CALIDAD DEL RAZONAMIENTO aislada de la ejecucion.
"""
import time
from dataclasses import dataclass, field
from unittest.mock import patch


@dataclass
class Trace:
    entrada: str
    capa: str = ""                       # instantanea | parser | agente | chat
    tools: list[str] = field(default_factory=list)
    args: list[dict] = field(default_factory=list)
    respuesta: str = ""
    pidio_aclaracion: bool = False
    segundos: float = 0.0


# Frases con las que JARVIS pide aclaracion en vez de adivinar
_MARCAS_ACLARACION = (
    "que aplicacion", "puede ser mas especifico", "a que se refiere",
    "no entendi", "podria precisar", "que desea", "cual de", "especifique",
    "no estoy seguro", "necesito saber", "me falta",
)


def _pide_aclaracion(texto: str) -> bool:
    t = (texto or "").lower()
    return any(m in t for m in _MARCAS_ACLARACION) or (
        t.endswith("?") and len(t) < 160)


def trace_message(jarvis, mensaje: str,
                  historial: list[tuple[str, str]] | None = None) -> Trace:
    """Corre el mensaje por la cascada real y registra la decision."""
    from jarvis_local.fast_response import fast_respond
    from jarvis_local.intent.parser import dividir_acciones

    tr = Trace(entrada=mensaje)
    t0 = time.time()

    jarvis.history.clear()
    if historial:
        for rol, texto in historial:
            if rol == "user":
                jarvis.history.add_user(texto)
            else:
                jarvis.history.add_assistant(texto)

    # Capa 1: respuestas instantaneas (sin LLM, sin herramientas)
    fast = fast_respond(mensaje)
    if fast is not None:
        tr.capa = "instantanea"
        tr.respuesta = fast
        tr.pidio_aclaracion = _pide_aclaracion(fast)
        tr.segundos = time.time() - t0
        return tr

    # Peticion de varias acciones: cada clausula baja por la cascada completa,
    # igual que hace Jarvis._chat_encadenado().
    clausulas = dividir_acciones(mensaje)
    if len(clausulas) > 1:
        for clausula in clausulas:
            sub = _trace_una(jarvis, clausula, historial)
            tr.tools.extend(sub.tools)
            tr.args.extend(sub.args)
        tr.capa = "encadenado"
        tr.respuesta = f"[{len(tr.tools)} acciones]"
        tr.segundos = time.time() - t0
        return tr

    sub = _trace_una(jarvis, mensaje, historial)
    sub.entrada = mensaje
    sub.segundos = time.time() - t0
    return sub


def _trace_una(jarvis, mensaje: str,
               historial: list[tuple[str, str]] | None = None) -> Trace:
    """Cascada para UNA sola accion: parser -> agente -> chat."""
    from jarvis_local.agent import loop as agent_loop
    from jarvis_local.intent.parser import parse_intent

    tr = Trace(entrada=mensaje)
    t0 = time.time()

    # Capa 2: parser deterministico
    intent = parse_intent(mensaje)
    if intent.kind in ("tool_read", "tool_execute", "tool_plan"):
        tr.capa = "parser"
        tr.tools = [_a_nombre_de_herramienta(intent.tool)]
        tr.args = [intent.arguments or {}]
        tr.respuesta = f"[parser -> {intent.tool}]"
        tr.segundos = time.time() - t0
        return tr
    if intent.kind in ("ambiguous", "unsupported"):
        tr.capa = "parser"
        tr.respuesta = intent.clarification or intent.reason or ""
        tr.pidio_aclaracion = _pide_aclaracion(tr.respuesta)
        tr.segundos = time.time() - t0
        return tr

    # Capa 3: agente (tool calling). Se intercepta el ejecutor: queremos saber
    # QUE decidio, no abrir aplicaciones de verdad.
    llamadas: list[tuple[str, dict]] = []

    def _execute_falso(name, arguments):
        llamadas.append((name, arguments or {}))
        return f"[simulado: {name} ejecutada correctamente]", False

    with patch.object(agent_loop, "execute", side_effect=_execute_falso):
        historia = jarvis.history.get_messages() if historial else None
        res = agent_loop.run_agent(jarvis.client, mensaje, history=historia)

    if llamadas:
        tr.capa = "agente"
        tr.tools = [n for n, _ in llamadas]
        tr.args = [a for _, a in llamadas]
        tr.respuesta = res.text
        tr.segundos = time.time() - t0
        return tr

    # Capa 4: conversacion (ninguna herramienta). No llamamos al LLM de chat:
    # para el router, esto ya es "ninguna accion".
    tr.capa = "chat"
    tr.respuesta = res.text or "[iria a conversacion con el LLM]"
    tr.pidio_aclaracion = _pide_aclaracion(tr.respuesta)
    tr.segundos = time.time() - t0
    return tr


# El parser usa nombres antiguos; el registro del agente usa los nuevos.
# Este mapa los unifica para poder comparar ambas capas contra lo esperado.
_ALIAS = {
    "open_app": "abrir_aplicacion",
    "system_status": "estado_del_sistema",
    "weather": "clima",
    "wiki": "wikipedia",
    "news_headlines": "noticias",
    "tell_joke": "contar_chiste",
    "get_ip": "mi_direccion_ip",
    "calculate": "calcular",
    "wolfram": "preguntar_wolframalpha",
    "search_jobs": "buscar_empleo",
    "open_job": "abrir_oferta_empleo",
    "show_jobs": "mostrar_ofertas_empleo",
    "open_website": "abrir_sitio_web",
    "google_search": "buscar_en_google",
    "youtube_play": "reproducir_en_youtube",
    "play_music": "reproducir_musica_local",
    "take_note": "tomar_nota",
    "screenshot": "captura_de_pantalla",
    "switch_window": "cambiar_ventana",
    "send_email": "enviar_correo",
    "hide_files": "ocultar_archivos",
    "list_files": "listar_archivos",
    "search_files": "buscar_archivo",
    "create_file": "crear_archivo",
    "create_directory": "crear_carpeta",
    "delete_file": "borrar_archivo",
    "run_command": "ejecutar_comando",
    "file_info": "listar_archivos",
    "locate": "ubicar_lugar",
    "calendar_events": "proximos_eventos",
    "browser_navigate": "navegar_con_selenium",
    "close_browser": "cerrar_navegador",
    "close_app": "cerrar_aplicacion",
    "close_all_apps": "cerrar_todas_aplicaciones",
    "list_apps": "abrir_aplicacion",
}


def _a_nombre_de_herramienta(tool: str | None) -> str:
    return _ALIAS.get(tool or "", tool or "")
