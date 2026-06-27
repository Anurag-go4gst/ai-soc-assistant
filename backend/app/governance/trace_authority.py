"""Authority tier labels for debug / governance trace panels (metadata only)."""

from __future__ import annotations

from typing import Any, Literal

AuthorityTier = Literal["AUTHORITATIVE", "PLANNING", "ADVISORY", "DIAGNOSTIC"]

TIER_AUTHORITATIVE: AuthorityTier = "AUTHORITATIVE"
TIER_PLANNING: AuthorityTier = "PLANNING"
TIER_ADVISORY: AuthorityTier = "ADVISORY"
TIER_DIAGNOSTIC: AuthorityTier = "DIAGNOSTIC"


def authority_label(
    tier: AuthorityTier,
    note: str,
) -> dict[str, str]:
    return {"authority_tier": tier, "authority_note": note}


def attach_authority_tier(
    payload: dict[str, Any] | None,
    *,
    tier: AuthorityTier,
    note: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    enriched = dict(payload)
    enriched.update(authority_label(tier, note))
    return enriched


def build_control_plane_authority_index(
    *,
    has_run_contract: bool,
    has_final_evidence_gate: bool,
) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {
        "route_adjudication": authority_label(
            TIER_AUTHORITATIVE,
            "Final route adjudication after deterministic policy.",
        ),
        "routing_provenance": authority_label(
            TIER_AUTHORITATIVE,
            "Canonical routing provenance for the live turn.",
        ),
        "evidence_plan": authority_label(
            TIER_PLANNING,
            "Evidence collection plan; planning snapshot only.",
        ),
        "resource_planner": authority_label(
            TIER_PLANNING,
            "Composed ResourcePlan decisions; not execution authority.",
        ),
        "planning_decision": authority_label(
            TIER_PLANNING,
            "Planner path selection metadata.",
        ),
        "llm_intent_advisory": authority_label(
            TIER_ADVISORY,
            "LLM intent advisory; deterministic policy wins on conflict.",
        ),
        "llm_advisory_trace": authority_label(
            TIER_ADVISORY,
            "LLM advisory attempt/candidate metadata; dropped reasons are not final failure.",
        ),
        "llm_plan_validation": authority_label(
            TIER_ADVISORY,
            "LLM plan validation outcome; advisory unless promoted by policy.",
        ),
        "rag_trace": authority_label(
            TIER_ADVISORY,
            "RAG retrieval hints and evidence refs.",
        ),
        "precondition_evaluation": authority_label(
            TIER_DIAGNOSTIC,
            "Route-plan shadow precondition evaluation (diagnostic).",
        ),
        "candidate_spl_generation": authority_label(
            TIER_PLANNING,
            "SPL candidate generation metadata prior to final RunContract projection.",
        ),
        "spl_slot_binding": authority_label(
            TIER_DIAGNOSTIC,
            "Slot binding validator diagnostics unless projected by RunContract block reason.",
        ),
        "mcp_execution": authority_label(
            TIER_AUTHORITATIVE,
            "Final MCP execution gate outcome for the turn when present.",
        ),
        "answer_contract": authority_label(
            TIER_AUTHORITATIVE,
            "Answer contract read-model for finalize.",
        ),
        "final_answer_validation": authority_label(
            TIER_AUTHORITATIVE,
            "Final answer validator outcome.",
        ),
    }
    if has_run_contract:
        index["run_contract"] = authority_label(
            TIER_AUTHORITATIVE,
            "RunContract owns final-run public posture: render, SPL lifecycle, MCP posture.",
        )
    if has_final_evidence_gate:
        index["final_evidence_gate"] = authority_label(
            TIER_AUTHORITATIVE,
            "FinalEvidenceGate owns evidence-derived HIL, live-language, and MITRE/severity caps.",
        )
    return index
