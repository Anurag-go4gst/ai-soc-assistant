"""Deterministic understanding authority provenance (P4).

Packages the T1–T3 complete-or-abstain decision and optional T4 hop into
analyst-visible lines. No chain-of-thought, prompts, or model reasoning.
Reuses :func:`abstain_acceptance` as the single gate authority.
"""

from __future__ import annotations

from typing import Any

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.lane_router import T1_PATHS, T2_PATHS, T3_PATHS, initial_tier_for_match_path
from app.chat.semantic_t4_understanding import _ABSTAIN_REASONS_WITHOUT_T4, abstain_acceptance
from app.spl.spl_provenance_trace import build_spl_authoring_provenance_lines

_INTENT_LABELS: dict[str, str] = {
    "spl_generation_only": "SPL authoring",
    "spl_generation_and_run": "SPL generation and run",
    "live_investigation": "Live investigation",
    "guided_investigation": "Guided investigation",
    "knowledge_recall": "Knowledge recall",
    "knowledge_only": "Knowledge",
    "policy_knowledge": "Policy knowledge",
    "mitre_mapping": "MITRE mapping",
    "mitre_explanation": "MITRE explanation",
    "clarification_required": "Clarification",
    "hybrid_investigation_plus_policy": "Hybrid investigation",
    "reference_knowledge": "Reference knowledge",
}


def _as_contract(raw: dict[str, Any] | ResolvedQueryContract | None) -> ResolvedQueryContract | None:
    if raw is None:
        return None
    if isinstance(raw, ResolvedQueryContract):
        return raw
    if isinstance(raw, dict) and raw.get("intent_family"):
        try:
            return ResolvedQueryContract(**raw)
        except Exception:
            return None
    return None


def _match_path(contract: ResolvedQueryContract) -> str:
    provenance = contract.provenance or {}
    return str(
        provenance.get("deterministic_match_path")
        or provenance.get("observed_match_path")
        or provenance.get("match_path")
        or contract.qualification_source
        or ""
    ).strip()


def _intent_label(intent_family: str | None) -> str:
    key = str(intent_family or "").strip()
    if not key:
        return "Unknown"
    return _INTENT_LABELS.get(key, key.replace("_", " "))


def _t4_line(contract: ResolvedQueryContract, *, acceptance_decision: str) -> str:
    if acceptance_decision == "ACCEPT":
        return "skipped"
    semantic = (contract.provenance or {}).get("semantic_t4")
    semantic = semantic if isinstance(semantic, dict) else {}
    acceptance = abstain_acceptance(contract)
    if _ABSTAIN_REASONS_WITHOUT_T4 & set(acceptance.reason_codes):
        return "skipped"
    if contract.understanding_source == "semantic_t4" and semantic.get("accepted"):
        return "used"
    if semantic.get("invoked"):
        if semantic.get("timed_out"):
            return "unavailable"
        if semantic.get("accepted") is False:
            reasons = semantic.get("rejected_reasons") or []
            if reasons:
                return "unavailable"
            return "rejected"
        return "used"
    if acceptance.t4_permitted:
        return "skipped"
    return "skipped"


def _tier_ladder(contract: ResolvedQueryContract) -> tuple[str, list[dict[str, str]]]:
    semantic = (contract.provenance or {}).get("semantic_t4")
    semantic = semantic if isinstance(semantic, dict) else {}
    acceptance = abstain_acceptance(contract)
    # T4 runs only after a complete T1–T3 ABSTAIN. A merged Final RQC may look
    # complete even though the gate abstained — use the T4 trace as authority.
    if contract.understanding_source == "semantic_t4" or semantic.get("invoked"):
        acceptance_decision = "ABSTAIN"
    else:
        acceptance_decision = acceptance.decision

    match_path = _match_path(contract)
    initial_tier = initial_tier_for_match_path(match_path or None)

    if acceptance_decision == "ACCEPT":
        return acceptance_decision, [
            {"label": "T1–T3", "value": "accepted"},
            {"label": "T4", "value": "skipped"},
        ]

    t1 = "no match"
    if match_path in T1_PATHS:
        t1 = "no accepted match"

    t2 = "no accepted match"
    if match_path in T2_PATHS:
        t2 = "no accepted match"

    t3 = "abstained"
    if match_path in T3_PATHS:
        t3 = "abstained"
    elif initial_tier in {"T1", "T2"}:
        t3 = "no accepted match"

    return acceptance_decision, [
        {"label": "T1 exact", "value": t1},
        {"label": "T2 catalogue", "value": t2},
        {"label": "T3 candidates", "value": t3},
        {"label": "T4 semantic", "value": _t4_line(contract, acceptance_decision=acceptance_decision)},
    ]


def build_understanding_provenance(
    *,
    resolved_query_contract: dict[str, Any] | ResolvedQueryContract | None,
    route_adjudication: dict[str, Any] | None = None,
    routed: dict[str, Any] | None = None,
    candidate_spl: dict[str, Any] | None = None,
    spl_validation: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build deterministic authority-path lines for analyst provenance surfaces."""
    contract = _as_contract(resolved_query_contract)
    if contract is None:
        return None

    acceptance = abstain_acceptance(contract)
    acceptance_decision, tier_lines = _tier_ladder(contract)
    adjudication = route_adjudication if isinstance(route_adjudication, dict) else {}
    routed_payload = routed if isinstance(routed, dict) else {}
    owner = (
        str(adjudication.get("selected_skill") or "").strip()
        or str(routed_payload.get("selected_skill") or "").strip()
        or None
    )

    lines = [
        *tier_lines,
        {"label": "Final intent", "value": _intent_label(contract.intent_family)},
        {"label": "Final owner", "value": owner or "—"},
        {
            "label": "Final RQC",
            "value": (
                f"{contract.understanding_source or 'unknown'}/"
                f"{contract.qualification_tier or '—'}/"
                f"{acceptance_decision}"
            ),
        },
    ]
    lines.extend(build_spl_authoring_provenance_lines(candidate_spl, spl_validation))

    semantic = (contract.provenance or {}).get("semantic_t4")
    semantic = semantic if isinstance(semantic, dict) else {}

    t4_status = _t4_line(contract, acceptance_decision=acceptance_decision)
    return {
        "schema_version": "understanding_provenance_v1",
        "acceptance_decision": acceptance_decision,
        "qualification_tier": contract.qualification_tier,
        "understanding_source": contract.understanding_source,
        "reason_codes": list(acceptance.reason_codes),
        "final_rqc": {
            "intent_family": contract.intent_family,
            "answer_goal": contract.answer_goal,
            "qualification_tier": contract.qualification_tier,
            "understanding_source": contract.understanding_source,
            "acceptance_decision": acceptance_decision,
            "clarification_required": bool(contract.clarification_required),
        },
        "lines": lines,
        "t4_invoked": bool(semantic.get("invoked")),
        "t4_accepted": bool(semantic.get("accepted")),
        "t4_skipped": t4_status == "skipped",
    }
