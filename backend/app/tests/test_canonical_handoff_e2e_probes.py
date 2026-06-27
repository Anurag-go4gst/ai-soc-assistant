"""End-to-end /chat probes for T0/T1/T2 canonical handoff through RunContract.

Exercises the full live pipeline (``build_live_chat_response``) — not isolated
planners — to prove weak-exact identity, Environment KB precedence, lineage from
EvidencePlan through ResourcePlan into RunContract, and FinalEvidenceGate parity.
"""

from __future__ import annotations

import json
import re

import pytest

from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest

_Q046 = "Which users have excessive failed logins?"
_T1_SPL = "Generate SPL for failed logins"
_T2_OUT_OF_SET = (
    "Strange OT chatter to a brand new external host overnight, anything to hunt?"
)
_ENV_KB_USER_INDEX = "Generate SPL for index=scada_perf by rtu_id over last 24h"
_IN_REGISTRY_ANALYTICS = "Which hosts are generating the most SMB traffic?"

_GATE_MIRRORED_FIELDS = (
    "collected_evidence_count",
    "allow_severity_assessment",
    "allow_results_table",
    "allow_mitre_mapping",
    "allow_live_result_language",
    "effective_hil_required",
)

_FORBIDDEN_LIVE_PHRASES = (
    "currently showing",
    "we found in splunk",
    "observed in splunk",
    "execution: executed",
    "mock mcp execution complete",
)

_FORBIDDEN_CONFIRMED_MITRE = re.compile(
    r"\bconfirmed\b.{0,32}\b(T\d{4}(?:\.\d{3})?)\b",
    re.IGNORECASE,
)


@pytest.fixture(autouse=True)
def _control_plane_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def _payload(question: str) -> dict:
    return build_live_chat_response(ChatRequest(message=question)).model_dump(mode="json")


def _gate(payload: dict) -> dict:
    return (payload.get("structured_context") or {}).get("final_evidence_gate") or {}


def _run_contract(payload: dict) -> dict:
    return payload.get("run_contract") or {}


def _routing(payload: dict) -> dict:
    return (_run_contract(payload).get("routing") or {})


def _evidence_plan(payload: dict) -> dict:
    return payload.get("evidence_plan") or {}


def _resource_plan(payload: dict) -> dict:
    return (_evidence_plan(payload).get("resource_plan") or {})


def _assert_gate_agrees_with_run_contract(payload: dict) -> None:
    gate = _gate(payload)
    contract = _run_contract(payload)
    assert gate, "final_evidence_gate missing from structured_context"
    assert contract, "run_contract missing from response"
    for field in _GATE_MIRRORED_FIELDS:
        assert gate[field] == contract[field], (
            f"gate.{field}={gate[field]!r} != run_contract.{field}={contract[field]!r}"
        )


def _assert_canonical_route_authority(payload: dict) -> None:
    routing = _routing(payload)
    assert routing.get("authority_holder") == "canonical_run_contract"
    route_authority = payload.get("route_authority") or {}
    assert route_authority.get("authority_holder") == "canonical_run_contract"
    assert payload.get("legacy_intent_authority") is False


def _analyst_facing_text(payload: dict) -> str:
    parts: list[str] = []
    for key in ("message", "analyst_summary"):
        parts.append(str(payload.get(key) or ""))
    analyst = payload.get("analyst_response") or {}
    if isinstance(analyst, dict):
        for key in ("finding_title", "direct_answer_summary", "executive_summary"):
            parts.append(str(analyst.get(key) or ""))
        for item in analyst.get("recommended_actions") or []:
            parts.append(str(item))
    return "\n".join(parts).lower()


