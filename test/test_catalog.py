"""FASE B — catálogo único de herramientas + contrato de herramienta.

Blinda:
  1. Todos los contratos están completos (validate_contract vacío).
  2. Un contrato a medias se detecta (no pasa en silencio).
  3. Dar de alta una herramienta toca UN SOLO archivo: un ToolContract nuevo
     aparece en las tres vistas derivadas sin tocar nada más.
  4/5. Paridad con los catálogos que había antes de FASE B (fixture congelado):
     cada clave de _READ/_WRITE/_PLAN_TOOLS sigue resolviendo y el registro del
     agente (nombres, orden, esquemas, needs_confirmation) es idéntico.
  6. El informe de "herramientas sólo alcanzables por el camino lento" es exacto.
  7. needs_confirmation coherente con el nivel de riesgo.
"""
import json
from pathlib import Path

import pytest

from jarvis_local.safety.policy import RiskLevel
from jarvis_local.tools import catalog

_BASELINE = json.loads(
    (Path(__file__).parent / "fixtures" / "catalogo_baseline_pre_faseB.json").read_text(encoding="utf-8")
)


# ---------- 1. completitud ----------

def test_todos_los_contratos_son_validos():
    problemas: list[str] = []
    for c in catalog.CONTRACTS:
        problemas += catalog.validate_contract(c, others=catalog.CONTRACTS)
    assert not problemas, "contratos incompletos:\n- " + "\n- ".join(problemas)


def test_nombres_unicos():
    """Ningún nombre (canónico, alias o intent) apunta a dos contratos distintos."""
    vistos: dict[str, str] = {}
    for c in catalog.CONTRACTS:
        for n in set(c.all_names()):
            assert n not in vistos, f"nombre '{n}' en dos contratos ({c.name} y {vistos[n]})"
            vistos[n] = c.name


# ---------- 2. un contrato a medias NO pasa ----------

def _base_kwargs(**over):
    kw = dict(
        name="prueba_tmp",
        description="Una herramienta de prueba con descripción suficientemente larga.",
        parameters=catalog._obj({"x": catalog._str("un valor")}),
        run=lambda x="": "ok",
        risk=RiskLevel.EXECUTE,
        verify="se comprueba mirando algo",
        revert="se revierte haciendo lo contrario",
    )
    kw.update(over)
    return kw


@pytest.mark.parametrize("over, aguja", [
    ({"name": "Mal Nombre"}, "name inválido"),
    ({"description": "corta"}, "demasiado corta"),
    ({"verify": "  "}, "falta 'verify'"),
    ({"revert": ""}, "falta 'revert'"),
    ({"risk": RiskLevel.DELETE, "needs_confirmation": False}, "exige needs_confirmation"),
    ({"parameters": {"type": "object", "properties": {}, "required": ["y"]}}, "required 'y'"),
    ({"parser_argmap": {"a": "noexiste"}}, "parser_argmap"),
    ({"parser_fixed": {"noexiste": 1}}, "parser_fixed"),
    ({"parameters": {"type": "object", "properties": {"z": catalog._str("z")}}},
     "no es parámetro de run"),
])
def test_contrato_a_medias_se_detecta(over, aguja):
    # DELETE fuerza needs_confirmation en __post_init__; para ese caso lo probamos
    # saltándonos el post_init con object.__setattr__ imposible -> validamos el
    # resto vía parámetros que no lo tocan.
    if over.get("risk") == RiskLevel.DELETE:
        c = catalog.ToolContract(**_base_kwargs(**over))
        object.__setattr__(c, "needs_confirmation", False)
    else:
        c = catalog.ToolContract(**_base_kwargs(**over))
    problemas = catalog.validate_contract(c)
    assert any(aguja in p for p in problemas), f"esperaba '{aguja}' en {problemas}"


# ---------- 3. alta = un solo archivo ----------

def test_alta_de_herramienta_toca_un_solo_archivo():
    """Un ToolContract nuevo se propaga a todas las vistas derivadas sin tocar
    más código (las funciones aceptan la lista de contratos; en producción es
    CONTRACTS, aquí una copia extendida = 'añadir una fila a catalog.py')."""
    nueva = catalog.ToolContract(
        "eco_de_prueba",
        "Herramienta de prueba visible para el LLM: devuelve un eco. Descripción larga.",
        catalog._obj({"q": catalog._str("consulta")}),
        lambda q="": f"eco:{q}",
        RiskLevel.EXECUTE,
        verify="se comprueba mirando el eco devuelto", revert="n/a",
        parser_intents=("echo_test",),
    )
    ext = [*catalog.CONTRACTS, nueva]
    # by_name resuelve por canónico y por intent del parser
    assert catalog.by_name("eco_de_prueba", ext) is nueva
    assert catalog.by_name("echo_test", ext) is nueva
    # ruta parser: entra en write_tools con las dos claves
    wt = catalog.write_tools(ext)
    assert "eco_de_prueba" in wt and "echo_test" in wt
    assert wt["echo_test"]({"q": "hola"}) == "eco:hola"
    # ruta agente: entra en agent_contracts y su schema es correcto
    ac = catalog.agent_contracts(ext)
    assert "eco_de_prueba" in [c.name for c in ac]
    from jarvis_local.agent import registry
    t = registry._from_contract(nueva)
    assert t.schema()["function"]["name"] == "eco_de_prueba"


