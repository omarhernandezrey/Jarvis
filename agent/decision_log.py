"""
JARVIS Local - Log estructurado de decisiones del router.

Cada decision de enrutamiento queda en un JSONL auditable: que pidio el usuario,
que confianza tuvo el retriever, que herramientas se ejecutaron y como termino.
Sin esto, un fallo de razonamiento solo se puede reproducir a mano.

    {"ts": "...", "entrada": "abre chrome", "confianza": 0.6,
     "herramientas": ["abrir_aplicacion"], "resultado": "ok"}

Analisis rapido:
    python -m jarvis_local.agent.decision_log        # resumen
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from jarvis_local.config import BASE_DIR

LOG_PATH = BASE_DIR / "logs" / "decisions.jsonl"
MAX_LINEAS = 5000  # rotacion simple: el log no debe crecer sin limite


def log_decision(entrada: str, confianza: float, herramientas: list[str],
                 salidas: list[str], resultado: str) -> None:
    """Registra una decision de enrutamiento. Nunca lanza excepcion."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        registro = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "entrada": entrada[:200],
            "confianza": round(float(confianza), 3),
            "herramientas": herramientas,
            "resultado": resultado,
            "salida": (salidas[-1][:160] if salidas else ""),
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        _rotar()
    except Exception:
        pass  # el log jamas debe tumbar una conversacion


def _rotar() -> None:
    if not LOG_PATH.exists():
        return
    try:
        lineas = LOG_PATH.read_text(encoding="utf-8").splitlines()
        if len(lineas) > MAX_LINEAS:
            LOG_PATH.write_text("\n".join(lineas[-MAX_LINEAS:]) + "\n",
                                encoding="utf-8")
    except Exception:
        pass


def leer(limite: int = 0) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    registros = []
    for linea in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            registros.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return registros[-limite:] if limite else registros


def resumen() -> str:
    """Resumen auditable: como se estan resolviendo las peticiones."""
    regs = leer()
    if not regs:
        return "Sin decisiones registradas todavia."

    resultados = Counter(r["resultado"] for r in regs)
    herramientas = Counter(h for r in regs for h in r["herramientas"])
    sin_ruta = [r for r in regs
                if r["resultado"] == "sin_herramientas_plausibles"]
    aclaraciones = [r for r in regs if r["resultado"] == "aclaracion"]

    lineas = [f"Decisiones registradas: {len(regs)}", "", "Resultados:"]
    for res, n in resultados.most_common():
        lineas.append(f"  {n:5}  {res}")
    lineas += ["", "Herramientas mas usadas:"]
    for h, n in herramientas.most_common(10):
        lineas.append(f"  {n:5}  {h}")
    lineas += ["",
               f"Fueron a conversacion sin herramienta: {len(sin_ruta)}",
               f"Pidieron aclaracion: {len(aclaraciones)}"]
    if sin_ruta:
        lineas += ["", "Ultimas que no encontraron herramienta (revisar si"
                   " deberian tenerla):"]
        for r in sin_ruta[-5:]:
            lineas.append(f"  ({r['confianza']}) {r['entrada'][:60]}")
    return "\n".join(lineas)


if __name__ == "__main__":
    print(resumen())
