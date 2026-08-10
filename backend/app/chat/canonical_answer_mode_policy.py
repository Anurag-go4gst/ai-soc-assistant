"""Ordered canonical answer-mode policy.

The rule table is intentionally data-visible: reviewers and tests can inspect both
precedence and the routing dimensions each rule considers.  Matchers remain named
functions because several rules combine dimensions with different boolean semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from app.chat.contracts.canonical_planning_input import CanonicalPlanningInput
from app.chat.contracts.evidence_plan import AnswerMode

PolicyDimension = Literal[
    "processing_lane",
    "answer_goal",
    "intent_family",
    "clarification_required",
]


class CanonicalAnswerModePolicyError(Exception):
    """Canonical routing dimensions contradict the governed answer-mode policy."""

    def __init__(
        self,
        *,
        reason: str,
        detail: str,
        category: str = "answer_mode_policy",
    ) -> None:
        self.reason = reason
        self.detail = detail
        self.category = category
        super().__init__(reason)


@dataclass(frozen=True)
class CanonicalAnswerModeDecision:
    rule_name: str
    answer_mode: AnswerMode | None


@dataclass(frozen=True)
class CanonicalAnswerModeRule:
    name: str
    dimensions: tuple[PolicyDimension, ...]
    answer_mode: AnswerMode | None
    matcher: Callable[[CanonicalPlanningInput], bool]
    error_reason: str | None = None


def _is_clarification(canonical: CanonicalPlanningInput) -> bool:
    return (
        canonical.guided_resolution.clarification_required
        or canonical.routing.intent_family == "clarification_required"
    )


def _is_alert_summary_spl_contradiction(canonical: CanonicalPlanningInput) -> bool:
    return canonical.routing.intent_family == "alert_summary" and canonical.routing.answer_goal in {
        "spl_generation",
        "spl_artifact",
    }


def _is_reference_or_knowledge(canonical: CanonicalPlanningInput) -> bool:
    return canonical.routing.processing_lane == "knowledge_short_circuit" or canonical.routing.intent_family in {
        "reference_knowledge",
        "knowledge_only",
    }


def _is_spl(canonical: CanonicalPlanningInput) -> bool:
    return canonical.routing.answer_goal in {"spl_generation", "spl_artifact"} or canonical.routing.intent_family in {
        "spl_generation_only",
        "spl_generation_and_run",
    }


def _is_guided(canonical: CanonicalPlanningInput) -> bool:
    return (
        canonical.routing.answer_goal == "guided_investigation"
        or canonical.routing.intent_family == "guided_investigation"
    )


def _is_alert_summary(canonical: CanonicalPlanningInput) -> bool:
    return canonical.routing.intent_family == "alert_summary"


def _planner_decides(_canonical: CanonicalPlanningInput) -> bool:
    return True


CANONICAL_ANSWER_MODE_POLICY: tuple[CanonicalAnswerModeRule, ...] = (
    CanonicalAnswerModeRule(
        name="clarification",
        dimensions=("clarification_required", "intent_family"),
        answer_mode="clarification",
        matcher=_is_clarification,
    ),
    CanonicalAnswerModeRule(
        name="alert_summary_spl_contradiction",
        dimensions=("answer_goal", "intent_family"),
        answer_mode=None,
        matcher=_is_alert_summary_spl_contradiction,
        error_reason="contradictory_alert_summary_spl_goal",
    ),
    CanonicalAnswerModeRule(
        name="reference_or_knowledge",
        dimensions=("processing_lane", "intent_family"),
        answer_mode="rag_only",
        matcher=_is_reference_or_knowledge,
    ),
    CanonicalAnswerModeRule(
        name="spl",
        dimensions=("answer_goal", "intent_family"),
        answer_mode="live_investigation",
        matcher=_is_spl,
    ),
    CanonicalAnswerModeRule(
        name="guided",
        dimensions=("answer_goal", "intent_family"),
        answer_mode="guided_investigation",
        matcher=_is_guided,
    ),
    CanonicalAnswerModeRule(
        name="alert_summary",
        dimensions=("intent_family",),
        answer_mode="rag_only",
        matcher=_is_alert_summary,
    ),
    CanonicalAnswerModeRule(
        name="planner_decides",
        dimensions=("processing_lane", "answer_goal", "intent_family"),
        answer_mode=None,
        matcher=_planner_decides,
    ),
)


def resolve_canonical_answer_mode(
    canonical: CanonicalPlanningInput,
) -> CanonicalAnswerModeDecision:
    """Resolve the first matching rule or raise a typed policy contradiction."""
    for rule in CANONICAL_ANSWER_MODE_POLICY:
        if not rule.matcher(canonical):
            continue
        if rule.error_reason:
            raise CanonicalAnswerModePolicyError(
                reason=rule.error_reason,
                detail=(
                    f"processing_lane={canonical.routing.processing_lane};"
                    f"answer_goal={canonical.routing.answer_goal};"
                    f"intent_family={canonical.routing.intent_family}"
                ),
            )
        return CanonicalAnswerModeDecision(
            rule_name=rule.name,
            answer_mode=rule.answer_mode,
        )
    raise AssertionError("canonical answer-mode policy must end with planner_decides")


__all__ = [
    "CANONICAL_ANSWER_MODE_POLICY",
    "CanonicalAnswerModeDecision",
    "CanonicalAnswerModePolicyError",
    "CanonicalAnswerModeRule",
    "resolve_canonical_answer_mode",
]