def test_alta_parser_only_no_entra_al_agente():
    nueva = catalog.ToolContract(
        "solo_parser_prueba",
        "Entrada fina que sólo resuelve el parser.",
        catalog._obj({}, []),
        lambda: "ok",
        RiskLevel.EXECUTE,
        llm_visible=False,
        verify="se comprueba con algo", revert="n/a",
        parser_intents=("fine_test",),
    )
    ext = [*catalog.CONTRACTS, nueva]
    assert "solo_parser_prueba" in catalog.write_tools(ext)
    assert "solo_parser_prueba" not in [c.name for c in catalog.agent_contracts(ext)]
    assert "solo_parser_prueba" in catalog.parser_only(ext)


# ---------- 4/5. paridad con el estado anterior a FASE B ----------

def test_paridad_dicts_ruta_parser():
    for label, old, new in [
        ("_READ_TOOLS", _BASELINE["read"], catalog.read_tools()),
        ("_WRITE_TOOLS", _BASELINE["write"], catalog.write_tools()),
        ("_PLAN_TOOLS", _BASELINE["plan"], catalog.plan_tools()),
    ]:
        faltan = [k for k in old if k not in new]
        assert not faltan, f"{label}: claves que ya no resuelven: {faltan}"


def test_paridad_registro_del_agente():
    from jarvis_local.agent import registry
    nombres = [t.name for t in registry.TOOLS]
    assert nombres == _BASELINE["registry_names"], "cambió el conjunto/orden de tools del agente"
    for t in registry.TOOLS:
        assert t.schema() == _BASELINE["registry_schemas"][t.name], f"esquema distinto: {t.name}"
        assert t.needs_confirmation == _BASELINE["registry_conf"][t.name], \
            f"needs_confirmation distinto: {t.name}"


def test_jarvis_usa_el_catalogo():
    import jarvis_local.jarvis as J
    assert J._READ_TOOLS is not None and len(J._READ_TOOLS) >= 15
    assert "weather" in J._READ_TOOLS and "calculate" in J._READ_TOOLS
    assert "open_app" in J._WRITE_TOOLS and "run_command" in J._WRITE_TOOLS
    assert "send_email" in J._PLAN_TOOLS and "hide_files" in J._PLAN_TOOLS


# ---------- 6. informe camino lento ----------

def test_informe_camino_lento_exacto():
    """Herramientas que el LLM ve pero que NINGUNA regla del parser alcanza.

    FASE C · C6 sacó "recordar" de esta lista: antes era la única de las 5
    sin NINGÚN intent de parser (las otras 4 ya llegaban por sus intents
    finos — volume_up, media_play_pause, lock_pc, minimize_all...). Esas 4
    se quedan aquí a propósito: el contrato GENÉRICO que ve el LLM
    (controlar_volumen, controlar_musica, energia_del_equipo,
    organizar_ventanas) no tiene un intent propio, pero su CAPACIDAD sí es
    alcanzable por el parser a través del hermano fino — ver
    docs/PLAN_EJECUCION.md § FASE C · C6."""
    assert catalog.slow_path_only() == [
        "controlar_musica", "controlar_volumen", "energia_del_equipo",
        "organizar_ventanas",
    ]


def test_recordar_ya_no_es_solo_agente():
    assert "recordar" not in catalog.slow_path_only()
    assert catalog.by_name("recordar").parser_intents == ("recordar",)


def test_informe_parser_only_no_vacio():
    # lo inverso: entradas finas que sólo resuelve el parser (volumen/energía
    # sueltos, copiar/mover/renombrar archivo, contactos...). Si esto se vacía,
    # es que se rompió la granularidad fina de la ruta rápida.
    po = catalog.parser_only()
    assert "volume_up" in po and "copiar_archivo" in po and "lock_pc" in po


# ---------- 7. riesgo <-> confirmación ----------

