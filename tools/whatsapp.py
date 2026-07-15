"""
JARVIS Local - Envio de WhatsApp

"enviale un whatsapp a juan diciendo que ya voy" abre WhatsApp (la app de
escritorio si esta instalada, o WhatsApp Web) con el chat y el mensaje ya
escritos: el usuario solo pulsa enviar. JARVIS nunca envia solo.

Los contactos viven en data/contacts.json: {"juan": "573001234567", ...}
"""
import json
import os
import re
import unicodedata
import urllib.parse
import webbrowser

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel

CONTACTS_PATH = os.path.join(os.path.dirname(__file__), "..", "data",
                             "contacts.json")

# Indicativo por defecto para numeros locales de 10 digitos (Colombia)
DEFAULT_COUNTRY_CODE = "57"


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _load_contacts() -> dict:
    if not os.path.exists(CONTACTS_PATH):
        return {}
    try:
        with open(CONTACTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_contacts(contacts: dict) -> None:
    os.makedirs(os.path.dirname(CONTACTS_PATH), exist_ok=True)
    with open(CONTACTS_PATH, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=1)


def _normalize_phone(raw: str) -> str | None:
    """Deja solo digitos y completa el indicativo si es un celular local."""
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    if len(digits) == 10:
        digits = DEFAULT_COUNTRY_CODE + digits
    return digits if 10 <= len(digits) <= 15 else None


def _resolve_recipient(to: str) -> tuple[str | None, str]:
    """(telefono, nombre_mostrado) a partir de un nombre o un numero."""
    to = to.strip()
    digitos = re.sub(r"[^\d]", "", to)
    if len(digitos) >= 7:  # es un numero, no un nombre
        return _normalize_phone(to), to
    contacts = _load_contacts()
    key = _norm(to)
    if key in contacts:
        return _normalize_phone(contacts[key]), to
    # busqueda parcial: "juan" encuentra "juan perez"
    for nombre, numero in contacts.items():
        if key and key in nombre:
            return _normalize_phone(numero), nombre
    return None, to


def _open_whatsapp(phone: str, message: str) -> str:
    """Abre la app de escritorio si existe; si no, WhatsApp Web. Devuelve
    'app' o 'web' segun el canal usado."""
    text = urllib.parse.quote(message)
    try:
        os.startfile(f"whatsapp://send?phone={phone}&text={text}")
        return "app"
    except OSError:
        webbrowser.open(f"https://wa.me/{phone}?text={text}")
        return "web"


def send_whatsapp(to: str, message: str) -> ActionPlan:
    """Abre WhatsApp con el chat y el mensaje listos para enviar."""
    plan = ActionPlan(action="enviar_whatsapp",
                      params={"para": to, "mensaje": message},
                      risk=RiskLevel.EXECUTE,
                      reason="Abrir WhatsApp con el mensaje preparado")
    if not to.strip():
        plan.status = ActionStatus.ERROR
        plan.error = "sin destinatario"
        plan.result = "A quien le envio el WhatsApp, senor?"
        return plan
    if not message.strip():
        plan.status = ActionStatus.ERROR
        plan.error = "sin mensaje"
        plan.result = "Que mensaje le escribo, senor?"
        return plan
    phone, display = _resolve_recipient(to)
    if not phone:
        contactos = ", ".join(sorted(_load_contacts())) or "ninguno guardado"
        plan.status = ActionStatus.ERROR
        plan.error = "contacto no encontrado"
        plan.result = (f"No tengo el numero de '{to}', senor. Contactos: "
                       f"{contactos}. Puede decir: 'agrega el contacto {to} "
                       f"con numero 3001234567'.")
        return plan
    try:
        canal = _open_whatsapp(phone, message)
        donde = "la aplicacion" if canal == "app" else "WhatsApp Web"
        plan.params["telefono"] = phone
        plan.result = (f"Abri {donde} con el mensaje para {display} listo, "
                       "senor. Solo debe pulsar enviar.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude abrir WhatsApp: {e}"
    return plan


def add_contact(name: str, phone: str) -> ActionPlan:
    plan = ActionPlan(action="agregar_contacto",
                      params={"nombre": name, "numero": phone},
                      risk=RiskLevel.CREATE, reason="Guardar contacto de WhatsApp")
    key = _norm(name)
    normalizado = _normalize_phone(phone)
    if not key or not normalizado:
        plan.status = ActionStatus.ERROR
        plan.error = "datos invalidos"
        plan.result = ("Necesito un nombre y un numero valido, senor. "
                       "Ejemplo: 'agrega el contacto juan con numero 3001234567'.")
        return plan
    try:
        contacts = _load_contacts()
        contacts[key] = normalizado
        _save_contacts(contacts)
        plan.result = f"Contacto {name} guardado con el numero {normalizado}, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude guardar el contacto: {e}"
    return plan


def list_contacts() -> ActionPlan:
    plan = ActionPlan(action="listar_contactos", risk=RiskLevel.READ,
                      reason="Operacion de solo lectura")
    contacts = _load_contacts()
    if not contacts:
        plan.result = ("No tiene contactos guardados, senor. Puede decir: "
                       "'agrega el contacto juan con numero 3001234567'.")
    else:
        lineas = [f"  {n}: {t}" for n, t in sorted(contacts.items())]
        plan.result = "Sus contactos de WhatsApp, senor:\n" + "\n".join(lineas)
    plan.status = ActionStatus.EXECUTED
    return plan
