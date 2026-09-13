"""JARVIS Local - Auditoría append-only (PLAN_EJECUCION FASE D · D2).

Registro inmutable de TODA acción de escritura / destructiva / de sistema:
qué herramienta, cuándo, con qué parámetros, el `VerifyOutcome` de D1
(`plan.params["verify"]`) y si hubo confirmación explícita del usuario.

Propiedades:

  - **Append-only de verdad**: cada escritura abre el fichero con `O_APPEND`
    (el kernel garantiza que el `write` va al final aunque haya escritores
    concurrentes) y hace `fsync`. NO hay API de update ni delete. Se puede
    endurecer a nivel de FS con `chattr +a logs/audit.jsonl` (ext4).
  - **Rotación por tamaño**: al pasar de `audit_max_bytes` el fichero se
    rota a `audit-<timestamp>.jsonl` y se conservan los últimos `audit_keep`.
  - **Redacta secretos** (`safety/secrets`) en parámetros y en el texto del
    resultado ANTES de escribir: la auditoría no puede ser el agujero por
    donde se filtre lo que la capa 0 ya tapa para el modelo y los logs.
  - **Consultable** por el propio JARVIS por la ruta del parser (sin agente):
    `tools/audit_query.py` ("qué hiciste hoy", "qué cambiaste ayer").

Solo se audita `risk >= CREATE` (crear/ejecutar/borrar/sistema). Lecturas no.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
from datetime import date, datetime
from pathlib import Path

from jarvis_local.config import BASE_DIR, get_config
from jarvis_local.safety.policy import RiskLevel
from jarvis_local.safety.secrets import redact_secrets

# Riesgos que SÍ se auditan (una acción que cambia o puede cambiar la máquina).
_AUDITED = {RiskLevel.CREATE, RiskLevel.EXECUTE, RiskLevel.DELETE, RiskLevel.CRITICAL}

_OUTCOME_MAX = 400  # el texto de resultado se trunca: la auditoría no es un log de salidas


def _redact_value(v):
    if isinstance(v, str):
        red, _ = redact_secrets(v)
        return red
    if isinstance(v, dict):
        return {k: _redact_value(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_redact_value(x) for x in v]
    return v


class AuditLog:
    def __init__(self, path: Path | None = None, *, max_bytes: int | None = None,
                 keep: int | None = None):
        cfg = get_config().get("logging", {})
        if path:
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_dir = (BASE_DIR / cfg.get("dir", "logs")).resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
            self.path = log_dir / cfg.get("audit_log", "audit.jsonl")
        self.max_bytes = int(max_bytes if max_bytes is not None
                             else cfg.get("audit_max_bytes", 5 * 1024 * 1024))
        self.keep = int(keep if keep is not None else cfg.get("audit_keep", 10))
        self._lock = threading.Lock()

    # -- escritura (append-only) --------------------------------------------

    def _rotate_if_needed(self, next_line_bytes: int) -> None:
        try:
            size = self.path.stat().st_size
        except OSError:
            return
        if size + next_line_bytes < self.max_bytes:
            return
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
        rotated = self.path.with_name(f"{self.path.stem}-{stamp}{self.path.suffix}")
        n = 1
        while rotated.exists():  # colisión (mismo microsegundo): desempatar
            rotated = self.path.with_name(f"{self.path.stem}-{stamp}-{n}{self.path.suffix}")
            n += 1
        try:
            os.replace(self.path, rotated)
        except OSError:
            return
        viejos = sorted(self.path.parent.glob(f"{self.path.stem}-*{self.path.suffix}"))
        for f in viejos[:-self.keep] if self.keep > 0 else viejos:
            with contextlib.suppress(OSError):
                f.unlink()

    def _append(self, entry: dict) -> None:
        line = (json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            self._rotate_if_needed(len(line))
            fd = os.open(str(self.path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)

    def record(self, *, tool: str, risk, params: dict | None, verify: dict | None,
               status: str, outcome: str = "", confirmed: bool | None = None,
               source: str = "") -> bool:
        """Registra una acción. Devuelve True si se escribió (risk auditado)."""
        risk_name = risk.name if isinstance(risk, RiskLevel) else str(risk or "")
        if isinstance(risk, RiskLevel) and risk not in _AUDITED:
            return False
        red_outcome, _ = redact_secrets(outcome or "")
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "risk": risk_name,
            "params": _redact_value(params or {}),
            "verify": verify,  # ya viene de plan.params["verify"] (D1); dict o None
            "confirmed": confirmed,
            "status": str(status or ""),
            "outcome": red_outcome[:_OUTCOME_MAX],
            "source": source,
        }
        self._append(entry)
        return True

    def record_plan(self, plan, *, source: str, confirmed: bool | None = None,
                    tool_name: str | None = None) -> bool:
        """Registra desde un `ActionPlan` (el caso normal)."""
        params = dict(getattr(plan, "params", {}) or {})
        verify = params.pop("verify", None)
        status = getattr(getattr(plan, "status", None), "value", "") or ""
        outcome = getattr(plan, "result", "") or getattr(plan, "error", "") or ""
        return self.record(
            tool=tool_name or getattr(plan, "action", "") or "?",
            risk=getattr(plan, "risk", None),
            params=params, verify=verify, status=status, outcome=outcome,
            confirmed=confirmed, source=source)

    # -- lectura (para D2.3: la consulta desde JARVIS) ---------------------

    def _iter_files(self) -> list[Path]:
        rotados = sorted(self.path.parent.glob(f"{self.path.stem}-*{self.path.suffix}"))
        return [*rotados, self.path]

    def read(self, *, since: datetime | None = None, until: datetime | None = None,
             limit: int = 1000) -> list[dict]:
        """Entradas entre `since` y `until` (incl.), más recientes al final."""
        out: list[dict] = []
        for f in self._iter_files():
            if not f.exists():
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            for ln in text.splitlines():
                if not ln.strip():
                    continue
                try:
                    e = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                ts = _parse_ts(e.get("ts"))
                if ts is None:
                    continue
                if since and ts < since:
                    continue
                if until and ts > until:
                    continue
                out.append(e)
        out.sort(key=lambda e: e.get("ts", ""))
        return out[-limit:]

    def for_day(self, day: date, limit: int = 1000) -> list[dict]:
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        return self.read(since=start, until=end, limit=limit)

    def last_entry(self) -> dict | None:
        """Última entrada registrada (FASE I · I5: "última sesión" del HUD).

        A diferencia de `read()`, NUNCA carga el histórico completo: sólo la
        cola del fichero activo (y, si acaba de rotar y está vacío, la del
        rotado más reciente). Se sondea cada 2 s desde el HUD — tiene que ser
        barato sin importar cuánto pese `audit.jsonl`."""
        files = self._iter_files()
        for f in (files[-1], *reversed(files[:-1])):  # activo primero, luego rotados
            try:
                if not f.exists() or f.stat().st_size == 0:
                    continue
                with f.open("rb") as fh:
                    fh.seek(0, os.SEEK_END)
                    size = fh.tell()
                    fh.seek(max(0, size - 4096))
                    tail = fh.read().decode("utf-8", errors="ignore")
            except OSError:
                continue
            for ln in reversed(tail.splitlines()):
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    return json.loads(ln)
                except json.JSONDecodeError:
                    continue
        return None


def _parse_ts(s) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# Instancia compartida (como `logger` en safety/logger.py).
audit = AuditLog()
