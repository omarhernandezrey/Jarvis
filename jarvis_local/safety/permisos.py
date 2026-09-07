"""PLAN_EJECUCION FASE E · E2 — modelo de permisos.

Aplica a la oleada E y a las siguientes (F, G). Tres niveles, por el
`RiskLevel` del contrato de la herramienta:

  READ                 -> se ejecuta sin preguntar.
  CREATE / EXECUTE      -> se ejecuta y se VERIFICA (D1: `verify.finish`).
  DELETE / CRITICAL     -> CONFIRMACIÓN explícita del usuario, mostrando
                           exactamente QUÉ y SOBRE QUÉ, con cancelación
                           (/confirmar · /cancelar); luego se ejecuta y se
                           verifica.

Todo —lectura incluida cuando cambia algo, escritura y destructivo— queda en
la auditoría append-only de D2.

**Nada de sudo implícito.** JARVIS nunca invoca `sudo`. Si una acción necesita
root, se BLOQUEA con la regla de sudoers CONCRETA que habría que añadir y se
le pide al usuario (`bloqueo_por_sudo`). Ver `docs/PERMISOS_SUDO.md`.
"""
from __future__ import annotations

import os
import re

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

# --- los tres niveles ------------------------------------------------------
_NIVEL = {
    RiskLevel.NONE: "auto",
    RiskLevel.READ: "auto",
    RiskLevel.CREATE: "verificar",
    RiskLevel.EXECUTE: "verificar",
    RiskLevel.DELETE: "confirmar",
    RiskLevel.CRITICAL: "confirmar",
}


def nivel(risk: RiskLevel) -> str:
    """'auto' | 'verificar' | 'confirmar'."""
    return _NIVEL.get(risk, "confirmar")


def exige_confirmacion(risk: RiskLevel) -> bool:
    return nivel(risk) == "confirmar"


def texto_confirmacion(verbo: str, objetivo: str,
                       detalles: dict | None = None) -> str:
    """Renderizador CANÓNICO de la confirmación: mismo formato para toda la
    oleada. Muestra qué (`verbo`) y sobre qué (`objetivo` + `detalles`)."""
    lineas = [f"Voy a {verbo}: {objetivo}"]
    for k, v in (detalles or {}).items():
        lineas.append(f"  {k}: {v}")
    lineas.append("Escribe /confirmar para hacerlo o /cancelar para dejarlo.")
    return "\n".join(lineas)


# --- sudo: nunca implícito ----------------------------------------------------
# Reglas concretas para /etc/sudoers.d/jarvis (`sudo visudo -f`). Se
# entregan al usuario cuando una acción las necesita; JARVIS no las usa solo.
SUDOERS_RULES: dict[str, str] = {
    # Parar/arrancar/reiniciar UNA unidad de SISTEMA concreta (E4). Se
    # plantea por unidad, no en bloque: NOPASSWD a `systemctl *` es un
    # agujero. `<UNIDAD>` se sustituye por la unidad exacta.
    "systemctl_sistema": (
        "%sudo ALL=(root) NOPASSWD: /usr/bin/systemctl start <UNIDAD>, "
        "/usr/bin/systemctl stop <UNIDAD>, /usr/bin/systemctl restart <UNIDAD>"
    ),
    # Matar un proceso de OTRO usuario (E3). No se recomienda una regla:
    # hazlo tú.
    "kill_otro_usuario": (
        "# No hay regla: matar procesos de otros usuarios lo haces tú con "
        "`sudo kill <PID>`. JARVIS no lo hará."
    ),
}


def bloqueo_por_sudo(capacidad: str, objetivo: str, hazlo_tu: str) -> ActionPlan:
    """ActionPlan BLOQUEADO cuando la acción necesitaría root. Trae la regla
    de sudoers concreta y la alternativa manual."""
    regla = SUDOERS_RULES.get(capacidad, "# (sin regla predefinida)")
    plan = ActionPlan(action="bloqueado_sudo",
                      params={"capacidad": capacidad, "objetivo": objetivo},
                      risk=RiskLevel.CRITICAL, status=ActionStatus.BLOCKED,
                      reason=f"{objetivo} necesita permisos de administrador")
    plan.result = (
        f"Eso necesita permisos de administrador y yo no uso sudo, senor "
        f"({objetivo}).\n"
        f"Para habilitarlo, añade a /etc/sudoers.d/jarvis (con "
        f"`sudo visudo -f /etc/sudoers.d/jarvis`):\n"
        f"    {regla}\n"
        f"Mientras tanto, hazlo tú: {hazlo_tu}"
    )
    return plan


# --- comprobaciones de propiedad --------------------------------------------

def proceso_es_del_usuario(pid: int) -> bool | None:
    """True si el proceso `pid` pertenece al usuario que ejecuta JARVIS
    (matable sin sudo). None si no se pudo determinar."""
    try:
        import psutil
        return psutil.Process(pid).uids().real == os.getuid()
    except Exception:
        return None


def unidad_es_de_sistema(scope: str) -> bool:
    """`scope` viene de la herramienta: 'user' -> unidad de usuario (sin sudo);
    cualquier otra cosa -> unidad de sistema (necesita sudo)."""
    return (scope or "system").strip().lower() != "user"


# --- transacción de paquetes en curso -------------------------------------
# Proteger `dpkg`/`apt` POR NOMBRE no basta: lo que importa es la transacción.
# El lock de dpkg no se puede sondear de forma fiable sin ser root (dpkg usa
# locks fcntl F_SETLK y el fichero es 640 de root). La señal práctica: hay un
# proceso de gestor de paquetes TRANSITORIO corriendo (`dpkg`, `apt`,
# `apt-get`, `aptitude`, `unattended-upgrade` — solo existen durante una
# transacción; `snapd`/`packagekitd` son demonios siempre vivos y no cuentan).
_PKG_TX = re.compile(r"^(?:dpkg(?:-\w+)?|apt|apt-get|aptitude|unattended-upgr)")


def transaccion_de_paquetes_en_curso() -> bool:
    """True si hay una instalación/actualización de paquetes en marcha. Barato
    (una pasada de process_iter)."""
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if _PKG_TX.match((p.info.get("name") or "").lower()):
                return True
    except Exception:
        pass
    return False


def bloqueo_por_transaccion(objetivo: str) -> ActionPlan:
    """ActionPlan BLOQUEADO: hay una transacción de paquetes en curso y la
    acción (`objetivo`) podría interferir con ella o con sus scripts de
    mantenimiento (que corren como root)."""
    plan = ActionPlan(action="bloqueado_transaccion",
                      params={"objetivo": objetivo},
                      risk=RiskLevel.CRITICAL, status=ActionStatus.BLOCKED,
                      reason="Transacción de paquetes en curso")
    plan.result = (
        f"Ahora no, senor: hay una instalación o actualización de paquetes en "
        f"curso. {objetivo} podría dejar el sistema a medias (un `postinst` "
        f"corriendo, un servicio reiniciándose). Espera unos minutos y "
        f"vuelve a pedírmelo."
    )
    return plan
