"""
JARVIS Local - Utilidades de Rendimiento
Módulo centralizado para operaciones de alto rendimiento.
"""
import json

from jarvis_local.logging_config import get_logger

logger = get_logger("performance")

# Intentar importar orjson para mejor rendimiento
try:
    import orjson
    HAS_ORJSON = True
    logger.debug("orjson disponible - rendimiento JSON mejorado")
except ImportError:
    HAS_ORJSON = False
    logger.debug("orjson no disponible - usando json estándar")


def dumps(obj, **kwargs) -> str:
    """Serializa objeto a JSON string."""
    if HAS_ORJSON:
        return orjson.dumps(obj).decode('utf-8')
    return json.dumps(obj, ensure_ascii=False, **kwargs)


def loads(s: str, **kwargs):
    """Deserializa JSON string a objeto."""
    if HAS_ORJSON:
        return orjson.loads(s)
    return json.loads(s, **kwargs)


def dumps_bytes(obj, **kwargs) -> bytes:
    """Serializa objeto a JSON bytes (más rápido)."""
    if HAS_ORJSON:
        return orjson.dumps(obj)
    return json.dumps(obj, ensure_ascii=False, **kwargs).encode('utf-8')


def loads_bytes(b: bytes, **kwargs):
    """Deserializa JSON bytes a objeto."""
    if HAS_ORJSON:
        return orjson.loads(b)
    return json.loads(b.decode('utf-8'), **kwargs)


# Intentar importar httpx para mejor rendimiento HTTP
try:
    import httpx
    HAS_HTTPX = True
    logger.debug("httpx disponible - rendimiento HTTP mejorado")
except ImportError:
    HAS_HTTPX = False
    logger.debug("httpx no disponible - usando requests")


def get_http_client(**kwargs):
    """Obtiene cliente HTTP (httpx si está disponible, requests si no)."""
    if HAS_HTTPX:
        return httpx.Client(**kwargs)
    import requests
    return requests.Session()


def async_http_client(**kwargs):
    """Obtiene cliente HTTP async (solo httpx)."""
    if HAS_HTTPX:
        return httpx.AsyncClient(**kwargs)
    raise ImportError("httpx requerido para cliente async")
