"""
JARVIS Local - Resumen del dia

"dame el resumen del dia": saludo + fecha + clima + agenda + titulares en una
sola respuesta. Cada seccion es independiente: si una falla (sin internet,
sin credenciales de Calendar), las demas salen igual.
"""
from datetime import datetime

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes",
         "sabado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _saludo() -> str:
    h = datetime.now().hour
    if h < 12:
        return "Buenos dias"
    if h < 19:
        return "Buenas tardes"
    return "Buenas noches"


def _fecha() -> str:
    now = datetime.now()
    return (f"{_DIAS[now.weekday()]} {now.day} de {_MESES[now.month - 1]} "
            f"de {now.year}, {now.strftime('%I:%M %p').lstrip('0').lower()}")


def _seccion_clima() -> str | None:
    from jarvis_local.tools.location import my_location
    from jarvis_local.tools.weather import get_weather
    loc = my_location()
    if not loc or not loc.get("city"):
        return None
    plan = get_weather(loc["city"])
    if plan.status != ActionStatus.EXECUTED or not plan.result:
        return None
    return plan.result


def _seccion_agenda() -> str | None:
    from jarvis_local.tools.gcalendar import upcoming_events
    plan = upcoming_events(limit=5)
    if plan.status != ActionStatus.EXECUTED or not plan.result:
        return None
    return plan.result


def _seccion_noticias() -> str | None:
    from jarvis_local.tools.news import headlines
    plan = headlines(limit=4)
    if plan.status != ActionStatus.EXECUTED or not plan.result:
        return None
    return plan.result


def daily_briefing() -> ActionPlan:
    """Resumen del dia: clima + agenda + noticias, tolerante a fallos."""
    plan = ActionPlan(action="resumen_del_dia", risk=RiskLevel.READ,
                      reason="Operacion de solo lectura")
    partes = [f"{_saludo()}, senor. Hoy es {_fecha()}."]
    fallidas = []
    for titulo, seccion in (("El clima", _seccion_clima),
                            ("Su agenda", _seccion_agenda),
                            ("Las noticias", _seccion_noticias)):
        try:
            texto = seccion()
        except Exception:
            texto = None
        if texto:
            partes.append(f"{titulo}: {texto.strip()}")
        else:
            fallidas.append(titulo.lower())
    if fallidas:
        partes.append("No pude consultar " + " ni ".join(fallidas) + ".")
    plan.result = "\n\n".join(partes)
    plan.status = ActionStatus.EXECUTED
    return plan
