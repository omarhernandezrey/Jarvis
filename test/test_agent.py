"""
Tests del agente con tool calling (Fase 6).
El cliente de Ollama se simula: los tests no dependen del modelo ni de la red,
solo verifican el contrato del bucle, el registro y la preseleccion.
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.agent.loop import _arguments, _clean_text, run_agent
from jarvis_local.agent.registry import (
    TOOLS,
    all_schemas,
    execute,
    get_tool,
    tool_names,
)
from jarvis_local.agent.selector import score_tools, select_tools, selected_names

# ---------- Registro ----------

def test_registro_no_vacio():
    assert len(TOOLS) >= 25
    assert len(tool_names()) == len(set(tool_names()))  # sin duplicados


def test_esquemas_validos():
    """Cada esquema debe cumplir el formato de tool calling de Ollama/OpenAI."""
    for s in all_schemas():
        assert s["type"] == "function"
        f = s["function"]
        assert f["name"] and isinstance(f["description"], str)
        assert len(f["description"]) > 20  # una descripcion util, no un nombre
        p = f["parameters"]
        assert p["type"] == "object"
        assert isinstance(p["properties"], dict)
        for req in p.get("required", []):
            assert req in p["properties"], f"{f['name']}: required '{req}' no existe"


def test_herramientas_criticas_presentes():
    for name in ("abrir_aplicacion", "clima", "buscar_empleo", "enviar_correo",
                 "estado_del_sistema", "wikipedia", "calcular"):
        assert get_tool(name) is not None


def test_acciones_peligrosas_requieren_confirmacion():
    for name in ("borrar_archivo", "enviar_correo", "ocultar_archivos"):
        assert get_tool(name).needs_confirmation is True


def test_execute_herramienta_inexistente():
    texto, pendiente = execute("herramienta_fantasma", {})
    assert "No existe" in texto
    assert pendiente is False


def test_execute_filtra_argumentos_inventados():
    """El LLM a veces alucina argumentos: se descartan sin romper."""
    with patch("jarvis_local.tools.jokes.tell_joke") as m:
        from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
        plan = ActionPlan(action="chiste", risk=RiskLevel.READ)
        plan.result = "Un chiste."
        plan.status = ActionStatus.EXECUTED
        m.return_value = plan
        texto, _ = execute("contar_chiste", {"parametro_inventado": "x"})
        assert texto == "Un chiste."


def test_execute_pide_argumento_faltante():
    texto, pendiente = execute("clima", {})  # city es opcional -> no falla
    assert isinstance(texto, str)
    texto2, _ = execute("wikipedia", {})     # topic es obligatorio
    assert "falta" in texto2.lower()


# ---------- Preseleccion de herramientas ----------

def test_selector_acota_el_catalogo():
    """Nunca se mandan las 30 herramientas al modelo: satura un 3B en CPU."""
    for frase in ["que clima hace en Cali", "abre whatsapp", "busca trabajo de contador"]:
        assert 0 < len(select_tools(frase)) <= 6


def test_selector_elige_la_correcta():
    assert "clima" in selected_names("va a llover en Cartagena?")
    assert "estado_del_sistema" in selected_names("como anda la ram de mi maquina")
    assert "buscar_empleo" in selected_names("consigueme vacantes de programador")
    assert "contar_chiste" in selected_names("ando aburrido, dime algo divertido")
    assert "abrir_aplicacion" in selected_names("abreme whatsapp")
    assert "wikipedia" in selected_names("quien fue Simon Bolivar")


def test_selector_sin_candidatas_en_charla():
    """Si nada encaja, el agente ni se invoca: la frase va al chat normal."""
    assert select_tools("hola, como te sientes hoy") == []
    assert select_tools("gracias por todo") == []


def test_score_prioriza_pistas_especificas():
    scores = dict(score_tools("donde queda Tokio"))
    assert scores.get("ubicar_lugar", 0) >= 3  # "donde queda" es multipalabra


# ---------- Bucle del agente ----------

def _mock_client(*respuestas):
    """Cliente falso que devuelve las respuestas dadas, una por llamada."""
    c = MagicMock()
    c.chat_with_tools = MagicMock(side_effect=list(respuestas))
    return c


def _tool_call(name, args):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def test_agente_ejecuta_la_herramienta_elegida():
    client = _mock_client(_tool_call("contar_chiste", {}))
    r = run_agent(client, "cuentame algo gracioso")
    assert r.tools_used == ["contar_chiste"]
    assert len(r.text) > 10
    assert r.pending_confirmation is False


def test_agente_sin_herramientas_devuelve_vacio():
    """Sin candidatas no se llama al modelo (ahorra ~20s en CPU)."""
    client = _mock_client()
    r = run_agent(client, "hola que tal")
    assert r.text == "" and r.tools_used == []
    client.chat_with_tools.assert_not_called()


def test_agente_respuesta_de_texto_sin_tools():
    client = _mock_client({"role": "assistant", "content": "Como guste, senor."})
    r = run_agent(client, "abre whatsapp")
    assert r.tools_used == []
    assert r.text == "Como guste, senor."


def test_agente_accion_peligrosa_espera_confirmacion():
    client = _mock_client(_tool_call(
        "enviar_correo", {"to": "x@y.com", "subject": "A", "body": "B"}))
    r = run_agent(client, "envia un correo a x@y.com asunto A mensaje B")
    assert r.pending_confirmation is True
    assert "confirmar" in r.text.lower()


def test_agente_ignora_herramienta_inexistente():
    client = _mock_client(
        _tool_call("herramienta_alucinada", {}),
        {"role": "assistant", "content": "No pude hacerlo, senor."},
    )
    r = run_agent(client, "abre whatsapp")
    assert "herramienta_alucinada" not in r.tools_used


def test_agente_tolera_argumentos_en_string_json():
    """Algunos modelos mandan los argumentos como string en vez de dict."""
    client = _mock_client(_tool_call("calcular", '{"expression": "2 + 2"}'))
    r = run_agent(client, "calcula 2 + 2")
    assert r.tools_used == ["calcular"]
    assert "4" in r.text


def test_agente_no_muere_si_la_herramienta_falla():
    client = _mock_client(_tool_call("clima", {"city": "Ciudad Inexistente XYZ"}))
    r = run_agent(client, "clima en Ciudad Inexistente XYZ")
    assert r.tools_used == ["clima"]  # respondio algo, no lanzo excepcion
    assert isinstance(r.text, str) and r.text


# ---------- Saneado de la respuesta ----------

def test_clean_text_descarta_json_filtrado():
    """El modelo a veces escribe el tool call como texto: no se muestra."""
    assert _clean_text('{"name": "clima", "arguments": {"city": "Cali"}}') == ""
    assert _clean_text('>{"name": "buscar_en_google", "arguments": {}}') == ""
    assert _clean_text("Como guste, senor.") == "Como guste, senor."
    assert _clean_text("") == ""


def test_arguments_parsea_dict_y_string():
    assert _arguments({"function": {"arguments": {"a": 1}}}) == {"a": 1}
    assert _arguments({"function": {"arguments": '{"a": 1}'}}) == {"a": 1}
    assert _arguments({"function": {"arguments": "no es json"}}) == {}
    assert _arguments({}) == {}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("OK: Todos los tests del agente pasaron.")
