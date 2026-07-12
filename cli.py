#!/usr/bin/env python3
"""
JARVIS Local - Interfaz de Linea de Comandos (Fase 3)
Chat local con Ollama + Herramientas + Voz.
"""
import os
import shlex
import sys

# Forzar UTF-8 en la consola de Windows para que los acentos se muestren correctamente
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.config import get_config
from jarvis_local.jarvis import Jarvis
from jarvis_local.safety.policy import ActionStatus, policy
from jarvis_local.tools.apps import ALLOWED_APP_NAMES, execute_open_app, list_apps, open_app
from jarvis_local.tools.files import (
    copy_file,
    create_directory,
    create_file,
    list_files,
    move_file,
    plan_delete,
    read_metadata,
    rename_file,
    search_files,
)
from jarvis_local.tools.terminal import plan_command

BANNER = """
  ==================================================
             JARVIS LOCAL - Fase 3
    Chat + Herramientas + Voz Local Offline
  ==================================================
"""

HELP_TEXT = """
Chat:
  Escribe cualquier mensaje para conversar con JARVIS
  salir                  Salir de JARVIS

Chat (prefijo /):
  /ayuda                 Muestra esta ayuda
  /estado                Estado de Ollama
  /limpiar               Borrar historial
  /ui                    Abrir Interfaz Web de JARVIS
  /desktop               Abrir Interfaz de Escritorio nativa

Voz (/voz):
  /voz                   Capturar voz, transcribir, enviar a Ollama
  /voz calibrar          Calibrar ruido base del microfono
  /voz diagnostico       Mostrar diagnostico del sistema de voz
  /voz voces             Listar voces TTS disponibles
  /voz voz <indice>      Seleccionar voz TTS por indice
  /voz velocidad <120-250> Cambiar velocidad TTS (palabras/min)
  /voz volumen <0.0-1.0> Cambiar volumen TTS
  /voz probar            Reproducir prueba de voz
  /voz on                Activar lectura de respuestas con TTS
  /voz off               Desactivar lectura de respuestas
  /voz estado            Mostrar configuracion de voz

Herramientas (/archivos):
  /archivos listar <ruta>
  /archivos buscar <nombre> <ruta>
  /archivos crear-archivo <ruta> <contenido>
  /archivos crear-carpeta <ruta>
  /archivos copiar <origen> <destino>
  /archivos mover <origen> <destino>
  /archivos renombrar <ruta> <nuevo_nombre>
  /archivos borrar-plan <ruta>
  /archivos info <ruta>

Apps (/apps):
  /apps listar
  /apps abrir <chrome|vscode|explorador|powershell|terminal>

Terminal (/terminal):
  /terminal plan <comando>

Control de planes:
  /plan                  Ver plan pendiente
  /confirmar             Confirmar plan pendiente
  /cancelar              Cancelar plan pendiente

Tambien entiendo lenguaje natural (texto o voz):
  "abre whatsapp" / "abre youtube.com" / "busca gatos en google"
  "reproduce <cancion> en youtube" / "pon musica"
  "clima en <ciudad>" / "donde queda <lugar>" / "estado del sistema"
  "quien es <persona>" / "noticias" / "cuentame un chiste"
  "calcula 5 mas 3 por 2" / "cual es mi ip" / "toma nota <texto>"
  "captura de pantalla llamada <nombre>" / "cambia de ventana"
  "envia un correo a <destino> asunto <asunto> mensaje <texto>"
  "oculta los archivos de <carpeta>" / "muestra los archivos ocultos de <carpeta>"
  "mis proximos eventos" (Google Calendar, requiere configuracion)
  "busca trabajo de <cargo> en <ciudad>" (Computrabajo) / "abre la oferta 2"
  "muestrame las ofertas" / "navega a <sitio>" / "cierra el navegador"
"""


def parse_args(args_str: str) -> list[str]:
    try:
        return shlex.split(args_str)
    except ValueError:
        return args_str.split()


