"""
JARVIS Local - Redaccion de secretos
Detecta y redacta API keys, tokens, passwords y cookies en texto.
"""

import re

SECRET_PATTERNS = [
    (r'sk-[A-Za-z0-9_-]{20,}', "[OPENAI_API_KEY]"),
    (r'sk-ant-[A-Za-z0-9_-]{20,}', "[ANTHROPIC_API_KEY]"),
    (r'AIza[0-9A-Za-z_-]{20,}', "[GOOGLE_API_KEY]"),
    (r'ghp_[A-Za-z0-9]{20,}', "[GITHUB_TOKEN]"),
    (r'gho_[A-Za-z0-9]{20,}', "[GITHUB_OAUTH_TOKEN]"),
    (r'ghu_[A-Za-z0-9]{20,}', "[GITHUB_USER_TOKEN]"),
    (r'ghs_[A-Za-z0-9]{20,}', "[GITHUB_SERVER_TOKEN]"),
    (r'ghr_[A-Za-z0-9]{20,}', "[GITHUB_REFRESH_TOKEN]"),
    (r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', "[JWT_TOKEN]"),
    # OJO: el grupo 1 aqui es la ETIQUETA (password/token/...), no el
    # valor secreto -- el reemplazo `\1=[REDACTED]` solo debe reinsertar
    # la etiqueta. Antes el grupo capturaba el propio secreto y se
    # reinsertaba intacto en el "texto redactado".
    (r'\b(password|passwd|pwd|secret|token|key|api_key)\s*[:=]\s*'
     r'["\']?[^\s"\'&|<>{}\\$]{8,}["\']?',
     r'\1=[REDACTED]'),
    (r'(?:Authorization|Bearer)\s+[A-Za-z0-9_\-\.=]{20,}', "[AUTH_HEADER]"),
    (r'-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----[\s\S]*?-----END \1 PRIVATE KEY-----',
     "[PRIVATE_KEY]"),
    (r'xox[bpras]-[A-Za-z0-9-]{10,}', "[SLACK_TOKEN]"),
    (r'AC[a-f0-9]{32}', "[TWILIO_ACCOUNT_SID]"),
    (r'ses-[a-z]+-[a-z0-9]+', "[AWS_SES_TOKEN]"),
    # Contrasena de aplicacion de Gmail: 16 caracteres alfanumericos,
    # tipicamente mostrados en 4 grupos de 4 separados por espacios.
    (r'\b[a-zA-Z]{4}\s[a-zA-Z]{4}\s[a-zA-Z]{4}\s[a-zA-Z]{4}\b', "[GMAIL_APP_PASSWORD]"),
    # WolframAlpha App ID: p.ej. "XXXXXX-XXXXXXXXXX".
    (r'\b[A-Z0-9]{6}-[A-Z0-9]{10}\b', "[WOLFRAM_APP_ID]"),
    # Tokens OAuth2 de Google (access / refresh token).
    (r'\bya29\.[A-Za-z0-9_-]{20,}', "[GOOGLE_OAUTH_ACCESS_TOKEN]"),
    (r'\b1//[A-Za-z0-9_-]{20,}', "[GOOGLE_OAUTH_REFRESH_TOKEN]"),
]


def redact_secrets(text: str) -> tuple[str, int]:
    """
    Redacta secretos en el texto.

    Returns:
        Tuple[str, int]: (texto_redactado, numero_de_secretos_encontrados)
    """
    redacted = text
    count = 0
    for pattern, replacement in SECRET_PATTERNS:
        found = len(re.findall(pattern, redacted, re.IGNORECASE))
        if found > 0:
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
            count += found
    return redacted, count


def contains_secrets(text: str) -> bool:
    """Verifica si el texto contiene algun patron de secreto."""
    _, count = redact_secrets(text)
    return count > 0
