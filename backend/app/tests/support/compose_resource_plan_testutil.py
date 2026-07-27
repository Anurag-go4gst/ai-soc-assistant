"""Test-only ResourcePlan composition for legacy ``plan_evidence`` callers.

Production runtime must compose/commit only through ``plan_evidence_from_canonical``.
"""

from __future__ import annotations

from typing import Any

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_classification import IntentClassification
from app.chat.evidence_planner import plan_evidence
from app.config import settings
from app.planner.composer import compose_resource_plan
from app.planner.resource_plan_authority import assert_resource_plan_authority, is_test_compose_allowed


def attach_resource_plan_for_tests(
    plan: EvidencePlan,
    *,
    intent: IntentClassification,
    use_case_id: str | None,
    query_understanding: Any,
    routed_skill: str | None = None,
) -> EvidencePlan:
    """Compose a shadow ResourcePlan under explicit ``TEST_AUTHORITY`` only."""
    assert_resource_plan_authority(operation="attach_resource_plan_for_tests")
    if not is_test_compose_allowed():
        return plan

    if (
        plan.answer_mode == "guided_investigation"
        and settings.ai_soc_guided_hybrid_investigation_enabled
    ):
        return plan

    match_path = getattr(query_understanding, "deterministic_match_path", None)
    try:
        composed = compose_resource_plan(
            plan,
            intent_family=intent.intent_family,
            use_case_id=use_case_id or plan.use_case_id,
            match_path=match_path,
            skill_id=routed_skill,
        )
    except Exception:
        return plan
    composed_payload = composed.model_dump()
    if plan.evidence_legs:
        provenance = dict(composed_payload.get("provenance") or {})
        provenance.update(
            {
                "evidence_legs": list(plan.evidence_legs),
                "correlation": dict(plan.correlation or {}),
            }
        )
        composed_payload["provenance"] = provenance
    return plan.model_copy(update={"resource_plan": composed_payload})


def plan_evidence_with_resource_plan(
    intent: IntentClassification,
    query_to_intent: dict[str, Any] | None = None,
    *,
    query_understanding: Any = None,
    routed: dict[str, Any] | None = None,
    user_query: str | None = None,
    selected_use_case_id: str | None = None,
) -> EvidencePlan:
    """Legacy test helper: ``plan_evidence`` + composed ``resource_plan`` shadow."""
    plan = plan_evidence(
        intent,
        query_to_intent,
        query_understanding=query_understanding,
        routed=routed,
        user_query=user_query,
        selected_use_case_id=selected_use_case_id,
    )
    use_case_id = selected_use_case_id or plan.use_case_id
    if use_case_id is None and query_understanding is not None:
        ids = list(getattr(query_understanding, "mapped_use_case_ids", None) or [])
        use_case_id = ids[0] if ids else None
    return attach_resource_plan_for_tests(
        plan,
        intent=intent,
        use_case_id=use_case_id,
        query_understanding=query_understanding,
        routed_skill=str((routed or {}).get("skill") or "") or None,
    )
