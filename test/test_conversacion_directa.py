"""FASE C · C2 — Puerta de conversación (causa raíz 1, `BANCO_PRUEBAS §12`).

Medido: la confianza del retriever para charla (0,40–0,54) se solapa con la
de peticiones legítimas de herramienta (0,46–0,66) — ningún umbral las separa.
En vez de un umbral, `_es_conversacion_directa` reconoce la FORMA de la charla
dirigida a JARVIS (piropo, pregunta sobre sí mismo, hipotético, pedir
sugerencia/dato sin tema) y corta ANTES del retriever. Determinista, 0 ms.

Blinda:
  - los 4 objetivos de C2: B01, B06, B09, B10 → conversación directa;
  - cero falsos positivos en las 60 frases del banco (grupos A, C, D, E);
  - que el gate corta de verdad ANTES de `confidence()`/`select_tools()`
    (no solo la función pura: el camino real en `run_agent`).
"""
from unittest.mock import MagicMock, patch

import pytest

from jarvis_local.agent.loop import _es_conversacion_directa, run_agent
from scripts.banco_pruebas import BANCO

# ---------- los 4 objetivos de C2 ----------

_REQUERIDOS = {
    "B01": "ome jarvis vos sí sos bacano",
    "B06": "cuál es tu color favorito",
    "B09": "bueno jarvis y vos cómo te sentís hoy",
    "B10": "cuéntame un dato curioso porfa",
}

_BONUS = {
    "B02": "qué opinás del clima loco que ha hecho estos días",
    "B05": "vé y qué harías vos si fueras humano",
    "B08": "qué se te ocurre para el almuerzo de hoy",
}


@pytest.mark.parametrize("id_, frase", _REQUERIDOS.items())
def test_objetivos_c2_son_conversacion_directa(id_, frase):
    assert _es_conversacion_directa(frase), f"{id_} no disparó el gate: {frase!r}"


@pytest.mark.parametrize("id_, frase", _BONUS.items())
def test_bonus_tambien_son_conversacion_directa(id_, frase):
    assert _es_conversacion_directa(frase), f"{id_} no disparó el gate: {frase!r}"


# ---------- cero falsos positivos en el banco completo ----------

def test_cero_falsos_positivos_en_el_banco():
    """El gate SOLO debe disparar en frases cuya capa_esperada sea 'chat'.
    Si dispara en una que espera parser/agente/confirmación/rechazo, una
    petición real se perdería silenciosamente."""
    falsos = [(it["id"], it["texto"]) for it in BANCO
              if _es_conversacion_directa(it["texto"]) and it["capa_esperada"] != "chat"]
    assert not falsos, f"falsos positivos: {falsos}"


def test_dispara_solo_en_las_esperadas_como_chat():
    """Documenta exactamente qué cubre hoy (7 de las 10 de grupo B)."""
    disparos = {it["id"] for it in BANCO if _es_conversacion_directa(it["texto"])}
    assert disparos == {"B01", "B02", "B05", "B06", "B08", "B09", "B10"}


# ---------- no colisiona con la orden vaga (grupo D) ----------

@pytest.mark.parametrize("frase", [
    "hazlo", "abre eso", "ponlo ahi", "buscalo", "mandalo pues",
    "necesito que hagas una cosa", "lo de siempre parce",
])
def test_no_colisiona_con_orden_vaga(frase):
    assert not _es_conversacion_directa(frase)


# ---------- corta de verdad ANTES del retriever ----------

@pytest.mark.parametrize("frase", list(_REQUERIDOS.values()))
def test_run_agent_no_toca_el_retriever(frase):
    """Si el gate falla, este test explota: confidence()/select_tools() no
    deben llamarse jamás para estas frases."""
    with patch("jarvis_local.agent.loop.confidence",
               side_effect=AssertionError("confidence() no debía llamarse")), \
         patch("jarvis_local.agent.loop.select_tools",
               side_effect=AssertionError("select_tools() no debía llamarse")):
        r = run_agent(MagicMock(), frase)
    assert r.tools_used == []
    assert r.needs_clarification is False
    assert r.text == ""
    assert r.pending_confirmation is False


def test_run_agent_deja_pasar_charla_sin_gate_al_camino_normal():
    """Una charla que el gate no cubre (p.ej. B04) sigue su camino de antes:
    no debe reventar ni comportarse distinto a como lo hacía."""
    with patch("jarvis_local.agent.loop.confidence", return_value=0.3), \
         patch("jarvis_local.agent.loop.select_tools", return_value=[]) as sel:
        r = run_agent(MagicMock(), "me siento cansado hoy hermano")
    assert sel.called  # sí pasó por el retriever, como antes de C2
    assert r.tools_used == []
