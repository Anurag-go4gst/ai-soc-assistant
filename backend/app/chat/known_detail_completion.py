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


#: Entity fields that count as the analyst narrowing the question to a specific target.
_SCOPING_ENTITY_FIELDS: tuple[str, ...] = ("host", "user", "asset", "source_ip", "alert_id")

#: Quantifiers the parser records as entity values; they express breadth, not a scope.
_GENERIC_ENTITY_VALUES = frozenset({"multiple", "all", "any", "several", "various", "unknown"})


def _analyst_scoped(query_understanding: Any) -> bool:
    """True when the question names a concrete host/user/asset/IP/alert to scope to."""
    entities = getattr(query_understanding, "entities", None)
    if entities is None:
        return False
    for field in _SCOPING_ENTITY_FIELDS:
        values = getattr(entities, field, None)
        if isinstance(values, str):
            values = [values]
        for value in values or []:
            text = str(value).strip().lower()
            if text and text not in _GENERIC_ENTITY_VALUES:
                return True
    return False


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

    user_only_missing = [k for k in missing if categories.get(k) == "user_only"]
    tool_missing = [k for k in missing if categories.get(k) == "tool_discoverable"]
    planner_missing = [k for k in missing if categories.get(k) == "planner_required"]

    # ``required`` is the use case's ``evidence_requirements`` — the fields the *answer*
    # presents (fail_count, first_failure, command_line, host, user, ...). Those are
    # produced by the governed SPL; they are not analyst inputs, and an absent one means
    # "the search has not run yet", not "the analyst owes us a value". Feeding them into
    # an input-completeness gate diverted governed catalogue questions into guided
    # resolution, which dropped their approved template SPL for an ungoverned lab draft
    # and moved the route off its catalogue skill.
    #
    # So on a mapped catalogue use case these are advisory: they surface as limitations
    # and telemetry, and never divert or clarify. Genuine input gaps on this lane are
    # unbound *template slots*, which the SPL slot-resolution path already owns
    # (``graph_node_spl_source_resolve`` + source-profile binding), and unmapped asks
    # still fall through to the guided lane via the lane router.
    # ...but only when the analyst supplied no concrete scope. Two different questions
    # reach this gate:
    #   * "Which hosts ran suspicious PowerShell?" — nothing scoped, so it is the
    #     catalogue question as written; the governed template answers it and the
    #     evidence requirements are simply what the search will return.
    #   * "Investigate failed login spike for host:WRONG-99" — the analyst *did* scope it,
    #     so a still-missing user-only field is a real gap worth clarifying.
    # The signal is a concrete scoping entity in the question, not ``relevant_present``:
    # that set also counts keys inferred from intent/telemetry, so it reports True for
    # unscoped catalogue questions too. Generic quantifiers ("multiple", "all") are
    # explicitly not a scope.
    advisory_only = bool(use_case_id) and not _analyst_scoped(query_understanding)
    blocking_missing = [] if advisory_only else [*user_only_missing, *tool_missing]
    divert = bool(blocking_missing) and not relevant_present

    clarification = bool(user_only_missing) and not advisory_only

    status: Literal["complete", "incomplete", "clarification_required"] = "complete"
    divert_reason: str | None = None
    if not blocking_missing:
        # Planner-supplied fields alone leave the path complete: the plan can proceed and
        # the governed SPL renders. They surface as limitations, not as a gate.
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
        divert_to_guided=divert or (bool(tool_missing) and not advisory_only),
        divert_reason=divert_reason,
        clarification_required=clarification and not divert,
        limitations=limitations,
    )
