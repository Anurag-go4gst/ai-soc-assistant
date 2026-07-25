"""Known-path completeness gate and missing-field classification."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.chat.evidence_planner import _present_evidence_keys
from app.use_cases.content_enrichment import get_runtime_curated_enrichment

MissingFieldCategory = Literal["planner_required", "tool_discoverable", "user_only", "optional"]

# Keys that DetailTools may help resolve on diversion.
_TOOL_DISCOVERABLE = frozenset(
    {
        "index",
        "sourcetype",
        "src",
        "source_ip",
        "host",
        "domain",
        "reference_dataset",
    }
)

_USER_ONLY = frozenset(
    {
        "alert_id",
        "time_window",
        "user",
        "approval",
        "analyst_confirmation",
    }
)


class KnownCompletenessResult(BaseModel):
    required_fields: list[str] = Field(default_factory=list)
    present_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    missing_field_categories: dict[str, MissingFieldCategory] = Field(default_factory=dict)
    optional_fields: list[str] = Field(default_factory=list)
    relevant_telemetry_present: bool = False
    completeness_status: Literal["complete", "incomplete", "clarification_required"] = "complete"
    divert_to_guided: bool = False
    divert_reason: str | None = None
    clarification_required: bool = False
    limitations: list[str] = Field(default_factory=list)


def classify_missing_field(key: str) -> MissingFieldCategory:
    if key in _USER_ONLY:
        return "user_only"
    if key in _TOOL_DISCOVERABLE:
        return "tool_discoverable"
    return "planner_required"


def evaluate_known_detail_completion(
    *,
    use_case_id: str | None,
    query_to_intent: dict[str, Any] | None,
    query_understanding: Any,
) -> KnownCompletenessResult:
    present = _present_evidence_keys(
        query_to_intent=query_to_intent,
        query_understanding=query_understanding,
    )
    context = get_runtime_curated_enrichment(use_case_id) if use_case_id else None
    required = list(dict.fromkeys(context.evidence_requirements)) if context else []
    optional = []
    if context:
        optional = [k for k in context.not_claimed_defaults if k not in required]

    missing = [k for k in required if k not in present]
    categories = {k: classify_missing_field(k) for k in missing}
    relevance_universe = set(required) | set(optional)
    relevant_present = bool(present & relevance_universe)

    divert = bool(missing) and not relevant_present
    user_only_missing = [k for k in missing if categories.get(k) == "user_only"]
    tool_missing = [k for k in missing if categories.get(k) == "tool_discoverable"]
    planner_missing = [k for k in missing if categories.get(k) == "planner_required"]

    clarification = bool(user_only_missing) or (
        bool(planner_missing) and not tool_missing and not divert
    )

    status: Literal["complete", "incomplete", "clarification_required"] = "complete"
    divert_reason: str | None = None
    if not missing:
        status = "complete"
    elif divert:
        status = "incomplete"
        divert_reason = "no_relevant_required_present"
    elif clarification:
        status = "clarification_required"
    else:
        status = "incomplete"
        divert_reason = "tool_discoverable_gaps"

    limitations: list[str] = []
    optional_missing = [k for k in optional if k not in present]
    if optional_missing and not missing:
        limitations.append(f"optional_evidence_missing:{','.join(optional_missing[:5])}")

    return KnownCompletenessResult(
        required_fields=required,
        present_fields=sorted(present),
        missing_fields=missing,
        missing_field_categories=categories,
        optional_fields=optional,
        relevant_telemetry_present=relevant_present,
        completeness_status=status,
        divert_to_guided=divert or bool(tool_missing),
        divert_reason=divert_reason,
        clarification_required=clarification and not divert,
        limitations=limitations,
    )
