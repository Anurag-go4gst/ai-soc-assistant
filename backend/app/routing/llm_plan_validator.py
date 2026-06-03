"""Validate advisory LLM route-plan JSON against control-plane evidence and intent (Phase 5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.contracts.route_adjudication import RouteAdjudication
from app.config import settings
from app.routing.governance import (
    ROUTING_MODE_LLM_ASSISTED_SEMANTIC,
    ROUTING_MODE_LLM_PRIMARY_LAB,
    ROUTING_MODE_LLM_SHADOW_ONLY,
)
from app.routing.skills import valid_skill

POLICY_VERSION = "2026-06-control-plane-v1"

LlmPlanValidationStatus = Literal["skipped", "accepted", "rejected", "corrected"]

_ASSISTED_ROUTING_MODES = frozenset(
    {
        ROUTING_MODE_LLM_ASSISTED_SEMANTIC,
        ROUTING_MODE_LLM_PRIMARY_LAB,
        ROUTING_MODE_LLM_SHADOW_ONLY,
    }
)

_SKILL_ALIASES: dict[str, str] = {
    "credential stuffing detection": "attack_discovery",
}


@dataclass
class LlmPlanValidationResult:
    status: LlmPlanValidationStatus
    advisory_plan: dict[str, Any] | None = None
    corrected_plan: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    policy_version: str = POLICY_VERSION
    mcp_execution_allowed: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def should_validate_llm_advisory_plan(routing_mode: str | None = None) -> bool:
    """True when routing mode permits LLM assist validation (not deterministic-only)."""
    mode = (routing_mode or settings.routing_mode).strip().lower()
    if mode == "llm_primary":
        mode = ROUTING_MODE_LLM_ASSISTED_SEMANTIC
    return mode in _ASSISTED_ROUTING_MODES


def build_advisory_plan_from_context(
    *,
    comparison: dict[str, Any] | None = None,
    route_plan_shadow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Best-effort advisory plan JSON from routed comparison / shadow (no LLM call)."""
    plan: dict[str, Any] = {}
    if isinstance(comparison, dict):
        llm_shadow = comparison.get("llm_shadow")
        if isinstance(llm_shadow, dict):
            plan.update(_advisory_from_llm_route(llm_shadow))
    if isinstance(route_plan_shadow, dict):
        for key in ("needs_spl", "needs_mcp", "needs_rag", "needs_mitre", "mcp_execution_allowed"):
            if key in route_plan_shadow:
                plan[key] = route_plan_shadow[key]
        skill = route_plan_shadow.get("primary_skill") or route_plan_shadow.get("advisory_skill")
        if isinstance(skill, str) and skill.strip():
            plan.setdefault("skill", skill.strip())
    return plan


def validate_llm_advisory_plan(
    advisory_plan: dict[str, Any] | None,
    *,
    evidence_plan: dict[str, Any] | EvidencePlan | None = None,
    route_adjudication: dict[str, Any] | RouteAdjudication | None = None,
    intent_classification: dict[str, Any] | IntentClassification | None = None,
    candidate_mappings: dict[str, Any] | None = None,
    routing_mode: str | None = None,
) -> LlmPlanValidationResult:
    """JSON-only validation; never grants execution or calls an LLM provider."""
    _ = candidate_mappings  # reserved for trace enrichment
    if not should_validate_llm_advisory_plan(routing_mode):
        return LlmPlanValidationResult(
            status="skipped",
            reasons=["routing_mode_deterministic_only_or_unsupported"],
            policy_version=POLICY_VERSION,
        )

    if not isinstance(advisory_plan, dict) or not advisory_plan:
        return LlmPlanValidationResult(
            status="skipped",
            reasons=["no_advisory_plan_payload"],
            policy_version=POLICY_VERSION,
        )

    plan = dict(advisory_plan)
    evidence = _coerce_evidence_plan(evidence_plan)
    intent = _coerce_intent(intent_classification)
    adjudication = _coerce_adjudication(route_adjudication)

    reasons: list[str] = []
    warnings: list[str] = []
    corrected = dict(plan)

    corrected["mcp_execution_allowed"] = False
    if plan.get("mcp_execution_allowed") is True:
        reasons.append("mcp_execution_allowed_forbidden")

    skill = _extract_skill(plan)
    normalized_skill = _normalize_skill(skill)
    if skill and normalized_skill is None:
        reasons.append(f"unknown_skill_rejected:{skill}")
    elif normalized_skill and normalized_skill != skill:
        corrected["skill"] = normalized_skill
        warnings.append(f"skill_normalized:{skill}->{normalized_skill}")

    if evidence is not None:
        _validate_against_evidence_plan(corrected, evidence, reasons, warnings)

    if intent is not None:
        _validate_against_intent(corrected, intent, reasons, warnings)

    if adjudication is not None and adjudication.final_route and normalized_skill:
        if normalized_skill != adjudication.final_route:
            warnings.append(
                f"advisory_skill_differs_from_route_adjudication:{normalized_skill}!={adjudication.final_route}"
            )

    if reasons:
        return LlmPlanValidationResult(
            status="rejected",
            advisory_plan=plan,
            corrected_plan=corrected,
            reasons=sorted(set(reasons)),
            warnings=sorted(set(warnings)),
            policy_version=POLICY_VERSION,
            mcp_execution_allowed=False,
        )

    status: LlmPlanValidationStatus = "corrected" if warnings or corrected != plan else "accepted"
    return LlmPlanValidationResult(
        status=status,
        advisory_plan=plan,
        corrected_plan=corrected,
        reasons=[],
        warnings=sorted(set(warnings)),
        policy_version=POLICY_VERSION,
        mcp_execution_allowed=False,
    )


