"""REV4 batch 1 P2 — InvestigationPlan contract and deterministic baseline."""

from __future__ import annotations

import pytest

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.investigation_plan_builder import build_deterministic_investigation_plan

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)

_FORBIDDEN_EXECUTION_FIELDS = frozenset(
    {
        "execution_eligible",
        "mcp_allowed",
        "spl_execution_eligible",
        "freeform_spl_execution_eligible",
        "safe_catalog_spl_execution_eligible",
        "final_route",
        "severity",
    }
)


def test_investigation_plan_contract_has_no_execution_flag_fields() -> None:
    assert not _FORBIDDEN_EXECUTION_FIELDS.intersection(InvestigationPlan.model_fields)


def test_deterministic_baseline_for_sample_guided_query() -> None:
    plan = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    assert isinstance(plan, InvestigationPlan)
    assert plan.plan_source == "deterministic_only"
    assert plan.human_review_required is True
    assert plan.llm_budget_used == 0
    assert plan.refinement_round == 0
    assert plan.read_only_tool_requests == []
    assert plan.safe_spl_template_requests == []
    assert plan.discovery_needed is False
    assert plan.rag_sufficient is False
    assert plan.hypotheses
    assert plan.evidence_needed
    assert plan.investigation_objective
    assert "freeform_spl_execution" in plan.blocked_capabilities


def test_deterministic_baseline_uses_grounding_without_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("InvestigationPlan baseline must not invoke tools")

    monkeypatch.setattr(
        "app.chat.investigation_plan_builder.build_guided_hunt_grounding",
        lambda **kwargs: type(
            "GroundingStub",
            (),
            {
                "detection_families": ["dns_beaconing_candidate"],
                "limitations": ["review-only"],
                "environment_kb_slots": ["index_ot=ot_*"],
                "asset_registry_hints": ["asset_count=3"],
                "skill_refs": [],
                "soc_kb_refs": [],
            },
        )(),
    )
    plan = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    assert plan.env_kb_needed is True
    assert any("env_kb_slot:" in item for item in plan.environment_constraints)
    assert any(item.startswith("detection_family:") for item in plan.candidate_sources)


def test_deterministic_baseline_serializes_cleanly() -> None:
    plan = build_deterministic_investigation_plan(query=SAMPLE_QUERY)
    payload = plan.model_dump()
    assert payload["plan_source"] == "deterministic_only"
    assert payload["human_review_required"] is True
    for field in _FORBIDDEN_EXECUTION_FIELDS:
        assert field not in payload
