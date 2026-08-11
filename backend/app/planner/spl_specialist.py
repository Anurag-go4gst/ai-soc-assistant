"""Deterministic SPL specialist — committed-plan readiness metadata only.

The builder may inspect template/resource registry posture and bounded slot
summaries.  It never renders SPL, calls an LLM, invokes the validator, or
changes execution eligibility.
"""

from __future__ import annotations

from typing import Any

from app.planner.planner_hierarchy import SpecialistProposal, SplSpecialistReport
from app.planner.resource_registry import ResourceRegistry, load_resource_registry
from app.spl.template_registry import SplTemplateDefinition, load_spl_templates


def build_spl_audit_report(
    *,
    evidence_plan: dict[str, Any] | None,
    resource_registry: ResourceRegistry | None = None,
    templates: list[SplTemplateDefinition] | None = None,
    delegation_id: str = "del:spl",
) -> SplSpecialistReport:
    """Return bounded SPL readiness metadata for an existing SPL plan step."""
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    resources = resource_registry or load_resource_registry()
    catalog = templates if templates is not None else load_spl_templates()
    template_by_id = {item.template_id: item for item in catalog}
    step = _spl_step(plan)

    plan_needs_spl = bool(plan.get("needs_spl") or step)
    plan_spl_allowed = bool(plan.get("spl_allowed"))
    planned_resource_id = str(step.get("resource_id") or "") if step else None
    fallback_resource_id = str(step.get("on_unavailable") or "") if step else None
    fallback_resource_id = fallback_resource_id or None
    template_id = _planned_template_id(planned_resource_id)
    template = template_by_id.get(template_id or "")
    template_status = str(template.status) if template is not None else None
    template_production_executable = (
        template.is_production_executable() if template is not None else None
    )

    options: list[str] = []
    planned_descriptor = resources.by_id(planned_resource_id) if planned_resource_id else None
    fallback_descriptor = resources.by_id(fallback_resource_id) if fallback_resource_id else None
    governed_ready = bool(
        template is not None
        and template.is_production_executable()
        and planned_descriptor is not None
        and planned_descriptor.availability in {"available", "fixture_only"}
    )
    if governed_ready:
        options.append("governed_template")
    fallback_ready = bool(
        fallback_descriptor is not None
        and fallback_descriptor.kind == "spl_lab_draft_family"
        and fallback_descriptor.availability in {"available", "fixture_only"}
    )
    skill_fallback_ready = bool(
        planned_descriptor is not None
        and planned_descriptor.resource_id == "skill:spl_generation"
        and planned_descriptor.availability in {"available", "fixture_only"}
    )
    if fallback_ready or skill_fallback_ready:
        options.append("review_only_fallback")

    required_slots = _required_slots(step, template)
    slot_status, missing_slots = _slot_readiness(plan, step, required_slots)
    blockers: list[str] = []
    warnings: list[str] = []
    if plan_needs_spl and not plan_spl_allowed:
        blockers.append("spl_not_allowed_by_plan")
    if template_id and template is None:
        blockers.append("spl_template_missing")
    elif template is not None and not template.is_production_executable():
        blockers.append("spl_template_not_production_executable")
    if step and planned_descriptor is None:
        blockers.append("spl_resource_unavailable")
    if missing_slots:
        blockers.append("required_slots_missing")
    if _source_profile_missing_slots(plan):
        blockers.append("source_profile_missing")
    if slot_status == "unknown" and required_slots:
        warnings.append("slot_binding_unknown")

    spl_source = _spl_source(
        plan_needs_spl=plan_needs_spl,
        plan_spl_allowed=plan_spl_allowed,
        governed_ready=governed_ready,
        fallback_ready=bool(fallback_ready or skill_fallback_ready),
    )
    proposals = _fill_blank_proposal(
        step=step,
        template_id=template_id,
        fallback_resource_id=fallback_resource_id,
        required_slots=required_slots,
    )
    return SplSpecialistReport(
        delegation_id=delegation_id,
        decision_reason=f"spl_{spl_source}",
        authority="proposed_validated" if proposals else "advisory",
        plan_needs_spl=plan_needs_spl,
        plan_spl_allowed=plan_spl_allowed,
        planned_resource_id=planned_resource_id,
        template_id=template_id,
        template_status=template_status,
        template_production_executable=template_production_executable,
        fallback_resource_id=fallback_resource_id,
        candidate_source_options=options,
        spl_source=spl_source,
        slot_binding_status=slot_status,
        missing_required_slots=missing_slots,
        validation_required=bool(step),
        execution_eligible=False,
        blockers=blockers,
        warnings=warnings,
        proposals=proposals,
    )


