"""Deterministic success-after-failure phrase detection (shared, import-safe)."""

from __future__ import annotations


def detect_success_after_failure(normalized: str) -> bool:
    """True when the query asks about success following prior authentication failures."""
    text = " ".join(normalized.lower().split())
    if any(
        term in text
        for term in (
            "no successful login",
            "no success",
            "no login success",
            "without successful login",
        )
    ):
        return False
    if any(
        term in text
        for term in (
            "successful login after",
            "successful vpn login after",
            "successful vpn logins after",
            "success after",
            "success following",
            "after repeated failure",
            "after repeated failures",
            "after failures",
            "after failed login",
            "after failed logins",
            "followed by a successful login",
            "followed by successful login",
            "followed by a successful sign-in",
            "followed by a successful sign in",
            "followed by a successful signin",
            "failures followed by",
            "failure followed by",
            "failed logins followed by",
            "login failures followed by",
            "failures followed by success",
        )
    ):
        return True
    if "successful login" in text and any(
        term in text for term in ("followed", "after failure", "after failures", "after failed", "after repeated")
    ):
        return True
    successful = "successful" in text or "success" in text or "sign-in" in text or "sign in" in text
    if successful and ("after" in text or "followed by" in text) and "fail" in text:
        return True
    return False
