"""OPTIONAL_PHASE_S S4 — deterministic AUTO_FIX_SAFE rewrites.

Permitted only where semantics are provable (same-field OR → IN with exact values).
Every rewrite passes assert_rewrite_preserves; FAIL retains v1 as selected candidate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.draft_quality import (
    _Q04_OR_CHAIN_THRESHOLD,
    _SAME_FIELD_OR,
    evaluate_draft_quality,
)
from app.spl.rewrite_guard import assert_rewrite_preserves

_OR_SPLIT = re.compile(r"\s+OR\s+", re.IGNORECASE)
_FIELD_VALUE = re.compile(
    r"^\s*([A-Za-z_][\w.]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s|()]+)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AutoFixResult:
    candidate_spl: str
    applied: bool
    retained_v1: bool
    steps: list[str] = field(default_factory=list)
    rewrite_guard: dict[str, Any] = field(default_factory=dict)
    optimization_classification: str = "PASS"
    llm_lineage: bool = False


def _parse_or_chain(fragment: str) -> tuple[str, list[str]] | None:
    parts = _OR_SPLIT.split(fragment.strip())
    if len(parts) < 2:
        return None
    field_name: str | None = None
    values: list[str] = []
    for part in parts:
        match = _FIELD_VALUE.match(part)
        if not match:
            return None
        name, value = match.group(1), match.group(2)
        if field_name is None:
            field_name = name
        elif name.lower() != field_name.lower():
            return None
        values.append(value)
    if field_name is None or len(values) < _Q04_OR_CHAIN_THRESHOLD:
        return None
    return field_name, values


def _or_chain_to_in(fragment: str) -> str | None:
    parsed = _parse_or_chain(fragment)
    if parsed is None:
        return None
    field_name, values = parsed
    return f"{field_name} IN ({','.join(values)})"


def rewrite_same_field_or_to_in(spl: str) -> tuple[str, list[str]]:
    """Replace excessive same-field OR chains with IN() — exact values only."""
    steps: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        fragment = match.group(0)
        rewritten = _or_chain_to_in(fragment)
        if rewritten is None or rewritten == fragment:
            return fragment
        steps.append("or_chain_to_in")
        return rewritten

    optimized = _SAME_FIELD_OR.sub(_replace, spl or "")
    return optimized, steps


def apply_auto_fix_safe(
    spl: str,
    *,
    rqc: dict[str, Any] | None = None,
    intent_spec: dict[str, Any] | None = None,
    llm_lineage: bool = False,
) -> AutoFixResult:
    """Apply Layer-2 AUTO_FIX_SAFE when draft quality classifies as such."""
    original = (spl or "").strip()
    if not original:
        return AutoFixResult(
            candidate_spl=original,
            applied=False,
            retained_v1=True,
            optimization_classification="PASS",
            llm_lineage=llm_lineage,
        )

    quality = evaluate_draft_quality(original)
    classification = quality.optimization_classification
    if classification != "AUTO_FIX_SAFE":
        return AutoFixResult(
            candidate_spl=original,
            applied=False,
            retained_v1=True,
            optimization_classification=classification,
            llm_lineage=llm_lineage,
        )

    candidate_v2, steps = rewrite_same_field_or_to_in(original)
    if candidate_v2 == original or not steps:
        return AutoFixResult(
            candidate_spl=original,
            applied=False,
            retained_v1=True,
            steps=steps,
            optimization_classification=classification,
            llm_lineage=llm_lineage,
        )

    guard = assert_rewrite_preserves(original, candidate_v2, rqc=rqc, intent_spec=intent_spec)
    if guard["verdict"] != "PASS":
        return AutoFixResult(
            candidate_spl=original,
            applied=False,
            retained_v1=True,
            steps=steps,
            rewrite_guard=guard,
            optimization_classification=classification,
            llm_lineage=llm_lineage,
        )

    return AutoFixResult(
        candidate_spl=candidate_v2,
        applied=True,
        retained_v1=False,
        steps=steps,
        rewrite_guard=guard,
        optimization_classification=classification,
        llm_lineage=llm_lineage,
    )
