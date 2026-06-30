"""Phase 2B — full pipeline dispatch authority from evidence + route inputs."""

from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.contracts.pipeline_dispatch import (
    LlmHop,
    PipelineDispatchContract,
    PipelineDispatchState,
    PipelineStage,
    RequestMode,
)
from app.chat.contracts.slot_handoff import SlotHandoffSummary, slot_handoff_from_normalized_summary
from app.chat.evidence_planner import build_catalog_display_evidence_plan, plan_evidence
from app.config import settings


_SPL_CHAIN: tuple[PipelineStage, ...] = (
    PipelineStage.workflow_spl,
    PipelineStage.spl_postprocessor,
    PipelineStage.spl_source_resolve,
)


def _coerce_evidence_plan(raw: dict[str, Any] | EvidencePlan | None) -> EvidencePlan | None:
    if raw is None:
        return None
    if isinstance(raw, EvidencePlan):
        return raw
    if isinstance(raw, dict) and raw:
        if "answer_mode" in raw:
            return EvidencePlan.model_validate(raw)
        return None
    return None


def _synthetic_evidence_plan(
    *,
    intent_classification: dict[str, Any] | IntentClassification | None,
    query_to_intent: dict[str, Any] | None,
    routed: dict[str, Any] | None,
    query_understanding: Any,
    selected_use_case: Any,
    planning_decision: dict[str, Any] | None,
) -> EvidencePlan | None:
    """CP-off fallback: derive an evidence plan for dispatch without mutating pipeline state."""
    if intent_classification is not None:
        return plan_evidence(
            intent_classification,
            query_to_intent=query_to_intent,
            routed=routed,
            query_understanding=query_understanding,
            selected_use_case=selected_use_case,
        )
    use_case_id = None
    if selected_use_case is not None:
        use_case_id = getattr(selected_use_case, "use_case_id", None) or (
            selected_use_case.get("use_case_id") if isinstance(selected_use_case, dict) else None
        )
    catalog = build_catalog_display_evidence_plan(
        use_case_id=use_case_id,
        intent_classification=(
            intent_classification.model_dump()
            if isinstance(intent_classification, IntentClassification)
            else intent_classification
        ),
        query_to_intent=query_to_intent,
        query_understanding=query_understanding,
    )
    if catalog:
        return EvidencePlan.model_validate(catalog)
    if isinstance(planning_decision, dict) and planning_decision.get("path_type") == "rag_only":
        return EvidencePlan(
            answer_mode="rag_only",
            rag_phase="rag_only",
            needs_rag=True,
            needs_spl=False,
            needs_mcp=False,
            needs_mitre=False,
            spl_allowed=False,
            mcp_allowed=False,
            policy_context_required=False,
            policy_context_recommended=True,
            reasons=["cp_off_dispatch_rag_only_fallback"],
        )
    return None


def _intent_family(
    *,
    intent_classification: dict[str, Any] | IntentClassification | None,
    query_to_intent: dict[str, Any] | None,
) -> str | None:
    if isinstance(intent_classification, IntentClassification):
        return intent_classification.intent_family
    if isinstance(intent_classification, dict):
        return str(intent_classification.get("intent_family") or "") or None
    if isinstance(query_to_intent, dict):
        nested = query_to_intent.get("intent_classification")
        if isinstance(nested, dict):
            return str(nested.get("intent_family") or "") or None
    return None


def _resolve_request_mode(
    *,
    family: str | None,
    plan: EvidencePlan,
) -> RequestMode:
    if family == "knowledge_only" or family in {"policy_knowledge", "sop_or_playbook"}:
        return "knowledge"
    if family in {"mitre_mapping", "mitre_explanation"}:
        return "mitre_knowledge"
    if family == "cve_investigation":
        return "cve_review"
    if family == "spl_generation_only":
        if plan.answer_mode == "spl_utility_authoring":
            return "utility_spl"
        return "spl_authoring"
    if family == "spl_generation_and_run":
        return "spl_and_run"
    if family in {"hybrid_investigation_plus_policy", "hybrid_alert_review"}:
        return "hybrid"
    if family == "clarification_required" or plan.answer_mode == "clarification":
        return "clarification"
    if family in {"guided_investigation", "github_investigation"}:
        return "clarification"
    if plan.answer_mode == "rag_only":
        return "knowledge"
    if plan.answer_mode == "live_investigation":
        return "live_investigation"
    if plan.answer_mode == "hybrid":
        return "hybrid"
    if plan.answer_mode == "guided_investigation":
        return "clarification"
    return "clarification"


