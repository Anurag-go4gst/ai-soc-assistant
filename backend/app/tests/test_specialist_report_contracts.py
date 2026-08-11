"""Safety and bounds for Resource Planner specialist report contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.planner.planner_hierarchy import (
    McpSpecialistReport,
    SpecialistProposal,
    SplSpecialistReport,
    apply_specialist_reports,
    work_bundle_from_resource_plan,
)
from app.planner.resource_plan import PlanStep, ResourcePlan


def _plan() -> ResourcePlan:
    return ResourcePlan(
        plan_source="deterministic",
        steps=[
            PlanStep(
                step_id="spl",
                resource_id="skill:spl_generation",
                purpose="spl_artifact",
                args_template={"template_id": "", "use_case_id": "locked_use_case"},
                policy_checks=["spl_validator", "execution_eligible_false"],
            ),
            PlanStep(
                step_id="mcp",
                resource_id="mcp_tool:splunk_run_query",
                purpose="mcp_execution",
                args_template={"execution_intent": ""},
                status="blocked_policy",
                status_reason="mcp_not_allowed_by_evidence_plan",
                policy_checks=["mcp_not_allowed_by_evidence_plan"],
            ),
        ],
    )


def _bundle():
    return work_bundle_from_resource_plan(_plan(), bundle_id="bundle:test")


def test_mcp_report_contract_is_bounded_and_statused() -> None:
    report = McpSpecialistReport(
        delegation_id="del:mcp",
        decision_reason="gate_required",
        plan_needs_mcp=True,
        plan_mcp_allowed=False,
        discovery_allowed=True,
        planned_hop_count=2,
        hop_count=2,
        registry_mode="registry",
        global_execution_enabled=False,
        configured_server_count=2,
        available_server_count=1,
        candidate_server_ids=["splunk-primary"],
        candidate_tool_names=["splunk_run_query"],
        execution_posture="gate_required",
        requires_execution_gate=True,
        blockers=["mcp_execution_disabled"],
    )

    assert report.planned_hop_count == report.hop_count == 2
    assert report.execution_posture == "gate_required"

    with pytest.raises(ValidationError):
        McpSpecialistReport(
            delegation_id="del:mcp",
            decision_reason="invalid",
            planned_hop_count=-1,
        )
    with pytest.raises(ValidationError):
        McpSpecialistReport(
            delegation_id="del:mcp",
            decision_reason="invalid",
            candidate_tool_names=[f"tool_{index}" for index in range(17)],
        )


def test_spl_report_contract_is_non_executable_and_bounded() -> None:
    report = SplSpecialistReport(
        delegation_id="del:spl",
        decision_reason="template_ready",
        plan_needs_spl=True,
        plan_spl_allowed=True,
        planned_resource_id="skill:spl_generation",
        template_id="auth_failed_login_spike",
        template_status="active",
        template_production_executable=True,
        candidate_source_options=["governed_template"],
        spl_source="governed_template",
        slot_binding_status="missing_required_slots",
        missing_required_slots=["index", "sourcetype"],
        validation_required=True,
        execution_eligible=False,
    )

    assert report.execution_eligible is False
    with pytest.raises(ValidationError):
        SplSpecialistReport(
            delegation_id="del:spl",
            decision_reason="invalid",
            execution_eligible=True,
        )
    with pytest.raises(ValidationError):
        SplSpecialistReport(
            delegation_id="del:spl",
            decision_reason="invalid",
            spl_source="template_or_fallback",
        )


@pytest.mark.parametrize(
    "forbidden_key",
    (
        "candidate_spl",
        "normalized_spl",
        "validator_approved",
        "execution_enabled",
        "execution_eligible",
        "policy_checks",
        "status",
        "endpoint",
        "auth_token",
        "secret",
        "raw_query",
        "prompt",
        "rag_text",
    ),
)
def test_specialist_proposals_reject_forbidden_fields(forbidden_key: str) -> None:
    report = SplSpecialistReport(
        delegation_id="del:spl",
        decision_reason="invalid_proposal",
        proposals=[
            SpecialistProposal(
                proposal_id="proposal:forbidden",
                purpose="spl_artifact",
                resource_id="skill:spl_generation",
                args_template={forbidden_key: "forbidden"},
            )
        ],
    )

    with pytest.raises(ValueError, match="forbidden specialist proposal field"):
        apply_specialist_reports(_bundle(), [report])


def test_specialist_merge_fills_blank_without_overwriting_authority() -> None:
    allowed = SplSpecialistReport(
        delegation_id="del:spl",
        decision_reason="fill_blank",
        proposals=[
            SpecialistProposal(
                proposal_id="proposal:template",
                purpose="spl_artifact",
                resource_id="skill:spl_generation",
                args_template={"template_id": "auth_failed_login_spike"},
            )
        ],
    )
    merged = apply_specialist_reports(_bundle(), [allowed])
    spl_task = next(task for task in merged.tasks if task.step_id == "spl")
    assert spl_task.args_template == {
        "template_id": "auth_failed_login_spike",
        "use_case_id": "locked_use_case",
    }
    assert spl_task.policy_checks == ["spl_validator", "execution_eligible_false"]
    assert spl_task.status == "planned"

    overwrite = allowed.model_copy(
        update={
            "proposals": [
                SpecialistProposal(
                    proposal_id="proposal:overwrite",
                    purpose="spl_artifact",
                    resource_id="skill:spl_generation",
                    args_template={"use_case_id": "replacement"},
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="non-blank specialist proposal target"):
        apply_specialist_reports(_bundle(), [overwrite])


def test_specialist_merge_rejects_cross_lane_and_missing_targets() -> None:
    cross_lane = SplSpecialistReport(
        delegation_id="del:spl",
        decision_reason="wrong_lane",
        proposals=[
            SpecialistProposal(
                proposal_id="proposal:wrong-lane",
                purpose="mcp_execution",
                resource_id="mcp_tool:splunk_run_query",
                args_template={"execution_intent": "spl_search"},
            )
        ],
    )
    with pytest.raises(ValueError, match="cross-lane specialist proposal"):
        apply_specialist_reports(_bundle(), [cross_lane])

    missing = SplSpecialistReport(
        delegation_id="del:spl",
        decision_reason="missing_target",
        proposals=[
            SpecialistProposal(
                proposal_id="proposal:missing",
                purpose="spl_artifact",
                resource_id="skill:not_in_plan",
                args_template={"template_id": "auth_failed_login_spike"},
            )
        ],
    )
    with pytest.raises(ValueError, match="no existing specialist proposal target"):
        apply_specialist_reports(_bundle(), [missing])
