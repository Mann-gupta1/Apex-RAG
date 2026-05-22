"""PII redaction (regex fallback path is always available)."""
from __future__ import annotations

from apex.safety.pii_redact import _redact_with_regex, redact


def test_email_redaction_regex_fallback():
    text = "Please contact john.doe@example.com for details."
    result = _redact_with_regex(text)
    assert "<EMAIL_ADDRESS>" in result.text
    assert "john.doe@example.com" not in result.text
    assert any(e["entity_type"] == "EMAIL_ADDRESS" for e in result.entities)


def test_phone_redaction_regex_fallback():
    text = "Call me at +1 415 555 2671 tomorrow."
    result = _redact_with_regex(text)
    assert "<PHONE_NUMBER>" in result.text


def test_redact_respects_disabled_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_PII_REDACTION", "false")
    from apex.settings import reset_caches

    reset_caches()
    out = redact("contact john.doe@example.com")
    assert out.text == "contact john.doe@example.com"
    monkeypatch.delenv("ENABLE_PII_REDACTION", raising=False)
    reset_caches()


def test_ssn_redaction():
    out = _redact_with_regex("SSN 123-45-6789 attached.")
    assert "<US_SSN>" in out.text
