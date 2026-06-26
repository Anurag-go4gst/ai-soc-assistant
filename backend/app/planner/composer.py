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

from app.connectors.mcp.splunk_mcp_readiness import plan_splunk_discovery_calls
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
            mcp_step.status = "blocked_policy"
            mcp_step.status_reason = "skill_contract"
            mcp_step.policy_checks.append("blocked_by_skill_contract")
        required = [str(item) for item in contract.get("required_evidence") or []]
        if required:
            check = "skill_required_evidence:" + ",".join(sorted(required))
            for step in (rag_step, spl_step, mcp_step):
                if step is not None:
                    step.policy_checks.append(check)
    if mcp_step is not None and getattr(evidence_plan, "mcp_allowed", False) is not True:
        if mcp_step.status != "blocked_policy":
            mcp_step.status = "blocked_policy"
            mcp_step.status_reason = "mcp_not_allowed_by_evidence_plan"
        if "mcp_not_allowed_by_evidence_plan" not in mcp_step.policy_checks:
            mcp_step.policy_checks.append("mcp_not_allowed_by_evidence_plan")
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
    if answer_mode == "guided_investigation":
        steps.extend(
            [
                PlanStep(
                    step_id="evidence",
                    resource_id="skill:evidence_collection",
                    purpose="evidence_collection",
                    policy_checks=["metadata_only", "analyst_validation_required"],
                ),
                PlanStep(
                    step_id="sufficiency",
                    resource_id="skill:context_sufficiency",
                    purpose="context_sufficiency",
                    policy_checks=["no_unsupported_claims", "analyst_validation_required"],
                ),
            ]
        )
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
    if intent_family == "guided_investigation" or skill_id == "guided_investigation":
        provenance["resource_decisions"] = build_guided_investigation_resource_decisions(
            evidence_plan,
            match_path=match_path,
        )
    elif _should_emit_hybrid_discovery_plan(
        evidence_plan,
        intent_family=intent_family,
        skill_id=skill_id,
    ):
        provenance["resource_decisions"] = build_hybrid_mcp_discovery_resource_decisions(
            evidence_plan,
            path_type=_infer_path_type_for_discovery(evidence_plan, intent_family=intent_family),
            match_path=match_path,
        )
    return ResourcePlan(
        steps=steps,
        plan_source="deterministic",
        provenance=provenance,
    )


def build_guided_investigation_resource_decisions(
    evidence_plan: Any | None,
    *,
    match_path: str | None = None,
) -> dict[str, Any]:
    discovery_calls = plan_splunk_discovery_calls(include_knowledge_objects=True)
    limitations = list(getattr(evidence_plan, "limitations", []) or []) or [
        "No live query was executed.",
        "No MITRE technique or incident severity is asserted without evidence.",
    ]
    return {
        "match_path": match_path,
        "rag": {
            "needed": True,
            "source": "soc_kb_rag",
            "no_match_behavior": "general_guidance_allowed",
        },
        "spl": {
            "needed": "optional",
            "review_only": True,
            "skip_reason": "No existing deterministic draft family matched this out-of-registry hunt.",
        },
        "mcp": _mcp_discovery_decision_block(discovery_calls, needed=False, allowed=False),
        "mitre": {"allowed": False, "skip_reason": "No evidence-supported technique claim is available."},
        "severity": {"allowed": False, "skip_reason": "No grounded incident severity is available."},
        "hil": {"required": True, "reason": "Analyst validates hypotheses and local data scope."},
        "limitations": limitations,
    }


def build_hybrid_mcp_discovery_resource_decisions(
    evidence_plan: Any | None,
    *,
    path_type: str | None = None,
    match_path: str | None = None,
) -> dict[str, Any]:
    """Phase A discovery planning for hybrid / spl_review paths — planned-only, no live I/O."""
    discovery_calls = plan_splunk_discovery_calls(include_knowledge_objects=True)
    needs_mcp = bool(getattr(evidence_plan, "needs_mcp", False))
    needs_spl = bool(getattr(evidence_plan, "needs_spl", False))
    needs_rag = bool(getattr(evidence_plan, "needs_rag", False))
    return {
        "match_path": match_path,
        "path_type": path_type,
        "rag": {"needed": needs_rag, "source": "soc_kb_rag"},
        "spl": {
            "needed": needs_spl,
            "review_only": path_type in {"spl_review", "spl_review_plus_rag", None},
            "skip_reason": None if needs_spl else "spl_not_required_for_path",
        },
        "mcp": _mcp_discovery_decision_block(
            discovery_calls,
            needed=needs_mcp,
            allowed=False,
            skip_reason="Search execution gated; discovery checklist is planned-only until COE enables.",
        ),
        "mitre": {"allowed": bool(getattr(evidence_plan, "needs_mitre", False))},
        "severity": {"allowed": bool(getattr(evidence_plan, "needs_mitre", False))},
        "hil": {"required": True, "reason": "Analyst confirms SPL and approves any search execution."},
        "limitations": list(getattr(evidence_plan, "limitations", []) or []),
    }


def _mcp_discovery_decision_block(
    discovery_calls: list[Any],
    *,
    needed: bool,
    allowed: bool,
    skip_reason: str = "Execution gates closed; checklist runnable manually by analyst.",
) -> dict[str, Any]:
    return {
        "needed": needed,
        "allowed": allowed,
        "skip_reason": skip_reason,
        "planned_discovery": [record.tool_name for record in discovery_calls],
        "planned_discovery_calls": [
            {
                "kind": record.kind,
                "server": record.server,
                "tool_name": record.tool_name,
                "arguments": dict(record.arguments),
                "block_reason": record.block_reason,
                "failure_mode": record.failure_mode,
                "policy_checks": list(record.policy_checks),
            }
            for record in discovery_calls
        ],
    }


def _should_emit_hybrid_discovery_plan(
    evidence_plan: Any,
    *,
    intent_family: str | None,
    skill_id: str | None,
) -> bool:
    if intent_family == "guided_investigation" or skill_id == "guided_investigation":
        return False
    answer_mode = str(getattr(evidence_plan, "answer_mode", "") or "")
    if answer_mode == "hybrid":
        return True
    if getattr(evidence_plan, "needs_spl", False) and getattr(evidence_plan, "needs_rag", False):
        return True
    if getattr(evidence_plan, "needs_spl", False) and getattr(evidence_plan, "needs_mitre", False):
        return True
    if getattr(evidence_plan, "needs_spl", False) and getattr(evidence_plan, "needs_mcp", False):
        return True
    return False


def _infer_path_type_for_discovery(
    evidence_plan: Any,
    *,
    intent_family: str | None,
) -> str | None:
    answer_mode = str(getattr(evidence_plan, "answer_mode", "") or "")
    if answer_mode == "hybrid" or intent_family == "hybrid_investigation_plus_policy":
        return "hybrid_investigation"
    if getattr(evidence_plan, "needs_spl", False) and getattr(evidence_plan, "needs_rag", False):
        return "spl_review_plus_rag"
    if getattr(evidence_plan, "needs_spl", False):
        return "spl_review"
    return None


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
