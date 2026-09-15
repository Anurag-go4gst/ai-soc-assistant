"""Post-approval investigation convergence: one lifecycle, consistent projections.

The approved investigation owns execution-requested / read-required /
source-unavailable / blocked-inconclusive. Legacy review-only SPL machinery may
emit a fallback artifact; it must not redefine the turn as review_only /
no_live_query / "neither requested nor authorised".
"""

from __future__ import annotations

from typing import Any

from app.chat.contracts.answer_contract import build_answer_contract
from app.chat.final_answer_readability import apply_final_answer_readability
from app.chat.reviewer_trace import assemble_forensic_bundle, build_reviewer_trace
from app.chat.trace_effective_state import build_effective_state_projection
from app.orchestration.workflow_planner import plan_workflow


def _approved_gi_source_unavailable_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "selected_skill": "guided_investigation",
        "answer_mode": "guided_investigation",
        "approved_investigation_envelope": {
            "envelope_version": 2,
            "allowed_read_only_capabilities": ["mcp:splunk_run_query"],
        },
        "investigation_approval": {"status": "approved"},
        "investigation_run_status": {"status": "blocked"},
        "candidate_spl": {
            "candidate_spl": "search index=windows earliest=-24h | stats count | head 100",
            "execution_eligible": False,
            "generation_mode": "deterministic_lab_draft",
        },
        "spl_validation": {
            "approved": False,
            "normalized_spl": None,
            "execution_eligible": False,
        },
        "spl_draft_preview": {
            "draft_spl": "search index=windows earliest=-24h | stats count | head 100",
            "generation_mode": "deterministic_lab_draft",
        },
        "execution": {
            "status": "skipped",
            "block_reason": "read_source_required_but_unavailable",
            "tool_selection_reason": "read_source_required_but_unavailable",
            "executed_spl": None,
        },
        "run_contract": {
            "execution_needed_for_answer": True,
            "execution_authorized": False,
            "spl_candidate_present": True,
            "mcp_allowed": False,
        },
        "evidence_plan": {
            "answer_mode": "guided_investigation",
            "needs_mcp": True,
            "needs_spl": True,
            "mcp_available": False,
            "mcp_allowed": False,
        },
        "control_plane_trace": {
            "evidence_plan": {
                "needs_mcp": True,
                "needs_spl": True,
                "needs_rag": False,
                "mcp_available": False,
            },
            "query_to_intent": {"query_signals": {}},
            "mcp_execution": {"status": "skipped", "result_count": 0},
            "spl_artifact_handoff_summary": {
                "review_only": True,
                "artifact_present": True,
                "artifact_review_required": True,
            },
        },
        "analyst_response": {
            "review_notice": "Candidate SPL — review only, not executed.",
            "execution_status_label": "review_only_not_executed",
        },
        "human_review": {"required": False},
    }
    payload.update(overrides)
    return payload


def _reviewer_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    effective = build_effective_state_projection(payload)
    bundle = assemble_forensic_bundle(
        trace_id="gi-convergence",
        run={
            "trace_id": "gi-convergence",
            "status": "completed",
            "selected_skill": payload.get("selected_skill"),
            "answer_mode": payload.get("answer_mode"),
            "metadata": {
                "effective_state": effective,
                "selected_skill": payload.get("selected_skill"),
                "answer_mode": payload.get("answer_mode"),
            },
        },
        events=[
            {
                "kind": "step",
                "step_name": "workflow_plan_created",
                "event": {
                    "skill": payload.get("selected_skill"),
                    "plan_role": "investigation",
                },
            }
        ],
        payload=payload,
    )
    return build_reviewer_trace(bundle)


def test_approved_gi_unavailable_is_not_review_only_lifecycle() -> None:
    payload = _approved_gi_source_unavailable_payload()
    effective = build_effective_state_projection(payload)
    reviewer = _reviewer_from_payload(payload)

    assert effective["execution"]["execution_requested"] is True
    assert effective["review_only"] is False
    assert effective["explicit_do_not_execute"] is False
    assert effective["execution"]["execution_performed"] is False
    assert effective["spl_authoring"]["spl_truth"] == "draft_fallback"
    assert effective["spl_authoring"]["spl_role"] == "investigation_fallback"
    assert effective["evidence"]["spl_artifact"]["status"] == "draft_fallback"
    assert effective["evidence"]["spl_execution_result"]["reason"] != "review_only_no_execution"
    assert effective["validation"]["normalized_spl_available"] is False
    assert effective["hil"]["artifact_review_required"] is False

    decision = reviewer["review_decision"]
    assert decision["run_outcome"] == "blocked_source_unavailable"
    assert decision["reason"] is not None
    assert "neither requested nor authorised" not in decision["reason"].lower()
    assert "unavailable" in decision["reason"].lower()
    assert reviewer["execution"]["execution_requested"] is True
    assert reviewer["execution"]["execution_performed"] is False
    assert reviewer["connectors"]["read_source_required"] is True
    assert reviewer["connectors"]["mcp_required_this_turn"] is True
    assert reviewer["connectors"]["read_source_available"] is False
    assert reviewer["spl"]["spl_truth"] == "draft_fallback"
    assert reviewer["spl"]["normalized_spl_available"] is False
    assert reviewer["evidence"]["spl_artifact_status"] == "draft_fallback"


