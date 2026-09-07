"""PLAN_EJECUCION FASE E · E1 — lista de intocables (guardia DURO).

Antes de dar a JARVIS poder para matar procesos (E3) y parar servicios (E4):
qué NO se toca NUNCA, ni aunque el usuario lo pida explícitamente. Matar
gnome-shell no es un bug — es perder la sesión y todas las ventanas abiertas.

NO hay ruta de "forzar". Si se pide algo de esta lista, la herramienta lo
BLOQUEA, dice POR QUÉ, y ofrece la alternativa correcta.

Marcado de origen:
  [base]  lista fija que pidió el usuario — no negociable.
  [+E1]   añadido tras inventariar ESTE sistema (Ubuntu + GDM3 + GNOME/Wayland
          + PipeWire). El usuario lo revisa y puede recortar antes de fijarlo.
"""
from __future__ import annotations

import contextlib
import os
import re

# =============================================================================
# Procesos (E3). clave = nombre de proceso (comm); el matcher tolera la
# truncación de `comm` a 15 chars y también busca en la línea de comandos.
# =============================================================================
PROC_REASONS: dict[str, str] = {
    # --- sesión gráfica: matarlo = perder la sesión y TODAS las ventanas ---
    "gnome-shell":          "es el compositor y shell de tu sesión Wayland; matarlo cierra el escritorio y todas las ventanas abiertas",   # [base]
    "gnome-session-binary": "gestiona tu sesión gráfica; matarlo te cierra la sesión",   # [+E1]
    "gnome-session":        "gestiona tu sesión gráfica",   # [+E1]
    "mutter":               "es el compositor de ventanas",   # [base] (compositor Wayland)
    "kwin_wayland":         "es el compositor de ventanas",   # [base]
    "plasmashell":          "es el shell del escritorio",   # [+E1]
    "Xwayland":             "hace funcionar las apps X11 dentro de tu sesión Wayland; matarlo las cierra todas",   # [+E1]
    # --- gestor de pantalla: matarlo = caes al login ---
    "gdm":                  "es el gestor de pantalla; matarlo te devuelve a la pantalla de login",   # [+E1]
    "gdm3":                 "es el gestor de pantalla; matarlo te devuelve a la pantalla de login",   # [+E1]
    "gdm-session-worker":   "sostiene tu sesión de login",   # [+E1]
    # --- init y núcleo de systemd ---
    "systemd":              "es el proceso 1 (init) del sistema, o tu gestor de sesión de usuario",   # [base]
    "systemd-logind":       "gestiona sesiones, asientos y el bloqueo de pantalla",   # [base]
    "systemd-journald":     "es el sistema de logs; sin él se pierde el registro de lo que pasa",   # [+E1]
    "systemd-udevd":        "gestiona los dispositivos del sistema (disco, USB, red)",   # [+E1]
    "systemd-resolved":     "resuelve DNS para todo el sistema; matarlo deja la red sin nombres",   # [+E1]
    "systemd-oomd":         "es el gestor de memoria del sistema",   # [+E1]
    # --- bus de mensajes: sin él el escritorio se desmonta ---
    "dbus-daemon":          "es el bus de mensajes del sistema y de la sesión",   # [base]
    "dbus-broker":          "es el bus de mensajes del sistema y de la sesión",   # [+E1] (variante moderna)
    "dbus-broker-launch":   "arranca el bus de mensajes",   # [+E1]
    # --- red: matarlo puede dejarte sin conexión y sin poder recuperarla ---
    "NetworkManager":       "gestiona tu conexión de red",   # [base]
    "wpa_supplicant":       "gestiona la autenticación del WiFi",   # [+E1]
    "ModemManager":         "gestiona el módem y los datos móviles",   # [+E1]
    # --- acceso remoto: matarlo te deja fuera si estás conectado por SSH ---
    "sshd":                 "es el servidor SSH; si estás conectado en remoto, matarlo te deja fuera",   # [base]
    # --- permisos ---
    "polkitd":              "concede permisos de administrador; sin él fallan las peticiones con contraseña",   # [+E1]
    # --- audio (recuperable, pero rompe TODO el sonido) ---
    "pipewire":             "es el servidor de audio",   # [+E1]
    "pipewire-pulse":       "es la capa de compatibilidad de audio (PulseAudio)",   # [+E1]
    "wireplumber":          "es el gestor de sesiones de audio",   # [+E1]
    # --- el cerebro de JARVIS ---
    "ollama":               "es el servidor del modelo; matarlo me deja sin cerebro a mitad de tarea",   # [base]
    "llama-server":         "es el motor del modelo que estoy usando ahora mismo",   # [+E1]
    # --- contenedores: matarlos aborta builds y deja contenedores huérfanos ---
    "dockerd":              "es el demonio de Docker; matarlo aborta cualquier `docker build` o contenedor en marcha",   # [+E1·b]
    "docker":               "es Docker; matarlo aborta builds y contenedores en marcha y deja estado colgando",   # [+E1·b]
    "containerd":           "es el runtime de contenedores (Docker/Kubernetes); matarlo deja los contenedores en estado inconsistente",   # [+E1·b]
    # --- gestores de paquetes: matarlos a mitad de transacción rompe dpkg/snap ---
    "dpkg":                "está instalando o quitando paquetes; matarlo deja el sistema de paquetes a medias (hay que hacer `sudo dpkg --configure -a` para recuperar)",   # [+E1·c]
    "apt":                 "es una instalación de paquetes en curso; matarla rompe la transacción",   # [+E1·c]
    "apt-get":             "es una instalación de paquetes en curso; matarla rompe la transacción",   # [+E1·c]
    "aptitude":            "es una instalación de paquetes en curso; matarla rompe la transacción",   # [+E1·c]
    "unattended-upgr":     "es la actualización automática de seguridad; matarla a medias rompe dpkg",   # [+E1·c] (comm truncado)
    "packagekitd":         "es el servicio de instalación de software (GNOME Software); matarlo a mitad de una instalación rompe dpkg",   # [+E1·c]
    "packagekit":          "es el servicio de instalación de software",   # [+E1·c]
    "snapd":               "gestiona los paquetes snap; matarlo a mitad de una instalación deja el snap corrupto",   # [+E1·c]
    # --- discos: matarlo durante un montaje/formateo puede corromper datos ---
    "udisksd":             "gestiona discos y montajes; matarlo durante una operación puede corromper el sistema de archivos de un USB o partición",   # [+E1·c]
    # --- secretos de la sesión: matarlos pierde contraseñas y claves desbloqueadas ---
    "gnome-keyring-d":     "guarda los secretos descifrados de tu sesión (contraseñas de wifi, del correo...); matarlo hace que todo te los vuelva a pedir",   # [+E1·c] (comm truncado)
    "gcr-ssh-agent":       "guarda tus claves SSH desbloqueadas; matarlo te obliga a volver a meter la frase de paso",   # [+E1·c]
    "ssh-agent":           "guarda tus claves SSH desbloqueadas; matarlo te obliga a volver a meter la frase de paso",   # [+E1·c]
}

