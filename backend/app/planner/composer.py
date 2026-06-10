"""Deterministic plan composer (T0.3) — EvidencePlan → composed ResourcePlan.

Composes the ordered step list from the already-decided EvidencePlan plus
intent/use-case context. Composition is a pure translation: a step is
emitted for exactly the purposes the EvidencePlan booleans request, so
`project_booleans(composed) == needs_*` holds by construction (parity-tested
against the sentinel set). Value added on top of the booleans: concrete
registry resource binding, step ordering by rag_phase, and template→lab-draft
degrade chains for the execution loop (T0.4).
"""

from __future__ import annotations

from typing import Any

from app.planner.resource_plan import PlanStep, ResourcePlan
from app.planner.resource_registry import ResourceRegistry, load_resource_registry

_COMPOSER_VERSION = "deterministic_v1"


def compose_resource_plan(
    evidence_plan: Any,
    *,
    intent_family: str | None = None,
    use_case_id: str | None = None,
    match_path: str | None = None,
    registry: ResourceRegistry | None = None,
) -> ResourcePlan:
    """Translate a decided EvidencePlan into an ordered, fallback-aware plan."""
    registry = registry or load_resource_registry()
    steps: list[PlanStep] = []

    rag_step = _rag_step(evidence_plan) if getattr(evidence_plan, "needs_rag", False) else None
    spl_step = _spl_step(evidence_plan, use_case_id, registry) if getattr(evidence_plan, "needs_spl", False) else None
    mcp_step = _mcp_step(evidence_plan) if getattr(evidence_plan, "needs_mcp", False) else None
    mitre_step = (
        PlanStep(
            step_id="mitre",
            resource_id="skill:mitre_mapping",
            purpose="mitre_mapping",
            policy_checks=["mitre_evidence_preconditions", "mitre_visibility_policy"],
        )
        if getattr(evidence_plan, "needs_mitre", False)
        else None
    )

    rag_phase = str(getattr(evidence_plan, "rag_phase", "") or "")
    if rag_step is not None and rag_phase in {"rag_only", "pre_mcp"}:
        steps.append(rag_step)
    if spl_step is not None:
        steps.append(spl_step)
    if mcp_step is not None:
        steps.append(mcp_step)
    if rag_step is not None and rag_phase == "post_mcp":
        steps.append(rag_step)
    if mitre_step is not None:
        steps.append(mitre_step)

    answer_mode = str(getattr(evidence_plan, "answer_mode", "") or "")
    if answer_mode != "clarification":
        steps.append(
            PlanStep(
                step_id="narration",
                resource_id="llm_role:narration",
                purpose="narration",
                policy_checks=["answer_guard", "deterministic_fallback_on_failure"],
            )
        )

    return ResourcePlan(
        steps=steps,
        plan_source="deterministic",
        provenance={
            "composer": _COMPOSER_VERSION,
            "intent_family": intent_family,
            "use_case_id": use_case_id,
            "match_path": match_path,
        },
    )


def _rag_step(evidence_plan: Any) -> PlanStep:
    policy_checks = ["governed_rag_only"]
    if getattr(evidence_plan, "policy_context_required", False):
        policy_checks.append("policy_context_required")
    return PlanStep(
        step_id="rag",
        resource_id="rag_corpus:soc_kb",
        purpose="knowledge_retrieval",
        policy_checks=policy_checks,
    )


def _spl_step(evidence_plan: Any, use_case_id: str | None, registry: ResourceRegistry) -> PlanStep:
    """Bind the SPL purpose to a governed template family when one is active;
    otherwise the spl_generation skill (which renders the lab-draft preview)."""
    policy_checks = ["spl_validator", "execution_eligible_false"]
    required = list(getattr(evidence_plan, "required_evidence_keys", []) or [])
    if required:
        policy_checks.append("required_evidence:" + ",".join(sorted(required)))

    template_id = f"spl_template_family:{use_case_id}" if use_case_id else None
    if template_id and registry.by_id(template_id) is not None:
        fallback = next(
            (
                item.resource_id
                for item in registry.by_kind("spl_lab_draft_family")
                if item.fallback_of == template_id
            ),
            None,
        )
        return PlanStep(
            step_id="spl",
            resource_id=template_id,
            purpose="spl_artifact",
            on_unavailable=fallback,
            policy_checks=policy_checks,
        )
    return PlanStep(
        step_id="spl",
        resource_id="skill:spl_generation",
        purpose="spl_artifact",
        policy_checks=policy_checks,
    )


def _mcp_step(evidence_plan: Any) -> PlanStep:
    return PlanStep(
        step_id="mcp",
        resource_id="mcp_tool:splunk_run_query",
        purpose="mcp_execution",
        policy_checks=[
            "mcp_execution_gate",
            "approved_normalized_spl_only",
            "global_and_server_execution_flags",
        ],
    )
