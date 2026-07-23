"""Workers must consume only policy-validated WorkBundle after specialist merge."""

from __future__ import annotations

import pytest

from app.graph.resource_planner_graph import (
    _MERGE_DECISION_VALIDATED,
    _apply_work_bundle_to_workers,
)
from app.planner.planner_hierarchy import (
    SpecialistProposal,
    SplSpecialistReport,
    WorkBundle,
    apply_specialist_reports,
    build_planner_iteration,
    materialize_resource_plan_from_bundle,
    work_bundle_from_resource_plan,
)
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.schemas.requests import ChatRequest


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
        ],
    )


def test_apply_work_bundle_to_workers_ignores_raw_work_bundle_without_validated_channel() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:raw")
    bundle = apply_specialist_reports(
        bundle,
        [
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
        ],
    )
    state = {
        "request": ChatRequest(message="failed login spike"),
        "evidence_plan": {"resource_plan": plan.model_dump()},
        "work_bundle": bundle.model_dump(),
    }
    out = _apply_work_bundle_to_workers(state)
    assert out["evidence_plan"].get("resource_plan") == plan.model_dump()


def test_apply_work_bundle_to_workers_applies_validated_enrichment() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:valid")
    bundle = apply_specialist_reports(
        bundle,
        [
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
        ],
    )
    assert bundle.merge_decision_reason == _MERGE_DECISION_VALIDATED
    state = {
        "request": ChatRequest(message="failed login spike"),
        "evidence_plan": {"resource_plan": plan.model_dump()},
        "validated_work_bundle": bundle.model_dump(),
    }
    out = _apply_work_bundle_to_workers(state)
    resource_plan = out["evidence_plan"]["resource_plan"]
    spl_step = next(step for step in resource_plan["steps"] if step["step_id"] == "spl")
    assert spl_step["args_template"]["use_case_id"] == "auth_failed_login_spike"


def test_apply_work_bundle_to_workers_skips_without_merge_decision_reason() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:unmerged")
    bundle.tasks[0].args_template = {"use_case_id": "rogue"}
    state = {
        "request": ChatRequest(message="failed login spike"),
        "evidence_plan": {"resource_plan": plan.model_dump()},
        "validated_work_bundle": bundle.model_dump(),
    }
    out = _apply_work_bundle_to_workers(state)
    spl_step = next(step for step in out["evidence_plan"]["resource_plan"]["steps"] if step["step_id"] == "spl")
    assert "use_case_id" not in spl_step.get("args_template", {})


def test_materialize_rejects_policy_bypass_before_workers_can_consume() -> None:
    plan = _sample_plan()
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:tampered")
    bundle.tasks[0].policy_checks = []
    with pytest.raises(ValueError, match="policy violations"):
        materialize_resource_plan_from_bundle(bundle)


def test_apply_work_bundle_to_workers_records_invalid_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _sample_plan()
    state = {
        "request": ChatRequest(message="failed login spike"),
        "evidence_plan": {"resource_plan": plan.model_dump()},
        "validated_work_bundle": {"bundle_id": "bad", "tasks": "not-a-list"},
    }
    out = _apply_work_bundle_to_workers(state)
    log = out.get("decision_log") or []
    assert any(
        isinstance(item, dict)
        and item.get("node") == "work_bundle.apply"
        and str(item.get("decision_reason", "")).startswith("validated_work_bundle_model_invalid")
        for item in log
    )


def test_build_planner_iteration_marks_validated_merge_reason() -> None:
    plan = _sample_plan()
    iteration = build_planner_iteration(
        iteration=0,
        resource_plan=plan,
        delegations=[],
        reports=[
            SplSpecialistReport(
                delegation_id="del:spl",
                decision_reason="noop",
            )
        ],
        bundle_id="bundle:iter",
    )
    assert iteration.bundle is not None
    assert iteration.bundle.merge_decision_reason == _MERGE_DECISION_VALIDATED
    materialize_resource_plan_from_bundle(iteration.bundle)
