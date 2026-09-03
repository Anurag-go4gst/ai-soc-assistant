"""Secret redaction and safe-serialization helpers for telemetry payloads.

This module is the single source of truth for what counts as a secret in
telemetry, debug, and ``settings/status`` outputs. Tightening here
benefits every surface that calls ``minimize`` or ``truncate``.

Policy:

  * Drop any dict entry whose key matches a known secret keyword (broader
    than the previous keyword set — see ``_SECRET_KEY_PARTS``).
  * Mask any string value that looks like a Bearer token, JWT, PEM block,
    or carries a known API key prefix.
  * Mask long high-entropy hex / base64-ish blobs that are very likely
    secrets (heuristic; see ``_looks_like_high_entropy_token``).
  * Truncate long strings to ``MAX_STRING_LEN``.
  * Cap top-level serialized payloads to ``MAX_SERIALIZED_PAYLOAD_BYTES``
    (enforced by ``db._json``).
"""

from __future__ import annotations

import re
from typing import Any


MAX_STRING_LEN: int = 2000
MAX_LIST_LEN: int = 25
MAX_SERIALIZED_PAYLOAD_BYTES: int = 64 * 1024  # 64 KiB

_REDACTED = "[redacted]"

_SECRET_KEY_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "pwd",
    "passphrase",
    "secret",
    "token",
    "credential",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "session_secret",
    "session_id",
    "cookie",
    "authorization",
    "bearer",
    "jwt",
    "sign_key",
    "signing_key",
)


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SECRET_KEY_PARTS)


_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}\b")
_PEM_RE = re.compile(r"-----BEGIN [A-Z ]+-----[\s\S]+?-----END [A-Z ]+-----")
_API_KEY_PREFIX_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{16,}|xox[abprs]-[A-Za-z0-9-]{8,}|gh[pousr]_[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{8,}|AIza[0-9A-Za-z_\-]{20,})\b"
)


def mask_secret_substrings(value: str) -> str:
    masked = value
    masked = _BEARER_RE.sub(f"Bearer {_REDACTED}", masked)
    masked = _JWT_RE.sub(_REDACTED, masked)
    masked = _PEM_RE.sub(_REDACTED, masked)
    masked = _API_KEY_PREFIX_RE.sub(_REDACTED, masked)
    return masked


def _looks_like_high_entropy_token(value: str) -> bool:
    """Heuristic: long contiguous run of base64/hex chars with mixed cases
    and digits, no whitespace. Conservative — only matches blobs >= 40
    chars to avoid eating ordinary identifiers.
    """
    if len(value) < 40 or " " in value:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/=._\-]+", value):
        return False
    has_upper = any(c.isupper() for c in value)
    has_lower = any(c.islower() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_upper and has_lower and has_digit


def _redact_string(value: str) -> str:
    masked = mask_secret_substrings(value)
    if _looks_like_high_entropy_token(masked):
        return _REDACTED
    return masked


def truncate(value: Any, limit: int = MAX_STRING_LEN) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) > limit:
        text = text[:limit] + "...[truncated]"
    return _redact_string(text)


def minimize(value: Any) -> Any:
    """Recursively drop secret keys, mask secret-looking values, and
    truncate strings. Lists are capped at ``MAX_LIST_LEN`` entries.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if is_secret_key(key):
                continue
            out[key] = minimize(v)
        return out
    if isinstance(value, (list, tuple)):
        return [minimize(v) for v in list(value)[:MAX_LIST_LEN]]
    if isinstance(value, str):
        return truncate(value)
    return value


# Exact keys (and `_password` / `_api_key` suffixes) dropped from forensic LLM
# payloads. Deliberately not the substring matcher in ``is_secret_key`` — that
# matcher treats `max_tokens` as a secret because it contains `token`.
_FORENSIC_DROP_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "passphrase",
        "secret",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "session_secret",
        "cookie",
        "cookies",
        "authorization",
        "bearer",
        "jwt",
        "credential",
        "credentials",
        "sign_key",
        "signing_key",
        "access_token",
        "refresh_token",
        "id_token",
        "auth_token",
    }
)
_FORENSIC_DROP_SUFFIXES = (
    "_password",
    "_passwd",
    "_secret",
    "_api_key",
    "_apikey",
    "_private_key",
    "_session_secret",
    "_authorization",
    "_cookie",
    "_bearer",
)


def is_forensic_secret_key(key: str) -> bool:
    """True for credential keys. ``max_tokens`` / ``prompt_hash`` stay."""
    lowered = str(key or "").lower().replace("-", "_")
    if lowered in _FORENSIC_DROP_KEYS:
        return True
    return any(lowered.endswith(suffix) for suffix in _FORENSIC_DROP_SUFFIXES)


def redact_secrets_keep_text(value: Any) -> Any:
    """Redact secrets without truncating semantic prompt/response text.

    Forensic LLM reconstruction needs the exact redacted prompt and raw model
    output. ``minimize`` truncates strings to ``MAX_STRING_LEN`` and would
    destroy that. This path still drops credential keys and masks bearer/JWT/
    PEM/API-key substrings inside values.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if is_forensic_secret_key(key):
                continue
            out[key] = redact_secrets_keep_text(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_secrets_keep_text(item) for item in value]
    if isinstance(value, str):
        return mask_secret_substrings(value)
    return value


def secret_substrings_were_masked(original: str | None, redacted: str | None) -> bool:
    if not isinstance(original, str) or not isinstance(redacted, str):
        return False
    return original != redacted


__all__ = [
    "MAX_SERIALIZED_PAYLOAD_BYTES",
    "MAX_STRING_LEN",
    "MAX_LIST_LEN",
    "is_secret_key",
    "is_forensic_secret_key",
    "mask_secret_substrings",
    "minimize",
    "redact_secrets_keep_text",
    "secret_substrings_were_masked",
    "truncate",
]
