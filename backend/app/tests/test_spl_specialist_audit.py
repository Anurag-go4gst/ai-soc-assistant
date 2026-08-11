"""Deterministic, non-executable SPL specialist readiness audit."""

from __future__ import annotations

from app.planner.planner_hierarchy import apply_specialist_reports, work_bundle_from_resource_plan
from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_registry import ResourceDescriptor, ResourceRegistry
from app.planner.spl_specialist import build_spl_audit_report
from app.spl.template_registry import SplTemplateDefinition


def _template(
    *,
    status: str = "active",
    production_ready: bool = True,
) -> SplTemplateDefinition:
    return SplTemplateDefinition(
        template_id="auth_failed_login_spike",
        status=status,
        use_case_id="auth_failed_login_spike",
        required_parameters=["index", "sourcetype"],
        enabled=True,
        production_ready=production_ready,
        spl_text="search index=<secret-index> token=must_not_escape",
    )


def _resources() -> ResourceRegistry:
    return ResourceRegistry(
        schema_version=2,
        resources=[
            ResourceDescriptor(
                resource_id="spl_template_family:auth_failed_login_spike",
                kind="spl_template_family",
                capabilities=["governed_spl_generation", "spl_validation"],
                availability="available",
                onboarding_status="fixture_tested",
            ),
            ResourceDescriptor(
                resource_id="spl_lab_draft_family:auth_failed_login_threshold",
                kind="spl_lab_draft_family",
                capabilities=["spl_draft_preview"],
                availability="available",
                onboarding_status="fixture_tested",
                fallback_of="spl_template_family:auth_failed_login_spike",
            ),
            ResourceDescriptor(
                resource_id="skill:spl_generation",
                kind="skill",
                capabilities=["allowed_tool:spl_template_registry"],
                availability="available",
                onboarding_status="fixture_tested",
            ),
        ],
    )


def _plan(
    *,
    resource_id: str | None,
    spl_allowed: bool = True,
    fallback: str | None = None,
    slots: dict | None = None,
    unbound: list[dict] | None = None,
    source_missing: list[dict] | None = None,
    args_template: dict | None = None,
) -> dict:
    steps = []
    if resource_id:
        steps.append(
            {
                "step_id": "spl",
                "resource_id": resource_id,
                "purpose": "spl_artifact",
                "args_template": args_template or {},
                "on_unavailable": fallback,
                "policy_checks": ["spl_validator", "execution_eligible_false"],
                "status": "planned" if spl_allowed else "blocked_policy",
            }
        )
    payload = {
        "needs_spl": bool(resource_id),
        "spl_allowed": spl_allowed,
        "use_case_id": "auth_failed_login_spike",
        "resource_plan": {"plan_source": "deterministic", "steps": steps},
    }
    if slots is not None or unbound is not None:
        payload["normalized_slot_summary"] = {
            "normalized_slots": slots or {},
            "unbound_constraints": unbound or [],
        }
    if source_missing is not None:
        payload["source_profile_binding_summary"] = {
            "source_profile_bindings_missing": source_missing,
        }
    return payload


def test_not_needed_spl_report_is_non_executable() -> None:
    report = build_spl_audit_report(
        evidence_plan=_plan(resource_id=None),
        resource_registry=_resources(),
        templates=[_template()],
    )

    assert report.spl_source == "not_needed"
    assert report.slot_binding_status == "not_required"
    assert report.validation_required is False
    assert report.execution_eligible is False
    assert report.proposals == []


def test_active_template_reports_governed_readiness() -> None:
    report = build_spl_audit_report(
        evidence_plan=_plan(
            resource_id="spl_template_family:auth_failed_login_spike",
            fallback="spl_lab_draft_family:auth_failed_login_threshold",
            slots={"index": "main", "sourcetype": "wineventlog"},
        ),
        resource_registry=_resources(),
        templates=[_template()],
    )

    assert report.plan_needs_spl is True
    assert report.plan_spl_allowed is True
    assert report.template_id == "auth_failed_login_spike"
    assert report.template_status == "active"
    assert report.template_production_executable is True
    assert report.fallback_resource_id == "spl_lab_draft_family:auth_failed_login_threshold"
    assert report.candidate_source_options == ["governed_template", "review_only_fallback"]
    assert report.spl_source == "governed_template"
    assert report.slot_binding_status == "ready"
    assert report.validation_required is True
    assert report.execution_eligible is False


