"""Final evidence planner (Planner 2) — sole ResourcePlan authority from canonical input."""

from __future__ import annotations

import uuid
from typing import Any

from app.chat.canonical_answer_mode_policy import resolve_canonical_answer_mode
from app.chat.canonical_handoff_store import commit_resource_plan, get_committed_resource_plan
from app.chat.contracts.canonical_planning_input import CanonicalPlanningInput
from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.evidence_planner import plan_evidence
from app.chat.planning_telemetry import (
    emit_handoff_persisted,
    emit_planner_handoff_consumed,
    emit_planner_handoff_created,
    emit_resource_plan_commit_reused,
    emit_resource_plan_created,
)

def _evidence_plan_from_committed(committed_evidence: dict[str, Any]) -> EvidencePlan:
    return EvidencePlan.model_validate(committed_evidence)


def plan_evidence_from_canonical(
    canonical: CanonicalPlanningInput,
    *,
    state: dict[str, Any] | None = None,
    intent_classification: dict[str, Any] | None = None,
    query_to_intent: dict[str, Any] | None = None,
    query_understanding: Any = None,
    routed: dict[str, Any] | None = None,
    selected_use_case: Any = None,
    user_query: str | None = None,
) -> tuple[EvidencePlan, list[str], list[str]]:
    """Create EvidencePlan + ResourcePlan from canonical input only."""
    handoff_id = canonical.trace.handoff_id
    handoff_version = canonical.trace.handoff_version
    answer_mode_decision = resolve_canonical_answer_mode(canonical)

    existing = get_committed_resource_plan(handoff_id, handoff_version)
    if existing is not None:
        resource_plan_id, resource_plan, committed_evidence = existing
        if committed_evidence:
            plan = _evidence_plan_from_committed(committed_evidence)
            consumed = [
                "routing.intent_family",
                "routing.answer_goal",
                "routing.processing_lane",
                "idempotent_replay",
            ]
            if state is not None:
                emit_resource_plan_commit_reused(
                    state,
                    resource_plan_id=resource_plan_id,
                    handoff_id=handoff_id,
                    handoff_version=handoff_version,
                )
            return plan, consumed, ["provenance.prompt_template_id"]

    if state is not None:
        emit_planner_handoff_created(state, canonical)

    if isinstance(intent_classification, dict) and intent_classification.get("intent_family"):
        intent_payload = dict(intent_classification)
    else:
        wire_goal = canonical.routing.answer_goal
        if wire_goal == "reference_explanation":
            wire_goal_list = ["reference_lookup"]
        elif wire_goal == "clarification":
            wire_goal_list = ["clarification"]
        else:
            wire_goal_list = [wire_goal] if wire_goal in {
                "live_results",
                "analyst_action_guidance",
                "policy_citation",
                "spl_artifact",
                "mitre_mapping",
                "mitre_explanation",
                "severity_assessment",
                "procedural_steps",
                "reference_lookup",
            } else ["live_results"]
        intent_payload = {
            "intent_family": canonical.routing.intent_family,
            "primary_intent": canonical.routing.primary_skill,
            "query_type": "ask_for_explanation",
            "answer_goal": wire_goal_list,
            "confidence": canonical.query_understanding.confidence or 0.8,
            "confidence_band": "high",
            "requires_clarification": canonical.guided_resolution.clarification_required,
            "requires_hil": canonical.governance.approval_required,
            "action_mode": "recommend_only",
            "reason": canonical.routing.route_reason or "canonical_planning_input",
            "answer_goal_primary": canonical.routing.answer_goal,
        }

    plan = plan_evidence(
        intent_payload,
        query_to_intent=query_to_intent,
        routed=routed,
        query_understanding=query_understanding,
        selected_use_case=selected_use_case,
        user_query=user_query or canonical.message.content_reference,
    )

    target_mode = answer_mode_decision.answer_mode
    if target_mode is not None and plan.answer_mode != target_mode:
        plan = plan.model_copy(update={"answer_mode": target_mode})  # type: ignore[arg-type]

    resource_plan_id = f"rp:{uuid.uuid4().hex[:12]}"
    from app.planner.composer import compose_resource_plan
    from app.planner.resource_plan_authority import resource_plan_authority

    with resource_plan_authority():
        composed = compose_resource_plan(
            plan,
            intent_family=canonical.routing.intent_family,
            use_case_id=canonical.routing.use_case_id,
            match_path=canonical.routing.match_path,
            skill_id=canonical.routing.primary_skill,
        )
    provenance = dict(composed.provenance or {})
    provenance["resource_plan_id"] = resource_plan_id
    provenance["handoff_id"] = handoff_id
    provenance["handoff_version"] = handoff_version
    provenance["processing_lane"] = canonical.routing.processing_lane
    provenance["answer_goal"] = canonical.routing.answer_goal
    provenance["committed"] = True
    composed_payload = composed.model_copy(update={"provenance": provenance}).model_dump()
    plan = plan.model_copy(update={"resource_plan": composed_payload})
    evidence_payload = plan.model_dump()

    commit_resource_plan(
        handoff_id=handoff_id,
        handoff_version=handoff_version,
        resource_plan_id=resource_plan_id,
        resource_plan=composed_payload,
        evidence_plan=evidence_payload,
    )

    if state is not None:
        emit_handoff_persisted(
            state,
            handoff_id=handoff_id,
            handoff_version=handoff_version,
            handoff_status="plan_committed",
            trace_id=canonical.trace.trace_id,
            session_id=None,
        )

    consumed_fields = [
        "routing.intent_family",
        "routing.answer_goal",
        "routing.processing_lane",
        "routing.primary_skill",
        "routing.use_case_id",
        "detail_state.missing_fields",
        "governance",
        "planning_goal.evidence_requirements",
    ]
    ignored_fields = ["provenance.prompt_template_id"]
    if state is not None:
        emit_planner_handoff_consumed(
            state,
            canonical,
            consumed_fields=consumed_fields,
            ignored_fields=ignored_fields,
            resource_plan_id=resource_plan_id,
        )
        emit_resource_plan_created(state, canonical, resource_plan_id=resource_plan_id)
    return plan, consumed_fields, ignored_fields