def handle_archivos(args: list[str]):
    if not args:
        print("Uso: /archivos <accion> ...")
        return
    action = args[0].lower()
    try:
        if action == "listar":
            path = args[1] if len(args) > 1 else "."
            plan = list_files(path)
            print(plan)
        elif action == "buscar":
            if len(args) < 3:
                print("Uso: /archivos buscar <nombre> <ruta>")
                return
            plan = search_files(args[1], args[2])
            print(plan)
        elif action == "crear-archivo":
            if len(args) < 2:
                print("Uso: /archivos crear-archivo <ruta> [contenido]")
                return
            content = " ".join(args[2:]) if len(args) > 2 else ""
            plan = create_file(args[1], content)
            print(plan)
        elif action == "crear-carpeta":
            if len(args) < 2:
                print("Uso: /archivos crear-carpeta <ruta>")
                return
            plan = create_directory(args[1])
            print(plan)
        elif action == "copiar":
            if len(args) < 3:
                print("Uso: /archivos copiar <origen> <destino>")
                return
            plan = copy_file(args[1], args[2])
            print(plan)
        elif action == "mover":
            if len(args) < 3:
                print("Uso: /archivos mover <origen> <destino>")
                return
            plan = move_file(args[1], args[2])
            print(plan)
        elif action == "renombrar":
            if len(args) < 3:
                print("Uso: /archivos renombrar <ruta> <nuevo_nombre>")
                return
            plan = rename_file(args[1], args[2])
            print(plan)
        elif action == "borrar-plan":
            if len(args) < 2:
                print("Uso: /archivos borrar-plan <ruta>")
                return
            plan = plan_delete(args[1])
            print(plan)
        elif action == "info":
            if len(args) < 2:
                print("Uso: /archivos info <ruta>")
                return
            plan = read_metadata(args[1])
            print(plan)
        else:
            print(f"Accion desconocida: {action}")
    except Exception as e:
        print(f"[ERROR] {e}")


def handle_apps(args: list[str]):
    if not args:
        print("Uso: /apps <listar|abrir> ...")
        return
    action = args[0].lower()
    try:
        if action == "listar":
            plan = list_apps()
            print(plan)
        elif action == "abrir":
            if len(args) < 2:
                print(f"Uso: /apps abrir <{'|'.join(ALLOWED_APP_NAMES)}>")
                return
            plan = open_app(args[1])
            print(plan)
        else:
            print(f"Accion desconocida: {action}")
    except Exception as e:
        print(f"[ERROR] {e}")


def handle_terminal(args: list[str]):
    if not args or args[0].lower() != "plan":
        print("Uso: /terminal plan <comando>")
        return
    if len(args) < 2:
        print("Uso: /terminal plan <comando>")
        return
    command = " ".join(args[1:])
    plan = plan_command(command)
    print(plan)


def _set_voice(jarvis, enabled: bool):
    """Conecta (o desconecta) el TTS al streaming del chat.

    Con esto JARVIS empieza a hablar la primera frase mientras el modelo aun
    escribe el resto, en vez de esperar la respuesta completa.
    """
    if not enabled:
        jarvis.speak_fn = None
        return
    try:
        from jarvis_local.voice.tts import speak
        jarvis.speak_fn = speak
    except Exception as e:
        print(f"[ERROR Voz] No pude activar la voz: {e}")
        jarvis.speak_fn = None


