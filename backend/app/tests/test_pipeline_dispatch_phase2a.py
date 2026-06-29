"""Phase 2A — pipeline dispatch shell wiring at evidence planning."""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import graph_node_evidence_planning
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest


_SPL_QUERY = "Generate SPL for index=scada_perf by rtu_id over last 24h"


def _planning_state(query: str = _SPL_QUERY) -> dict:
    qu = understand_query(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill="spl_generation",
    )
    return {
        "request": ChatRequest(message=query),
        "query_understanding": qu,
        "routed": {"skill": "spl_generation"},
        "query_to_intent": q2i.model_dump(mode="json"),
        "intent_classification": q2i.intent_classification.model_dump(mode="json"),
        "selected_use_case": None,
    }


def test_pipeline_dispatch_attached_after_cp_on_evidence_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)

    state = graph_node_evidence_planning(_planning_state())

    dispatch = state.get("pipeline_dispatch")
    assert isinstance(dispatch, dict)
    assert dispatch["decision"]["stage_schedule"] == []
    assert dispatch["decision"]["llm_hops"] == []
    assert dispatch["decision"]["dispatch_reasons"] == ["pipeline_dispatch_stub_phase0"]
    assert dispatch["runtime_context"]["dispatch_cursor"] is None
    assert dispatch["decision"]["slot_handoff"]["normalized_slots"] == (
        state["evidence_plan"]["normalized_slot_summary"]["normalized_slots"]
    )


def test_pipeline_dispatch_cp_off_stub_attached_when_v2_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)

    state = graph_node_evidence_planning(_planning_state())

    assert state["evidence_plan"] is None
    dispatch = state.get("pipeline_dispatch")
    assert isinstance(dispatch, dict)
    assert dispatch["decision"]["stage_schedule"] == []
    assert dispatch["decision"]["slot_handoff"]["normalized_slots"] == {}


def test_pipeline_dispatch_not_attached_when_v2_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)

    state = graph_node_evidence_planning(_planning_state())

    assert "pipeline_dispatch" not in state
    assert state.get("evidence_plan") is not None
