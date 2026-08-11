"""Hierarchy contracts — WorkBundle must not bypass ResourcePlan policy."""

from __future__ import annotations

import pytest

from app.planner.composer import compose_resource_plan
from app.planner.planner_hierarchy import (
    DecisionRecord,
    KnowledgeSpecialistReport,
    McpSpecialistReport,
    PlannerIteration,
    SkillSpecialistReport,
    SpecialistDelegation,
    SpecialistProposal,
    SplSpecialistReport,
    WorkBundle,
    apply_specialist_reports,
    build_planner_iteration,
    materialize_resource_plan_from_bundle,
    new_decision_record_id,
    validate_bundle_policy_parity,
    work_bundle_from_resource_plan,
)
from app.planner.resource_plan import PlanStep, ResourcePlan, project_booleans


def _sample_plan() -> ResourcePlan:
    return ResourcePlan(
        plan_source="deterministic",
        steps=[
            PlanStep(
                step_id="spl",
                resource_id="skill:spl_generation",
                purpose="spl_artifact",
                policy_checks=["spl_validator", "execution_eligible_false"],
            ),
            PlanStep(
                step_id="mcp",
                resource_id="mcp_tool:splunk_run_query",
                purpose="mcp_execution",
                status="blocked_policy",
                status_reason="mcp_not_allowed_by_evidence_plan",
                policy_checks=["mcp_not_allowed_by_evidence_plan"],
            ),
        ],
    )


def test_work_bundle_round_trips_resource_plan() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    rebuilt = materialize_resource_plan_from_bundle(bundle)
    assert rebuilt.plan_source == plan.plan_source
    assert [step.model_dump() for step in rebuilt.steps] == [
        step.model_dump() for step in plan.steps
    ]
    assert rebuilt.provenance.get("work_bundle_id") == "bundle:test"
    assert project_booleans(rebuilt) == project_booleans(plan)


def test_validate_bundle_policy_parity_catches_removed_checks() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    bundle.tasks[0].policy_checks = ["spl_validator"]
    violations = validate_bundle_policy_parity(bundle)
    assert any("execution_eligibility_bypassed" in item for item in violations)


def test_validate_bundle_policy_parity_catches_relaxed_block() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    bundle.tasks[1].status = "planned"
    violations = validate_bundle_policy_parity(bundle)
    assert any(item.startswith("blocked_status_relaxed:") for item in violations)


def test_validate_bundle_policy_parity_catches_unauthorized_step() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    bundle.tasks.append(
        bundle.tasks[0].model_copy(update={"step_id": "rogue", "task_id": "task:rogue"})
    )
    violations = validate_bundle_policy_parity(bundle)
    assert any(item.startswith("unauthorized_step_added:") for item in violations)


def test_materialize_resource_plan_from_bundle_rejects_policy_bypass() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    bundle.tasks[0].policy_checks = []
    with pytest.raises(ValueError, match="policy violations"):
        materialize_resource_plan_from_bundle(bundle)


def test_apply_specialist_reports_enriches_args_without_policy_mutation() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    reports = [
        SplSpecialistReport(
            delegation_id="del:spl",
            decision_reason="template_bind",
            proposals=[
                SpecialistProposal(
                    proposal_id="p1",
                    purpose="spl_artifact",
                    args_template={"use_case_id": "auth_failed_login_spike"},
                )
            ],
        )
    ]
    merged = apply_specialist_reports(bundle, reports)
    spl_task = next(task for task in merged.tasks if task.step_id == "spl")
    assert spl_task.args_template["use_case_id"] == "auth_failed_login_spike"
    assert spl_task.source_specialist == "spl"
    assert "execution_eligible_false" in spl_task.policy_checks
    rebuilt = materialize_resource_plan_from_bundle(merged)
    assert rebuilt.step_by_id("spl") is not None
    assert rebuilt.step_by_id("spl").args_template["use_case_id"] == "auth_failed_login_spike"


def test_apply_specialist_reports_cannot_relax_blocked_mcp() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:test")
    reports = [
        McpSpecialistReport(
            delegation_id="del:mcp",
            decision_reason="retry_search",
            proposals=[
                SpecialistProposal(
                    proposal_id="p1",
                    purpose="mcp_execution",
                    args_template={"index": "main"},
                )
            ],
        )
    ]
    merged = apply_specialist_reports(bundle, reports)
    mcp_task = next(task for task in merged.tasks if task.step_id == "mcp")
    assert mcp_task.status == "blocked_policy"
    assert mcp_task.args_template["index"] == "main"


def test_specialist_delegation_rejects_out_of_lane_ownership() -> None:
    with pytest.raises(ValueError, match="cannot own"):
        SpecialistDelegation(
            delegation_id="del:bad",
            specialist_id="skill",
            ownership_scope=["mcp_search_hops"],
            decision_reason="invalid",
        )


def test_decision_record_requires_audit_fields() -> None:
    record = DecisionRecord(
        record_id=new_decision_record_id(),
        node="resource_planner.merge",
        authority="resource_planner",
        decision_reason="fan_in_complete",
        inputs_ref=["specialist_reports"],
        outputs_ref=["work_bundle"],
    )
    assert record.decision_reason
    assert record.inputs_ref and record.outputs_ref


def test_build_planner_iteration_wires_delegations_and_bundle() -> None:
    plan = _sample_plan()
    delegations = [
        SpecialistDelegation(
            delegation_id="del:skill",
            specialist_id="skill",
            ownership_scope=["route", "skill_id"],
            decision_reason="catalogue_lane",
        ),
        SpecialistDelegation(
            delegation_id="del:spl",
            specialist_id="spl",
            ownership_scope=["spl_compose"],
            decision_reason="spl_lane",
        ),
    ]
    reports = [
        SkillSpecialistReport(
            delegation_id="del:skill",
            decision_reason="knowledge_recall",
            skill_id="knowledge_recall",
            catalogue_tier="T1",
        ),
        SplSpecialistReport(
            delegation_id="del:spl",
            decision_reason="fallback_template",
            spl_source="governed_template",
        ),
    ]
    iteration = build_planner_iteration(
        iteration=1,
        resource_plan=plan,
        delegations=delegations,
        reports=reports,
    )
    assert isinstance(iteration, PlannerIteration)
    assert iteration.bundle is not None
    assert len(iteration.bundle.tasks) == len(plan.steps)
    assert iteration.resource_plan.summary() == materialize_resource_plan_from_bundle(
        iteration.bundle
    ).summary()


def test_composed_plan_maps_to_work_bundle_without_policy_loss() -> None:
    from app.chat.contracts.evidence_plan import EvidencePlan

    evidence = EvidencePlan(
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
    composed = compose_resource_plan(evidence, skill_id="spl_generation")
    bundle = work_bundle_from_resource_plan(composed, bundle_id="bundle:composer")
    assert validate_bundle_policy_parity(bundle) == []
    mcp_tasks = [task for task in bundle.tasks if task.purpose == "mcp_execution"]
    assert mcp_tasks
    assert mcp_tasks[0].status == "blocked_policy"
    assert any(
        check in mcp_tasks[0].policy_checks for check in ("mcp_not_allowed_by_evidence_plan",)
    )


def test_knowledge_specialist_report_tracks_reference_domains() -> None:
    report = KnowledgeSpecialistReport(
        delegation_id="del:knowledge",
        decision_reason="atlas_lookup",
        reference_domains=["atlas", "mitre"],
    )
    assert report.specialist_id == "knowledge"
    assert report.reference_domains == ["atlas", "mitre"]
