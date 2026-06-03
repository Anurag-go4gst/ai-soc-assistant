"""Allowlist parsing for Stage 3L-S3.3A (no settings import — avoids config cycles)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Final

COV_Q046_PILOT_COVERAGE_ID: Final[str] = "cov.q046.excessive_failed_logins_sample"
BLOCKED_AUTHORITY_COVERAGE_IDS: Final[frozenset[str]] = frozenset(
    {
        "cov.q007.dga_detection_binding",
    }
)
_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "coverage" / "pattern_coverage_v1.json"


@lru_cache(maxsize=1)
def manifest_allowlistable_coverage_ids() -> frozenset[str]:
    """Manifest coverage IDs eligible for ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST."""
    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    allowed: set[str] = set()
    for entry in payload.get("entries", []):
        cov_id = entry.get("coverage_id")
        if not isinstance(cov_id, str) or not cov_id.strip():
            continue
        if cov_id in BLOCKED_AUTHORITY_COVERAGE_IDS:
            continue
        if str(entry.get("coverage_group", "")) == "detection_dependent":
            continue
        allowed.add(cov_id)
    return frozenset(allowed)


ALLOWLISTABLE_COVERAGE_IDS: Final[frozenset[str]] = manifest_allowlistable_coverage_ids()


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
