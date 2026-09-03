"""JARVIS Local - Diagnóstico del entorno (TAREA D1).

    python -m jarvis_local.cli doctor

Comprueba, una por una, las dependencias que JARVIS necesita y dice cuáles
están LISTAS y cuáles FALTAN, con la acción concreta para arreglarlo. No
modifica nada.
"""
from __future__ import annotations

import shutil
import socket

OK = "  [ OK ] "
NO = "  [FALTA] "
WARN = "  [ ~~ ] "


def _linea(estado: str, nombre: str, detalle: str = "") -> tuple[bool, str]:
    ok = estado is OK
    return ok, f"{estado}{nombre}" + (f"  — {detalle}" if detalle else "")


def _check_red() -> tuple[bool, str]:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3).close()
        return _linea(OK, "Internet", "hay conexión")
    except OSError:
        return _linea(WARN, "Internet", "sin conexión — clima/wiki/empleo no funcionarán")


def _modelo_soporta_tools(c, modelo: str) -> bool | None:
    """True/False si se puede determinar por /api/show; None si no se sabe."""
    try:
        caps = c.get_model_info(modelo).get("capabilities")
        if isinstance(caps, list):
            return "tools" in caps
    except Exception:  # noqa: BLE001
        pass
    return None


def _check_ollama() -> list[tuple[bool, str]]:
    from jarvis_local.config import get_config
    from jarvis_local.ollama_client.client import OllamaClient

    cfg = get_config()["ollama"]
    c = OllamaClient()
    if not c.is_running():
        return [_linea(NO, "Ollama", f"no responde en {cfg['host']} — arráncalo: `ollama serve`")]

    out = [_linea(OK, "Ollama", cfg["host"])]
    instalados = {m.get("name", "").split(":")[0] for m in c.list_models()}
    agente = cfg.get("agent_model", cfg.get("model", "llama3.2:3b"))
    requeridos = {
        "chat": cfg.get("model", "llama3.2:3b"),
        "agente (routing)": agente,
        "memoria semántica": "bge-m3",
    }
    for rol, modelo in requeridos.items():
        base = modelo.split(":")[0]
        if base in instalados:
            out.append(_linea(OK, f"Modelo {rol}", modelo))
        else:
            out.append(_linea(NO, f"Modelo {rol}", f"falta {modelo} — `ollama pull {modelo}`"))

    # El modelo de routing DEBE soportar tool calling nativo. Si no, el agente
    # no puede elegir herramientas (ver docs/AUDITORIA_2026-09.md §7).
    if agente.split(":")[0] in instalados and _modelo_soporta_tools(c, agente) is False:
        out.append(_linea(NO, "Tool calling",
                          f"{agente} no soporta 'tools' — usa un modelo con "
                          "function calling (llama3.2:3b, qwen2.5:3b)"))
    return out


def _check_secrets() -> list[tuple[bool, str]]:
    from jarvis_local.config import BASE_DIR, get_secrets

    f = BASE_DIR / "secrets.yaml"
    if not f.exists():
        return [_linea(WARN, "secrets.yaml", "no existe — correo/Wolfram/Calendar/Spotify off "
                       "(copia secrets.example.yaml)")]
    try:
        s = get_secrets()
    except Exception as e:  # noqa: BLE001
        return [_linea(NO, "secrets.yaml", f"no se pudo leer: {e}")]

    out = [_linea(OK, "secrets.yaml", "legible")]
    email = s.get("email", {}) or {}
    out.append(_linea(OK if email.get("address") and email.get("app_password") else WARN,
                      "Correo (SMTP)",
                      "configurado" if email.get("address") else "sin address/app_password"))
    out.append(_linea(OK if (s.get("wolframalpha", {}) or {}).get("app_id") else WARN,
                      "WolframAlpha", "app_id presente" if (s.get("wolframalpha", {}) or {}).get("app_id")
                      else "sin app_id"))
    return out


def _check_google_calendar() -> tuple[bool, str]:
    from jarvis_local.config import BASE_DIR

    cred = BASE_DIR / "credentials.json"
    tok = BASE_DIR / "token.json"
    if not cred.exists():
        return _linea(WARN, "Google Calendar", "sin credentials.json (opcional)")
    if not tok.exists():
        return _linea(WARN, "Google Calendar",
                      "sin autorizar — `python -m jarvis_local.cli --reauth-calendar`")
    try:
        from jarvis_local.tools.gcalendar import ReauthRequired, _get_service
        _get_service()
        return _linea(OK, "Google Calendar", "token válido")
    except ReauthRequired:
        return _linea(NO, "Google Calendar",
                      "token caducado — `python -m jarvis_local.cli --reauth-calendar`")
    except Exception as e:  # noqa: BLE001
        return _linea(WARN, "Google Calendar", f"no verificable: {e}")


def _check_spotify() -> tuple[bool, str]:
    from jarvis_local.config import BASE_DIR
    from jarvis_local.tools.spotify import has_credentials

    if not has_credentials():
        return _linea(WARN, "Spotify", "sin client_id/secret en secrets.yaml (opcional)")
    cache = BASE_DIR / "data" / ".spotify_cache"
    if not cache.exists():
        return _linea(WARN, "Spotify",
                      "sin autorizar — `python -m jarvis_local.cli --reauth-spotify`")
    return _linea(OK, "Spotify", "credenciales + token cacheado")


def _check_microfono() -> tuple[bool, str]:
    try:
        import sounddevice as sd
        entradas = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
        if entradas:
            return _linea(OK, "Micrófono", f"{len(entradas)} dispositivo(s) de entrada")
        return _linea(WARN, "Micrófono", "sin dispositivos de entrada — la voz no captará")
    except Exception as e:  # noqa: BLE001
        return _linea(WARN, "Micrófono", f"no verificable: {e}")


def _check_navegador() -> tuple[bool, str]:
    for exe in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        if shutil.which(exe):
            return _linea(OK, "Navegador (Selenium)", exe)
    return _linea(WARN, "Navegador (Selenium)", "no se encontró Chrome/Chromium en PATH")


def diagnosticar() -> tuple[bool, str]:
    """Corre todos los chequeos. Devuelve (todo_ok, informe_texto)."""
    grupos: list[list[tuple[bool, str]]] = [
        [_check_red()],
        _check_ollama(),
        _check_secrets(),
        [_check_google_calendar()],
        [_check_spotify()],
        [_check_microfono()],
        [_check_navegador()],
    ]
    lineas = ["JARVIS · diagnóstico del entorno", "=" * 34]
    criticos_ok = True
    for grupo in grupos:
        for _ok, texto in grupo:
            lineas.append(texto)
            if texto.startswith(NO):
                criticos_ok = False
    lineas.append("")
    lineas.append("Todo lo esencial está listo." if criticos_ok
                  else "Hay elementos en FALTA (arriba). Lo marcado con ~~ es opcional.")
    return criticos_ok, "\n".join(lineas)


def main() -> int:
    ok, informe = diagnosticar()
    print(informe)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
