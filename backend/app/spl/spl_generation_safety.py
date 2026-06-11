"""Post-render SPL generation safety lint and execution-readiness metadata.

Complements pre-render slot binding and mandatory ``validate_spl()``. Does not
enable MCP, implement RBAC, or change execution gates.
"""

from __future__ import annotations

import re
from typing import Any

SAFETY_POLICY_VERSION = "2026-06-spl-generation-safety-v1"

_TSTATS_PREFIX = re.compile(r"^\s*tstats\b", re.IGNORECASE)
_SUMMARIESONLY_TRUE = re.compile(r"\bsummariesonly\s*=\s*true\b", re.IGNORECASE)
_BASE_SEARCH_SEGMENT = re.compile(r"^\s*search\s+([^|]+)", re.IGNORECASE)
_BROAD_WILDCARD = re.compile(r"(?:^\s*\*\s*$|\*\w{1,3}\*|\bsearch\s+\*)", re.IGNORECASE)
_STRFTIME_BEFORE_AGG = re.compile(
    r"strftime\s*\(\s*(?:_time|event_time|lockout_time)\s*,",
    re.IGNORECASE,
)
_AGG_COMMAND = re.compile(r"\|\s*(?:bin|stats|streamstats|timechart)\b", re.IGNORECASE)
_NULL_ARITHMETIC = re.compile(
    r"\beval\b[^|]*\bnull\s*\(\s*\)\s*[\+\-\*/]",
    re.IGNORECASE,
)


def attach_execution_readiness_metadata(
    candidate_payload: dict[str, Any],
    validation_payload: dict[str, Any],
) -> None:
    """Document MCP/RBAC prerequisites without implementing RBAC in SPL generation."""
    readiness = {
        "execution_eligible": False,
        "execution_enabled": False,
        "mcp_execution_enabled": False,
        "requires_mcp_identity_rbac_check": True,
        "spl_generation_safety_policy": SAFETY_POLICY_VERSION,
    }
    candidate_payload.update(readiness)
    validation_payload.update(readiness)


def assess_post_render_spl_quality(spl: str) -> dict[str, Any]:
    """Non-blocking quality lint; may elevate review_required without weakening validator."""
    warnings: list[str] = []
    review_reasons: list[str] = []

    if _TSTATS_PREFIX.search(spl) and not _SUMMARIESONLY_TRUE.search(spl):
        review_reasons.append("tstats_summariesonly_missing")
        warnings.append("tstats_requires_summariesonly_review")

    if _BROAD_WILDCARD.search(_base_search_clause(spl)):
        warnings.append("broad_unfielded_wildcard_base_search")

    if _strftime_before_aggregation(spl):
        warnings.append("strftime_before_aggregation")

    if _NULL_ARITHMETIC.search(spl):
        warnings.append("null_arithmetic_pattern")

    return {
        "quality_warnings": sorted(set(warnings)),
        "quality_review_reasons": sorted(set(review_reasons)),
    }


def apply_spl_generation_safety(
    candidate_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    *,
    spl: str,
) -> None:
    """Apply post-render quality lint and execution-readiness metadata."""
    attach_execution_readiness_metadata(candidate_payload, validation_payload)
    quality = assess_post_render_spl_quality(spl)
    if quality["quality_warnings"]:
        validation_payload["warnings"] = sorted(
            set(list(validation_payload.get("warnings") or []) + quality["quality_warnings"])
        )
        candidate_payload["warnings"] = sorted(
            set(list(candidate_payload.get("warnings") or []) + quality["quality_warnings"])
        )
    if quality["quality_review_reasons"]:
        validation_payload["spl_quality_review_reasons"] = quality["quality_review_reasons"]
        validation_payload["review_required"] = True
        candidate_payload["review_required"] = True
        reasons = list(validation_payload.get("review_required_reasons") or [])
        reasons.extend(quality["quality_review_reasons"])
        validation_payload["review_required_reasons"] = sorted(set(reasons))
        candidate_payload["review_required_reasons"] = sorted(set(reasons))


def _base_search_clause(spl: str) -> str:
    match = _BASE_SEARCH_SEGMENT.match(spl)
    if match:
        return match.group(1)
    return spl.split("|", 1)[0]


def _strftime_before_aggregation(spl: str) -> bool:
    if not _STRFTIME_BEFORE_AGG.search(spl):
        return False
    agg = _AGG_COMMAND.search(spl)
    if agg is None:
        return False
    strftime_match = _STRFTIME_BEFORE_AGG.search(spl)
    return bool(strftime_match and strftime_match.start() < agg.start())
