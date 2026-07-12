"""
JARVIS Local - Google Calendar (Fase 4)
Proximos eventos del calendario. Requiere configuracion OAuth opcional:
  pip install google-api-python-client google-auth-oauthlib
  credentials.json en jarvis_local/ (ver secrets.example.yaml)
"""
import os
from datetime import datetime, timezone
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus
from jarvis_local.config import BASE_DIR

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

SETUP_MSG = ("Google Calendar no esta configurado, senor. Pasos:\n"
             "  1. pip install google-api-python-client google-auth-oauthlib\n"
             "  2. Cree credenciales OAuth en console.cloud.google.com/apis/credentials\n"
             "  3. Guarde el JSON descargado como jarvis_local/credentials.json\n"
             "  4. Vuelva a pedirme sus eventos (se abrira el navegador para autorizar)")


def _get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)


def upcoming_events(limit: int = 5) -> ActionPlan:
    plan = ActionPlan(action="eventos_calendario", risk=RiskLevel.READ,
                      reason="Consultar proximos eventos de Google Calendar")
    try:
        import googleapiclient  # noqa: F401
    except ImportError:
        plan.status = ActionStatus.ERROR
        plan.result = SETUP_MSG
        return plan
    if not CREDENTIALS_FILE.exists():
        plan.status = ActionStatus.ERROR
        plan.result = SETUP_MSG
        return plan
    try:
        service = _get_service()
        now = datetime.now(timezone.utc).isoformat()
        events = service.events().list(
            calendarId="primary", timeMin=now, maxResults=limit,
            singleEvents=True, orderBy="startTime").execute().get("items", [])
        if not events:
            plan.result = "No tiene eventos proximos en su calendario, senor."
            plan.status = ActionStatus.EXECUTED
            return plan
        lines = []
        for ev in events:
            start = ev["start"].get("dateTime", ev["start"].get("date", ""))
            start = start.replace("T", " ")[:16]
            lines.append(f"  - {start}: {ev.get('summary', '(sin titulo)')}")
        plan.result = "Sus proximos eventos, senor:\n" + "\n".join(lines)
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude consultar el calendario: {e}"
    return plan
