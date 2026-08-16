"""Plan 8 D0 — attach EVIDENCE sufficiency from E0A EvidenceState vs final RQC."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.staged_sufficiency import from_evidence_state
from app.evidence.minimal_evidence_state import derive_minimal_evidence_state


def attach_evidence_sufficiency(state: dict[str, Any]) -> dict[str, Any]:
    """Write evidence_sufficiency from current governed state. Never pending_finalize.

    Does not replace a Stage 3J context_sufficiency envelope already computed by
    finalize. Does not grant routes, capabilities, RBAC, HIL, or execution.
    """
    evidence_state = state.get("evidence_state")
    if not isinstance(evidence_state, dict):
        evidence_state = derive_minimal_evidence_state(
            source_evidence=state.get("source_evidence") if isinstance(state.get("source_evidence"), list) else None,
            structured_context=state.get("structured_context")
            if isinstance(state.get("structured_context"), dict)
            else None,
            evidence_plan=state.get("evidence_plan") if isinstance(state.get("evidence_plan"), dict) else None,
            resolved_query_contract=state.get("resolved_query_contract")
            if isinstance(state.get("resolved_query_contract"), dict)
            else None,
            canonical_facts=state.get("canonical_facts") if isinstance(state.get("canonical_facts"), dict) else None,
            final_evidence_gate=state.get("final_evidence_gate")
            if isinstance(state.get("final_evidence_gate"), dict)
            else None,
            execution=state.get("execution") if isinstance(state.get("execution"), dict) else None,
        ).model_dump_view()
    from app.evidence.session_evidence_applicability import (
        apply_session_evidence_applicability,
        session_applicability_inputs,
    )

    prior_scope, prior_refs = session_applicability_inputs(state)
    if prior_scope or prior_refs:
        evidence_state = apply_session_evidence_applicability(
            evidence_state,
            resolved_query_contract=state.get("resolved_query_contract")
            if isinstance(state.get("resolved_query_contract"), dict)
            else None,
            prior_scope=prior_scope,
            prior_refs=prior_refs,
        ).model_dump_view()
    result = from_evidence_state(
        evidence_state,
        resolved_query_contract=state.get("resolved_query_contract")
        if isinstance(state.get("resolved_query_contract"), dict)
        else None,
    )
    payload = result.model_dump(mode="json")
    staged_surface = {
        "status": result.status,
        "synthesis_allowed": False,
        "synthesis_readiness": result.status in {"SUFFICIENT", "PARTIAL"},
        "reasons": list(result.reason_codes),
        "missing_evidence": list(result.missing),
        "next_action": result.next_action,
        "stop_reason": result.reason_codes[0] if result.reason_codes else None,
        "stale_evidence": list(evidence_state.get("stale") or []),
        "invalidated_evidence": list(evidence_state.get("invalidated") or []),
        "blocked_evidence": list(evidence_state.get("blocked") or []),
        "stage": "EVIDENCE",
    }
    existing = state.get("context_sufficiency")
    preserve_stage3j = (
        isinstance(existing, dict)
        and str(existing.get("status") or "") not in {"", "pending_finalize"}
        and str(existing.get("status") or "")
        not in {"SUFFICIENT", "PARTIAL", "INSUFFICIENT", "BLOCKED"}
    )
    return {
        **state,
        "evidence_state": evidence_state,
        "evidence_sufficiency": payload,
        "context_sufficiency": existing if preserve_stage3j else staged_surface,
    }