def handle_confirm(jarvis=None):
    plan = policy.confirm()
    if not plan:
        print("No hay ningun plan pendiente para confirmar.")
        return
    if plan.status == ActionStatus.BLOCKED:
        print(plan)
        return
    if plan.status == ActionStatus.CONFIRMED:
        if plan.action == "abrir_app":
            plan = execute_open_app(plan.params["app"])
            print(plan)
        elif plan.action == "enviar_correo":
            from jarvis_local.tools.email_sender import execute_send
            plan = execute_send(plan.params["to"], plan.params["subject"],
                                plan.params["body"])
            print(plan.result or plan)
        elif plan.action in ("ocultar_archivos", "mostrar_archivos"):
            from jarvis_local.tools.hidden_files import execute_hide
            plan = execute_hide(plan.params["path"], plan.params["hide"])
            print(plan.result or plan)
        elif plan.action in ("crear_archivo", "crear_carpeta"):
            print(plan)
            print("[INFO] Creacion confirmada pero no ejecutada en esta fase (solo simulacion).")
        elif plan.action in ("copiar_archivo", "mover_archivo", "renombrar"):
            print(plan)
            print("[INFO] Operacion confirmada pero no ejecutada en esta fase (solo simulacion).")
        elif plan.action == "ejecutar_comando":
            print(plan)
            print("[INFO] Comando confirmado pero no ejecutado en esta fase (solo simulacion).")
        elif plan.action == "borrar_historial":
            if jarvis is not None:
                jarvis.history.clear()
                jarvis.store.clear()
            print("[OK] Historial borrado.")
        elif plan.action == "borrar_memoria":
            from jarvis_local.config import BASE_DIR
            from jarvis_local.storage.memory import MemoryStore
            mem = MemoryStore(BASE_DIR / "data")
            mem_id = getattr(plan, "_mem_id", plan.params.get("memory_id", ""))
            if mem.delete(mem_id):
                print(f"[OK] Memoria {mem_id[:8]}... borrada.")
            else:
                print("[ERROR] Memoria no encontrada.")
        elif plan.action == "limpiar_memorias":
            from jarvis_local.config import BASE_DIR
            from jarvis_local.storage.memory import MemoryStore
            mem = MemoryStore(BASE_DIR / "data")
            mem.clear()
            print("[OK] Todas las memorias borradas.")
        else:
            print(plan)
    else:
        print(plan)


def handle_cancel():
    plan = policy.reject()
    if not plan:
        print("No hay ningun plan pendiente para cancelar.")
        return
    print(plan)


