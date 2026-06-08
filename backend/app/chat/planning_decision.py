from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.contracts.planning_decision import BranchName, PlanningDecision
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.use_cases.content_enrichment import (
    load_curated_enrichment_context,
    resolve_use_case_activation,
)

_CROSSWALK_PATH = Path(__file__).resolve().parents[3] / "docs" / "evals" / "soc_capability_crosswalk.json"

ALLOWED_LIVE_SKILLS = frozenset(
    {"alert_summary", "spl_generation", "attack_discovery", "knowledge_recall"}
)

PATH_TYPE_BRANCH_MAP: dict[str, list[BranchName]] = {
    "rag_only": ["rag"],
    "spl_review": ["spl", "evidence", "severity"],
    "spl_review_plus_rag": ["spl", "rag", "evidence", "severity"],
    "hybrid_investigation": ["spl", "rag", "evidence", "mitre", "severity", "hil"],
    "mitre_context_required": ["hil", "clarification"],
    "generic_soc_guidance": ["rag", "evidence"],
    "unsafe_blocked": ["unsafe_blocked", "hil", "block"],
    "clarification_required": ["hil", "clarification"],
    "legacy_or_unsupported": ["rag"],
}


def plan_path_and_tools(
    *,
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    routed: dict[str, Any] | None,
    query_understanding: Any = None,
    selected_use_case: Any = None,
    llm_intent_advisory: dict[str, Any] | LLMIntentAdvisory | None = None,
) -> PlanningDecision:
    """Deterministic planner path/tool selection (Phase 3).

    Default-off via ``ai_soc_planner_path_selection_enabled``. When disabled, emits
    trace-only metadata identical to Phase 1 behavior. When enabled, uses the
    explicit path/branch mapping table without enabling execution.
    """
    advisory = _coerce_advisory(llm_intent_advisory)
    decision = _build_planning_decision(
        intent_classification=intent_classification,
        evidence_plan=evidence_plan,
        routed=routed,
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
        llm_intent_advisory=advisory,
        planner_path_selection_enabled=settings.ai_soc_planner_path_selection_enabled,
    )
    if not settings.ai_soc_planner_path_selection_enabled:
        return decision.model_copy(
            update={
                "authority_source": "deterministic_trace_only",
                "planner_path_selection_enabled": False,
                "precedence_applied": _trace_only_precedence(decision),
            }
        )
    return decision.model_copy(
        update={
            "authority_source": "deterministic_planner_path_selection",
            "planner_path_selection_enabled": True,
            "branches": _planner_branches(decision.path_type, decision.branches),
            "precedence_applied": _planner_precedence(decision, advisory),
        }
    )


def compute_planning_decision_trace_only(
    *,
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    routed: dict[str, Any] | None,
    query_understanding: Any = None,
    selected_use_case: Any = None,
) -> PlanningDecision:
    """Phase 1 compatibility wrapper (trace-only, flag-independent)."""
    return plan_path_and_tools(
        intent_classification=intent_classification,
        evidence_plan=evidence_plan,
        routed=routed,
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
        llm_intent_advisory=None,
    ).model_copy(
        update={
            "authority_source": "deterministic_trace_only",
            "planner_path_selection_enabled": False,
        }
    )


