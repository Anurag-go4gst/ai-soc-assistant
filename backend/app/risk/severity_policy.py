from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

MATRIX_PATH = Path(__file__).with_name("severity_matrix.json")
ACTION_PRIORITIES = ("urgent", "high", "standard_triage", "low")
PRIORITY_ENUM = ("P1", "P2", "P3", "P4")

ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL = "Not assigned from this question alone"
ANALYTICS_REVIEW_TYPE_NOTE = "Review type: analytics/query review."


class SeverityDecision(BaseModel):
    use_case_id: str | None = None
    severity_label: str
    matched_rules: list[str] = Field(default_factory=list)
    why_not_higher: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    recommended_priority: str
    allowed_action_tier: int


@lru_cache(maxsize=1)
def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def decide_severity(use_case_id: str | None, structured_context: dict[str, Any] | None, source_refs: list[str]) -> SeverityDecision:
    metrics = dict((structured_context or {}).get("metrics") or {})
    policy = _policy_for(use_case_id)
    if not policy:
        return SeverityDecision(
            use_case_id=use_case_id,
            severity_label="P3 Medium",
            matched_rules=["default_no_policy"],
            why_not_higher=["No use-case-specific severity policy is active yet."],
            missing_evidence=[],
            source_refs=source_refs,
            recommended_priority="standard_triage",
            allowed_action_tier=1,
        )

    label = str(policy.get("default_severity") or "P3 Medium")
    matched = ["default_policy"]
    for rule in policy.get("rules") or []:
        conditions = dict(rule.get("conditions") or {})
        if _conditions_match(conditions, metrics):
            label = str(rule["severity"])
            matched = [str(rule.get("why") or rule["severity"])]
            break

    missing_p1 = [item for item in policy.get("p1_requires") or [] if not metrics.get(item)]
    why_not_higher = []
    if not label.startswith("P1") and missing_p1:
        why_not_higher.append("P1 requires: " + ", ".join(missing_p1))

    return SeverityDecision(
        use_case_id=use_case_id,
        severity_label=label,
        matched_rules=matched,
        why_not_higher=why_not_higher,
        missing_evidence=missing_p1,
        source_refs=source_refs,
        recommended_priority=_priority(label),
        allowed_action_tier=1,
    )


def apply_analytics_severity_guard(
    decision: SeverityDecision,
    *,
    analytics_query: bool,
    alert_context_present: bool,
) -> SeverityDecision:
    """Suppress the default P3 for pure analytics/ranking questions.

    Only the no-policy default is replaced: an active use-case severity policy
    (or alert evidence) always keeps authority over this presentation guard.
    """
    if not analytics_query or alert_context_present:
        return decision
    if "default_no_policy" not in decision.matched_rules:
        return decision
    return decision.model_copy(
        update={
            "severity_label": ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
            "matched_rules": ["analytics_query_no_alert_evidence"],
            "why_not_higher": [
                "Pure analytics/ranking question without alert evidence or an active "
                "use-case severity policy; incident severity is not assigned."
            ],
            "recommended_priority": "not_applicable",
        }
    )


def _is_priority_label(severity_label: str) -> bool:
    """True for an actual P1-P4 incident label (not a 'Not assigned' sentinel)."""
    return bool(re.match(r"^P[1-4]\b", str(severity_label or "").strip()))


def apply_gate_severity_cap(
    decision: SeverityDecision,
    *,
    allow_severity_assessment: bool,
) -> SeverityDecision:
    """Cap a displayed severity to 'Not assigned' when the gate disallows assessment.

    This is the single display-gating point so that every downstream surface
    (analyst card, lineage, governance trace, response payload, action
    capability) consumes the same gated severity. When
    ``allow_severity_assessment`` is True, or the label is already a
    non-priority sentinel, the decision passes through unchanged.
    """
    if allow_severity_assessment:
        return decision
    if not _is_priority_label(decision.severity_label):
        return decision
    return decision.model_copy(
        update={
            "severity_label": ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
            "matched_rules": ["gate_severity_not_permitted"],
            "why_not_higher": [
                "The evidence gate does not permit a severity assessment for this "
                "answer (no collected environment evidence or policy-backed alert "
                "context); incident severity is not assigned."
            ],
            "recommended_priority": "not_applicable",
        }
    )


def _policy_for(use_case_id: str | None) -> dict[str, Any] | None:
    if not use_case_id:
        return None
    return next((dict(item) for item in _matrix().get("policies", []) if item.get("use_case_id") == use_case_id), None)


def _conditions_match(conditions: dict[str, Any], metrics: dict[str, Any]) -> bool:
    for key, expected in conditions.items():
        if key.endswith("_gte"):
            metric_key = key[:-4]
            if float(metrics.get(metric_key, 0) or 0) < float(expected):
                return False
        elif metrics.get(key) != expected:
            return False
    return True


def _priority(severity_label: str) -> str:
    if severity_label.startswith("P1"):
        return "urgent"
    if severity_label.startswith("P2"):
        return "high"
    if severity_label.startswith("P4"):
        return "low"
    return "standard_triage"
