"""Additive API contract bridge — safe planning outcome + execution uncertainty (G1/G2).

Producer path (live /chat):
  pipeline state ``canonical_planning_outcome`` / ``canonical_planning_failure``
  → ``build_planning_outcome_summary`` (this module)
  → ``PlaceholderResponse.planning_outcome``

  pipeline state ``execution`` dict (incl. hook idempotency / planner executor)
  → ``normalize_execution_envelope`` (this module)
  → ``PlaceholderResponse.execution`` with ``outcome_uncertain`` + ``reconciliation_reason``

Does not alter routing, planning, execution gates, or persistence behavior.
"""

from __future__ import annotations

from typing import Any, Literal

from app.chat.canonical_outcome_read import OutcomeReadKind, read_canonical_planning_outcome
from app.schemas.responses import (
    ExecutionEnvelope,
    HumanReviewEnvelope,
    PlaceholderResponse,
    PlanningOutcomeSummary,
)

PlanningOutcomeCategory = Literal[
    "policy",
    "clarification",
    "planner",
    "database",
    "resolution",
    "unsupported",
    "execution",
    "invariant",
]

RECONCILIATION_REASON_ALLOWLIST: frozenset[str] = frozenset(
    {
        "execution_outcome_uncertain",
        "execution_step_in_progress",
    }
)

_DEFAULT_RECONCILIATION_REASON = "execution_outcome_uncertain"

_STATUS_USER_MESSAGE: dict[str, str] = {
    "clarification_required": "More detail is needed before this investigation can proceed.",
    "policy_blocked": "This request was blocked by SOC policy.",
    "planning_failed": "Investigation planning could not be completed for this question.",
    "persistence_failed": "This turn could not be saved safely; do not assume it was recorded.",
    "resolution_failed": "Required investigation context could not be resolved.",
    "unsupported": "This request is not supported in the current SOC assistant scope.",
    "execution_failed": "A governed execution step failed before a safe answer could be produced.",
    "planned": "Investigation planning completed.",
}

_STATUS_RECOVERY_HINT: dict[str, str] = {
    "clarification_required": "Provide the requested context and send your message again.",
    "policy_blocked": "Use a read-only investigation request or follow your escalation SOP.",
    "planning_failed": "Retry with a shorter question. Contact the SOC platform team if this persists.",
    "persistence_failed": "Retry once. If it continues, contact your operator before retrying execution.",
    "resolution_failed": "Clarify the alert, asset, or time window, then ask again.",
    "unsupported": "Rephrase within supported SOC investigation or knowledge tasks.",
    "execution_failed": "Review the governed answer below; do not retry execution without analyst review.",
    "planned": "",
}

_CATEGORY_BY_STATUS: dict[str, PlanningOutcomeCategory] = {
    "policy_blocked": "policy",
    "clarification_required": "clarification",
    "planning_failed": "planner",
    "persistence_failed": "database",
    "resolution_failed": "resolution",
    "unsupported": "unsupported",
    "execution_failed": "execution",
}


def _safe_user_line(
    preferred: str | None,
    fallback: str,
    *,
    max_len: int = 500,
) -> str:
    text = str(preferred or "").strip()
    if not text:
        text = fallback
    lowered = text.lower()
    if any(
        token in lowered
        for token in (
            "traceback",
            "exception",
            "sqlalchemy",
            "asyncpg",
            "password",
            "token",
            "api_key",
            "http://",
            "https://",
        )
    ):
        text = fallback
    return text[:max_len]


def _category_for_status(status: str, failure_category: str | None) -> PlanningOutcomeCategory | None:
    if failure_category in _CATEGORY_BY_STATUS.values():
        return failure_category  # type: ignore[return-value]
    return _CATEGORY_BY_STATUS.get(status)


def build_planning_outcome_summary(
    state: dict[str, Any],
    *,
    human_review: HumanReviewEnvelope | dict[str, Any] | None = None,
    message: str | None = None,
) -> PlanningOutcomeSummary | None:
    """Build safe planning summary from pipeline state. Returns None when status is ``planned``."""
    read = read_canonical_planning_outcome(state)
    status: str | None = None
    failure_category: str | None = None

    if read.kind != OutcomeReadKind.ABSENT and read.outcome is not None:
        status = read.outcome.status
        if read.outcome.failure is not None:
            failure_category = read.outcome.failure.category
    else:
        failure = state.get("canonical_planning_failure")
        if isinstance(failure, dict):
            status = str(failure.get("outcome") or "")
            failure_category = str(failure.get("category") or "") or None
        dispatch = state.get("plan_dispatch_trace") or {}
        if isinstance(dispatch, dict) and dispatch.get("canonical_status"):
            status = str(dispatch.get("canonical_status"))

    if not status or status == "planned":
        return None

    if status not in _STATUS_USER_MESSAGE:
        status = "planning_failed"
        failure_category = failure_category or "planner"

    review = human_review if isinstance(human_review, dict) else (
        human_review.model_dump() if hasattr(human_review, "model_dump") else {}
    )
    safe_review = str(review.get("safe_message_for_user") or "").strip()

    default_message = _STATUS_USER_MESSAGE[status]
    default_hint = _STATUS_RECOVERY_HINT[status]

    user_message = _safe_user_line(safe_review or message, default_message)
    recovery_hint = _safe_user_line(None, default_hint)
    category = _category_for_status(status, failure_category)

    return PlanningOutcomeSummary(
        status=status,
        user_message=user_message,
        recovery_hint=recovery_hint,
        category=category,
    )


def sanitize_reconciliation_reason(
    raw: str | None,
    *,
    outcome_uncertain: bool,
) -> str | None:
    if not outcome_uncertain:
        return None
    cleaned = str(raw or "").strip()
    if cleaned in RECONCILIATION_REASON_ALLOWLIST:
        return cleaned
    return _DEFAULT_RECONCILIATION_REASON


def normalize_execution_envelope(execution: Any) -> ExecutionEnvelope | None:
    """Coerce pipeline execution dict/model to API envelope with uncertainty fields."""
    if execution is None:
        return None
    if isinstance(execution, ExecutionEnvelope):
        payload = execution.model_dump()
    elif isinstance(execution, dict):
        payload = dict(execution)
    else:
        return None

    outcome_uncertain = bool(payload.get("outcome_uncertain"))
    raw_reason = payload.get("reconciliation_reason") or payload.get("block_reason") or payload.get("reason")
    payload["outcome_uncertain"] = outcome_uncertain
    payload["reconciliation_reason"] = sanitize_reconciliation_reason(
        str(raw_reason) if raw_reason is not None else None,
        outcome_uncertain=outcome_uncertain,
    )

    allowed = set(ExecutionEnvelope.model_fields.keys())
    filtered = {key: payload[key] for key in payload if key in allowed}
    return ExecutionEnvelope.model_validate(filtered)


def enrich_placeholder_response(
    response: PlaceholderResponse,
    state: dict[str, Any] | None = None,
) -> PlaceholderResponse:
    """Attach G1/G2 fields without changing message authority fields."""
    state_payload = state if isinstance(state, dict) else {}
    planning = build_planning_outcome_summary(
        state_payload,
        human_review=response.human_review,
        message=response.message,
    )
    execution = normalize_execution_envelope(response.execution)
    updates: dict[str, Any] = {}
    if planning is not None:
        updates["planning_outcome"] = planning
    if execution is not None:
        updates["execution"] = execution
    if not updates:
        return response
    return response.model_copy(update=updates)