def test_utility_review_only_authoring_is_unchanged() -> None:
    payload = {
        "answer_mode": "spl_utility_authoring",
        "candidate_spl": {
            "candidate_spl": "search index=<your_index> | stats count",
            "utility_spl_draft_trace": {
                "semantic_fidelity_final": {"passed": True, "losses": []},
            },
        },
        "spl_validation": {"approved": False, "reject_reasons": ["review_only_spl_authoring"]},
        "execution": {"status": "skipped"},
        "run_contract": {"execution_needed_for_answer": False, "spl_candidate_present": True},
        "control_plane_trace": {
            "evidence_plan": {"needs_spl": True, "needs_mcp": False, "needs_rag": False},
            "query_to_intent": {"query_signals": {"review_only_spl": True}},
            "mcp_execution": {"status": "skipped", "result_count": 0},
            "spl_artifact_handoff_summary": {"review_only": True, "artifact_present": True},
        },
        "human_review": {"required": False},
    }
    effective = build_effective_state_projection(payload)
    reviewer = _reviewer_from_payload(payload)
    assert effective["review_only"] is True
    assert effective["execution"]["execution_requested"] is False
    assert effective["evidence"]["spl_artifact"]["status"] == "obtained"
    assert reviewer["review_decision"]["run_outcome"] == "completed_review_only"
    assert "neither requested nor authorised" in (reviewer["review_decision"]["reason"] or "")


def test_live_read_tool_plan_does_not_stamp_review_only_blueprint() -> None:
    telemetry = _FakeTelemetry()
    plan = plan_workflow(
        selected_skill="guided_investigation",
        tool_plan=["retrieve_approved_knowledge", "optional_review_only_spl", "mcp_search"],
        query="Investigate WINWORD.EXE spawned powershell.exe on WS-14",
        trace_id="gi-live-read",
        telemetry=telemetry,
    )
    assert plan["plan_role"] == "investigation"
    assert "review_only" not in plan["safety_gates"]
    assert "no_live_query" not in plan["safety_gates"]
    assert "no_execution" not in plan["safety_gates"]
    assert "live_read_required" in plan["safety_gates"]
    assert "optional_spl_fallback" in plan["safety_gates"]
    assert "mcp:splunk" in plan["required_sources"]
    assert telemetry.steps[0]["plan_role"] == "investigation"


def test_live_read_flag_overrides_empty_tool_plan() -> None:
    plan = plan_workflow(
        selected_skill="guided_investigation",
        tool_plan=[],
        query="Investigate WINWORD.EXE spawned powershell.exe on WS-14",
        trace_id="gi-flag",
        telemetry=_FakeTelemetry(),
        live_read_required=True,
    )
    assert plan["plan_role"] == "investigation"
    assert "no_live_query" not in plan["safety_gates"]
    assert "live_read_required" in plan["safety_gates"]
    plan = plan_workflow(
        selected_skill="guided_investigation",
        tool_plan=["retrieve_approved_knowledge", "optional_review_only_spl", "no_mcp"],
        query="How should SOC investigate OT scans?",
        trace_id="gi-review",
        telemetry=_FakeTelemetry(),
    )
    assert plan["plan_role"] == "guided_review_blueprint"
    assert "review_only" in plan["safety_gates"]
    assert "no_live_query" in plan["safety_gates"]


def test_answer_contract_source_unavailable_is_not_review_only() -> None:
    contract = build_answer_contract(
        intent_classification={"intent_family": "guided_investigation", "answer_goal": ["live_results"]},
        evidence_plan={
            "answer_mode": "guided_investigation",
            "needs_mcp": True,
            "needs_spl": True,
            "spl_allowed": True,
            "mcp_allowed": False,
            "requires_hil": False,
        },
        mitre_decision={"answer_visible": False},
        severity_decision=None,
        spl_validation={"approved": False, "normalized_spl": None},
        execution={
            "status": "skipped",
            "block_reason": "read_source_required_but_unavailable",
        },
        human_review={"required": False},
        mitre_mappings=[],
        candidate_spl={"candidate_spl": "search index=windows | stats count"},
    )
    assert contract.execution_status_label == "execution_pending_mcp_unavailable"
    assert contract.execution_status_display is not None
    assert "Review only" not in contract.execution_status_display


