"""REV4 batch 2 P13a — guided hybrid refinement cap."""

from __future__ import annotations

import pytest

from app.chat.contracts.investigation_plan import InvestigationPlan
from app.chat.guided_hybrid_refinement import (
    MAX_GUIDED_INVESTIGATION_ROUNDS,
    REFINEMENT_CAP_WARNING,
    apply_refinement_cap_warning,
    refinement_cap_reached,
    should_run_refinement_pass,
)
from app.chat import pipeline as _pipeline
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
from pathlib import Path

_PIPELINE_SRC = Path(_pipeline.__file__).read_text()

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
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "telemetry_mode", "none")
    monkeypatch.setattr(settings, "ai_soc_telemetry_sink", "none")


def test_refinement_is_deterministic_only_and_never_iterates() -> None:
    """B2-R2: the refinement loop had exactly one driver, and it was retired.

    `refinement_recommended` is set either from the deterministic baseline
    (always False, see `investigation_plan_builder`) or from an LLM proposal
    when `llm_attempted` is true. With the imperative guided proposer retired,
    `llm_attempted` is always False, so guided investigations run exactly one
    round and the `MAX_GUIDED_INVESTIGATION_ROUNDS` cap is no longer reachable.

    This replaces a test that drove the loop by forcing the proposer to always
    recommend refinement. The cap logic is intentionally left in place — this
    test pins that it is inert, so a future adaptive-planning seam that
    reintroduces refinement has to face the bound rather than silently bypass
    an unguarded loop.
    """
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    handoff = trace.get("guided_handoff") or {}

    assert handoff.get("refinement_round") == 0
    assert handoff.get("refinement_rounds") == [0]
    assert handoff.get("investigation_plan_raw_llm") is None

    dispatch = trace.get("plan_dispatch") or {}
    schedule = dispatch.get("dispatch_schedule") or []
    assert "guided_refinement" not in schedule
    assert "guided_investigation_plan_llm" not in schedule

    # RETAINED: deterministic guided execution and its safety posture.
    assert "execution" not in schedule
    assert "graph_node_execution" not in schedule
    assert response.evidence_plan.get("mcp_allowed") is False
    assert response.execution.status == "skipped"
    assert response.candidate_spl is None


def test_refinement_cap_bound_still_guards_the_loop() -> None:
    """The cap constant survives retirement; only its driver is gone."""
    assert MAX_GUIDED_INVESTIGATION_ROUNDS >= 1
    assert "refinement_round >= MAX_GUIDED_INVESTIGATION_ROUNDS" in _PIPELINE_SRC


def test_flag_off_unchanged_by_refinement_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", False)
    response = build_live_chat_response(ChatRequest(message=SAMPLE_QUERY))
    trace = response.control_plane_trace or {}
    assert "guided_handoff" not in trace
    dispatch = trace.get("plan_dispatch") or {}
    assert dispatch.get("dispatch_schedule") == ["prepare_rag_only", "rag_early"]
