"""TAREA D3 — prueba de voz end-to-end.

Cierra el círculo completo: audio real -> STT (faster-whisper) -> texto ->
router de Jarvis -> herramienta correcta.

Está marcada `live` porque carga el modelo Whisper (~150 MB la primera vez y
varios segundos de CPU). No corre en cada push; sí en el job nocturno de CI y
a mano con:

    pytest -m live test/test_voice_e2e.py -v

El fixture `test/fixtures/abre_la_calculadora.wav` se sintetiza con edge-tts;
se regenera con `python test/fixtures/_generar_fixture_voz.py`.

Para que la prueba NO abra la calculadora de verdad (la máquina de pruebas es
modesta), se intercepta la ejecución de la herramienta de escritura: lo que se
verifica es el enrutado, no el efecto.
"""
import os
import sys
import unicodedata
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

pytestmark = pytest.mark.live

_FIXTURE = Path(__file__).parent / "fixtures" / "abre_la_calculadora.wav"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().strip()


@pytest.fixture(scope="module")
def texto_transcrito() -> str:
    if not _FIXTURE.exists():
        pytest.skip(f"falta el fixture de audio: {_FIXTURE}")
    from jarvis_local.voice.stt import transcribe_file

    texto = transcribe_file(str(_FIXTURE))
    if not texto:
        pytest.skip("Whisper no devolvió texto (modelo no disponible)")
    return texto


def test_stt_transcribe_la_frase_conocida(texto_transcrito):
    """El STT reconoce la frase con tolerancia (puntuación, mayúsculas)."""
    t = _norm(texto_transcrito)
    assert "abre" in t
    assert "calculadora" in t


def test_voz_a_router_abre_la_calculadora(texto_transcrito):
    """La frase transcrita baja por la cascada y enruta a `open_app`."""
    from jarvis_local.jarvis import Jarvis

    llamadas = []

    def _fake_write(tool, args):
        llamadas.append((tool, args))
        return "Abriendo la calculadora, señor."

    with patch.object(Jarvis, "_ensure_model", return_value=None):
        j = Jarvis()

    with patch("jarvis_local.jarvis._execute_tool_write", side_effect=_fake_write):
        respuesta = j.chat(texto_transcrito)

    assert j.last_reply_kind == "tool", (
        f"esperaba enrutado a herramienta, fue {j.last_reply_kind!r} "
        f"para {texto_transcrito!r}"
    )
    assert llamadas, "no se invocó ninguna herramienta de escritura"
    tool, args = llamadas[0]
    assert tool == "open_app"
    assert "calculadora" in _norm(str(args))
    assert "calculadora" in _norm(respuesta)