def main():
    print(BANNER)
    print("Verificando conexion con Ollama...")

    try:
        jarvis = Jarvis()
    except ConnectionError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    cfg = get_config()
    tts_enabled = cfg.get("voice", {}).get("tts_enabled", False)

    print(f"[OK] {jarvis.get_status()}")
    print(f"Modelo: {jarvis.cfg['ollama']['model']} (cargando en segundo plano...)")
    print(f"Voz: {'ON (edge-tts)' if tts_enabled else 'OFF'}")
    print(HELP_TEXT)
    print("Escribe tu mensaje y presiona Enter. Para activar voz: /voz on\n")

    if tts_enabled:
        try:
            from datetime import datetime

            from jarvis_local.voice.tts import speak as _tts_speak
            hora = datetime.now().hour
            if hora < 12:
                _greeting = "Buenos dias Omar. JARVIS listo."
            elif hora < 18:
                _greeting = "Buenas tardes Omar. JARVIS listo."
            else:
                _greeting = "Buenas noches Omar. JARVIS listo."
            _tts_speak(_greeting)
        except Exception:
            pass

    try:
        while True:
            user_input = input("[Tu]: ").strip()

            if not user_input:
                continue

            cmd = user_input.lower().lstrip("/")

            if cmd in ("salir", "exit", "quit"):
                if hasattr(jarvis, '_continuous_ctrl') and jarvis._continuous_ctrl:
                    jarvis._continuous_ctrl.stop()
                print("\n[JARVIS]: Hasta luego, Omar.")
                break

            if user_input.startswith("/"):
                parts = parse_args(user_input[1:])
                if not parts:
                    continue
                sub = parts[0].lower()

                if sub in ("ayuda", "help"):
                    print(HELP_TEXT)
                elif sub in ("estado", "status"):
                    print(f"[{jarvis.get_status()}]")
                    print(f"[Voz: {'ON' if tts_enabled else 'OFF'}]")
                elif sub in ("limpiar", "clear"):
                    jarvis.history.clear()
                    jarvis.store.clear()
                    print("[OK] Historial borrado.")
                elif sub == "historial":
                    if len(parts) > 1 and parts[1].lower() == "limpiar":
                        from jarvis_local.safety.policy import (
                            ActionPlan,
                            ActionStatus,
                            RiskLevel,
                            policy,
                        )
                        plan = ActionPlan(
                            action="borrar_historial", risk=RiskLevel.DELETE,
                            reason="Borrar historial local requiere confirmacion",
                            simulation_result="[Plan pendiente] Accion: borrar historial local. Escribe /confirmar para ejecutar o /cancelar para cancelar.",
                        )
                        plan.status = ActionStatus.PLANNED
                        policy.pending_plan = plan
                        print(plan)
                    else:
                        msgs = jarvis.store.to_list(10)
                        if not msgs:
                            print("[Historial vacio]")
                        else:
                            print(f"\nHistorial (ultimos {len(msgs)} mensajes):")
                            for m in msgs:
                                role = "Tu" if m["role"] == "user" else "JARVIS"
                                content = m["content"][:80] + ("..." if len(m["content"]) > 80 else "")
                                print(f"  [{role}] {content}")
                elif sub == "memoria":
                    from jarvis_local.config import BASE_DIR
                    from jarvis_local.storage.memory import MemoryStore
                    mem = MemoryStore(BASE_DIR / "data")
                    if len(parts) < 2:
                        print("Uso: /memoria <guardar|listar|borrar|limpiar|usar|dejar|activas|desactivar-todas|buscar>")
                    elif parts[1].lower() == "guardar":
                        if len(parts) < 3:
                            print("Uso: /memoria guardar <texto>")
                        else:
                            text = " ".join(parts[2:])
                            item = mem.add(text)
                            if item:
                                print(f"[OK] Memoria guardada. ID: {item['id'][:8]}...")
                            else:
                                print("[ERROR] Limite de memorias alcanzado (max 100) o texto vacio.")
                    elif parts[1].lower() == "listar":
                        items = mem.list()
                        if not items:
                            print("[Sin memorias guardadas]")
                        else:
                            print(f"\nMemorias ({len(items)}):")
                            for it in items:
                                print(f"  [{it['id'][:8]}] {it['text'][:80]}")
                    elif parts[1].lower() == "borrar":
                        if len(parts) < 3:
                            print("Uso: /memoria borrar <id>")
                        else:
                            mem_id = parts[2]
                            from jarvis_local.safety.policy import (
                                ActionPlan,
                                ActionStatus,
                                RiskLevel,
                            )
                            from jarvis_local.safety.policy import policy as pol
                            plan = ActionPlan(
                                action="borrar_memoria", risk=RiskLevel.DELETE,
                                params={"memory_id": mem_id},
                                reason="Borrar memoria requiere confirmacion",
                                simulation_result=f"[Plan pendiente] Accion: borrar memoria {mem_id[:8]}... Escribe /confirmar para ejecutar o /cancelar para cancelar.",
                            )
                            plan.status = ActionStatus.PLANNED
                            pol.pending_plan = plan
                            pol.pending_plan._mem_id = mem_id
                            print(plan)
                    elif parts[1].lower() == "limpiar":
                        from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel
                        from jarvis_local.safety.policy import policy as pol
                        plan = ActionPlan(
                            action="limpiar_memorias", risk=RiskLevel.DELETE,
                            reason="Limpiar todas las memorias requiere confirmacion",
                            simulation_result="[Plan pendiente] Accion: borrar todas las memorias. Escribe /confirmar para ejecutar o /cancelar para cancelar.",
                        )
                        plan.status = ActionStatus.PLANNED
                        pol.pending_plan = plan
                        print(plan)
                    elif parts[1].lower() == "usar":
                        if len(parts) < 3:
                            print("Uso: /memoria usar <id>")
                        else:
                            mem_id = parts[2]
                            items = mem.list()
                            found = next((it for it in items if it["id"].startswith(mem_id)), None)
                            if not found:
                                print(f"Memoria con ID '{mem_id[:8]}...' no encontrada.")
                            else:
                                ok, msg = jarvis.memory_context.activate(found)
                                print(f"[{'OK' if ok else 'ERROR'}] {msg}")
                    elif parts[1].lower() == "dejar":
                        if len(parts) < 3:
                            print("Uso: /memoria dejar <id>")
                        else:
                            mem_id = parts[2]
                            if jarvis.memory_context.deactivate(mem_id):
                                print(f"[OK] Memoria {mem_id[:8]}... desactivada.")
                            else:
                                print(f"No se encontro la memoria activa con ID '{mem_id[:8]}...'.")
                    elif parts[1].lower() == "activas":
                        actives = jarvis.memory_context.list_active()
                        if not actives:
                            print("[Sin memorias activas]")
                        else:
                            print(f"\nMemorias activas ({len(actives)}/{5}):")
                            for a in actives:
                                print(f"  [{a['id'][:8]}] {a['text'][:80]}")
                    elif parts[1].lower() == "desactivar-todas":
                        jarvis.memory_context.clear()
                        print("[OK] Todas las memorias desactivadas.")
                    elif parts[1].lower() == "buscar":
                        if len(parts) < 3:
                            print("Uso: /memoria buscar <texto o pregunta>")
                        else:
                            query = " ".join(parts[2:])
                            items = mem.list()
                            # Busqueda semantica: encuentra por significado
                            # ("que me gusta tomar?" -> "prefiero el cafe")
                            results = []
                            if jarvis.auto_recall is not None:
                                hits = jarvis.auto_recall.index.search(
                                    query, items, top_k=5, min_score=0.4)
                                results = [(m, s) for m, s in hits]
                            if not results:  # respaldo: coincidencia literal
                                results = [(it, 0.0) for it in items
                                           if query.lower() in it["text"].lower()]
                            if not results:
                                print(f"No se encontraron memorias sobre '{query}'.")
                            else:
                                print(f"\nResultados ({len(results)}):")
                                for it, score in results:
                                    rel = f" ({score:.0%})" if score else ""
                                    print(f"  [{it['id'][:8]}]{rel} {it['text'][:80]}")
                    else:
                        print(f"Comando memoria desconocido: {parts[1]}")
                elif sub == "voz":
                    if len(parts) < 2:
                        _handle_voz_capture(jarvis, tts_enabled)
                    elif parts[1].lower() == "on":
                        tts_enabled = True
                        _set_voice(jarvis, True)
                        print("[Voz] Lectura de respuestas ACTIVADA "
                              "(habla mientras genera)")
                    elif parts[1].lower() == "off":
                        tts_enabled = False
                        _set_voice(jarvis, False)
                        print("[Voz] Lectura de respuestas DESACTIVADA")
                    elif parts[1].lower() == "calibrar":
                        try:
                            from jarvis_local.voice.stt import calibrate
                            calibrate()
                        except Exception as e:
                            print(f"[ERROR Calibracion] {e}")
                    elif parts[1].lower() == "diagnostico":
                        try:
                            from jarvis_local.voice.stt import diagnose
                            diagnose()
                        except Exception as e:
                            print(f"[ERROR Diagnostico] {e}")
                    elif parts[1].lower() == "continuo":
                        if len(parts) == 2:
                            if (hasattr(jarvis, '_continuous_ctrl') and jarvis._continuous_ctrl
                                    and jarvis._continuous_ctrl.is_running()):
                                print("[Voz continua] Ya esta activa. Usa /voz continuo detener para detenerla.")
                            else:
                                from jarvis_local.voice.continuous import ContinuousVoiceController
                                from jarvis_local.voice.stt import (
                                    capture_and_transcribe,
                                    load_voice_config,
                                )
                                from jarvis_local.voice.tts import is_speaking as tts_is_speaking_fn
                                from jarvis_local.voice.tts import speak as tts_speak_fn
                                vcfg = load_voice_config()
                                mic_name = "auto"
                                try:
                                    import sounddevice as sd
                                    d = sd.query_devices(kind="input")
                                    mic_name = d.get("name", "auto")
                                except Exception:
                                    pass
                                ctrl = ContinuousVoiceController(
                                    stt_fn=capture_and_transcribe,
                                    chat_fn=jarvis.chat,
                                    tts_speak_fn=tts_speak_fn if tts_enabled else None,
                                    tts_speaking_fn=tts_is_speaking_fn,
                                )
                                jarvis._continuous_ctrl = ctrl
                                ctrl.start()
                                print("[Voz continua] ACTIVADA. Di 'Jarvis' seguido de tu solicitud.")
                                print(f"[Voz continua] Microfono: {mic_name}")
                                print(f"[Voz continua] Fragmentos: 2s | STT: faster-whisper {vcfg.get('stt_model','base')}")
                                print("  Usa /voz continuo detener para parar.")
                        elif parts[2].lower() == "detener":
                            if hasattr(jarvis, '_continuous_ctrl') and jarvis._continuous_ctrl:
                                jarvis._continuous_ctrl.stop()
                                jarvis._continuous_ctrl = None
                            print("[Voz continua] DETENIDA.")
                        elif parts[2].lower() == "estado":
                            if hasattr(jarvis, '_continuous_ctrl') and jarvis._continuous_ctrl:
                                st = jarvis._continuous_ctrl.get_state()
                                print(f"[Voz continua] {'ON' if st['active'] else 'OFF'}")
                                print(f"  Estado: {st['state']}")
                                print(f"  Wake word: {st['wake_word']}")
                                print(f"  Fragmento: {st['fragment_duration_s']}s")
                                print(f"  Pausa TTS: {st['tts_pause_ms']}ms")
                                if st.get('buffer'):
                                    print(f"  Buffer actual: {st['buffer']}")
                                if st.get('last_command'):
                                    print(f"  Ultimo comando: {st['last_command'][:80]}")
                                if st.get('silence_count'):
                                    print(f"  Silencio: {st['silence_count']}/{st.get('command_timeout_s',8)//2}")
                            else:
                                print("[Voz continua] OFF")
                        elif parts[2].lower() == "prueba":
                            from jarvis_local.voice.stt import (
                                capture_and_transcribe,
                                load_voice_config,
                            )
                            vcfg = load_voice_config()
                            mic_name = "auto"
                            try:
                                import sounddevice as sd
                                d = sd.query_devices(kind="input")
                                mic_name = d.get("name", "auto")
                            except Exception:
                                pass
                            print(f"[Voz continua prueba] Microfono: {mic_name}")
                            text = capture_and_transcribe(2, show_stats=True)
                            if text:
                                print(f"[Voz continua prueba] Transcripcion: \"{text}\"")
                            else:
                                print("[Voz continua prueba] Sin texto reconocido.")
                        else:
                            print("Uso: /voz continuo [detener|estado|prueba]")
                    elif parts[1].lower() == "voces":
                        try:
                            from jarvis_local.voice.tts import list_voices
                            voces = list_voices()
                            print(f"\nVoces TTS disponibles ({len(voces)}):")
                            for v in voces:
                                print(f"  [{v['index']}] {v['name']} | langs={v['languages']}")
                        except Exception as e:
                            print(f"[ERROR Voces] {e}")
                    elif parts[1].lower() == "voz":
                        try:
                            idx = int(parts[2])
                            from jarvis_local.voice.tts import select_voice
                            if select_voice(idx):
                                print(f"[Voz] Voz cambiada a indice {idx}")
                            else:
                                print(f"[ERROR] Indice de voz invalido: {idx}")
                        except (IndexError, ValueError):
                            print("Uso: /voz voz <indice>")
                        except Exception as e:
                            print(f"[ERROR] {e}")
                    elif parts[1].lower() == "velocidad":
                        try:
                            wpm = int(parts[2])
                            from jarvis_local.voice.tts import set_rate
                            if set_rate(wpm):
                                print(f"[Voz] Velocidad: {wpm} palabras/min")
                            else:
                                print("[ERROR] Velocidad fuera de rango (120-250)")
                        except (IndexError, ValueError):
                            print("Uso: /voz velocidad <120-250>")
                        except Exception as e:
                            print(f"[ERROR] {e}")
                    elif parts[1].lower() == "volumen":
                        try:
                            vol = float(parts[2])
                            from jarvis_local.voice.tts import set_volume
                            if set_volume(vol):
                                print(f"[Voz] Volumen: {vol:.1f}")
                            else:
                                print("[ERROR] Volumen fuera de rango (0.0-1.0)")
                        except (IndexError, ValueError):
                            print("Uso: /voz volumen <0.0-1.0>")
                        except Exception as e:
                            print(f"[ERROR] {e}")
                    elif parts[1].lower() == "probar":
                        from jarvis_local.voice.tts import speak
                        speak("Prueba de voz de Jarvis.")
                        print("[Voz] Prueba de voz reproducida.")
                    else:
                        stt_model = cfg.get("voice", {}).get("stt_model", "small")
                        threshold_val = None
                        noise_floor = None
                        try:
                            from jarvis_local.voice.stt import _get_threshold, load_voice_config
                            vcfg = load_voice_config()
                            threshold_val = _get_threshold()
                            noise_floor = vcfg.get("stt_noise_floor")
                        except Exception:
                            pass
                        if noise_floor is not None:
                            print(f"[Voz] Ruido base calibrado: {noise_floor:.6f}")
                        from jarvis_local.voice.tts import get_voice_state
                        tts_state = get_voice_state()
                        print(f"[Voz] STT: faster-whisper {stt_model}")
                        print(f"[Voz] TTS: pyttsx3 (SAPI5) | {'ON' if tts_enabled else 'OFF'}")
                        print(f"[Voz] Voz: indice {tts_state['voice_index']}")
                        print(f"[Voz] Velocidad: {tts_state['rate']} wpm | Volumen: {tts_state['volume']:.1f}")
                        if threshold_val is not None:
                            print(f"[Voz] Umbral STT: {threshold_val:.6f}")
                elif sub == "archivos":
                    handle_archivos(parts[1:])
                elif sub == "apps":
                    handle_apps(parts[1:])
                elif sub == "terminal":
                    handle_terminal(parts[1:])
                elif sub == "plan":
                    p = policy.pending_plan
                    if p:
                        print(p)
                    else:
                        print("No hay ningun plan pendiente.")
                elif sub == "ui":
                    print("Iniciando Interfaz Web JARVIS...")
                    try:
                        from jarvis_local.ui.server import main as ui_main
                        ui_main()
                    except KeyboardInterrupt:
                        print("\nInterfaz web detenida.")
                    except Exception as e:
                        print(f"[ERROR UI] {e}")
                elif sub == "desktop":
                    print("Iniciando JARVIS Desktop...")
                    try:
                        from jarvis_local.ui.desktop import main as desktop_main
                        desktop_main()
                    except KeyboardInterrupt:
                        print("\nInterfaz desktop cerrada.")
                    except Exception as e:
                        print(f"[ERROR Desktop] {e}")
                elif sub == "confirmar":
                    handle_confirm(jarvis)
                elif sub == "cancelar":
                    handle_cancel()
                else:
                    print(f"Comando desconocido: {user_input}")
                    print("Usa /ayuda para ver comandos disponibles.")
                continue

            print()
            try:
                response = jarvis.chat(user_input)
            except ConnectionError as e:
                print(f"\n[ERROR] {e}")
                print("Asegurate de que Ollama este corriendo.")
                continue
            except RuntimeError as e:
                print(f"\n[ERROR] {e}")
                continue

            print(f"\n[JARVIS]: {response}\n")

            # Con la voz activa, el chat ya hablo por frases mientras generaba
            # (jarvis.speak_fn). Aqui solo se habla lo que no paso por el LLM:
            # respuestas instantaneas, resultados de herramientas y planes.
            if tts_enabled and response and not jarvis.spoke_last_response:
                try:
                    from jarvis_local.voice.tts import speak
                    speak(response)
                except Exception:
                    pass

    except KeyboardInterrupt:
        if hasattr(jarvis, '_continuous_ctrl') and jarvis._continuous_ctrl:
            jarvis._continuous_ctrl.stop()
        print("\n\n[JARVIS]: Hasta luego, Omar.")
    except EOFError:
        print()


def _handle_voz_capture(jarvis, tts_enabled):
    try:
        from jarvis_local.voice.stt import listen
        text = listen()
        if not text:
            return

        print()
        response = jarvis.chat(text)
        print(f"\n[JARVIS]: {response}\n")

        if tts_enabled and response:
            from jarvis_local.voice.tts import speak
            speak(response)

    except ConnectionError as e:
        print(f"\n[ERROR] {e}")
    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
    except Exception as e:
        print(f"[ERROR Voz] {e}")


if __name__ == "__main__":
    main()