def _build_planning_decision(
    *,
    intent_classification: dict[str, Any] | None,
    evidence_plan: dict[str, Any] | None,
    routed: dict[str, Any] | None,
    query_understanding: Any,
    selected_use_case: Any,
    llm_intent_advisory: LLMIntentAdvisory | None,
    planner_path_selection_enabled: bool,
) -> PlanningDecision:
    intent = intent_classification if isinstance(intent_classification, dict) else {}
    plan = evidence_plan if isinstance(evidence_plan, dict) else {}
    routed_payload = routed if isinstance(routed, dict) else {}

    use_case_id = _use_case_id(selected_use_case, query_understanding, routed_payload, llm_intent_advisory)
    question_ref = _question_ref(query_understanding, routed_payload, llm_intent_advisory)
    crosswalk = _crosswalk_status(use_case_id=use_case_id, question_ref=question_ref)

    path_type = _resolve_path_type(intent, plan, crosswalk, llm_intent_advisory, query_understanding)
    branches = _branches_for(path_type, plan)
    selected_tools = _selected_tools(path_type, plan, routed_payload)
    blocked_tools = _blocked_tools(path_type, plan)
    live_skill = _live_execution_skill(routed_payload)
    activation = resolve_use_case_activation(use_case_id)
    curated_context = load_curated_enrichment_context(use_case_id) if planner_path_selection_enabled else None

    runtime_status = crosswalk.get("runtime_support_status")
    planner_runtime_activation_allowed = (
        planner_path_selection_enabled
        and activation.planner_runtime_activation_allowed
        and runtime_status == "runtime_active"
        and path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"}
    )

    return PlanningDecision(
        path_type=path_type,
        branches=branches,
        use_case_id=use_case_id,
        question_ref=question_ref,
        runtime_support_status=runtime_status,
        crosswalk_lookup_status=crosswalk.get("lookup_status", "not_available"),
        live_execution_skill=live_skill,
        planning_or_analytic_skill=_planning_skill(query_understanding),
        activation_lifecycle_stage=activation.activation_lifecycle_stage,
        activation_decision=activation.model_dump(),
        curated_enrichment_context=(
            {
                "use_case_id": curated_context.use_case_id,
                "activation_lifecycle_stage": curated_context.activation_lifecycle_stage,
                "runtime_support_status": curated_context.runtime_support_status,
                "spl_template_status": curated_context.spl_template_status,
                "allowed_spl_templates": curated_context.allowed_spl_templates,
                "rag_doc_ids": curated_context.rag_doc_ids,
                "mitre_candidates": curated_context.mitre_candidates,
                "provenance_ref_count": len(curated_context.provenance_ref_ids),
            }
            if curated_context is not None
            else None
        ),
        selected_tools=selected_tools,
        blocked_tools=blocked_tools,
        clarification_needed=bool(intent.get("requires_clarification")) or path_type in {
            "clarification_required",
            "mitre_context_required",
        },
        hil_required=bool(intent.get("requires_hil")) or path_type in {
            "unsafe_blocked",
            "clarification_required",
            "mitre_context_required",
        },
        reason=_reason(path_type, intent, plan),
        authority_source=(
            "deterministic_planner_path_selection"
            if planner_path_selection_enabled
            else "deterministic_trace_only"
        ),
        precedence_applied=_planner_precedence(
            PlanningDecision(
                path_type=path_type,
                branches=branches,
                use_case_id=use_case_id,
                question_ref=question_ref,
                runtime_support_status=runtime_status,
                crosswalk_lookup_status=crosswalk.get("lookup_status", "not_available"),
                live_execution_skill=live_skill,
                planning_or_analytic_skill=_planning_skill(query_understanding),
                activation_lifecycle_stage=activation.activation_lifecycle_stage,
                activation_decision=activation.model_dump(),
                selected_tools=selected_tools,
                blocked_tools=blocked_tools,
                clarification_needed=bool(intent.get("requires_clarification")),
                hil_required=bool(intent.get("requires_hil")),
                reason=_reason(path_type, intent, plan),
            ),
            llm_intent_advisory,
        )
        if planner_path_selection_enabled
        else _trace_only_precedence(
            PlanningDecision(
                path_type=path_type,
                branches=branches,
                reason=_reason(path_type, intent, plan),
                runtime_support_status=runtime_status,
            )
        ),
        execution_enabled=False,
        planner_path_selection_enabled=planner_path_selection_enabled,
        planner_runtime_activation_allowed=planner_runtime_activation_allowed,
    )


def _resolve_path_type(
    intent: dict[str, Any],
    plan: dict[str, Any],
    crosswalk: dict[str, str | None],
    advisory: LLMIntentAdvisory | None,
    query_understanding: Any = None,
) -> str:
    family = str(intent.get("intent_family") or "")
    runtime_status = crosswalk.get("runtime_support_status")

    if _unsafe_containment_detected(intent, query_understanding):
        return "unsafe_blocked"

    if family == "clarification_required":
        action_mode = str(intent.get("action_mode") or "")
        if action_mode == "recommend_only" and bool(intent.get("requires_hil")):
            return "unsafe_blocked"
        return "clarification_required"

    if _advisory_blocked(advisory):
        return "unsafe_blocked"

    if family == "mitre_mapping" and bool(intent.get("requires_clarification")):
        return "mitre_context_required"

    if plan.get("answer_mode") == "rag_only":
        return "rag_only"

    if family == "knowledge_only":
        return "generic_soc_guidance"

    if family in {"policy_knowledge", "sop_or_playbook"}:
        return "rag_only"

    if plan.get("needs_spl") and plan.get("needs_rag"):
        return "spl_review_plus_rag"

    if family == "hybrid_alert_review" or (
        plan.get("needs_spl") and plan.get("needs_mitre") and not bool(intent.get("requires_clarification"))
    ):
        return "hybrid_investigation"

    if plan.get("needs_spl"):
        return "spl_review"

    if plan.get("needs_mitre"):
        return "mitre_context_required" if bool(intent.get("requires_clarification")) else "hybrid_investigation"

    if runtime_status in {"metadata_only", "planned", "unsupported"} and not plan.get("needs_rag"):
        return "generic_soc_guidance"

    if family == "clarification_required" or bool(intent.get("requires_clarification")):
        return "clarification_required"

    return "generic_soc_guidance"


