"""Detect investigation-shaped Final RQCs for the plan-before-ResourcePlan gate (P0).

Investigation-shaped turns must not commit a ResourcePlan until an approved
investigation envelope exists (P4). Non-investigation catalogue work (pure
knowledge_recall / SOP citation with no live-search need) keeps today's one-pass
ResourcePlan path.
"""

from __future__ import annotations

from typing import Any

from app.chat.skill_intent_compatibility import CAPABILITY_MCP, CAPABILITY_SPL

#: Intent families that own multi-step / live investigation work after Final RQC.
INVESTIGATION_INTENT_FAMILIES: frozenset[str] = frozenset(
    {
        "guided_investigation",
        "live_investigation",
        "hybrid_investigation",
        "hybrid_investigation_plus_policy",
        "github_investigation",
        "cve_investigation",
    }
)

#: Skills that own investigation composition (never one-pass knowledge dump).
INVESTIGATION_OWNER_SKILLS: frozenset[str] = frozenset(
    {
        "guided_investigation",
    }
)

#: Answer goals that indicate live investigation / hunt work.
INVESTIGATION_ANSWER_GOALS: frozenset[str] = frozenset(
    {
        "live_results",
        "analyst_action_guidance",
        "procedural_steps",
    }
)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump(mode="json")
        return payload if isinstance(payload, dict) else {}
    return {}


def _capability_set(raw: Any) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, frozenset):
        return frozenset(str(item) for item in raw)
    if isinstance(raw, (set, list, tuple)):
        return frozenset(str(item) for item in raw)
    return frozenset()


def is_investigation_shaped_final_rqc(
    *,
    resolved_query_contract: dict[str, Any] | Any | None,
    primary_skill: str | None = None,
    intent_classification: dict[str, Any] | None = None,
    query_understanding: Any | None = None,
) -> bool:
    """True when the Final RQC (plus bound owner) must wait for investigation plan approval.

    Conservative union of owner skill, investigation intent family, live-search
    capability needs, and the parser's ``soc_investigation_shaped`` signal.
    Pure ``knowledge_recall`` without those signals returns False.
    """
    rqc = _as_dict(resolved_query_contract)
    intent = intent_classification if isinstance(intent_classification, dict) else {}
    skill = str(primary_skill or "").strip()
    if skill in INVESTIGATION_OWNER_SKILLS:
        return True

    family = str(
        rqc.get("intent_family")
        or intent.get("intent_family")
        or intent.get("primary_intent")
        or ""
    ).strip()
    if family in INVESTIGATION_INTENT_FAMILIES:
        return True

    answer_goal = str(rqc.get("answer_goal") or "").strip()
    required = _capability_set(rqc.get("required_capabilities"))
    needs_live_search = bool(required & {CAPABILITY_SPL, CAPABILITY_MCP})

    qu = query_understanding
    soc_shaped = bool(getattr(qu, "soc_investigation_shaped", False)) if qu is not None else False
    if isinstance(qu, dict):
        soc_shaped = bool(qu.get("soc_investigation_shaped"))

    if soc_shaped and (needs_live_search or answer_goal in INVESTIGATION_ANSWER_GOALS):
        return True

    if needs_live_search and answer_goal in INVESTIGATION_ANSWER_GOALS and family not in {
        "knowledge_recall",
        "reference_knowledge",
        "policy_citation",
    }:
        # Catalogue hunt / live-posture rows that already require SPL/MCP for an
        # investigation goal share the wait-for-plan lifecycle (T1–T3 convergence).
        return True

    return False
