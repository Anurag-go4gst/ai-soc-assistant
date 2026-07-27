"""Phase 2A — pipeline dispatch shell wiring at evidence planning."""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import graph_node_evidence_planning
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest


from app.tests.support.legacy_planning_harness import with_legacy_langgraph_harness


_SPL_QUERY = "Generate SPL for index=scada_perf by rtu_id over last 24h"


def _planning_state(query: str = _SPL_QUERY) -> dict:
    qu = understand_query(query)
    q2i = build_query_to_intent(
        query=query,
        query_understanding=qu,
        routed_skill="spl_generation",
    )
    return with_legacy_langgraph_harness(
        {
            "request": ChatRequest(message=query),
            "query_understanding": qu,
            "routed": {"skill": "spl_generation"},
            "query_to_intent": q2i.model_dump(mode="json"),
            "intent_classification": q2i.intent_classification.model_dump(mode="json"),
            "selected_use_case": None,
        }
    )


def test_pipeline_dispatch_attached_after_cp_on_evidence_planning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)

    state = graph_node_evidence_planning(_planning_state())

    dispatch = state.get("pipeline_dispatch")
    assert isinstance(dispatch, dict)
    assert dispatch["decision"]["request_mode"] == "spl_authoring"
    # MCP eligibility on all tiers (2026-07 directive, item 2.1): this live-data
    # SPL-authoring query is now architecturally eligible for mcp_execution under
    # lives downstream at evaluate_mcp_execution, not in the stage schedule.
    assert dispatch["decision"]["stage_schedule"] == [
        "workflow_spl",
        "spl_postprocessor",
        "spl_source_resolve",
        "mcp_execution",
    ]
    assert dispatch["runtime_context"]["dispatch_cursor"] is None
    assert dispatch["decision"]["slot_handoff"]["normalized_slots"] == (
        state["evidence_plan"]["normalized_slot_summary"]["normalized_slots"]
    )


def test_pipeline_dispatch_cp_off_stub_attached_when_v2_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)

    state = graph_node_evidence_planning(_planning_state())

    assert state.get("evidence_plan") is not None
    dispatch = state.get("pipeline_dispatch")
    assert isinstance(dispatch, dict)
    assert dispatch["decision"]["request_mode"] == "spl_authoring"
    assert "workflow_spl" in dispatch["decision"]["stage_schedule"]
    assert dispatch["decision"]["slot_handoff"]["normalized_slots"]["index"] == "scada_perf"


def test_pipeline_dispatch_not_attached_when_v2_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)

    qu = understand_query(_SPL_QUERY)
    q2i = build_query_to_intent(
        query=_SPL_QUERY,
        query_understanding=qu,
        routed_skill="spl_generation",
    )
    state = graph_node_evidence_planning(
        {
            "request": ChatRequest(message=_SPL_QUERY),
            "query_understanding": qu,
            "routed": {"skill": "spl_generation"},
            "query_to_intent": q2i.model_dump(mode="json"),
            "intent_classification": q2i.intent_classification.model_dump(mode="json"),
            "selected_use_case": None,
        }
    )

    assert "pipeline_dispatch" not in state
    # The legacy evidence-planning node is forbidden under canonical planning, so it
    # returns a typed failure. It used to also emit a stub ``evidence_plan`` carrying
    # only ``reasons`` + ``canonical_failure``; that dict failed
    # ``EvidencePlan.model_validate`` in every consumer, so it is no longer produced.
    assert state.get("evidence_plan") is None
    assert state["canonical_planning_failure"]["reason"] == "canonical_forbids_legacy_evidence_planning"
