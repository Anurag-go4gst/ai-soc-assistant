"""Redaction for forensic LLM payloads: secrets out, semantic text kept."""

from __future__ import annotations

from app.connectors.telemetry.redaction import (
    is_forensic_secret_key,
    minimize,
    redact_secrets_keep_text,
)


def test_max_tokens_is_not_treated_as_a_secret_key() -> None:
    assert is_forensic_secret_key("max_tokens") is False
    assert is_forensic_secret_key("prompt_hash") is False
    assert is_forensic_secret_key("authorization") is True
    assert is_forensic_secret_key("api_key") is True
    assert is_forensic_secret_key("session_secret") is True


def test_redact_secrets_keep_text_preserves_long_prompts() -> None:
    prompt = "A" * 5000
    payload = {
        "authorization": "Bearer super-secret-token-value",
        "api_key": "sk-abcdefghijklmnopqrstuvwxyz012345",
        "max_tokens": 800,
        "user_prompt": prompt,
        "raw_text": prompt,
    }
    redacted = redact_secrets_keep_text(payload)
    assert "authorization" not in redacted
    assert "api_key" not in redacted
    assert redacted["max_tokens"] == 800
    assert redacted["user_prompt"] == prompt
    assert redacted["raw_text"] == prompt


def test_minimize_still_truncates_but_forensic_path_does_not() -> None:
    prompt = "Investigate " + ("x" * 4000)
    minimized = minimize({"user_prompt": prompt, "max_tokens": 400})
    forensic = redact_secrets_keep_text({"user_prompt": prompt, "max_tokens": 400})
    assert str(minimized["user_prompt"]).endswith("...[truncated]")
    assert forensic["user_prompt"] == prompt
    assert forensic["max_tokens"] == 400


def test_bearer_substrings_are_masked_inside_prompt_text() -> None:
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaa.bbbb"
    redacted = redact_secrets_keep_text({"user_prompt": text})
    assert "Bearer [redacted]" in redacted["user_prompt"] or "[redacted]" in redacted["user_prompt"]
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted["user_prompt"]
