"""PLAN_EJECUCION FASE E · E0 — presupuesto de memoria (bloqueante).

`docs/OPERACION_MEMORIA.md` documenta la política; esto la implementa. Sin
`psutil` ni `fork`: una lectura de `/proc/meminfo`.

Con bge-m3 (~1,3 GB) + llama3.2:3b (~2,3 GB) residentes (`keep_alive: 30m` de
C4/C5) sobre un escritorio ya pesado, este equipo entra en swap y cada turno
del agente pasa de segundos a minutos. La FASE E añade trabajo por turno, así
que:

  - tras `select_tools()` (última vez que el turno toca bge-m3), si la RAM
    disponible cae por debajo del umbral, se suelta bge-m3 de memoria;
  - se detecta el swap de forma barata;
  - cuando se detecta, JARVIS lo DICE ("voy degradado por memoria") en vez de
    limitarse a tardar cinco minutos.

En un SO sin `/proc/meminfo` (Windows) todo esto es no-op.
"""
from __future__ import annotations

# Umbrales de docs/OPERACION_MEMORIA.md §3.
MEM_AVAILABLE_MIN_KB = 800_000     # por debajo: no hay sitio para otro modelo
SWAP_USADO_WARN_KB = 200_000       # por encima: hay páginas en swap
# Swap OCUPADO no es lo mismo que THRASHING: tras una sesión pesada quedan
# GB en swap aunque la RAM ya esté libre y esas páginas frías no se vuelvan a
# tocar. "Degradado" = hay swap en uso Y además queda poca RAM disponible
# (headroom por debajo del cual un turno sí va a paginar de verdad).
MEM_DEGRADADO_KB = 2_000_000

_MEMINFO = "/proc/meminfo"


def _leer_meminfo() -> dict[str, int]:
    """{clave: kB}. Vacío si no hay /proc/meminfo (no-Linux) o no se pudo leer."""
    try:
        out: dict[str, int] = {}
        with open(_MEMINFO, encoding="ascii") as f:
            for linea in f:
                clave, _, resto = linea.partition(":")
                partes = resto.split()
                if partes:
                    out[clave.strip()] = int(partes[0])
        return out
    except (OSError, ValueError):
        return {}


def snapshot() -> dict:
    """Estado de memoria de un vistazo. `disponible=False` si no se pudo leer."""
    m = _leer_meminfo()
    if "MemAvailable" not in m:
        return {"disponible": False}
    mem_av = m["MemAvailable"]
    swap_usado = max(0, m.get("SwapTotal", 0) - m.get("SwapFree", 0))
    hay_swap = swap_usado > SWAP_USADO_WARN_KB
    return {
        "disponible": True,
        "mem_available_kb": mem_av,
        "swap_usado_kb": swap_usado,
        "ajustado": mem_av < MEM_AVAILABLE_MIN_KB,
        "en_swap": hay_swap,
        "degradado": hay_swap and mem_av < MEM_DEGRADADO_KB,
    }


def ajustado() -> bool:
    """True si `MemAvailable` está por debajo del umbral: no cabe otro modelo."""
    return bool(snapshot().get("ajustado"))


def en_swap() -> bool:
    """True si hay páginas en swap (ocupado — no implica thrashing)."""
    return bool(snapshot().get("en_swap"))


def degradado() -> bool:
    """True si hay swap en uso Y además poca RAM disponible: el turno va a
    paginar de verdad."""
    return bool(snapshot().get("degradado"))


def aviso_degradado() -> str | None:
    """Frase para anteponer a la respuesta cuando el equipo va a ir lento por
    memoria. None si no (o si no se pudo medir)."""
    s = snapshot()
    if not s.get("degradado"):
        return None
    libre_mb = s["mem_available_kb"] // 1024
    return (f"Voy a ir lento, senor: la RAM esta al limite ({libre_mb} MB "
            "disponibles) y el sistema esta en swap. Cierre alguna aplicacion "
            "o pidame que quite el modelo de embeddings de memoria.")


def soltar_embeddings() -> bool:
    """Descarga bge-m3 de RAM (`keep_alive: 0`). Best-effort; True si la
    petición se envió. El coste es ~2-3 s de recarga en el turno siguiente,
    barato frente a minutos de swap."""
    try:
        import requests

        from jarvis_local.config import get_config
        from jarvis_local.storage.semantic import EMBED_MODEL
        host = get_config()["ollama"].get("host", "http://localhost:11434")
        requests.post(
            f"{host}/api/embed",
            json={"model": EMBED_MODEL, "input": ["x"], "keep_alive": 0},
            timeout=8,
        )
        return True
    except Exception:
        return False


def linea_estado() -> str:
    """Una línea para `estado_del_sistema` — hace consultable la señal."""
    s = snapshot()
    if not s.get("disponible"):
        return "Memoria: no medible en este sistema."
    libre_mb = s["mem_available_kb"] // 1024
    swap_mb = s["swap_usado_kb"] // 1024
    if s["degradado"]:
        estado = "DEGRADADO (poca RAM + en swap)"
    elif s["en_swap"]:
        estado = "swap ocupado pero RAM holgada (páginas frías)"
    elif s["ajustado"]:
        estado = "ajustada"
    else:
        estado = "holgada"
    return f"Memoria: {libre_mb} MB disponibles, swap {swap_mb} MB — {estado}."
