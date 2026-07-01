"""REV4 batch 2 P13a — guided hybrid refinement cap."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_hybrid_refinement import (
    MAX_GUIDED_INVESTIGATION_ROUNDS,
    REFINEMENT_CAP_WARNING,
    apply_refinement_cap_warning,
    refinement_cap_reached,
    should_run_refinement_pass,
)
from app.chat.guided_investigation_plan_llm import InvestigationPlanLlmResult
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest

SAMPLE_QUERY = (
    "How should I investigate unusual outbound traffic from an OT host overnight?"
)


def test_refinement_cap_constants() -> None:
    assert MAX_GUIDED_INVESTIGATION_ROUNDS == 3


def test_should_run_refinement_pass_until_cap() -> None:
    assert should_run_refinement_pass(refinement_round=0, refinement_recommended=True) is True
    assert should_run_refinement_pass(refinement_round=1, refinement_recommended=True) is True
    assert should_run_refinement_pass(refinement_round=2, refinement_recommended=True) is False
    assert should_run_refinement_pass(refinement_round=0, refinement_recommended=False) is False


def test_refinement_cap_reached_on_final_allowed_round() -> None:
    assert refinement_cap_reached(refinement_round=2, refinement_recommended=True) is True
    assert refinement_cap_reached(refinement_round=1, refinement_recommended=True) is False


def test_apply_refinement_cap_warning_is_stable() -> None:
    plan = InvestigationPlan(
        investigation_objective="test",
        refinement_recommended=True,
    )
    capped = apply_refinement_cap_warning(plan)
    assert capped.refinement_recommended is False
    assert REFINEMENT_CAP_WARNING in capped.validation_warnings


@pytest.fixture(autouse=True)
def _hybrid_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


def test_refinement_loop_stops_at_cap_and_trace_shows_rounds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _always_recommend(*_args: Any, **_kwargs: Any) -> InvestigationPlanLlmResult:
        calls["count"] += 1
        return InvestigationPlanLlmResult(
            raw_llm={"refinement_recommended": True},
            proposal={"refinement_recommended": True, "refinement_rationale": "more evidence"},
            attempted=True,
            timed_out=False,
            provider_label="test",
            dropped_reasons=[],
        )

    monkeypatch.setattr(
        "app.chat.pipeline.propose_investigation_plan_llm",
        _always_recommend,
    )
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    handoff = trace.get("guided_handoff") or {}
    assert handoff.get("refinement_round") == MAX_GUIDED_INVESTIGATION_ROUNDS - 1
    assert handoff.get("refinement_rounds") == [0, 1, 2]
    assert calls["count"] == MAX_GUIDED_INVESTIGATION_ROUNDS
    assert REFINEMENT_CAP_WARNING in (
        (handoff.get("investigation_plan_validated") or {}).get("validation_warnings") or []
    )
    dispatch = trace.get("plan_dispatch") or {}
    schedule = dispatch.get("dispatch_schedule") or []
    assert schedule.count("guided_refinement") == MAX_GUIDED_INVESTIGATION_ROUNDS - 1
    assert "execution" not in schedule
    assert "graph_node_execution" not in schedule
    assert response.evidence_plan.get("mcp_allowed") is False
    assert response.execution.status == "skipped"
    assert response.candidate_spl is None


def test_flag_off_unchanged_by_refinement_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    assert "guided_handoff" not in trace
    dispatch = trace.get("plan_dispatch") or {}
    assert dispatch.get("dispatch_schedule") == ["prepare_rag_only", "rag_early"]
