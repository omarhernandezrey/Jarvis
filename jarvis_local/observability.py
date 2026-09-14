"""JARVIS Local - Observabilidad: una traza por petición.

PLAN_EJECUCION FASE J · J3. No se instrumenta nada de cero: `jarvis.py` ya
sabía qué capa de la cascada resolvía cada petición (`last_reply_kind`) y
`decisions.jsonl` (agente) / `audit.jsonl` (D2, VERIFY) ya registraban lo
suyo. Lo que faltaba era (a) un registro por petición con qué capas se
atravesaron y cuánto tardó cada una, y (b) una vista que las una.

No hay un id de petición compartido explícito entre los tres ficheros —
`jarvis.py` procesa una petición de forma secuencial y rápida, así que la
ventana de tiempo del propio turno ([ts_inicio, ts_fin]) basta para saber sin
ambigüedad qué líneas de `decisions.jsonl`/`audit.jsonl` le pertenecen.

    {"request_id": "...", "ts_inicio": "...", "ts_fin": "...",
     "entrada": "abre chrome", "capas": [{"capa": "parser", "ms": 4.1}],
     "capa_resuelta": "parser", "resultado": "Firefox abierto...",
     "elapsed_ms": 12.3}

Consulta rápida:
    python -m jarvis_local.observability            # última traza
    python -m jarvis_local.observability 5           # últimas 5
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from jarvis_local.agent.decision_log import LOG_PATH as _DECISIONS_PATH
from jarvis_local.config import BASE_DIR
from jarvis_local.logging_config import get_logger

logger = get_logger("observability")

TRACE_PATH = BASE_DIR / "logs" / "trace.jsonl"
_MAX_LINEAS = 2000
_MARGEN = timedelta(seconds=2)  # colchón para relojes/escrituras no atómicas


def record(*, request_id: str, entrada: str, capas: list[dict],
          capa_resuelta: str, resultado: str, elapsed_ms: float,
          ts_inicio: datetime, ts_fin: datetime) -> None:
    """Registra la traza de UNA petición completa. Nunca lanza excepción:
    una petición real no se cae porque falle su propia observabilidad."""
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "request_id": request_id,
            "ts_inicio": ts_inicio.isoformat(timespec="milliseconds"),
            "ts_fin": ts_fin.isoformat(timespec="milliseconds"),
            "entrada": (entrada or "")[:200],
            "capas": capas,
            "capa_resuelta": capa_resuelta,
            "resultado": (resultado or "")[:200],
            "elapsed_ms": round(elapsed_ms, 1),
        }
        with open(TRACE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _rotar()
    except Exception as e:
        logger.debug(f"Error escribiendo traza de observabilidad: {e}")


def _rotar() -> None:
    if not TRACE_PATH.exists():
        return
    try:
        lineas = TRACE_PATH.read_text(encoding="utf-8").splitlines()
        if len(lineas) > _MAX_LINEAS:
            TRACE_PATH.write_text("\n".join(lineas[-_MAX_LINEAS:]) + "\n",
                                  encoding="utf-8")
    except Exception as e:
        logger.debug(f"Error rotando traza de observabilidad: {e}")


def _leer_jsonl(path: Path, limite: int = 0) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out[-limite:] if limite else out


def _en_ventana(ts_str: str, ini: datetime, fin: datetime) -> bool:
    try:
        ts = datetime.fromisoformat(ts_str)
    except (TypeError, ValueError):
        return False
    return (ini - _MARGEN) <= ts <= (fin + _MARGEN)


def traza(n: int = 1) -> list[dict]:
    """Las últimas `n` peticiones, cada una enriquecida con lo que
    `decisions.jsonl` (herramientas/llamadas al LLM del agente) y
    `audit.jsonl` (resultado real de VERIFY) registraron en su ventana de
    tiempo. Más reciente al final, igual que los ficheros fuente."""
    base = _leer_jsonl(TRACE_PATH, n)
    if not base:
        return []
    decisiones = _leer_jsonl(_DECISIONS_PATH)
    try:
        from jarvis_local.safety.audit import audit
        auditoria = audit.read(limit=10_000)
    except Exception:
        auditoria = []

    enriquecidas = []
    for req in base:
        try:
            ini = datetime.fromisoformat(req["ts_inicio"])
            fin = datetime.fromisoformat(req["ts_fin"])
        except (KeyError, ValueError):
            enriquecidas.append(req)
            continue
        req = dict(req)
        req["decisiones_agente"] = [
            d for d in decisiones if _en_ventana(d.get("ts", ""), ini, fin)]
        req["auditoria_d2"] = [
            a for a in auditoria if _en_ventana(a.get("ts", ""), ini, fin)]
        enriquecidas.append(req)
    return enriquecidas


def formatear(req: dict) -> str:
    """Texto legible de una traza enriquecida (la que devuelve `traza()`)."""
    lineas = [
        f"Petición {req.get('request_id', '?')} — \"{req.get('entrada', '')}\"",
        f"  capa que resolvió: {req.get('capa_resuelta', '?')}"
        f"  ({req.get('elapsed_ms', '?')} ms totales)",
    ]
    for c in req.get("capas", []):
        marca = "coincidió" if c.get("coincidio") else "no coincidió"
        lineas.append(f"    · {c.get('capa')}: {c.get('ms')} ms ({marca})")
    for d in req.get("decisiones_agente", []):
        lineas.append(
            f"  agente: confianza={d.get('confianza')} "
            f"llm_calls={d.get('llm_calls')} llm_secs={d.get('llm_secs')} "
            f"herramientas={d.get('herramientas')} -> {d.get('resultado')}")
    for a in req.get("auditoria_d2", []):
        v = a.get("verify")
        v_txt = (f"ok={v.get('ok')} ({v.get('method')})" if isinstance(v, dict)
                else "sin verify")
        lineas.append(
            f"  auditoría: {a.get('tool')} [{a.get('risk')}] "
            f"status={a.get('status')} verify: {v_txt}")
    lineas.append(f"  resultado: {req.get('resultado', '')}")
    return "\n".join(lineas)


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    trazas = traza(n)
    if not trazas:
        print("No hay trazas registradas todavía.")
    for t in trazas:
        print(formatear(t))
        print()
