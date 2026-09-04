"""FASE C · C6 — frases de parser para las 5 herramientas solo-agente.

Antes de C6, `catalog.slow_path_only()` listaba `controlar_musica`,
`controlar_volumen`, `energia_del_equipo`, `organizar_ventanas` y `recordar`
como alcanzables SOLO por el agente (~40 s cada una). De esas 5, 4 ya tenían
intents FINOS de parser cubriendo su capacidad (`volume_up`, `media_play_
pause`, `lock_pc`, `minimize_all`…) — el hueco real era de FRASEO colombiano
(voseo imperativo, enclíticos) que no llegaba a esos gates. `recordar` no
tenía NINGÚN gate: toda frase de memoria caía al agente.

Este archivo blinda, por herramienta:
  - las frases colombianas reales que C6 cierra (no la forma canónica);
  - que `organizar_ventanas` avisa CLARO en Wayland, no falla en silencio;
  - que `energia_del_equipo` (apagar/suspender, destructivo) sigue con su
    guardia de confirmación (ventana cancelable), la ruta rápida no se la salta.
"""
from unittest.mock import patch

import pytest

from jarvis_local.intent.parser import parse_intent
from jarvis_local.jarvis import _execute_tool_write

# ---------- controlar_volumen: subir (voseo "subí"+enclítico) ----------

@pytest.mark.parametrize("frase", [
    "sube el volumen", "subeme el volumen", "súbeme el volumen",
    "subime el volumen", "subime al volumen",
])
def test_volumen_sube_con_voseo_y_enclitico(frase):
    ir = parse_intent(frase)
    assert ir.kind == "tool_execute" and ir.tool == "volume_up"


# ---------- controlar_musica: pausa (arreglo del misroute a spotify) ----------

@pytest.mark.parametrize("frase", [
    "pausa la musica", "pon pausa", "pone pausa", "poné pausa", "ponle pausa",
])
def test_musica_pausa_con_voseo_no_se_va_a_spotify(frase):
    ir = parse_intent(frase)
    assert ir.kind == "tool_execute" and ir.tool == "media_play_pause", (
        f"{frase!r} -> {ir.tool} (se esperaba media_play_pause)")


def test_pon_cancion_sigue_siendo_spotify_no_regresion():
    """El arreglo de 'pon pausa' no debe tragarse pedidos reales de canción."""
    ir = parse_intent("pon bohemian rhapsody")
    assert ir.tool == "spotify_play"
    assert ir.arguments["song"] == "bohemian rhapsody"


# ---------- energia_del_equipo: apagar/suspender/bloquear con voseo ----------

@pytest.mark.parametrize("frase, tool", [
    ("apaga el equipo", "shutdown_pc"), ("apagá el equipo", "shutdown_pc"),
    ("apagame el equipo", "shutdown_pc"),
    ("suspende el equipo", "suspend_pc"), ("suspendé el equipo", "suspend_pc"),
    ("bloquea la pantalla", "lock_pc"), ("bloqueá la pantalla", "lock_pc"),
    ("bloqueame la pantalla", "lock_pc"),
])
def test_energia_con_voseo(frase, tool):
    ir = parse_intent(frase)
    assert ir.kind == "tool_execute" and ir.tool == tool


@pytest.mark.parametrize("frase, flag", [
    ("apaga el equipo", "/s"), ("apagá el equipo", "/s"),
    ("reinicia el equipo", "/r"), ("reiniciá el equipo", "/r"),
])
def test_apagar_reiniciar_por_voseo_sigue_pidiendo_confirmacion(frase, flag):
    """Destructivo: la ruta rápida NO puede saltarse la ventana cancelable.
    apagar/reiniciar nunca son inmediatos -- se programan con cuenta
    regresiva y "cancela el apagado" los aborta (esa ventana ES la
    confirmación, ver tools/power.py). Se verifica que, viniendo por voseo,
    se sigue llamando al mismo camino con retraso — nunca un apagado directo
    sin ventana."""
    with patch("jarvis_local.tools.power._run_shutdown") as mock_run, \
         patch("jarvis_local.config.IS_WINDOWS", True), \
         patch("jarvis_local.tools.power.IS_WINDOWS", True):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        ir = parse_intent(frase)
        resultado = _execute_tool_write(ir.tool, ir.arguments)

    assert mock_run.called, "no se invocó el comando de apagado/reinicio"
    args_llamada = mock_run.call_args[0][0]
    assert flag in args_llamada, f"faltó la bandera {flag}: {args_llamada}"
    assert "/t" in args_llamada, "el apagado se pidió SIN retraso (sin ventana cancelable)"
    assert "cancela" in resultado.lower(), "la respuesta no ofrece cómo cancelar"


