"""Post-validation SPL simplifier (SPL audit Phase E).

Runs only after relevance + validation pass on correct SPL. Every simplification
is re-validated and re-checked for relevance; regressions reject the change and
return the original SPL unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.safeguards.spl_validator import validate_spl
from app.spl.spl_relevance_check import check_spl_relevance


@dataclass(frozen=True)
class SimplificationResult:
    simplified_spl: str
    applied: bool
    steps: list[str] = field(default_factory=list)
    rejected: bool = False
    reject_reason: str | None = None


def simplify_spl(spl: str, *, user_query: str | None = None) -> SimplificationResult:
    """Apply deterministic verbosity reductions to already-correct SPL."""
    del user_query  # reserved for future query-aware rules
    original = spl.strip()
    if not original:
        return SimplificationResult(original, False)

    steps: list[str] = []
    optimized = " ".join(original.split())
    if optimized != original:
        steps.append("normalize_whitespace")

    lowered = optimized.lower()

    if "| table " in lowered and "| stats " in lowered and lowered.index("| table ") < lowered.index("| stats "):
        segments = [part.strip() for part in optimized.split("|")]
        segments = [part for part in segments if not part.lower().startswith("table ")]
        optimized = " | ".join(segments)
        steps.append("drop_table_before_stats")
        lowered = optimized.lower()

    base_search = optimized.split("|", 1)[0].lower()
    if (
        ("dest_port=445" in base_search or "smb" in base_search)
        and "| where " in lowered
        and "%smb%" in lowered
    ):
        segments = [part.strip() for part in optimized.split("|")]
        filtered: list[str] = []
        dropped = False
        for part in segments:
            part_lower = part.lower()
            if part_lower.startswith("where ") and ("%smb%" in part_lower or "app_norm" in part_lower):
                dropped = True
                continue
            filtered.append(part)
        if dropped:
            optimized = " | ".join(filtered)
            steps.append("drop_redundant_smb_where")
            lowered = optimized.lower()

    if "earliest=" not in lowered:
        if "|" in optimized:
            head, tail = optimized.split("|", 1)
            optimized = f"{head.strip()} earliest=-60m latest=now | {tail.strip()}"
        else:
            optimized = f"{optimized} earliest=-60m latest=now"
        steps.append("append_default_time_bounds")
        lowered = optimized.lower()

    if "| head " not in lowered:
        if "| sort" in lowered:
            optimized = f"{optimized} | head 100"
            steps.append("append_head_after_sort")
        elif "| stats " in lowered:
            optimized = f"{optimized} | head 100"
            steps.append("append_head_after_stats")

    applied = optimized != original
    return SimplificationResult(optimized, applied, steps)


def simplify_spl_safe(spl: str, *, user_query: str | None = None) -> SimplificationResult:
    """Simplify SPL and reject the change when validation or relevance regresses."""
    result = simplify_spl(spl, user_query=user_query)
    if not result.applied:
        return result

    validation = validate_spl(result.simplified_spl)
    if not validation.get("approved"):
        return SimplificationResult(
            spl.strip(),
            False,
            result.steps,
            rejected=True,
            reject_reason="validation_regressed",
        )

    if user_query:
        relevance = check_spl_relevance(user_query, result.simplified_spl)
        if not relevance.relevant:
            return SimplificationResult(
                spl.strip(),
                False,
                result.steps,
                rejected=True,
                reject_reason="relevance_regressed",
            )

    return result
