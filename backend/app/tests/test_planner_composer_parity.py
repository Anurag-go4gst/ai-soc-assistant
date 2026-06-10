"""T0.3 — composed ResourcePlan projects exactly the legacy needs_* booleans.

Drives plan_evidence directly (no full pipeline) for every sentinel question
and asserts boolean parity plus composition invariants.
"""

from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.evals.sentinel_eval import load_sentinel_rows
from app.planner.resource_plan import ResourcePlan, project_booleans
from app.planner.resource_registry import load_resource_registry
from app.query_understanding.parser import understand_query

_BOOL_KEYS = ("needs_rag", "needs_spl", "needs_mcp", "needs_mitre")


def _plan_for(question: str):
    understanding = understand_query(question)
    result = build_query_to_intent(query=question, query_understanding=understanding)
    return plan_evidence(
        result.intent_classification,
        query_to_intent=result.model_dump(),
        query_understanding=understanding,
    )


@pytest.mark.parametrize("row", load_sentinel_rows(), ids=lambda row: row["key"])
def test_sentinel_boolean_parity(row) -> None:
    plan = _plan_for(row["question"])
    assert plan.resource_plan is not None, "composer must attach a plan"
    composed = ResourcePlan.model_validate(plan.resource_plan)
    projected = project_booleans(composed)
    legacy = {key: getattr(plan, key) for key in _BOOL_KEYS}
    assert projected == legacy, f"{row['key']}: {projected} != {legacy}"


@pytest.mark.parametrize("row", load_sentinel_rows(), ids=lambda row: row["key"])
def test_sentinel_steps_reference_registry_resources(row) -> None:
    registry = load_resource_registry()
    plan = _plan_for(row["question"])
    composed = ResourcePlan.model_validate(plan.resource_plan)
    for step in composed.steps:
        descriptor = registry.by_id(step.resource_id)
        assert descriptor is not None, step.resource_id
        assert descriptor.availability != "blocked", step.resource_id
    assert composed.plan_source == "deterministic"


def test_clarification_plan_has_no_resource_steps() -> None:
    plan = _plan_for("What happened for this specific notable event?")
    composed = ResourcePlan.model_validate(plan.resource_plan)
    assert plan.answer_mode == "clarification"
    assert composed.steps == []


def test_active_template_step_carries_lab_draft_fallback() -> None:
    plan = _plan_for("Which accounts had a successful login after repeated failures?")
    composed = ResourcePlan.model_validate(plan.resource_plan)
    spl_steps = [step for step in composed.steps if step.purpose == "spl_artifact"]
    assert spl_steps, "expected an SPL step"
    step = spl_steps[0]
    if step.resource_id.startswith("spl_template_family:"):
        assert step.on_unavailable, "active template must carry a lab-draft fallback"
        assert step.on_unavailable.startswith("spl_lab_draft_family:")
    assert "execution_eligible_false" in step.policy_checks