def test_readability_syncs_investigation_fallback_one_sentence() -> None:
    from app.schemas.responses import AnalystResponseEnvelope

    contract = build_answer_contract(
        intent_classification={"intent_family": "guided_investigation", "answer_goal": ["live_results"]},
        evidence_plan={
            "answer_mode": "guided_investigation",
            "needs_mcp": True,
            "needs_spl": True,
            "spl_allowed": True,
            "mcp_allowed": False,
            "requires_hil": False,
        },
        mitre_decision={"answer_visible": False},
        severity_decision=None,
        spl_validation={"approved": False, "normalized_spl": None},
        execution={
            "status": "skipped",
            "block_reason": "read_source_required_but_unavailable",
        },
        human_review={"required": False},
        candidate_spl={"candidate_spl": "search index=windows | stats count"},
    )
    result = apply_final_answer_readability(
        AnalystResponseEnvelope(
            draft_spl_code="search index=windows | stats count",
            spl_draft_preview={"draft_spl": "search index=windows | stats count"},
            one_sentence_finding="Review-only SPL draft - no live query was executed.",
        ),
        contract,
    )
    visible = f"{result.direct_answer_summary or ''} {result.one_sentence_finding or ''}"
    assert "Review-only SPL draft" not in visible
    assert "unavailable" in visible.lower()


def test_t2_surfacing_does_not_relabel_investigation_fallback(monkeypatch: Any) -> None:
    from app.chat.t2_answer_surfacing import apply_t2_answer_surfacing
    from app.config import settings
    from app.schemas.responses import AnalystResponseEnvelope

    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    contract = build_answer_contract(
        intent_classification={"intent_family": "guided_investigation", "answer_goal": ["live_results"]},
        evidence_plan={
            "answer_mode": "guided_investigation",
            "needs_mcp": True,
            "needs_spl": True,
            "spl_allowed": True,
            "mcp_allowed": False,
            "requires_hil": False,
        },
        mitre_decision={"answer_visible": False},
        severity_decision=None,
        spl_validation={"approved": False, "normalized_spl": None},
        execution={
            "status": "skipped",
            "block_reason": "read_source_required_but_unavailable",
        },
        human_review={"required": False},
        candidate_spl={"candidate_spl": "search index=windows | stats count"},
    )
    envelope = AnalystResponseEnvelope(
        draft_spl_code="search index=windows | stats count",
        spl_draft_preview={"draft_spl": "search index=windows | stats count"},
        one_sentence_finding="Review-only SPL draft - no live query was executed.",
    )
    _message, _updated_contract, updated = apply_t2_answer_surfacing(
        message="Guided investigation",
        answer_contract=contract,
        analyst_response=envelope,
        human_review={"required": False},
        candidate_spl={"candidate_spl": "search index=windows | stats count"},
        spl_draft_preview={"draft_spl": "search index=windows | stats count"},
        spl_validation={"approved": False, "normalized_spl": None},
        user_query="Investigate WINWORD.EXE spawned powershell.exe on WS-14",
        match_path="out_of_registry",
    )
    assert updated is not None
    visible = f"{updated.direct_answer_summary or ''} {updated.one_sentence_finding or ''}"
    assert "Review-only SPL draft" not in visible
    assert "unavailable" in visible.lower()
    assert updated.draft_spl_code


def test_workflow_plan_projects_plan_role() -> None:
    from app.schemas.responses import WorkflowPlan

    plan = WorkflowPlan.model_validate(
        {
            "trace_id": "gi",
            "skill": "guided_investigation",
            "tool_plan": ["mcp_search"],
            "status": "not_started",
            "execution_enabled": False,
            "steps": [],
            "required_connectors": ["mcp"],
            "safety_gates": ["live_read_required", "optional_spl_fallback"],
            "message": "Workflow plan created.",
            "plan_role": "investigation",
        }
    )
    assert plan.plan_role == "investigation"


class _FakeTelemetry:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def record_step(self, trace_id: str, step_name: str, status: str, **fields: Any) -> None:
        self.steps.append({"trace_id": trace_id, "step_name": step_name, "status": status, **fields})