def _advisory_from_llm_route(llm_route: dict[str, Any]) -> dict[str, Any]:
    metadata = llm_route.get("metadata") if isinstance(llm_route.get("metadata"), dict) else {}
    plan: dict[str, Any] = {
        "skill": llm_route.get("skill"),
        "confidence": llm_route.get("confidence"),
    }
    for key in (
        "needs_spl",
        "needs_mcp",
        "needs_rag",
        "needs_mitre",
        "mcp_execution_allowed",
        "mitre_answer_visible",
        "show_mitre_in_answer",
    ):
        if key in metadata:
            plan[key] = metadata[key]
    if "selected_skill" in metadata:
        plan["skill"] = metadata["selected_skill"]
    return {k: v for k, v in plan.items() if v is not None}


def _coerce_evidence_plan(
    evidence_plan: dict[str, Any] | EvidencePlan | None,
) -> EvidencePlan | None:
    if evidence_plan is None:
        return None
    if isinstance(evidence_plan, EvidencePlan):
        return evidence_plan
    if isinstance(evidence_plan, dict) and evidence_plan:
        return EvidencePlan.model_validate(evidence_plan)
    return None


def _coerce_intent(
    intent_classification: dict[str, Any] | IntentClassification | None,
) -> IntentClassification | None:
    if intent_classification is None:
        return None
    if isinstance(intent_classification, IntentClassification):
        return intent_classification
    if isinstance(intent_classification, dict) and intent_classification:
        return IntentClassification.model_validate(intent_classification)
    return None


def _coerce_adjudication(
    route_adjudication: dict[str, Any] | RouteAdjudication | None,
) -> RouteAdjudication | None:
    if route_adjudication is None:
        return None
    if isinstance(route_adjudication, RouteAdjudication):
        return route_adjudication
    if isinstance(route_adjudication, dict) and route_adjudication:
        return RouteAdjudication.model_validate(route_adjudication)
    return None


def _extract_skill(plan: dict[str, Any]) -> str | None:
    for key in ("skill", "selected_skill", "primary_skill", "final_skill"):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_skill(skill: str | None) -> str | None:
    if not skill:
        return None
    if valid_skill(skill):
        return skill
    alias = _SKILL_ALIASES.get(skill.strip().lower())
    if alias and valid_skill(alias):
        return alias
    return None


def _validate_against_evidence_plan(
    plan: dict[str, Any],
    evidence: EvidencePlan,
    reasons: list[str],
    warnings: list[str],
) -> None:
    needs_mcp = plan.get("needs_mcp")
    if needs_mcp is True and not evidence.mcp_allowed:
        reasons.append("needs_mcp_conflicts_with_evidence_plan_mcp_allowed_false")

    needs_spl = plan.get("needs_spl")
    policy_only = evidence.answer_mode in {"rag_only", "clarification"} or (
        not evidence.spl_allowed and not evidence.mcp_allowed
    )
    if needs_spl is True and policy_only:
        reasons.append("needs_spl_conflicts_with_rag_only_or_policy_evidence_plan")

    if evidence.answer_mode == "live_investigation" and evidence.mcp_allowed:
        if needs_spl is True and plan.get("needs_mcp") is False:
            reasons.append("needs_spl_without_mcp_for_live_investigation")

    if evidence.needs_mcp and plan.get("needs_mcp") is False:
        warnings.append("advisory_under_specifies_mcp_vs_evidence_plan")


def _validate_against_intent(
    plan: dict[str, Any],
    intent: IntentClassification,
    reasons: list[str],
    warnings: list[str],
) -> None:
    mitre_visible = plan.get("mitre_answer_visible")
    if mitre_visible is None:
        mitre_visible = plan.get("show_mitre_in_answer")

    if intent.requires_clarification and mitre_visible is True:
        reasons.append("mitre_visibility_conflicts_with_clarification_intent")

    if mitre_visible is True and "mitre_mapping" not in intent.answer_goal and "mitre_explanation" not in intent.answer_goal:
        if intent.intent_family not in {"mitre_mapping", "mitre_explanation"}:
            reasons.append("mitre_visibility_without_mitre_answer_goal")

    if intent.intent_family in {"policy_knowledge", "sop_or_playbook", "knowledge_only"}:
        if plan.get("needs_mcp") is True:
            reasons.append("needs_mcp_conflicts_with_policy_intent_family")
        if plan.get("needs_spl") is True:
            reasons.append("needs_spl_conflicts_with_policy_intent_family")