# Alternativa correcta por familia (lo que el usuario seguramente quería).
_ALTERNATIVAS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"gnome-shell|gnome-session|mutter|plasmashell|kwin"),
     "Si el escritorio va raro, cierra sesión y vuelve a entrar, o reinicia "
     "GNOME Shell con Alt+F2 → «r» (solo en X11). No lo mato yo."),
    (re.compile(r"^gdm|Xwayland"),
     "Para reiniciar el entorno gráfico: `sudo systemctl restart gdm` desde "
     "una terminal (te cerrará todo). No lo hago yo."),
    (re.compile(r"pipewire|wireplumber"),
     "Para reiniciar el audio sin cerrar nada: "
     "`systemctl --user restart pipewire pipewire-pulse wireplumber`."),
    (re.compile(r"NetworkManager|wpa_supplicant|ModemManager"),
     "Para reiniciar la red: `sudo systemctl restart NetworkManager` (perderás "
     "la conexión un momento). Hazlo tú, no a ciegas desde aquí."),
    (re.compile(r"ollama|llama-server"),
     "Si quieres liberar RAM del modelo sin matarlo: pídeme que suelte el "
     "modelo de embeddings, o `ollama stop <modelo>`."),
    (re.compile(r"sshd"),
     "Si necesitas reiniciar SSH, hazlo desde una consola local: "
     "`sudo systemctl restart ssh`."),
    (re.compile(r"docker|containerd"),
     "Para reiniciar Docker sin perder trabajo: espera a que terminen los "
     "builds y contenedores en curso y luego `sudo systemctl restart docker`. "
     "No lo mato yo."),
    (re.compile(r"^dpkg|^apt|unattended-upgr|packagekit|^snapd"),
     "Espera a que termine la instalación de paquetes (unos minutos). Si de "
     "verdad se colgó, recupéralo tú con `sudo dpkg --configure -a`. Nunca lo "
     "mates a medias."),
    (re.compile(r"gnome-keyring|gcr-ssh-agent|ssh-agent"),
     "Si el llavero da problemas, cierra sesión y vuelve a entrar. Matarlo te "
     "deja sin las contraseñas y claves desbloqueadas de esta sesión."),
    (re.compile(r"udisksd"),
     "Desmonta lo que tengas conectado y hazlo tú si de verdad hace falta: "
     "`sudo systemctl restart udisks2`."),
]

_GENERICA = ("Es un proceso crítico del sistema o de tu sesión. Si de verdad "
             "necesitas pararlo, hazlo tú desde una terminal — yo no lo toco.")