def test_cancelar_apagado_sigue_disponible():
    ir = parse_intent("cancela el apagado")
    assert ir.kind == "tool_execute" and ir.tool == "cancel_shutdown"


# ---------- organizar_ventanas: voseo + aviso claro en Wayland ----------

@pytest.mark.parametrize("frase, tool", [
    ("minimiza todo", "minimize_all"), ("minimizá todo", "minimize_all"),
    ("maximiza la ventana", "snap_window"), ("maximizá la ventana", "snap_window"),
])
def test_ventanas_con_voseo(frase, tool):
    ir = parse_intent(frase)
    assert ir.kind == "tool_execute" and ir.tool == tool


def test_ventanas_avisa_claro_en_wayland_no_falla_en_silencio():
    """La ruta rápida no puede fallar en silencio ni con un error crudo: debe
    decir, en una frase completa, que no puede en este escritorio."""
    with patch("jarvis_local.tools.desktop_actions.IS_WINDOWS", False):
        resultado = _execute_tool_write("minimize_all", {})
    assert resultado != "Operacion completada."
    assert not resultado.startswith("Error:"), (
        f"mensaje crudo en vez de la explicación completa: {resultado!r}")
    assert "wayland" in resultado.lower()
    assert len(resultado) > 40  # una frase de verdad, no un código de error


# ---------- recordar: sin ningún intent de parser antes de C6 ----------

@pytest.mark.parametrize("frase, dato", [
    ("recuerda que me gusta el cafe sin azucar", "me gusta el cafe sin azucar"),
    ("recuerdame que soy alergico a los mariscos", "soy alergico a los mariscos"),
    ("acuerdate que trabajo en bogota", "trabajo en bogota"),
    ("acordate que trabajo en bogota", "trabajo en bogota"),
    ("no olvides que mi cumpleanos es en marzo", "mi cumpleanos es en marzo"),
    ("ten en cuenta que prefiero llamadas cortas", "prefiero llamadas cortas"),
    ("ten cuenta que no como carne", "no como carne"),
])
def test_recordar_reconoce_las_formas_coloquiales(frase, dato):
    ir = parse_intent(frase)
    assert ir.kind == "tool_execute" and ir.tool == "recordar"
    assert ir.arguments["text"] == dato


def test_recordar_con_tiempo_sigue_siendo_recordatorio_no_memoria():
    """No debe regresionar A15/el resto: si HAY tiempo, es alarma, no memoria."""
    ir = parse_intent("recuerdame en 10 minutos sacar la ropa")
    assert ir.tool == "set_reminder"


def test_recordar_ejecuta_y_guarda_en_memoria(tmp_path, monkeypatch):
    """e2e por la ruta rápida: el dato queda de verdad en el store."""
    import jarvis_local.config as cfgmod
    monkeypatch.setattr(cfgmod, "BASE_DIR", tmp_path)
    ir = parse_intent("recuerda que prefiero el te sin azucar")
    resultado = _execute_tool_write(ir.tool, ir.arguments)
    assert "recordare" in resultado.lower() or "recordaré" in resultado.lower()

    from jarvis_local.storage.memory import MemoryStore
    store = MemoryStore(tmp_path / "data")
    textos = [m["text"] for m in store.list()]
    assert "prefiero el te sin azucar" in textos
