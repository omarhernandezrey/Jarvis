import array
import threading
import time

from hud_pro import HudBridge, HudWindow, OrbState
from jarvis_local.ui.hud_pro_adapter import JarvisHudAdapter


def _wait(app, cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.005)
    return cond()


def test_adapter_full_turn_from_worker(qapp):
    win = HudWindow()
    win.show()
    typed = []
    hud = JarvisHudAdapter(HudBridge(win), on_user_text=typed.append, model_name="qwen2.5:7b")
    pcm = array.array("h", [8000, -8000] * 256).tobytes()

    def pipeline():
        hud.on_wake_word()
        hud.on_mic_pcm16(pcm)
        hud.on_partial_transcript("pon música")
        hud.on_final_transcript("pon música")
        for tok in ["Listo, ", "reproduciendo."]:
            hud.on_llm_token(tok)
        hud.on_llm_done()
        hud.on_tts_start()
        hud.on_tts_end()

    t = threading.Thread(target=pipeline)
    t.start()
    t.join(5)
    assert _wait(qapp, lambda: win.state is OrbState.IDLE and len(win.chat.view.bubbles) == 2)
    assert [b.text for b in win.chat.view.bubbles] == ["pon música", "Listo, reproduciendo."]

    hud.on_error(RuntimeError("Ollama no responde"))
    assert _wait(qapp, lambda: win.state is OrbState.ERROR)
    assert "Ollama no responde" in win.status.hint.text()

    win.chat.input.edit.setText("hola")
    win.chat.input.submit()
    assert typed == ["hola"]
    win.close()