# =============================================================================
# Unidades de systemd (E4).
# =============================================================================
UNIT_REASONS: dict[str, str] = {
    "gdm.service":              "es el gestor de pantalla; pararlo te devuelve al login",   # [+E1]
    "NetworkManager.service":   "gestiona tu conexión de red",   # [base]
    "wpa_supplicant.service":   "gestiona el WiFi",   # [+E1]
    "ModemManager.service":     "gestiona el módem/datos móviles",   # [+E1]
    "dbus.service":             "es el bus de mensajes del sistema",   # [base]
    "systemd-logind.service":   "gestiona sesiones y asientos",   # [base]
    "polkit.service":           "concede permisos de administrador",   # [+E1]
    "systemd-journald.service": "es el sistema de logs",   # [+E1]
    "systemd-resolved.service": "resuelve DNS para todo el sistema",   # [+E1]
    "systemd-oomd.service":     "es el gestor de memoria del sistema",   # [+E1]
    "systemd-udevd.service":    "gestiona los dispositivos",   # [+E1]
    "ssh.service":              "es el servidor SSH",   # [base]
    "sshd.service":             "es el servidor SSH",   # [base]
    "ollama.service":           "es el servidor del modelo; sin él me quedo sin cerebro",   # [base]
    "docker.service":           "es Docker; pararlo aborta builds y contenedores en marcha",   # [+E1·b]
    "containerd.service":       "es el runtime de contenedores; pararlo deja los contenedores inconsistentes",   # [+E1·b]
    "snapd.service":            "gestiona los paquetes snap; pararlo a mitad de una instalación deja el snap corrupto",   # [+E1·c]
    "packagekit.service":       "es el servicio de instalación de software",   # [+E1·c]
    "unattended-upgrades.service": "es la actualización automática de seguridad",   # [+E1·c]
    "apt-daily.service":        "es la tarea diaria de apt (descarga/actualización)",   # [+E1·c]
    "apt-daily-upgrade.service": "es la tarea diaria de actualización de apt",   # [+E1·c]
    "udisks2.service":          "gestiona discos y montajes",   # [+E1·c]
}
_UNIT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^user@\d+\.service$"), "es tu sesión de usuario de systemd; pararla te cierra la sesión"),
]


# =============================================================================
# API
# =============================================================================

def own_pids() -> set[int]:
    """PIDs de JARVIS: él mismo, su padre, su grupo, y (si hay psutil) sus
    ancestros e hijos. Nunca se matan."""
    propios = {os.getpid()}
    with contextlib.suppress(Exception):
        propios.add(os.getppid())
    with contextlib.suppress(Exception):
        propios.add(os.getpgrp())
    with contextlib.suppress(Exception):
        import psutil
        p = psutil.Process()
        propios.update(a.pid for a in p.parents())
        propios.update(c.pid for c in p.children(recursive=True))
    return propios


def _norm(name: str) -> str:
    return (name or "").strip().lower().removesuffix(".exe")


def alternativa(name: str) -> str:
    for patron, txt in _ALTERNATIVAS:
        if patron.search(name or ""):
            return txt
    return _GENERICA


def is_untouchable_process(name: str | None = None, pid: int | None = None,
                           cmdline: str | None = None) -> tuple[bool, str]:
    """(True, motivo) si el proceso NO se puede matar nunca."""
    if pid == 1:
        return True, "es el proceso 1 (init); matarlo reinicia la máquina"
    if pid is not None and pid in own_pids():
        return True, "soy yo, o el proceso que me está ejecutando"

    n = _norm(name)
    cl = (cmdline or "").lower()
    for clave, motivo in PROC_REASONS.items():
        k = clave.lower()
        # `n.startswith(k)` cubre a la vez: nombre exacto, la truncación de
        # `comm` a 15 chars (gnome-session-binary -> "gnome-session-b") y las
        # familias (pipewire-pulse, gdm3, mutter-x11-frames, systemd-*).
        # Ninguna app de usuario normal empieza por uno de estos prefijos.
        if n.startswith(k) or (cl and re.search(rf"(^|/|\s){re.escape(k)}(\s|$|/)", cl)):
            return True, motivo
    return False, ""


def explicar() -> str:
    """Texto para la consulta 'qué no puedes tocar y por qué' (ruta parser)."""
    procs = "\n".join(f"  · {k} — {v}" for k, v in PROC_REASONS.items())
    units = "\n".join(f"  · {k} — {v}" for k, v in UNIT_REASONS.items())
    return (
        "Procesos que NO mato nunca, senor (ni aunque me lo pidas):\n"
        f"{procs}\n"
        "  · (además) el proceso 1 (init), yo mismo y mi árbol de procesos, y "
        "cualquier proceso del sistema mientras haya una instalación de "
        "paquetes en curso.\n\n"
        "Servicios de systemd que NO paro ni reinicio:\n"
        f"{units}\n"
        "  · (además) tu sesión de usuario (user@N.service).\n\n"
        "En todos, si me lo pides te explico por qué y te doy la alternativa "
        "correcta; no hay forma de forzarlo desde aquí."
    )


def is_untouchable_unit(unit: str | None = None) -> tuple[bool, str]:
    """(True, motivo) si la unidad de systemd NO se puede parar/reiniciar."""
    u = (unit or "").strip()
    if not u.endswith((".service", ".socket", ".target", ".slice")):
        u_svc = u + ".service"
    else:
        u_svc = u
    if u_svc in UNIT_REASONS:
        return True, UNIT_REASONS[u_svc]
    for patron, motivo in _UNIT_PATTERNS:
        if patron.search(u) or patron.search(u_svc):
            return True, motivo
    return False, ""
