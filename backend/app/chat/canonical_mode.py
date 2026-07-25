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
    evidence = dict(state.get("evidence_plan") or {})
    evidence.setdefault("reasons", [])
    if isinstance(evidence["reasons"], list):
        evidence["reasons"] = list(dict.fromkeys([*evidence["reasons"], reason]))
    evidence["canonical_failure"] = failure
    if outcome in {"clarification_required", "policy_blocked"}:
        evidence["answer_mode"] = outcome
    return {
        **state,
        "evidence_plan": evidence,
        "canonical_planning_failure": failure,
        "plan_dispatch_trace": {
            "dispatch_source": "canonical_failure",
            "dispatch_schedule": [],
            "failure": failure,
        },
    }
