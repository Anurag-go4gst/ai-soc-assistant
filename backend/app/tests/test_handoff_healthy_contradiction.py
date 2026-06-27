"""WS8: distinguish healthy handoff contradictions from real routing/MCP bugs."""

from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.guidance_templates import should_skip_llm_composer
from app.chat.intent_classifier import build_query_to_intent
from app.chat.run_contract_builder import project_mcp_posture
from app.config import settings
from app.coverage.promotion_lifecycle import (
    AUTHORITY_READY_EFFECTIVE,
    DEMOTED_THIS_TURN,
    effective_promotion_status,
)
from app.planner.composer import compose_resource_plan
from app.planner.executor import annotate_step_statuses
from app.query_understanding.parser import understand_query
from app.routing.route_adjudication import adjudicate_route
from app.routing.route_authority_allowlist import COV_Q046_PILOT_COVERAGE_ID

_Q046 = "Which users have excessive failed logins?"


def _q046_adjudication_inputs() -> tuple[dict, dict, dict, object]:
    qu = understand_query(_Q046)
    q2i = build_query_to_intent(query=_Q046, query_understanding=qu)
    intent = q2i.intent_classification.model_dump()
    evidence = plan_evidence(
        intent,
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
    ).model_dump()
    shadow = {
        "question_runtime_map": {
            "manifest_coverage_id": COV_Q046_PILOT_COVERAGE_ID,
            "coverage_id": COV_Q046_PILOT_COVERAGE_ID,
            "question_ref": "q0.q046",
        },
    }
    return intent, evidence, shadow, q2i


def test_healthy_contradiction_cp_off_preserves_exact_registry_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Weak row authority is traced but does not narrow routing until CP flag is on."""
    monkeypatch.setattr(settings, "route_authority_operation_authoritative_enabled", False)
    intent, evidence, shadow, q2i = _q046_adjudication_inputs()
    if q2i.candidate_mappings.get("match_path") not in {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
    }:
        pytest.skip("q046 did not resolve to an exact-105 match path in this environment")

    result = adjudicate_route(
        deterministic_route="attack_discovery",
        route_plan_shadow=shadow,
        evidence_plan=evidence,
        intent_classification=intent,
        query_understanding=understand_query(_Q046),
        query_to_intent=q2i.model_dump(),
    )

    assert result.authority_source == "exact_105_registry"
    assert result.row_authority_decision == "would_withhold_exact_registry"
    assert result.row_authority_applied is False


def test_healthy_contradiction_cp_on_narrows_weak_exact_to_canonical_evidence_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "route_authority_operation_authoritative_enabled", True)
    monkeypatch.setattr(
        settings,
        "route_authority_operation_coverage_allowlist",
        COV_Q046_PILOT_COVERAGE_ID,
    )
    intent, evidence, shadow, q2i = _q046_adjudication_inputs()
    if q2i.candidate_mappings.get("match_path") not in {
        "exact_105_question",
        "exact_105_plus_use_case_catalog",
    }:
        pytest.skip("q046 did not resolve to an exact-105 match path in this environment")

    result = adjudicate_route(
        deterministic_route="attack_discovery",
        route_plan_shadow=shadow,
        evidence_plan=evidence,
        intent_classification=intent,
        query_understanding=understand_query(_Q046),
        query_to_intent=q2i.model_dump(),
    )

    assert result.authority_source == "evidence_plan_live_or_hybrid"
    assert result.row_authority_applied is True
    assert evidence["row_authority_summary"]["row_authority_status"] == (
        "exact_known_weak_needs_enrichment"
    )


def test_healthy_contradiction_mcp_step_present_when_mcp_disallowed() -> None:
    """MCP-off live investigation must keep the MCP ResourcePlan step, marked blocked."""
    plan = EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    composed = compose_resource_plan(plan, intent_family="live_investigation", skill_id="attack_discovery")
    mcp = composed.step_by_id("mcp")
    assert mcp is not None
    assert mcp.purpose == "mcp_execution"
    assert mcp.status == "blocked_policy"


def test_mcp_off_and_mock_execution_use_same_resource_plan_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MCP posture may change, but the canonical ResourcePlan step identity cannot."""
    plan = EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=True,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=True,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    composed = compose_resource_plan(plan, intent_family="live_investigation", skill_id="attack_discovery")
    planned_mcp = composed.step_by_id("mcp")
    assert planned_mcp is not None
    planned_identity = (planned_mcp.step_id, planned_mcp.resource_id, planned_mcp.purpose)

    base_state = {
        "evidence_plan": {
            **plan.model_dump(),
            "resource_plan": composed.model_dump(),
        },
        "spl_validation": {"approved": True, "normalized_spl": "index=auth | head 1"},
    }

    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    blocked = annotate_step_statuses(
        {
            **base_state,
            "execution": {
                "status": "blocked",
                "block_reason": "mcp_global_execution_disabled",
                "selected_mcp_tool": "splunk_run_query",
            },
        }
    )
    blocked_mcp = next(
        step
        for step in blocked["evidence_plan"]["resource_plan"]["steps"]
        if step["purpose"] == "mcp_execution"
    )
    assert (
        blocked_mcp["step_id"],
        blocked_mcp["resource_id"],
        blocked_mcp["purpose"],
    ) == planned_identity
    assert blocked_mcp["status"] == "blocked_policy"
    blocked_posture = project_mcp_posture(blocked)
    assert blocked_posture is not None
    assert blocked_posture["status"] == "blocked_policy"
    assert blocked_posture["primary_reason"] == "mcp_global_execution_disabled"
    assert blocked_posture["execution_authorized"] is False

    monkeypatch.setattr(settings, "mcp_global_execution_enabled", True)
    mock_executed = annotate_step_statuses(
        {
            **base_state,
            "execution": {
                "status": "executed",
                "selected_mcp_tool": "splunk_run_query",
                "result_count": 1,
                "mock_execution": True,
            },
        }
    )
    mock_mcp = next(
        step
        for step in mock_executed["evidence_plan"]["resource_plan"]["steps"]
        if step["purpose"] == "mcp_execution"
    )
    assert (
        mock_mcp["step_id"],
        mock_mcp["resource_id"],
        mock_mcp["purpose"],
    ) == planned_identity
    assert mock_mcp["status"] == "executed"
    mock_posture = project_mcp_posture(mock_executed)
    assert mock_posture is not None
    assert mock_posture["status"] == "executed"
    assert mock_posture["selected_tool"] == "splunk_run_query"
    assert mock_posture["execution_authorized"] is True


