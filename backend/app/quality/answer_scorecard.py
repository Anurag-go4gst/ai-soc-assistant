"""Deterministic answer scorecard (WS3 T3.1) — read-model, never authority.

Summarizes whether the final chat answer is useful, complete, and governed:
ten named checks + an overall verdict, computed from the already-decided
payload (contract, analyst card, decisions). Reuses the Tier-D checks for
claim safety so scorecard and eval cannot drift. Nothing here changes
routing, severity, MITRE, SPL, HIL, or execution outcomes.
"""

from __future__ import annotations

from typing import Any

from app.quality.answer_quality_checks import run_answer_quality_checks

_HONORED_MATCH_PATHS = {
    "exact_105_question",
    "exact_105_plus_use_case_catalog",
    "use_case_catalog",
    "near_105_question",
    "semantic_105_question",
    "llm_promoted_with_registry_validation",
}

_SEVERITY_NOT_ASSIGNED = "not assigned"


def build_answer_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    """Score one chat response payload. Pure read-model."""
    analyst = payload.get("analyst_response") or {}
    contract = payload.get("answer_contract") or {}
    plan = payload.get("evidence_plan") or {}
    execution = payload.get("execution") or {}
    review = payload.get("human_review") or {}
    severity = payload.get("severity_decision") or {}
    candidate_spl = payload.get("candidate_spl") or {}
    query_to_intent = payload.get("query_to_intent") or {}
    mappings = query_to_intent.get("candidate_mappings") or {}
    intent = query_to_intent.get("intent_classification") or {}

    tier_d = {item.check_id: item.passed for item in run_answer_quality_checks(payload)}
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    def record(name: str, ok: bool, why: str) -> None:
        checks[name] = bool(ok)
        if not ok:
            reasons.append(f"{name}: {why}")

    match_path = str(mappings.get("match_path") or "")
    notice = bool(contract.get("out_of_catalog_notice"))
    hil_required = bool(contract.get("human_review_required") or review.get("required"))
    record(
        "route_honored",
        match_path in _HONORED_MATCH_PATHS or (match_path == "out_of_registry" and (notice or hil_required)),
        f"match_path={match_path or 'unknown'} without honest out-of-catalog handling",
    )

    clarification_turn = bool(
        intent.get("requires_clarification") or str(plan.get("answer_mode") or "") == "clarification"
    )
    guidance_backing = any(
        _present(analyst.get(field))
        for field in (
            "recommended_actions",
            "analyst_checklist",
            "investigation_steps",
            "sop_guidance",
            "retrieved_playbook",
            "review_notice",
            "draft_spl_code",
            "limitations",
        )
    ) or _present((analyst.get("spl_draft_preview") or {}).get("draft_spl"))
    record(
        "analyst_guidance_present",
        guidance_backing or clarification_turn or hil_required or notice,
        "answer carries no analyst guidance, clarification, or review notice",
    )

    render = contract.get("render_sections") or {}
    skill_sections_ok = True
    if bool(plan.get("enrichment_driven")):
        skill_sections_ok = bool(render.get("triage_checklist")) and bool(
            contract.get("analyst_checklist_safe")
        )
    record(
        "skill_sections_present",
        skill_sections_ok and tier_d.get("completeness_sections", True),
        "enrichment-active answer is missing its checklist sections (or an enabled section lacks backing)",
    )

    spl_involved = bool(plan.get("needs_spl")) or _present(candidate_spl.get("candidate_spl")) or _present(
        (analyst.get("spl_draft_preview") or {}).get("draft_spl")
    )
    spl_status_clear = not spl_involved or any(
        _present(value)
        for value in (
            analyst.get("spl_status"),
            payload.get("spl_template_status"),
            (analyst.get("spl_draft_preview") or {}).get("draft_status"),
            (payload.get("spl_validation") or {}).get("template_id"),
        )
    )
    record("spl_status_clear", spl_status_clear, "SPL/draft involved but no status surfaced")

    execution_state = str(execution.get("status") or "")
    record(
        "execution_status_clear",
        bool(execution_state) or not spl_involved,
        "execution state missing while SPL artifacts are in play",
    )

    record(
        "mitre_wording_safe",
        tier_d.get("grounding_no_orphan_claims", False),
        "MITRE/severity claims in prose do not trace to contract fields",
    )

    severity_label = str(
        (severity.get("severity_label") if isinstance(severity, dict) else None) or ""
    )
    knowledge_suppressed = contract.get("severity_label") is None and str(
        intent.get("intent_family") or ""
    ) in {"policy_knowledge", "sop_or_playbook", "knowledge_only", "mitre_explanation", "clarification_required"}
    record(
        "severity_state_clear",
        bool(severity_label) or knowledge_suppressed,
        "severity neither assigned, explicitly not-assigned, nor knowledge-suppressed",
    )

    hil_state_clear = isinstance(review.get("required"), bool) or _present(analyst.get("hil_status"))
    record("hil_status_clear", hil_state_clear, "human-review state not surfaced")

    record(
        "no_unsupported_claims",
        tier_d.get("no_forbidden_claims", False) and tier_d.get("honesty_limitations", False),
        "forbidden compromise/execution claim or missing non-execution disclosure",
    )

    resource_plan = plan.get("resource_plan") if isinstance(plan.get("resource_plan"), dict) else {}
    provenance = resource_plan.get("provenance") if isinstance(resource_plan.get("provenance"), dict) else {}
    out_of_registry = str(provenance.get("match_path") or match_path or "") == "out_of_registry"
    record(
        "out_of_catalog_honest",
        not out_of_registry or notice or hil_required,
        "out-of-registry answer without notice or review",
    )

    verdict = "pass" if all(checks.values()) else "review"
    narration = payload.get("narration_visibility")
    narration_summary = None
    if isinstance(narration, dict):
        narration_summary = {
            "final_answer_source": narration.get("final_answer_source"),
            "fallback_used": narration.get("fallback_used"),
            "guard_blocked": narration.get("guard_blocked"),
            "skip_category": narration.get("skip_category"),
        }
    return {
        "verdict": verdict,
        "checks": checks,
        "reasons": reasons,
        "tier_d": tier_d,
        "narration": narration_summary,
    }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return True
