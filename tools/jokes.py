"""
JARVIS Local - Chistes (Fase 4)
Chistes en espanol, 100% offline, con el tono formal de JARVIS.
"""
import random
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus

_JOKES = [
    "Por que los programadores confunden Halloween con Navidad? Porque OCT 31 es igual a DEC 25.",
    "Un byte le pregunta a otro: estas mal? Y el otro responde: no, solo un poco apagado.",
    "Cuantos programadores hacen falta para cambiar un bombillo? Ninguno, es un problema de hardware.",
    "Que le dijo un bit al otro? Nos vemos en el bus.",
    "Hay 10 tipos de personas: las que entienden binario y las que no.",
    "Por que el computador fue al medico? Porque tenia un virus.",
    "Que hace una abeja en el gimnasio? Zum-ba.",
    "Como se despiden los quimicos? Acido un placer.",
    "Que le dice un jaguar a otro jaguar? Jaguar you?",
    "Por que las focas del circo miran siempre hacia arriba? Porque es donde estan los focos.",
    "Que le dice el cero al ocho? Bonito cinturon.",
    "Como llama el vaquero a su hija? Hiiiiiiiiiija.",
    "Que hace un pez? Nada.",
    "Cual es el cafe mas peligroso del mundo? El ex-preso.",
    "Por que el libro de matematicas estaba triste? Porque tenia muchos problemas.",
    "Mi codigo funciona y no se por que. Mi codigo no funciona y tampoco se por que.",
    "Un SQL entra a un bar, se acerca a dos mesas y pregunta: puedo unirme (JOIN)?",
    "No es un bug, senor, es una funcionalidad no documentada.",
]


def tell_joke() -> ActionPlan:
    plan = ActionPlan(action="chiste", risk=RiskLevel.READ,
                      reason="Contar un chiste (offline)")
    plan.result = random.choice(_JOKES)
    plan.status = ActionStatus.EXECUTED
    return plan