def _spl_step(evidence_plan: dict[str, Any]) -> dict[str, Any] | None:
    resource_plan = evidence_plan.get("resource_plan")
    raw_steps = resource_plan.get("steps") if isinstance(resource_plan, dict) else []
    return next(
        (
            step
            for step in raw_steps or []
            if isinstance(step, dict) and step.get("purpose") == "spl_artifact"
        ),
        None,
    )


def _planned_template_id(resource_id: str | None) -> str | None:
    prefix = "spl_template_family:"
    if resource_id and resource_id.startswith(prefix):
        return resource_id[len(prefix) :]
    return None


def _required_slots(
    step: dict[str, Any] | None,
    template: SplTemplateDefinition | None,
) -> list[str]:
    args = step.get("args_template") if isinstance(step, dict) else None
    declared = args.get("required_slots") if isinstance(args, dict) else None
    if isinstance(declared, list) and declared:
        return sorted({str(item) for item in declared if str(item)})[:16]
    if template is None:
        return []
    return sorted({str(item) for item in template.required_parameters if str(item)})[:16]


def _slot_readiness(
    evidence_plan: dict[str, Any],
    step: dict[str, Any] | None,
    required_slots: list[str],
) -> tuple[str, list[str]]:
    if step is None:
        return "not_required", []
    if not required_slots:
        return "ready", []
    summary = evidence_plan.get("normalized_slot_summary")
    if not isinstance(summary, dict):
        return "unknown", []
    normalized = summary.get("normalized_slots")
    normalized = normalized if isinstance(normalized, dict) else {}
    present = {str(key) for key, value in normalized.items() if value not in {None, ""}}
    missing = set(required_slots) - present
    for item in summary.get("unbound_constraints") or []:
        if isinstance(item, dict) and item.get("slot") in required_slots:
            missing.add(str(item["slot"]))
    missing.update(_source_profile_missing_slots(evidence_plan) & set(required_slots))
    bounded = sorted(missing)[:16]
    return ("missing_required_slots", bounded) if bounded else ("ready", [])


def _source_profile_missing_slots(evidence_plan: dict[str, Any]) -> set[str]:
    summary = evidence_plan.get("source_profile_binding_summary")
    if not isinstance(summary, dict):
        return set()
    missing: set[str] = set()
    for item in summary.get("source_profile_bindings_missing") or []:
        if isinstance(item, dict) and item.get("slot"):
            missing.add(str(item["slot"]))
        elif isinstance(item, str):
            missing.add(item)
    return missing


def _spl_source(
    *,
    plan_needs_spl: bool,
    plan_spl_allowed: bool,
    governed_ready: bool,
    fallback_ready: bool,
) -> str:
    if not plan_needs_spl:
        return "not_needed"
    if not plan_spl_allowed:
        return "blocked"
    if governed_ready:
        return "governed_template"
    if fallback_ready:
        return "review_only_fallback"
    return "unavailable"


def _fill_blank_proposal(
    *,
    step: dict[str, Any] | None,
    template_id: str | None,
    fallback_resource_id: str | None,
    required_slots: list[str],
) -> list[SpecialistProposal]:
    if step is None:
        return []
    args = step.get("args_template")
    args = args if isinstance(args, dict) else {}
    fill: dict[str, Any] = {}
    if template_id and not args.get("template_id"):
        fill["template_id"] = template_id
    if fallback_resource_id and not args.get("fallback_resource_id"):
        fill["fallback_resource_id"] = fallback_resource_id
    if required_slots and not args.get("required_slots"):
        fill["required_slots"] = required_slots
    if not fill:
        return []
    return [
        SpecialistProposal(
            proposal_id=f"sp:{step.get('step_id') or 'spl'}",
            purpose="spl_artifact",
            resource_id=str(step.get("resource_id") or ""),
            args_template=fill,
            rationale="fill blank SPL readiness metadata on committed plan step",
        )
    ]