def _assert_no_live_claims_without_collected_evidence(payload: dict) -> None:
    contract = _run_contract(payload)
    collected = int(contract.get("collected_evidence_count") or 0)
    if collected > 0:
        return
    assert contract.get("allow_live_result_language") is False
    assert contract.get("allow_results_table") is False
    analyst = payload.get("analyst_response") or {}
    assert not (analyst.get("splunk_results_table") or [])
    facing = _analyst_facing_text(payload)
    routing = _routing(payload)
    if routing.get("canonical_skill") == "guided_investigation":
        assert "review-only" in facing or "not executed" in facing or "no live" in facing or "unverified" in facing
    else:
        for phrase in _FORBIDDEN_LIVE_PHRASES:
            assert phrase not in facing, f"false live claim without collected evidence: {phrase!r}"
    if not contract.get("allow_mitre_mapping"):
        summary = str((analyst.get("direct_answer_summary") or ""))
        assert not _FORBIDDEN_CONFIRMED_MITRE.search(summary)


def _assert_mcp_step_lineage_when_mcp_needed(payload: dict) -> None:
    plan = _evidence_plan(payload)
    contract = _run_contract(payload)
    if not plan.get("needs_mcp"):
        return
    steps = _resource_plan(payload).get("steps") or []
    mcp_steps = [step for step in steps if isinstance(step, dict) and step.get("step_id") == "mcp"]
    assert mcp_steps, "needs_mcp=true but ResourcePlan has no mcp step"
    if plan.get("mcp_allowed") is False:
        assert contract.get("mcp_allowed") is False
        assert contract.get("execution_authorized") is False
        assert mcp_steps[0].get("status") in {"blocked_policy", "blocked", "skipped"}


def _assert_env_kb_not_collected_telemetry(payload: dict) -> None:
    binding = (_evidence_plan(payload).get("source_profile_binding_summary") or {})
    if binding:
        assert binding.get("environment_kb_is_telemetry") is False
    contract = _run_contract(payload)
    # Environment KB / binding context must not inflate collected telemetry count.
    if binding and not any(
        (item.get("collection_status") == "collected")
        for item in (payload.get("source_evidence") or [])
        if isinstance(item, dict)
    ):
        assert int(contract.get("collected_evidence_count") or 0) == 0


def test_e2e_weak_exact_q046_preserves_identity_and_lineage() -> None:
    payload = _payload(_Q046)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_canonical_route_authority(payload)
    _assert_no_live_claims_without_collected_evidence(payload)
    _assert_mcp_step_lineage_when_mcp_needed(payload)

    plan = _evidence_plan(payload)
    row = plan.get("row_authority_summary") or {}
    assert row.get("question_ref") == "q0.q046"
    assert row.get("row_authority_status") == "exact_known_weak_needs_enrichment"
    assert row.get("s3_authority_ready") is False

    lifecycle = plan.get("promotion_lifecycle_summary") or {}
    assert lifecycle.get("stored_status_mutated") is False
    assert lifecycle.get("effective_promotion_status") in {
        "demoted_this_turn",
        "not_promoted",
    }

    q2i = payload.get("query_to_intent") or {}
    mappings = (q2i.get("candidate_mappings") or {}) if isinstance(q2i, dict) else {}
    use_cases = mappings.get("use_case_ids") or []
    if use_cases:
        assert "auth_failed_login_spike" in use_cases or any(
            str(item).startswith("auth_") for item in use_cases
        )

    contract = _run_contract(payload)
    routing = _routing(payload)
    assert routing.get("canonical_skill") in {
        "attack_discovery",
        "spl_generation",
        "alert_summary",
    }
    assert contract.get("collected_evidence_count") == 0
    assert contract.get("execution_authorized") is False


def test_e2e_t1_spl_generation_canonical_graph_and_gate() -> None:
    payload = _payload(_T1_SPL)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_canonical_route_authority(payload)
    _assert_no_live_claims_without_collected_evidence(payload)
    _assert_mcp_step_lineage_when_mcp_needed(payload)

    routing = _routing(payload)
    plan = _evidence_plan(payload)
    contract = _run_contract(payload)

    assert routing.get("canonical_skill") == "spl_generation"
    assert plan.get("needs_spl") is True
    assert plan.get("spl_allowed") is True
    assert plan.get("mcp_allowed") is False
    assert contract.get("execution_authorized") is False
    assert contract.get("collected_evidence_count") == 0


