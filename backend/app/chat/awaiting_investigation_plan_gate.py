"""Awaiting-investigation-plan HIL gate + guided LLM failure classification.

When investigation status is awaiting approval, material investigation packaging
(RAG collection, InvestigationOutcome, synthesis narration) must not run.
Guided LLM skip reasons must not be misreported as model unavailability.
"""

from __future__ import annotations

from typing import Any, Literal

GuidedFailureClass = Literal[
    "ACTUAL_MODEL_UNAVAILABLE",
    "ACTUAL_TIMEOUT",
    "ORCHESTRATION_SKIP",
    "POLICY_SKIP",
    "CONFIG_DISABLED",
    "UNKNOWN_INTERNAL_FAILURE",
    "NONE",
]

_AWAITING_APPROVAL_STATUSES = frozenset(
    {
        "awaiting_approval",
        "edited_awaiting_approval",
    }
)

_ORCHESTRATION_SKIP_MARKERS = (
    "synthesis_lab_already_narrated",
    "narration_hop_blocked",
    "turn_budget",
    "guided_route_locked",
    "composer_skipped",
    "already_narrated",
    "budget_exhausted",
    "hop_blocked",
)

_POLICY_SKIP_MARKERS = (
    "policy",
    "should_skip_llm_composer",
    "composer_policy",
    "blocked_by_policy",
)

_TIMEOUT_MARKERS = ("timeout", "timed_out", "deadline")

_UNAVAILABLE_MARKERS = (
    "connection",
    "provider_unavailable",
    "endpoint",
    "unreachable",
    "econnrefused",
    "dns",
    "http_error",
    "model_unavailable",
    "url_error",
)


def is_awaiting_investigation_approval(state: dict[str, Any] | None) -> bool:
    """True when the turn must stop at plan Approve/Edit/Cancel (no material execution packaging)."""
    if not isinstance(state, dict):
        return False
    approval = state.get("investigation_approval")
    if isinstance(approval, dict):
        status = str(approval.get("status") or "").strip()
        if status in _AWAITING_APPROVAL_STATUSES:
            return True
    planning = state.get("canonical_planning_outcome")
    if isinstance(planning, dict) and str(planning.get("status") or "") == "awaiting_investigation_plan":
        return True
    return False


def skipped_soc_kb_awaiting_approval_payload() -> dict[str, Any]:
    """Planning-phase RAG skip marker — not SourceEvidence collection.

    Shape mirrors utility-authoring skip so ``build_source_evidence`` and
    ``_rag_no_match`` treat it as non-material (empty retrieved_entries).
    """
    return {
        "retrieved_entries": [],
        "retrieval_status": "skipped",
        "ambiguity_status": "clear",
        "ambiguity_assist": None,
        "confidence": 0.0,
        "reasons": ["rag_skipped_awaiting_investigation_approval"],
        "warnings": [],
        "rag_skipped_awaiting_investigation_approval": True,
        "selected_collections": [],
        "collection_selection": {},
        "direct_to_llm": False,
        "llm_selection_enabled": False,
        "evidence_origin": "rag_skipped_awaiting_investigation_approval",
        "skipped_reason": "awaiting_investigation_approval",
    }


def classify_guided_llm_failure(reason: str | None) -> GuidedFailureClass:
    text = str(reason or "").strip().lower()
    if not text:
        return "NONE"
    if any(m in text for m in _TIMEOUT_MARKERS):
        return "ACTUAL_TIMEOUT"
    if any(m in text for m in _ORCHESTRATION_SKIP_MARKERS):
        return "ORCHESTRATION_SKIP"
    if "disabled" in text or "config" in text:
        return "CONFIG_DISABLED"
    if any(m in text for m in _POLICY_SKIP_MARKERS):
        return "POLICY_SKIP"
    if any(m in text for m in _UNAVAILABLE_MARKERS):
        return "ACTUAL_MODEL_UNAVAILABLE"
    if text in {"guided_llm_unavailable", "unavailable"}:
        return "ACTUAL_MODEL_UNAVAILABLE"
    return "UNKNOWN_INTERNAL_FAILURE"


def should_treat_guided_skip_as_degraded(reason: str | None) -> bool:
    """Orchestration/policy/config skips are not 'planner unavailable' degrades."""
    klass = classify_guided_llm_failure(reason)
    return klass in {
        "ACTUAL_MODEL_UNAVAILABLE",
        "ACTUAL_TIMEOUT",
        "UNKNOWN_INTERNAL_FAILURE",
    }


def analyst_facing_guided_degraded_message(
    *,
    failure_reason: str | None,
    checklist: list[str] | None = None,
) -> str:
    """Neutral analyst copy — never leak internal reason codes or env var names."""
    from app.chat.guided_step_sanitizer import filter_analyst_facing_steps

    klass = classify_guided_llm_failure(failure_reason)
    if klass == "ACTUAL_TIMEOUT":
        body = (
            "The guided planning step timed out before completion. "
            "No telemetry was queried."
        )
    elif klass == "ACTUAL_MODEL_UNAVAILABLE":
        body = (
            "The guided planning model is currently unavailable. "
            "No telemetry was queried."
        )
    elif klass in {"ORCHESTRATION_SKIP", "POLICY_SKIP", "CONFIG_DISABLED"}:
        body = (
            "The guided planning step could not complete. "
            "No telemetry was queried."
        )
    else:
        body = (
            "The guided planning step could not complete. "
            "No telemetry was queried."
        )
    items = filter_analyst_facing_steps(list(checklist or []))[:6]
    if not items:
        return body
    checklist_block = "\n".join(f"- {item}" for item in items)
    return f"{body}\n\nMinimal deterministic checklist:\n{checklist_block}"


def strip_material_fields_for_awaiting_approval(response_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Defense-in-depth: drop post-execution surfaces from an awaiting-approval payload."""
    out = dict(response_kwargs)
    out["investigation_outcome"] = None
    out["source_evidence"] = []
    out["analyst_response"] = None
    out["analyst_summary"] = None
    out["proposed_actions"] = None
    out["email_draft"] = None
    # Keep investigation_approval / validated_investigation_plan / planning_outcome.
    return out
