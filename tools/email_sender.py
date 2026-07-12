"""
JARVIS Local - Envio de correos (Fase 4)
Envia correos por SMTP con credenciales de secrets.yaml.
Accion de escritura hacia el exterior: SIEMPRE requiere plan + /confirmar.
"""
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jarvis_local.config import get_secrets
from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel, policy

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")

SETUP_MSG = ("El correo no esta configurado, senor. Copie secrets.example.yaml "
             "como secrets.yaml y complete la seccion 'email' con su direccion "
             "y una contrasena de aplicacion.")


def resolve_recipient(to: str) -> str | None:
    """Resuelve un destinatario: direccion directa o contacto de secrets.yaml."""
    to = to.strip().strip('"\'')
    if _EMAIL_RE.match(to):
        return to
    contacts = (get_secrets().get("email", {}) or {}).get("contacts", {}) or {}
    for name, addr in contacts.items():
        if name.lower() == to.lower():
            return addr
    return None


def plan_email(to: str, subject: str, body: str) -> ActionPlan:
    """Crea el plan de envio (pendiente de /confirmar)."""
    secrets = get_secrets().get("email", {}) or {}
    if not secrets.get("address") or not secrets.get("app_password"):
        return policy.block(SETUP_MSG)
    dest = resolve_recipient(to)
    if not dest:
        return policy.block(
            f"No reconozco el destinatario '{to}'. Use una direccion completa "
            "o agregue el contacto en secrets.yaml.")
    plan = ActionPlan(
        action="enviar_correo",
        params={"to": dest, "subject": subject, "body": body},
        risk=RiskLevel.EXECUTE,
        reason=f"Enviar correo a {dest}",
        simulation_result=(f"[Plan pendiente] Enviar correo\n"
                           f"  Para: {dest}\n  Asunto: {subject}\n"
                           f"  Mensaje: {body[:120]}\n"
                           "Escribe /confirmar para enviar o /cancelar."),
    )
    plan.status = ActionStatus.PLANNED
    policy.pending_plan = plan
    return plan


def execute_send(to: str, subject: str, body: str) -> ActionPlan:
    """Envia el correo CONFIRMADO via SMTP."""
    plan = ActionPlan(action="enviar_correo",
                      params={"to": to, "subject": subject},
                      risk=RiskLevel.EXECUTE, status=ActionStatus.CONFIRMED)
    secrets = get_secrets().get("email", {}) or {}
    address = secrets.get("address")
    password = secrets.get("app_password")
    if not address or not password:
        plan.status = ActionStatus.ERROR
        plan.result = SETUP_MSG
        return plan
    server = secrets.get("smtp_server", "smtp.gmail.com")
    port = int(secrets.get("smtp_port", 587))
    try:
        msg = MIMEMultipart()
        msg["From"] = address
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(server, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(address, password.replace(" ", ""))
            smtp.sendmail(address, [to], msg.as_string())
        plan.result = f"Correo enviado a {to}, senor."
        plan.status = ActionStatus.EXECUTED
    except smtplib.SMTPAuthenticationError:
        plan.status = ActionStatus.ERROR
        plan.result = ("Autenticacion fallida. Verifique la contrasena de "
                       "aplicacion en secrets.yaml.")
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude enviar el correo: {e}"
    return plan