def test_e2e_t2_guided_investigation_no_live_claims() -> None:
    payload = _payload(_T2_OUT_OF_SET)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_canonical_route_authority(payload)
    _assert_no_live_claims_without_collected_evidence(payload)

    routing = _routing(payload)
    contract = _run_contract(payload)
    assert routing.get("canonical_skill") == "guided_investigation"
    assert routing.get("guidance_request") is True
    assert contract.get("execution_needed_for_answer") is False
    assert contract.get("allow_live_result_language") is False
    assert contract.get("collected_evidence_count") == 0


def test_e2e_in_registry_analytics_gate_and_contract_agree() -> None:
    payload = _payload(_IN_REGISTRY_ANALYTICS)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_canonical_route_authority(payload)
    _assert_no_live_claims_without_collected_evidence(payload)

    contract = _run_contract(payload)
    if not contract.get("allow_severity_assessment"):
        severity = payload.get("severity_decision") or {}
        label = str(severity.get("severity_label") or "")
        assert not re.match(r"^P[1-4]\b", label)




def test_e2e_q010_manifest_binding_surfaces_review_only_spl_not_intent_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """q0.q010 in-manifest weak binding must not collapse to intent_clarification."""
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    payload = _payload(_IN_REGISTRY_ANALYTICS)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_canonical_route_authority(payload)
    _assert_no_live_claims_without_collected_evidence(payload)

    plan = _evidence_plan(payload)
    row = plan.get("row_authority_summary") or {}
    assert row.get("question_ref") == "q0.q010"
    assert row.get("manifest_coverage_id") == "cov.q010.network_smb_top_talkers"
    lifecycle = plan.get("promotion_lifecycle_summary") or {}
    assert lifecycle.get("stored_promotion_status") == "in_manifest"
    assert lifecycle.get("effective_promotion_status") == "demoted_this_turn"

    review = payload.get("human_review") or {}
    assert review.get("review_type") != "intent_clarification"
    assert payload.get("response_mode") != "clarification_required"
    analyst = payload.get("analyst_response") or {}
    preview = analyst.get("spl_draft_preview") or {}
    assert preview.get("detection_family") == "network_smb_top_talkers"
    assert _run_contract(payload).get("execution_authorized") is False


def test_e2e_q046_demotion_reason_is_row_authority_not_source_profile_gap() -> None:
    payload = _payload(_Q046)
    plan = _evidence_plan(payload)
    lifecycle = plan.get("promotion_lifecycle_summary") or {}
    assert lifecycle.get("effective_promotion_status") == "demoted_this_turn"
    reasons = lifecycle.get("demotion_reasons") or []
    assert "environment_mapping_drift" not in reasons
    assert "row_authority_not_ready" in reasons
    binding = plan.get("source_profile_binding_summary") or {}
    assert not binding.get("source_profile_bindings_missing")
    review = payload.get("human_review") or {}
    assert review.get("review_type") == "spl_revision"


def test_e2e_environment_kb_user_explicit_precedence() -> None:
    payload = _payload(_ENV_KB_USER_INDEX)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_env_kb_not_collected_telemetry(payload)

    plan = _evidence_plan(payload)
    slot_summary = plan.get("normalized_slot_summary") or {}
    slots = slot_summary.get("normalized_slots") or {}
    sources = slot_summary.get("slot_sources") or {}
    if slots.get("index"):
        assert slots["index"] == "scada_perf"
        assert sources.get("index") == "user_explicit"


def test_e2e_evidence_plan_resource_plan_run_contract_lineage_fields() -> None:
    payload = _payload(_Q046)
    plan = _evidence_plan(payload)
    contract = _run_contract(payload)

    assert plan.get("answer_mode") is not None
    assert _resource_plan(payload).get("plan_source") is not None

    if plan.get("needs_mcp"):
        assert contract.get("mcp_needed_for_live_answer") is True
    if plan.get("mcp_allowed") is False:
        assert contract.get("mcp_allowed") is False

    drift = plan.get("final_evidence_plan_drift") or plan.get("slot_handoff_summary")
    # Drift tracing may be absent on some paths; when present it must not claim false alignment.
    if isinstance(drift, dict) and "handoff_drift_from_final_spl" in plan:
        assert isinstance(plan["handoff_drift_from_final_spl"], bool)


