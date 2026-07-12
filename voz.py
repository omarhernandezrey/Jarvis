"""
JARVIS Local - Modo Voz Puro
Graba en ciclos de 4 segundos, Whisper detecta si hay habla.
Sin umbral manual — funciona con micrófonos de cualquier volumen.

Uso: python -m jarvis_local.voz
"""
import contextlib
import io as _io
import os
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@contextlib.contextmanager
def _silencio():
    old = sys.stdout
    sys.stdout = _io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old


def _log(msg: str):
    sys.__stdout__.write(msg + "\n")
    sys.__stdout__.flush()


def _escuchar() -> str | None:
    """
    Graba 4 segundos y transcribe con Whisper.
    Whisper descarta el audio si no hay habla real (vad_filter=True).
    Sin umbral de volumen — funciona con cualquier microfono.
    """
    import sounddevice as sd

    from jarvis_local.voice.stt import _get_whisper_model, load_voice_config

    cfg = load_voice_config()
    model_name = cfg.get("stt_model", "small")
    compute = cfg.get("stt_compute_type", "int8")

    SR = 16000
    DURACION = 4

    try:
        rec = sd.rec(int(DURACION * SR), samplerate=SR, channels=1, dtype="int16")
        sd.wait()
    except Exception as e:
        _log(f"[ERROR mic] {e}")
        return None

    audio = rec.flatten().astype("float32") / 32768.0

    try:
        model = _get_whisper_model(model_name, compute)
        segs, _ = model.transcribe(
            audio,
            language="es",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        texto = " ".join(s.text.strip() for s in segs).strip()
        return texto if len(texto) >= 2 else None
    except Exception as e:
        _log(f"[ERROR STT] {e}")
        return None


def main():
    _log("Iniciando JARVIS...")

    # Verificar microfono
    try:
        import sounddevice as sd
        mic = sd.query_devices(kind="input")
        _log(f"Microfono: {mic.get('name','?')[:50]}")
    except Exception as e:
        _log(f"[ERROR] Sin microfono: {e}")
        sys.exit(1)

    # Cargar Jarvis
    try:
        from jarvis_local.jarvis import Jarvis
        with _silencio():
            jarvis = Jarvis()
    except ConnectionError as e:
        _log(f"[ERROR] Ollama no esta corriendo: {e}")
        sys.exit(1)
    except RuntimeError as e:
        _log(f"[ERROR] {e}")
        sys.exit(1)

    from jarvis_local.voice.tts import is_speaking, speak

    _log("JARVIS activo. Habla cuando quieras. Ctrl+C para salir.")
    _log("-" * 50)

    # Precargar modelo Whisper (evita demora en primera captura)
    _log("Precargando modelo de voz...")
    try:
        from jarvis_local.voice.stt import _get_whisper_model, load_voice_config
        cfg = load_voice_config()
        model_name = cfg.get("stt_model", "small")
        compute = cfg.get("stt_compute_type", "int8")
        _get_whisper_model(model_name, compute)
        _log(f"Modelo '{model_name}' listo.")
    except Exception as e:
        _log(f"[WARN] No se pudo precargar modelo: {e}")

    # Saludo inicial
    from datetime import datetime
    hora = datetime.now().hour
    if hora < 12:
        saludo = "Buenos dias, senor Omar. JARVIS en linea. En que le puedo asistir?"
    elif hora < 18:
        saludo = "Buenas tardes, senor Omar. Sistemas operando con normalidad."
    else:
        saludo = "Buenas noches, senor Omar. JARVIS activo. Como le puedo ayudar?"

    speak(saludo)

    try:
        while True:
            # Esperar que JARVIS termine de hablar
            while is_speaking():
                time.sleep(0.05)

            _log("[escuchando...]")

            texto = _escuchar()

            if not texto:
                continue

            _log(f"[Tu] {texto}")

            # Detectar salida por voz
            if any(p in texto.lower() for p in [
                "apagar jarvis", "cierra jarvis", "adios jarvis",
                "hasta luego jarvis", "jarvis apagar"
            ]):
                speak("Hasta luego, senor Omar. Que tenga un excelente dia.")
                break

            # Responder
            with _silencio():
                try:
                    respuesta = jarvis.chat(texto)
                except Exception:
                    respuesta = "Disculpe senor, tuve un inconveniente tecnico."

            if respuesta:
                _log(f"[JARVIS] {respuesta[:100]}")
                speak(respuesta)

    except KeyboardInterrupt:
        _log("\nApagando...")
        speak("Hasta luego, senor Omar.")


if __name__ == "__main__":
    main()
