"""Plan 3 B2 — routed-skill × intent-family capability compatibility.

Pins the deterministic contract that reconciles the two planning surfaces, and the
router-reachable contradiction that exposed the need for it: a hunt-shaped OT query
routes to `knowledge_recall` (whose contract forbids SPL and MCP) while the intent
classifier resolves `spl_generation_only`.

Failing-first target: before B2, Phase Policy emitted a full SPL lane for that turn
while composition vetoed every matching step.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.pipeline_dispatch import PipelineStage
from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch
from app.chat.skill_intent_compatibility import (
    CAPABILITY_MCP,
    CAPABILITY_SPL,
    CompatibilityStatus,
    resolve_capability_compatibility,
    skill_contract_for,
)
from app.config import settings
from app.query_understanding.parser import understand_query

# The router-reachable contradiction that motivated this contract.
_OT_HUNT = "Unusual Modbus writes from an engineering workstation after hours, what should I check?"


@pytest.fixture(autouse=True)
def _cp_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)


def _resolve(skill: str, family: str):
    return resolve_capability_compatibility(
        routed_skill=skill, intent_family=family, skill_contract=skill_contract_for(skill)
    )


# --- the contract, against real registry contracts ---------------------------


@pytest.mark.parametrize(
    ("skill", "family", "expected"),
    [
        ("attack_discovery", "spl_generation_only", CompatibilityStatus.COMPATIBLE),
        ("attack_discovery", "live_investigation", CompatibilityStatus.COMPATIBLE),
        ("knowledge_recall", "knowledge_only", CompatibilityStatus.COMPATIBLE),
        ("knowledge_recall", "spl_generation_only", CompatibilityStatus.CAPABILITY_CONTRADICTION),
        ("alert_summary", "spl_generation_only", CompatibilityStatus.CAPABILITY_CONTRADICTION),
        ("guided_investigation", "spl_generation_only", CompatibilityStatus.CAPABILITY_CONTRADICTION),
    ],
)
def test_status_matrix(skill: str, family: str, expected: CompatibilityStatus) -> None:
    assert _resolve(skill, family).status == expected


def test_contradiction_never_widens_capability() -> None:
    """Fail closed: the contract wins, the intent does not gain SPL."""
    resolution = _resolve("knowledge_recall", "spl_generation_only")
    assert resolution.spl_permitted is False
    assert resolution.mcp_permitted is False
    assert CAPABILITY_SPL in resolution.denied_capabilities
    assert resolution.is_contradiction is True


def test_compatible_skill_keeps_its_capabilities() -> None:
    resolution = _resolve("attack_discovery", "spl_generation_only")
    assert resolution.spl_permitted is True
    assert resolution.denied_capabilities == frozenset()


def test_unknown_intent_family_is_unresolved_not_compatible() -> None:
    """Unknown semantics must not be asserted as safe."""
    resolution = _resolve("attack_discovery", "totally_new_family")
    assert resolution.status == CompatibilityStatus.UNRESOLVED


def test_missing_contract_is_unresolved() -> None:
    resolution = resolve_capability_compatibility(
        routed_skill="attack_discovery", intent_family="spl_generation_only", skill_contract=None
    )
    assert resolution.status == CompatibilityStatus.UNRESOLVED


def test_protected_alert_summary_pair_is_reported_distinctly() -> None:
    """The pre-existing alert_summary rule keeps its own identity."""
    from app.chat.skill_intent_compatibility import _PROTECTED_PAIRS

    assert ("alert_summary", "alert_summary") in _PROTECTED_PAIRS


def test_capability_lookup_reuses_the_composer_permit_logic() -> None:
    """One implementation answers 'does this skill allow SPL?' for both surfaces."""
    import inspect

    from app.chat import skill_intent_compatibility

    assert "_skill_permits" in inspect.getsource(skill_intent_compatibility)


# --- Phase Policy consumes the same resolution -------------------------------


def _hooks_for(query: str, skill: str) -> list[str] | None:
    from app.chat.contracts.pipeline_dispatch import imperative_hook_schedule_from_state
    from app.planner.resource_plan_authority import (
        TEST_AUTHORITY,
        register_test_resource_plan_compose_hook,
        resource_plan_authority,
    )
    from app.tests.support.compose_resource_plan_testutil import attach_resource_plan_for_tests

    register_test_resource_plan_compose_hook(attach_resource_plan_for_tests)
    with resource_plan_authority(TEST_AUTHORITY):
        qu = understand_query(query)
        q2i = build_query_to_intent(query=query, query_understanding=qu, routed_skill=skill)
        intent = q2i.intent_classification.model_dump()
        payload = plan_evidence(
            intent, query_to_intent=q2i.model_dump(), query_understanding=qu, routed={"skill": skill}
        ).model_dump()
        dispatch = build_pipeline_dispatch(
            evidence_plan=EvidencePlan.model_validate(
                {k: v for k, v in payload.items() if k in EvidencePlan.model_fields}
            ).model_dump(),
            intent_classification={"intent_family": intent.get("intent_family")},
            routed={"skill": skill},
        )
    state = {"pipeline_dispatch": dispatch.model_dump(mode="json")}
    return imperative_hook_schedule_from_state(state)


def test_phase_policy_emits_no_spl_lane_for_the_ot_contradiction() -> None:
    """Failing-first: this returned the full SPL lane before B2."""
    hooks = _hooks_for(_OT_HUNT, "knowledge_recall") or []
    assert "workflow_spl" not in hooks
    assert "spl_postprocessor" not in hooks
    assert "spl_source_resolve" not in hooks
    assert "execution" not in hooks


def test_phase_policy_keeps_the_spl_lane_for_a_compatible_skill() -> None:
    """Negative control: the constraint must not fire where capability is granted."""
    hooks = _hooks_for("Which users have excessive failed logins?", "attack_discovery") or []
    assert "workflow_spl" in hooks


def test_capability_constraint_only_removes_stages() -> None:
    """It may never add a lane the lifecycle policy did not choose."""
    from app.chat.pipeline_dispatch_builder import _apply_capability_constraints

    original = [PipelineStage.rag_early, PipelineStage.workflow_spl, PipelineStage.mcp_execution]
    constrained = _apply_capability_constraints(
        list(original), _resolve("knowledge_recall", "spl_generation_only")
    )
    assert set(constrained) <= set(original)
    assert PipelineStage.rag_early in constrained


def test_compatible_resolution_leaves_the_schedule_untouched() -> None:
    from app.chat.pipeline_dispatch_builder import _apply_capability_constraints

    original = [PipelineStage.workflow_spl, PipelineStage.mcp_execution]
    constrained = _apply_capability_constraints(
        list(original), _resolve("attack_discovery", "live_investigation")
    )
    assert constrained == original