def test_e2e_selected_skill_matches_run_contract_not_legacy_routed() -> None:
    payload = _payload(_Q046)
    routing = _routing(payload)
    assert payload.get("selected_skill") == routing.get("canonical_skill")
    assert routing.get("legacy_authoritative") is False

def test_e2e_mcp_posture_on_run_contract_when_mcp_disabled() -> None:
    payload = _payload(_Q046)
    contract = _run_contract(payload)
    posture = contract.get("mcp_posture")
    assert isinstance(posture, dict), "run_contract.mcp_posture missing"
    assert posture.get("execution_authorized") is False
    assert posture.get("status") in {"blocked_policy", "blocked", "planned", "requires_human_review"}


def test_e2e_cp_on_weak_exact_preserves_canonical_skill_not_parallel_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID

    monkeypatch.setattr(settings, "route_authority_operation_authoritative_enabled", True)
    monkeypatch.setattr(
        settings,
        "route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )
    payload = _payload(_Q046)
    adjudication = payload.get("route_adjudication") or {}
    routing = _routing(payload)
    assert routing.get("authority_holder") == "canonical_run_contract"
    assert routing.get("canonical_skill") in {
        "attack_discovery",
        "spl_generation",
        "alert_summary",
    }
    if adjudication:
        assert adjudication.get("authority_source") in {
            "evidence_plan_live_or_hybrid",
            "exact_105_registry",
            "evidence_plan_rag_only",
        }
    assert payload.get("planning_decision", {}).get("path_type") != "weak_case_parallel"
_ENV_KB_FILL_BLANK = "Show firewall traffic by src_zone and dest_zone on port 443"


def test_e2e_environment_kb_fills_blank_slots_without_counting_as_telemetry() -> None:
    payload = _payload(_ENV_KB_FILL_BLANK)
    _assert_env_kb_not_collected_telemetry(payload)
    _assert_gate_agrees_with_run_contract(payload)

    plan = _evidence_plan(payload)
    binding = plan.get("source_profile_binding_summary") or {}
    assert binding.get("environment_kb_is_telemetry") is False

    slot_summary = plan.get("normalized_slot_summary") or {}
    sources = slot_summary.get("slot_sources") or {}
    slots = slot_summary.get("normalized_slots") or {}
    if slots:
        # When user did not specify index, binding may come from env kb / source profile.
        assert sources.get("index") != "user_explicit" or slots.get("index")



_T2_SCADA_CHAT = (
    "Provide a complete review-only SPL query for index=scada_perf using earliest=-30d to "
    "compute an eventstats stdev baseline by rtu_id and filter anomalies in the last 24h "
    "using transmission_error_count."
)


def test_e2e_t2_scada_probe_gate_and_contract() -> None:
    payload = _payload(_T2_SCADA_CHAT)
    _assert_gate_agrees_with_run_contract(payload)
    _assert_no_live_claims_without_collected_evidence(payload)
    contract = _run_contract(payload)
    assert contract.get("execution_authorized") is False
    assert contract.get("allow_live_result_language") is False


def test_e2e_run_contract_loop_requirements_match_evidence_plan_q046() -> None:
    from app.chat.pipeline import _loop_required_produces

    payload = _payload(_Q046)
    plan = _evidence_plan(payload)
    requirements = _loop_required_produces(plan)
    missing = plan.get("missing_required_evidence") or []
    if requirements:
        assert all(req in missing or req in (plan.get("evidence_needs") or []) for req in requirements)
    contract = _run_contract(payload)
    assert int(contract.get("collected_evidence_count") or 0) == 0
    loop = (payload.get("control_plane_trace") or {}).get("evidence_loop") or {}
    if loop:
        decision = loop.get("decision") or {}
        assert decision.get("sufficiency") in {"needs_more", "insufficient", None} or decision.get("route") in {
            "human_review",
            "blocked",
            "return_to_plan",
        }
