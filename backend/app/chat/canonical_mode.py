"""Canonical planning mode helpers — sole authoritative runtime path."""

from __future__ import annotations

from typing import Any, Literal

CanonicalFailureOutcome = Literal[
    "clarification_required",
    "resolution_failed",
    "planning_failed",
    "policy_blocked",
    "execution_failed",
]

CONTRACT_VERSION = "2026-07-25"
NODE_VERSION = "canonical_v1"

_LEGACY_FAILURE_ALLOWLIST: frozenset[str] = frozenset({"resolution_failed", "planning_failed"})


def is_canonical_authoritative() -> bool:
    return True


def canonical_forbidden_legacy_reason(node: str) -> str:
    return f"canonical_mode_forbids_legacy:{node}"


def build_canonical_failure_state(
    state: dict[str, Any],
    *,
    outcome: CanonicalFailureOutcome,
    reason: str,
    detail: str | None = None,
) -> dict[str, Any]:
    """Return pipeline state with explicit canonical failure — no legacy fallback."""
    failure = {
        "outcome": outcome,
        "reason": reason,
        "detail": detail or reason,
        "canonical_mode": True,
    }
    next_state = {
        **state,
        "canonical_planning_failure": failure,
        "plan_dispatch_trace": {
            "dispatch_source": "canonical_failure",
            "dispatch_schedule": [],
            "failure": failure,
        },
    }
    existing = state.get("evidence_plan")
    if not isinstance(existing, dict) or not existing:
        # Never synthesise an EvidencePlan here. A dict carrying only ``reasons`` and
        # ``canonical_failure`` fails ``EvidencePlan.model_validate`` with ten missing
        # required fields — the same defect class as the old clarification payload.
        next_state.pop("evidence_plan", None)
        return next_state

    evidence = dict(existing)
    evidence.setdefault("reasons", [])
    if isinstance(evidence["reasons"], list):
        evidence["reasons"] = list(dict.fromkeys([*evidence["reasons"], reason]))
    evidence["canonical_failure"] = failure
    # ``answer_mode`` is a closed literal on EvidencePlan; only "clarification" exists.
    # Writing the outcome name verbatim produced answer_mode="policy_blocked" /
    # "clarification_required", which fails EvidencePlan validation on the next consumer.
    # A policy block is recorded in ``canonical_failure`` and leaves answer_mode alone.
    if outcome == "clarification_required":
        evidence["answer_mode"] = "clarification"
    next_state["evidence_plan"] = evidence
    return next_state


def build_typed_planning_failure_state(
    state: dict[str, Any],
    *,
    failure_status: Literal[
        "resolution_failed",
        "planning_failed",
        "unsupported",
        "execution_failed",
        "persistence_failed",
    ],
    reason: str,
    detail: str | None = None,
    category: str = "invariant",
) -> dict[str, Any]:
    """Pure failure-state builder — no telemetry side effects."""
    from app.chat.contracts.canonical_planning_outcome import failure_outcome

    outcome = failure_outcome(
        failure_status,
        category=category,
        reason=reason,
        detail=detail or reason,
        canonical_input=state.get("canonical_planning_input")
        if isinstance(state.get("canonical_planning_input"), dict)
        else None,
    )
    failure = {
        "outcome": failure_status,
        "reason": reason,
        "detail": detail or reason,
        "category": category,
        "canonical_mode": True,
    }
    return {
        **state,
        "canonical_planning_outcome": outcome.model_dump(),
        "canonical_planning_failure": failure,
        "plan_dispatch_trace": {
            "dispatch_source": "canonical_failure",
            "dispatch_schedule": [],
            "failure": failure,
            "canonical_status": failure_status,
        },
    }


def build_persistence_failed_state(
    state: dict[str, Any],
    *,
    reason: str,
    detail: str | None = None,
    category: str = "database",
) -> dict[str, Any]:
    """Fail closed when canonical handoff persistence is unavailable."""
    from app.chat.contracts.canonical_planning_outcome import failure_outcome
    from app.chat.response_validation import emit_request_failed

    outcome = failure_outcome(
        "persistence_failed",
        category=category,
        reason=reason,
        detail=detail,
    )
    failure = {
        "outcome": "persistence_failed",
        "reason": reason,
        "detail": detail or reason,
        "category": category,
        "canonical_mode": True,
    }
    next_state = {
        **state,
        "canonical_planning_outcome": outcome.model_dump(),
        "canonical_planning_failure": failure,
        "plan_dispatch_trace": {
            "dispatch_source": "canonical_failure",
            "dispatch_schedule": [],
            "failure": failure,
        },
    }
    next_state.pop("evidence_plan", None)
    return emit_request_failed(next_state, reason=reason, error_category=category)


def build_non_planned_dispatch_state(state: dict[str, Any], *, status: str) -> dict[str, Any]:
    """Record that dispatch was correctly skipped for a non-planned canonical outcome.

    Clarification and policy blocks are legitimate terminal outcomes, not planning
    failures — labelling them ``planning_failed`` misreports them to every downstream
    surface and to telemetry.
    """
    return {
        **state,
        "plan_dispatch_trace": {
            "dispatch_source": "canonical_non_planned",
            "dispatch_schedule": [],
            "canonical_status": status,
        },
    }