def test_weak_row_demotion_blocks_t0_composer_skip() -> None:
    lifecycle = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={
            "s3_authority_ready": False,
            "row_authority_status": "exact_known_weak_needs_enrichment",
        },
    )
    assert lifecycle["effective_promotion_status"] == DEMOTED_THIS_TURN
    assert "row_authority_not_ready" in lifecycle["demotion_reasons"]

    skip, reason = should_skip_llm_composer(
        query=_Q046,
        path_type="live_investigation",
        intent_family="live_investigation",
        match_path="exact_105_question",
        promotion_lifecycle_summary=lifecycle,
    )
    assert skip is False
    assert reason == ""


def test_authority_ready_row_skips_governed_composer_narration() -> None:
    lifecycle = effective_promotion_status(
        stored_promotion_status="in_manifest",
        row_authority_summary={
            "s3_authority_ready": True,
            "row_authority_status": "exact_known_authority_ready",
        },
    )
    assert lifecycle["effective_promotion_status"] == AUTHORITY_READY_EFFECTIVE

    skip, reason = should_skip_llm_composer(
        query=_Q046,
        path_type="live_investigation",
        intent_family="live_investigation",
        match_path="exact_105_question",
        promotion_lifecycle_summary=lifecycle,
    )
    assert skip is True
    assert reason == "t0_authority_ready:deterministic_exact_match_t0"


from app.chat.pipeline import build_live_chat_response
from app.schemas.requests import ChatRequest


def test_real_bug_weak_exact_does_not_bypass_missing_bindings() -> None:
    intent, evidence, shadow, q2i = _q046_adjudication_inputs()
    row = evidence.get("row_authority_summary") or {}
    assert row.get("s3_authority_ready") is False
    lifecycle = evidence.get("promotion_lifecycle_summary") or {}
    if lifecycle:
        assert lifecycle.get("effective_promotion_status") != "authority_ready"
    missing = evidence.get("missing_required_evidence") or []
    assert missing or row.get("row_authority_status") == "exact_known_weak_needs_enrichment"


def test_real_bug_no_live_language_without_mcp_evidence() -> None:
    payload = build_live_chat_response(
        ChatRequest(message=_Q046)
    ).model_dump(mode="json")
    contract = payload.get("run_contract") or {}
    assert int(contract.get("collected_evidence_count") or 0) == 0
    assert contract.get("allow_live_result_language") is False
    gate = (payload.get("structured_context") or {}).get("final_evidence_gate") or {}
    assert gate.get("allow_live_result_language") is False


def test_real_bug_mcp_step_never_omitted_when_needs_mcp() -> None:
    for skill in ("attack_discovery", "spl_generation", "alert_summary"):
        plan = EvidencePlan(
            answer_mode="live_investigation",
            rag_phase="post_mcp",
            needs_rag=False,
            needs_spl=True,
            needs_mcp=True,
            needs_mitre=False,
            spl_allowed=True,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=False,
        )
        composed = compose_resource_plan(plan, intent_family="live_investigation", skill_id=skill)
        assert composed.step_by_id("mcp") is not None


def test_ws4_mcp_parity_checklist_across_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    payload = build_live_chat_response(ChatRequest(message=_Q046)).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    contract = payload.get("run_contract") or {}
    if not plan.get("needs_mcp"):
        pytest.skip("probe did not require MCP")
    assert plan.get("mcp_allowed_normalized") is not None or plan.get("mcp_allowed") is False
    steps = (plan.get("resource_plan") or {}).get("steps") or []
    mcp_steps = [s for s in steps if isinstance(s, dict) and s.get("step_id") == "mcp"]
    assert mcp_steps
    posture = contract.get("mcp_posture") or {}
    assert posture.get("status") in {"blocked_policy", "blocked", "planned", "requires_human_review"}
    assert posture.get("execution_authorized") is False
    trace = payload.get("control_plane_trace") or {}
    assert trace.get("run_contract") or contract
