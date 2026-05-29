"""Allowlist parsing for Stage 3L-S3.3A (no settings import — avoids config cycles)."""

from __future__ import annotations

from typing import Final

COV_Q046_PILOT_COVERAGE_ID: Final[str] = "cov.q046.excessive_failed_logins_sample"
ALLOWLISTABLE_COVERAGE_IDS: Final[frozenset[str]] = frozenset({COV_Q046_PILOT_COVERAGE_ID})


def parse_route_authority_coverage_allowlist(raw: str) -> frozenset[str]:
    text = (raw or "").strip()
    if not text:
        return frozenset()
    return frozenset(part.strip() for part in text.split(",") if part.strip())


def validate_allowlist_ids(allowlist: frozenset[str]) -> None:
    unknown = allowlist - ALLOWLISTABLE_COVERAGE_IDS
    if unknown:
        allowed = ", ".join(sorted(ALLOWLISTABLE_COVERAGE_IDS))
        unknown_ids = ", ".join(sorted(unknown))
        raise ValueError(
            f"ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST contains disallowed coverage_id(s): "
            f"{unknown_ids}. Only {allowed} may appear."
        )