def _branches_for(path_type: str, plan: dict[str, Any]) -> list[BranchName]:
    mapped = list(PATH_TYPE_BRANCH_MAP.get(path_type, []))
    if mapped:
        return mapped
    branches: list[BranchName] = []
    if plan.get("needs_spl") or path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"}:
        branches.extend(["spl", "evidence"])
    if plan.get("needs_rag") or path_type in {"rag_only", "generic_soc_guidance", "spl_review_plus_rag"}:
        branches.append("rag")
    if plan.get("needs_mitre") or path_type == "hybrid_investigation":
        branches.append("mitre")
    if path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"}:
        branches.append("severity")
    if bool(plan.get("requires_hil")):
        branches.append("hil")
    return list(dict.fromkeys(branches))


def _planner_branches(path_type: str, fallback: list[BranchName]) -> list[BranchName]:
    mapped = PATH_TYPE_BRANCH_MAP.get(path_type)
    if mapped:
        return list(mapped)
    return list(fallback)


def _selected_tools(path_type: str, plan: dict[str, Any], routed: dict[str, Any]) -> list[str]:
    tools = [str(item) for item in routed.get("tool_plan") or []]
    if path_type == "rag_only":
        return [tool for tool in tools if "knowledge" in tool or "rag" in tool] or ["retrieve_approved_knowledge"]
    if path_type in {"spl_review", "spl_review_plus_rag", "hybrid_investigation"} and plan.get("needs_spl"):
        selected = [tool for tool in tools if "spl" in tool]
        return selected or ["generate_spl", "validate_spl"]
    if path_type == "generic_soc_guidance":
        return [tool for tool in tools if "knowledge" in tool or "rag" in tool]
    return tools


def _blocked_tools(path_type: str, plan: dict[str, Any]) -> list[str]:
    blocked: list[str] = []
    if not bool(plan.get("needs_spl")) or path_type in {
        "rag_only",
        "generic_soc_guidance",
        "mitre_context_required",
        "clarification_required",
        "unsafe_blocked",
    }:
        blocked.append("spl")
    if not bool(plan.get("needs_mcp")):
        blocked.append("mcp")
    blocked.extend(["candidate_spl_execution", "mcp_execution"])
    if path_type in {"unsafe_blocked", "clarification_required", "mitre_context_required", "rag_only"}:
        blocked.extend(["spl_execution", "mcp_execution"])
    return list(dict.fromkeys(blocked))


def _live_execution_skill(routed: dict[str, Any]) -> str | None:
    skill = routed.get("skill")
    if isinstance(skill, str) and skill in ALLOWED_LIVE_SKILLS:
        return skill
    return None


def _unsafe_containment_detected(intent: dict[str, Any], query_understanding: Any) -> bool:
    if str(intent.get("primary_intent") or "") == "human_review" and bool(intent.get("requires_hil")):
        return True
    raw_query = getattr(query_understanding, "raw_query", None)
    if isinstance(raw_query, str) and raw_query.strip():
        return bool(extract_query_signals(raw_query).get("block_or_contain"))
    return False


def _advisory_blocked(advisory: LLMIntentAdvisory | None) -> bool:
    if advisory is None:
        return False
    if advisory.adjudication_status == "rejected" and advisory.path_type_candidate == "unsafe_blocked":
        return True
    return False


def _trace_only_precedence(decision: PlanningDecision) -> list[str]:
    values = ["deterministic_intent_over_llm", "planner_trace_only_no_behavior_change"]
    if decision.path_type in {"unsafe_blocked", "clarification_required", "mitre_context_required"}:
        values.append("safety_or_context_gate")
    if decision.runtime_support_status:
        values.append("crosswalk_runtime_support_status_read_only")
    return values


