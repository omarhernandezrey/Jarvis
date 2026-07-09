#!/usr/bin/env python3
"""
JARVIS Local - Interfaz de Linea de Comandos (Fase 3)
Chat local con Ollama + Herramientas + Voz.
"""
import sys
import os
import shlex

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.jarvis import Jarvis
from jarvis_local.safety.policy import policy, ActionStatus, RiskLevel
from jarvis_local.tools.files import (
    list_files, search_files, create_file, create_directory,
    copy_file, move_file, rename_file, plan_delete, read_metadata,
)
from jarvis_local.tools.apps import open_app, list_apps, execute_open_app, ALLOWED_APP_NAMES
from jarvis_local.tools.terminal import plan_command
from jarvis_local.config import get_config

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


def handle_confirm():
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
        elif plan.action in ("crear_archivo", "crear_carpeta"):
            print(plan)
            print("[INFO] Creacion confirmada pero no ejecutada en esta fase (solo simulacion).")
        elif plan.action in ("copiar_archivo", "mover_archivo", "renombrar"):
            print(plan)
            print("[INFO] Operacion confirmada pero no ejecutada en esta fase (solo simulacion).")
        elif plan.action == "ejecutar_comando":
            print(plan)
            print("[INFO] Comando confirmado pero no ejecutado en esta fase (solo simulacion).")
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
    print(f"Modelo: {jarvis.cfg['ollama']['model']}")
    print(f"Voz: {'ON' if tts_enabled else 'OFF'}")
    print(HELP_TEXT)
    print("Escribe tu mensaje y presiona Enter.\n")

    try:
        while True:
            user_input = input("[Tu]: ").strip()

            if not user_input:
                continue

            cmd = user_input.lower().lstrip("/")

            if cmd in ("salir", "exit", "quit"):
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
                    print("[OK] Historial borrado.")
                elif sub == "voz":
                    if len(parts) < 2:
                        _handle_voz_capture(jarvis, tts_enabled)
                    elif parts[1].lower() == "on":
                        tts_enabled = True
                        print("[Voz] Lectura de respuestas ACTIVADA (SAPI5)")
                    elif parts[1].lower() == "off":
                        tts_enabled = False
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
                                print(f"[ERROR] Velocidad fuera de rango (120-250)")
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
                                print(f"[ERROR] Volumen fuera de rango (0.0-1.0)")
                        except (IndexError, ValueError):
                            print("Uso: /voz volumen <0.0-1.0>")
                        except Exception as e:
                            print(f"[ERROR] {e}")
                    elif parts[1].lower() == "probar":
                        from jarvis_local.voice.tts import speak
                        speak("Prueba de voz de Jarvis.")
                        print("[Voz] Prueba de voz reproducida.")
                    else:
                        stt_model = cfg.get("voice", {}).get("stt_model", "base")
                        threshold_val = None
                        noise_floor = None
                        try:
                            from jarvis_local.voice.stt import _get_threshold, load_voice_config
                            vcfg = load_voice_config()
                            threshold_val = _get_threshold()
                            noise_floor = vcfg.get("stt_noise_floor")
                        except Exception:
                            pass
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
                elif sub == "confirmar":
                    handle_confirm()
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

            if tts_enabled and response:
                try:
                    from jarvis_local.voice.tts import speak
                    speak(response)
                except Exception:
                    pass

    except KeyboardInterrupt:
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
