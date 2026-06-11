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
    skill_id: str | None = None,
) -> ResourcePlan:
    """Translate a decided EvidencePlan into an ordered, fallback-aware plan."""
    registry = registry or load_resource_registry()
    steps: list[PlanStep] = []
    contract = _skill_contract(skill_id, registry)
    skill_vetoes: list[str] = []

    rag_step = _rag_step(evidence_plan) if getattr(evidence_plan, "needs_rag", False) else None
    spl_step = _spl_step(evidence_plan, use_case_id, registry) if getattr(evidence_plan, "needs_spl", False) else None
    mcp_step = _mcp_step(evidence_plan) if getattr(evidence_plan, "needs_mcp", False) else None

    # WS2 T2.1: the routed skill's capability contract constrains composition.
    # A step whose purpose the skill blocks (or does not allow at all) is
    # vetoed before it ever exists; the veto is recorded in provenance.
    if contract is not None:
        if spl_step is not None and not _skill_permits(contract, "spl"):
            skill_vetoes.append("spl_artifact:skill_contract")
            spl_step = None
        if mcp_step is not None and not _skill_permits(contract, "mcp"):
            skill_vetoes.append("mcp_execution:skill_contract")
            mcp_step = None
        required = [str(item) for item in contract.get("required_evidence") or []]
        if required:
            check = "skill_required_evidence:" + ",".join(sorted(required))
            for step in (rag_step, spl_step, mcp_step):
                if step is not None:
                    step.policy_checks.append(check)
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

    provenance: dict[str, Any] = {
        "composer": _COMPOSER_VERSION,
        "intent_family": intent_family,
        "use_case_id": use_case_id,
        "match_path": match_path,
    }
    if skill_id:
        provenance["skill_id"] = skill_id
    if contract is not None and contract.get("default_workflow"):
        provenance["skill_workflow"] = list(contract["default_workflow"])
    if skill_vetoes:
        provenance["skill_vetoes"] = skill_vetoes
    return ResourcePlan(
        steps=steps,
        plan_source="deterministic",
        provenance=provenance,
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


# Tool-name fragments in skill catalog contracts that permit each purpose.
_PURPOSE_TOOL_HINTS = {
    "spl": ("spl_generation", "spl_template_registry", "spl_validator", "spl_validation"),
    "mcp": ("splunk_mcp_search", "mcp_search", "splunk_mcp"),
}


def _skill_contract(skill_id: str | None, registry: ResourceRegistry) -> dict[str, Any] | None:
    if not skill_id:
        return None
    descriptor = registry.by_id(f"skill:{skill_id}")
    if descriptor is None:
        return None
    contract = dict(descriptor.input_contract or {})
    # Allowed tools ride on the descriptor as capability strings.
    contract.setdefault(
        "allowed_tools",
        [
            cap.split(":", 1)[1]
            for cap in descriptor.capabilities
            if cap.startswith("allowed_tool:")
        ],
    )
    return contract


def _skill_permits(contract: dict[str, Any], purpose_key: str) -> bool:
    blocked = {str(item) for item in contract.get("blocked_tools") or []}
    hints = _PURPOSE_TOOL_HINTS[purpose_key]
    if purpose_key == "mcp" and "mcp_execution" in blocked:
        return False
    allowed = contract.get("default_workflow") or []
    allowed_tools = _allowed_tools_from_registry_caps(contract)
    pool = {*map(str, allowed), *allowed_tools}
    return any(any(hint in item for item in pool) for hint in hints)


def _allowed_tools_from_registry_caps(contract: dict[str, Any]) -> set[str]:
    # The registry descriptor stores allowed tools as capability strings
    # ("allowed_tool:<name>") on the skill resource; the raw contract dict may
    # also carry them directly when provided by tests.
    direct = contract.get("allowed_tools")
    if isinstance(direct, list):
        return {str(item) for item in direct}
    return set()