def _slots_missing_for_spl(handoff: SlotHandoffSummary) -> bool:
    slots = handoff.normalized_slots
    if not slots.get("index") and not slots.get("sourcetype"):
        return True
    return bool(handoff.unbound_constraints)


def _ambiguous_index_handoff(handoff: SlotHandoffSummary) -> bool:
    if handoff.validation_status.get("index") == "ambiguous":
        return True
    for constraint in handoff.unbound_constraints:
        if isinstance(constraint, dict) and constraint.get("slot") == "index":
            return True
    return False


def _needs_pre_spl_mcp_discovery(plan: EvidencePlan, handoff: SlotHandoffSummary) -> bool:
    """Discovery-need is separate from execution-need (spl_generation_only live-data case).

    ``live_data_request_mcp_needed_but_not_allowed`` marks execution denial, not an
    automatic pre-SPL discovery hop when index/sourcetype are already bound.
    """
    if not plan.needs_spl:
        return False
    if _slots_missing_for_spl(handoff):
        return True
    if _ambiguous_index_handoff(handoff) and settings.mcp_discovery_enabled:
        return True
    return False


def _needs_mcp_execution(plan: EvidencePlan) -> bool:
    return bool(plan.needs_mcp and plan.mcp_allowed)


def _spl_subgraph(
    *,
    plan: EvidencePlan,
    handoff: SlotHandoffSummary,
    force_pre_mcp: bool = False,
) -> list[PipelineStage]:
    include_pre = force_pre_mcp or _needs_pre_spl_mcp_discovery(plan, handoff)
    stages: list[PipelineStage] = []
    if include_pre:
        stages.append(PipelineStage.pre_spl_mcp_discovery)
    stages.extend(_SPL_CHAIN)
    if _needs_mcp_execution(plan):
        stages.append(PipelineStage.mcp_execution)
    return stages


def _build_llm_hops(
    *,
    request_mode: RequestMode,
    plan: EvidencePlan,
    handoff: SlotHandoffSummary,
    include_pre_mcp: bool,
) -> list[LlmHop]:
    hops: list[LlmHop] = []
    spl_modes = {
        "spl_authoring",
        "spl_and_run",
        "hybrid",
        "live_investigation",
    }
    if (
        settings.ai_soc_llm_spl_fallback_enabled
        and plan.needs_spl
        and plan.spl_allowed
        and request_mode in spl_modes
    ):
        hops.append(LlmHop.spl_plan_compiler)
    if (
        settings.mcp_discovery_enabled
        and include_pre_mcp
        and _ambiguous_index_handoff(handoff)
    ):
        hops.append(LlmHop.mcp_tool_planner)
    if (
        settings.ai_soc_llm_final_synthesis_enabled
        and settings.ai_soc_llm_live_synthesis_enabled
    ):
        hops.append(LlmHop.narration)
    return hops