def _planner_precedence(decision: PlanningDecision, advisory: LLMIntentAdvisory | None) -> list[str]:
    values = [
        "unsafe_or_blocked_beats_all",
        "clarification_beats_investigation",
        "deterministic_registry_over_llm_advisory",
        "crosswalk_metadata_not_runtime_activation",
        "planner_schedules_branches_no_execution",
    ]
    if decision.path_type in {"unsafe_blocked", "clarification_required", "mitre_context_required"}:
        values.append("safety_or_context_gate")
    if decision.runtime_support_status:
        values.append("crosswalk_runtime_support_status_read_only")
    if advisory is not None and advisory.adjudication_status not in {None, "skipped"}:
        values.append("llm_advisory_normalized_non_authoritative")
    if decision.planner_runtime_activation_allowed:
        values.append("runtime_activation_crosswalk_gate_passed")
    else:
        values.append("runtime_activation_disallowed")
    return values


def _reason(path_type: str, intent: dict[str, Any], plan: dict[str, Any]) -> str:
    reasons = [str(item) for item in plan.get("reasons") or []]
    if reasons:
        return "; ".join(reasons)
    if intent.get("reason"):
        return str(intent["reason"])
    return f"planner selected path_type={path_type}"


def _use_case_id(
    selected_use_case: Any,
    query_understanding: Any,
    routed: dict[str, Any],
    advisory: LLMIntentAdvisory | None,
) -> str | None:
    value = getattr(selected_use_case, "use_case_id", None)
    if isinstance(value, str) and value:
        return value
    mapped = getattr(query_understanding, "mapped_use_case_ids", None)
    if isinstance(mapped, list) and mapped:
        return str(mapped[0])
    provenance = routed.get("routing_provenance")
    if isinstance(provenance, dict):
        mapped = provenance.get("mapped_use_case_ids")
        if isinstance(mapped, list) and mapped:
            return str(mapped[0])
    if advisory and advisory.adjudication_status == "accepted" and advisory.use_case_id_candidate:
        return advisory.use_case_id_candidate
    return None


def _question_ref(
    query_understanding: Any,
    routed: dict[str, Any],
    advisory: LLMIntentAdvisory | None,
) -> str | None:
    value = getattr(query_understanding, "mapped_question_ref", None)
    if isinstance(value, str) and value:
        return value
    provenance = routed.get("routing_provenance")
    if isinstance(provenance, dict):
        value = provenance.get("mapped_question_ref")
        if isinstance(value, str) and value:
            return value
    if advisory and advisory.adjudication_status == "accepted" and advisory.question_ref_candidate:
        return advisory.question_ref_candidate
    return None


def _planning_skill(query_understanding: Any) -> str | None:
    value = getattr(query_understanding, "mapped_operation_type", None)
    return value if isinstance(value, str) and value else None


def _crosswalk_status(*, use_case_id: str | None, question_ref: str | None) -> dict[str, str | None]:
    crosswalk = _load_crosswalk()
    if crosswalk is None:
        return {"lookup_status": "crosswalk_missing", "runtime_support_status": None}

    for row in crosswalk.get("use_case_rows") or []:
        if isinstance(row, dict) and use_case_id and row.get("use_case_id") == use_case_id:
            return {
                "lookup_status": "matched_use_case",
                "runtime_support_status": _string_or_none(row.get("runtime_support_status")),
            }
    for row in crosswalk.get("question_rows") or []:
        if isinstance(row, dict) and question_ref and row.get("question_id") == question_ref:
            return {
                "lookup_status": "matched_question",
                "runtime_support_status": _string_or_none(row.get("runtime_support_status")),
            }
    return {"lookup_status": "not_found", "runtime_support_status": None}


def _coerce_advisory(
    advisory: dict[str, Any] | LLMIntentAdvisory | None,
) -> LLMIntentAdvisory | None:
    if advisory is None:
        return None
    if isinstance(advisory, LLMIntentAdvisory):
        return advisory
    if isinstance(advisory, dict):
        try:
            return LLMIntentAdvisory.model_validate(advisory)
        except Exception:
            return None
    return None


@lru_cache(maxsize=1)
def _load_crosswalk() -> dict[str, Any] | None:
    try:
        payload = json.loads(_CROSSWALK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