def test_destructivo_siempre_confirma():
    for c in catalog.CONTRACTS:
        if c.risk == RiskLevel.DELETE:
            assert c.needs_confirmation, f"{c.name} es DELETE y no confirma"


def test_lectura_nunca_confirma_ni_revierte():
    for c in catalog.CONTRACTS:
        if c.risk == RiskLevel.READ:
            assert not c.needs_confirmation, f"{c.name} es lectura y pide confirmación"


def test_cada_contrato_declara_verify_y_revert():
    for c in catalog.CONTRACTS:
        assert c.verify.strip(), f"{c.name} sin verify"
        assert c.revert.strip(), f"{c.name} sin revert"


# ---------- ramas sueltas del validador / adaptadores ----------

def test_validador_ramas_restantes():
    # risk que no es RiskLevel
    c = catalog.ToolContract(**_base_kwargs(risk="alto"))
    assert any("risk no es RiskLevel" in p for p in catalog.validate_contract(c))
    # run no callable
    c = catalog.ToolContract(**_base_kwargs(run="nope"))
    assert any("run no es callable" in p for p in catalog.validate_contract(c))
    # parameters no es objeto JSON Schema
    c = catalog.ToolContract(**_base_kwargs(parameters={"type": "array"}))
    assert any("no es un objeto JSON Schema" in p for p in catalog.validate_contract(c))
    # properties no es dict
    c = catalog.ToolContract(**_base_kwargs(parameters={"type": "object", "properties": []}))
    assert any("properties no es dict" in p for p in catalog.validate_contract(c))
    # colisión de nombres entre contratos
    a = catalog.ToolContract(**_base_kwargs(name="dup_x"))
    b = catalog.ToolContract(**_base_kwargs(name="dup_x"))
    assert any("colisión" in p for p in catalog.validate_contract(a, others=[a, b]))


def test_param_names_normal_y_kwargs():
    assert catalog._param_names(lambda a, b=1: None) == {"a", "b"}
    assert catalog._param_names(lambda **kw: None) is None          # **kwargs -> sin límite
    assert catalog._param_names(lambda *a, x=1: None) == {"x"}      # *args no cuenta


def test_by_name_desconocido_es_none():
    assert catalog.by_name("no_existe_esta_herramienta") is None


def test_contract_schema_y_all_names():
    c = catalog.by_name("abrir_aplicacion")
    s = c.schema()
    assert s == {"type": "function", "function": {
        "name": "abrir_aplicacion", "description": c.description, "parameters": c.parameters}}
    assert "abrir_aplicacion" in c.all_names() and "open_app" in c.all_names()


def test_post_init_fuerza_confirmacion_en_delete():
    c = catalog.ToolContract(
        "borrar_prueba", "Borra algo de prueba, con descripción larga suficiente.",
        catalog._obj({"path": catalog._str("ruta")}),
        lambda path="": "ok", RiskLevel.DELETE,
        verify="ya no existe", revert="irreversible",
    )
    assert c.needs_confirmation is True  # no se pasó, lo forzó __post_init__


def test_critical_no_se_fuerza_confirmacion():
    # energia_del_equipo / ejecutar_comando: CRITICAL pero sin /confirmar
    # (su guardia es otra). FASE B no debe endurecerlo.
    for n in ("energia_del_equipo", "ejecutar_comando"):
        assert catalog.by_name(n).needs_confirmation is False


def test_parser_executor_traduce_y_filtra():
    """El parser manda text/minutes/at + basura; el ejecutor real recibe
    texto/minutos/hora traducidos y descarta lo que no está en la firma."""
    from unittest.mock import patch
    c = catalog.by_name("crear_recordatorio")
    with patch("jarvis_local.tools.reminders.set_reminder", return_value="ok") as m:
        c.parser_executor()({"text": "sacar basura", "minutes": 10, "basura_extra": 1})
    # _set_reminder(texto, minutos, hora) -> reminders.set_reminder(texto, minutos, hora)
    assert m.call_args.args == ("sacar basura", 10, "")


def test_parser_executor_fixed_para_intent_fino():
    """El intent fino `volume_up` no lleva args: parser_fixed inyecta accion=subir."""
    from unittest.mock import patch
    c = catalog.by_name("volume_up")
    with patch("jarvis_local.tools.media_controls.volume_up", return_value="ok") as m:
        c.parser_executor()({})
    assert m.called


def test_volume_mute_bool_adaptador():
    # el intent fino manda {mute: bool}; se traduce a accion silenciar/activar
    from unittest.mock import patch
    with patch("jarvis_local.tools.media_controls.volume_mute") as m:
        catalog._volume_mute_bool(True)
        catalog._volume_mute_bool(False)
    assert [call.args for call in m.call_args_list] == [(True,), (False,)]
