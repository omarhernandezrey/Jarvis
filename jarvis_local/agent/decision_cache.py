"""JARVIS Local - Caché de decisiones del agente (TAREA C6).

Cachea sólo la ELECCIÓN del modelo: `frase normalizada -> (herramienta, args)`.
La EJECUCIÓN de la herramienta NUNCA se cachea: el clima, el estado del sistema
o una búsqueda de empleo se re-ejecutan siempre con datos frescos.

Sirve para no pagar los 20-70 s de tool-calling cuando el usuario repite una
frase igual o casi igual en poco tiempo ("otra vez", "de nuevo lo mismo").

En memoria del proceso, TTL corto y tamaño máximo: no persiste a disco (una
decisión de hace horas puede haber quedado obsoleta por cambios de contexto).
"""
import re
import time

_TTL_S = 600          # 10 min: pasado ese tiempo la decisión se re-consulta
_MAX = 128            # entradas; al desbordar se descarta la más antigua

# frase normalizada -> (guardado_en, herramienta, args)
_CACHE: dict[str, tuple[float, str, dict]] = {}

_WS = re.compile(r"\s+")
_TILDES = str.maketrans("áéíóúÁÉÍÓÚüÜ", "aeiouAEIOUuU")


def _key(frase: str) -> str:
    t = (frase or "").translate(_TILDES).lower().strip()
    t = _WS.sub(" ", t)
    return t.rstrip(" .!?")


def get(frase: str) -> tuple[str, dict] | None:
    """Devuelve (herramienta, args) si hay una decisión fresca para esta frase."""
    k = _key(frase)
    hit = _CACHE.get(k)
    if hit is None:
        return None
    guardado, tool, args = hit
    if time.time() - guardado > _TTL_S:
        _CACHE.pop(k, None)
        return None
    return tool, dict(args)


def put(frase: str, tool: str, args: dict) -> None:
    """Guarda la decisión (herramienta + args) para esta frase."""
    if not tool:
        return
    k = _key(frase)
    if k not in _CACHE and len(_CACHE) >= _MAX:
        # descartar la entrada más antigua
        mas_vieja = min(_CACHE, key=lambda kk: _CACHE[kk][0])
        _CACHE.pop(mas_vieja, None)
    _CACHE[k] = (time.time(), tool, dict(args))


def clear() -> None:
    _CACHE.clear()