def test_inactive_and_missing_templates_fail_closed() -> None:
    inactive = build_spl_audit_report(
        evidence_plan=_plan(
            resource_id="spl_template_family:auth_failed_login_spike",
            slots={"index": "main", "sourcetype": "wineventlog"},
        ),
        resource_registry=_resources(),
        templates=[_template(status="sample", production_ready=False)],
    )
    missing = build_spl_audit_report(
        evidence_plan=_plan(
            resource_id="spl_template_family:auth_failed_login_spike",
            slots={"index": "main", "sourcetype": "wineventlog"},
        ),
        resource_registry=_resources(),
        templates=[],
    )

    assert inactive.spl_source == "unavailable"
    assert "spl_template_not_production_executable" in inactive.blockers
    assert missing.spl_source == "unavailable"
    assert "spl_template_missing" in missing.blockers


def test_lab_review_fallback_is_explicitly_non_executable() -> None:
    report = build_spl_audit_report(
        evidence_plan=_plan(
            resource_id="skill:spl_generation",
            slots={},
        ),
        resource_registry=_resources(),
        templates=[_template()],
    )

    assert report.candidate_source_options == ["review_only_fallback"]
    assert report.spl_source == "review_only_fallback"
    assert report.validation_required is True
    assert report.execution_eligible is False


def test_missing_slots_and_source_profile_gaps_are_bounded() -> None:
    report = build_spl_audit_report(
        evidence_plan=_plan(
            resource_id="spl_template_family:auth_failed_login_spike",
            slots={"index": "main"},
            unbound=[{"slot": "sourcetype", "raw_value": "must_not_escape"}],
            source_missing=[{"slot": "sourcetype", "value": "must_not_escape"}],
        ),
        resource_registry=_resources(),
        templates=[_template()],
    )

    assert report.slot_binding_status == "missing_required_slots"
    assert report.missing_required_slots == ["sourcetype"]
    assert "required_slots_missing" in report.blockers
    assert "source_profile_missing" in report.blockers
    assert "must_not_escape" not in report.model_dump_json()


def test_report_contains_no_spl_and_calls_no_llm_renderer_or_validator(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.planner.spl_specialist.load_resource_registry",
        lambda: (_ for _ in ()).throw(AssertionError("resource loader called")),
    )
    monkeypatch.setattr(
        "app.planner.spl_specialist.load_spl_templates",
        lambda: (_ for _ in ()).throw(AssertionError("template loader called")),
    )

    report = build_spl_audit_report(
        evidence_plan=_plan(
            resource_id="spl_template_family:auth_failed_login_spike",
            slots={"index": "main", "sourcetype": "wineventlog"},
        ),
        resource_registry=_resources(),
        templates=[_template()],
    )
    payload = report.model_dump_json()

    assert "search index=" not in payload
    assert "secret-index" not in payload
    assert "candidate_spl" not in payload
    assert "normalized_spl" not in payload
    assert "validator_approved" not in payload


def test_fill_blank_metadata_merges_without_changing_plan_authority() -> None:
    evidence = _plan(
        resource_id="spl_template_family:auth_failed_login_spike",
        fallback="spl_lab_draft_family:auth_failed_login_threshold",
        slots={"index": "main"},
        args_template={"required_slots": []},
    )
    plan = ResourcePlan(
        plan_source="deterministic",
        steps=[PlanStep.model_validate(evidence["resource_plan"]["steps"][0])],
    )
    bundle = work_bundle_from_resource_plan(plan, bundle_id="bundle:spl")
    report = build_spl_audit_report(
        evidence_plan=evidence,
        resource_registry=_resources(),
        templates=[_template()],
    )

    merged = apply_specialist_reports(bundle, [report])
    task = merged.tasks[0]
    assert task.args_template == {
        "required_slots": ["index", "sourcetype"],
        "fallback_resource_id": "spl_lab_draft_family:auth_failed_login_threshold",
        "template_id": "auth_failed_login_spike",
    }
    assert task.policy_checks == ["spl_validator", "execution_eligible_false"]
    assert task.status == "planned"
