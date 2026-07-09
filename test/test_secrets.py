"""
Tests de redaccion de secretos - Fase 1
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from jarvis_local.safety.secrets import redact_secrets, contains_secrets


def test_redact_openai_key():
    text = "Mi clave es sk-proj-abc123def456ghijklmnopqrstuvwxyz"
    redacted, count = redact_secrets(text)
    assert count >= 1
    assert "sk-proj" not in redacted
    assert "[OPENAI_API_KEY]" in redacted


def test_redact_jwt_token():
    text = "Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    redacted, count = redact_secrets(text)
    assert count >= 1
    assert "eyJ" not in redacted or "[JWT_TOKEN]" in redacted


def test_redact_bearer_token():
    text = "Bearer ghp_abcdefghijklmnopqrstuvwxyz123456"
    redacted, count = redact_secrets(text)
    assert count >= 1


def test_no_false_positives():
    text = "Hola Jarvis, como estas? Me gusta programar en Python."
    redacted, count = redact_secrets(text)
    assert count == 0
    assert text == redacted


def test_contains_secrets_true():
    assert contains_secrets("sk-ant-api-abc123def456ghijklmnopqrstuvwxyz") is True


def test_contains_secrets_false():
    assert contains_secrets("Hola, que tal el clima hoy?") is False


def test_multiple_secrets():
    text = "key1: sk-abc123def456ghijklmno y key2: sk-xyz789uvw012pqrstuvw"
    redacted, count = redact_secrets(text)
    assert count >= 2


if __name__ == "__main__":
    test_redact_openai_key()
    test_redact_jwt_token()
    test_redact_bearer_token()
    test_no_false_positives()
    test_contains_secrets_true()
    test_contains_secrets_false()
    test_multiple_secrets()
    print("OK: Todos los tests de secretos pasaron.")
