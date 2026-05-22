"""Tests for the telemetry secret-redaction helpers."""

from app.connectors.telemetry.redaction import (
    MAX_SERIALIZED_PAYLOAD_BYTES,
    is_secret_key,
    mask_secret_substrings,
    minimize,
)


def test_expanded_secret_key_detection() -> None:
    for key in (
        "password",
        "passwd",
        "pwd",
        "passphrase",
        "secret",
        "api_token",
        "credential",
        "api_key",
        "apikey",
        "private_key",
        "session_secret",
        "session_id",
        "cookie",
        "authorization",
        "bearer",
        "jwt",
    ):
        assert is_secret_key(key), key


def test_mask_bearer_jwt_and_pem() -> None:
    text = (
        "Authorization: Bearer abc123XYZ.token "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NSJ9.abc-def-ghi "
        "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAg\n-----END PRIVATE KEY-----"
    )
    masked = mask_secret_substrings(text)
    assert "Bearer [redacted]" in masked
    assert "eyJ" not in masked
    assert "BEGIN PRIVATE KEY" not in masked


def test_mask_known_api_key_prefixes() -> None:
    for sample in (
        "sk-abcdefghijklmnop12345678",
        "xoxb-1234567890-abcde",
        "ghp_abcdefghijklmnopqrstuvwxyz1234",
        "AKIAIOSFODNN7EXAMPLE",
        "AIzaSyA-1234567890abcdefghijklmnopqrstu",
    ):
        masked = mask_secret_substrings(sample)
        assert "[redacted]" in masked, sample


def test_minimize_drops_secret_keys_and_recurses() -> None:
    payload = {
        "user": "alice",
        "password": "p@ssw0rd",
        "nested": {"api_key": "x", "ok": "fine"},
        "list": [{"token": "t", "id": 1}],
    }
    cleaned = minimize(payload)
    assert "password" not in cleaned
    assert "api_key" not in cleaned["nested"]
    assert cleaned["nested"]["ok"] == "fine"
    assert "token" not in cleaned["list"][0]
    assert cleaned["list"][0]["id"] == 1


def test_minimize_truncates_long_strings_and_masks_jwt() -> None:
    long = "x" * 5000
    out = minimize({"text": long})
    assert out["text"].endswith("[truncated]")
    jwt = "eyJabcdefgh.ijklmnopqr.stuvwxyz"
    out2 = minimize({"text": jwt})
    assert "[redacted]" in out2["text"]


def test_high_entropy_token_value_is_masked() -> None:
    token = "Z9aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789AbCd"
    out = minimize({"random": token})
    # High-entropy long value should be redacted entirely.
    assert out["random"] == "[redacted]"


def test_payload_byte_cap_constant_is_reasonable() -> None:
    assert MAX_SERIALIZED_PAYLOAD_BYTES >= 8 * 1024
    assert MAX_SERIALIZED_PAYLOAD_BYTES <= 1024 * 1024
