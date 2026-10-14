"""JARVIS Local - Caché de decisiones del agente (TAREA C6).

Cachea sólo la ELECCIÓN del modelo: `frase normalizada -> [(herramienta, args), ...]`.
La EJECUCIÓN de la herramienta NUNCA se cachea: el clima, el estado del sistema
o una búsqueda de empleo se re-ejecutan siempre con datos frescos.

Sirve para no pagar los 20-70 s de tool-calling cuando el usuario repite una
frase igual o casi igual en poco tiempo ("otra vez", "de nuevo lo mismo").

Guarda una LISTA de decisiones, no una sola: un turno puede encadenar varias
herramientas ("busca trabajo y abre la primera oferta"), y antes `put()`
sobrescribía con la última llamada de cada turno — un repeat de la frase
exacta dentro del TTL sólo reejecutaba esa última, perdiendo las anteriores
en silencio.

En memoria del proceso, TTL corto y tamaño máximo: no persiste a disco (una
decisión de hace horas puede haber quedado obsoleta por cambios de contexto).
"""
import re
import time

_TTL_S = 600          # 10 min: pasado ese tiempo la decisión se re-consulta
_MAX = 128            # entradas; al desbordar se descarta la más antigua

# frase normalizada -> (guardado_en, [(herramienta, args), ...])
_CACHE: dict[str, tuple[float, list[tuple[str, dict]]]] = {}

_WS = re.compile(r"\s+")
_TILDES = str.maketrans("áéíóúÁÉÍÓÚüÜ", "aeiouAEIOUuU")


def _key(frase: str) -> str:
    t = (frase or "").translate(_TILDES).lower().strip()
    t = _WS.sub(" ", t)
    return t.rstrip(" .!?")


def get(frase: str) -> list[tuple[str, dict]] | None:
    """Devuelve la lista [(herramienta, args), ...] si hay una decisión
    fresca para esta frase — en el orden en que se ejecutaron."""
    k = _key(frase)
    hit = _CACHE.get(k)
    if hit is None:
        return None
    guardado, decisiones = hit
    if time.time() - guardado > _TTL_S:
        _CACHE.pop(k, None)
        return None
    return [(tool, dict(args)) for tool, args in decisiones]


def put(frase: str, decisiones: list[tuple[str, dict]]) -> None:
    """Guarda la lista completa de decisiones (herramienta + args, en
    orden) que resolvieron este turno."""
    decisiones = [(tool, dict(args)) for tool, args in decisiones if tool]
    if not decisiones:
        return
    k = _key(frase)
    if k not in _CACHE and len(_CACHE) >= _MAX:
        # descartar la entrada más antigua
        mas_vieja = min(_CACHE, key=lambda kk: _CACHE[kk][0])
        _CACHE.pop(mas_vieja, None)
    _CACHE[k] = (time.time(), decisiones)


def clear() -> None:
    _CACHE.clear()