def _build_stage_schedule(
    *,
    request_mode: RequestMode,
    plan: EvidencePlan,
    handoff: SlotHandoffSummary,
    family: str | None,
) -> list[PipelineStage]:
    if request_mode == "clarification":
        if plan.needs_rag:
            return [PipelineStage.rag_early]
        return []

    if request_mode == "knowledge":
        return [PipelineStage.rag_early] if plan.needs_rag else []

    if request_mode == "mitre_knowledge":
        stages: list[PipelineStage] = []
        if plan.needs_rag or family == "mitre_explanation":
            stages.append(PipelineStage.rag_early)
        stages.append(PipelineStage.mitre_finalize)
        return stages

    if request_mode == "cve_review":
        stages = []
        if plan.needs_rag:
            stages.append(PipelineStage.rag_early)
        stages.append(PipelineStage.cve_adapter)
        return stages

    if request_mode == "utility_spl":
        return list(_SPL_CHAIN)

    if request_mode == "spl_authoring":
        return _spl_subgraph(plan=plan, handoff=handoff)

    if request_mode == "spl_and_run":
        return _spl_subgraph(plan=plan, handoff=handoff, force_pre_mcp=True)

    if request_mode == "hybrid":
        stages: list[PipelineStage] = []
        if plan.needs_rag:
            stages.append(PipelineStage.rag_early)
        stages.extend(_spl_subgraph(plan=plan, handoff=handoff))
        if plan.needs_mitre:
            stages.append(PipelineStage.mitre_finalize)
        return stages

    if request_mode == "live_investigation":
        stages = _spl_subgraph(plan=plan, handoff=handoff)
        if plan.needs_mitre and PipelineStage.mitre_finalize not in stages:
            stages.append(PipelineStage.mitre_finalize)
        return stages

    return []


def build_pipeline_dispatch(
    *,
    evidence_plan: dict[str, Any] | EvidencePlan | None = None,
    route_contract: dict[str, Any] | None = None,
    query_to_intent: dict[str, Any] | None = None,
    intent_classification: dict[str, Any] | IntentClassification | None = None,
    query_understanding: Any = None,
    routed: dict[str, Any] | None = None,
    selected_use_case: Any = None,
    planning_decision: dict[str, Any] | None = None,
    **_: Any,
) -> PipelineDispatchState:
    """Build post-evidence dispatch authority (stage_schedule + llm_hops)."""
    plan = _coerce_evidence_plan(evidence_plan)
    if plan is None:
        plan = _synthetic_evidence_plan(
            intent_classification=intent_classification,
            query_to_intent=query_to_intent,
            routed=routed,
            query_understanding=query_understanding,
            selected_use_case=selected_use_case,
            planning_decision=planning_decision,
        )

    summary = None
    if plan is not None:
        summary = plan.normalized_slot_summary
    elif isinstance(evidence_plan, dict):
        summary = evidence_plan.get("normalized_slot_summary")
    handoff = slot_handoff_from_normalized_summary(summary if isinstance(summary, dict) else None)

    if plan is None:
        return PipelineDispatchState(
            decision=PipelineDispatchContract(
                request_mode="clarification",
                stage_schedule=[],
                llm_hops=[],
                slot_handoff=handoff,
                dispatch_reasons=["pipeline_dispatch_no_evidence_plan"],
            )
        )

    family = _intent_family(
        intent_classification=intent_classification,
        query_to_intent=query_to_intent,
    )
    request_mode = _resolve_request_mode(family=family, plan=plan)
    stage_schedule = _build_stage_schedule(
        request_mode=request_mode,
        plan=plan,
        handoff=handoff,
        family=family,
    )
    include_pre_mcp = PipelineStage.pre_spl_mcp_discovery in stage_schedule
    llm_hops = _build_llm_hops(
        request_mode=request_mode,
        plan=plan,
        handoff=handoff,
        include_pre_mcp=include_pre_mcp,
    )

    reasons: list[str] = [f"request_mode:{request_mode}"]
    if family:
        reasons.append(f"intent_family:{family}")
    if _needs_pre_spl_mcp_discovery(plan, handoff) and not _needs_mcp_execution(plan):
        reasons.append("pre_spl_mcp_discovery_without_execution")
    if plan.reasons:
        reasons.extend(plan.reasons[:4])

    return PipelineDispatchState(
        decision=PipelineDispatchContract(
            request_mode=request_mode,
            stage_schedule=stage_schedule,
            llm_hops=llm_hops,
            slot_handoff=handoff,
            dispatch_reasons=reasons,
        )
    )
