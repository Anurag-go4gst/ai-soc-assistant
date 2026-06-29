"""Phase 0 — canonical handoff fix + dispatch contract stubs.

Covers:
- LLM 2C entity slots reach the evidence-plan handoff (root slot-drift fix).
- Dispatch contract stubs + projection round-trip + cursor helper.
- Authority read sweep: dispatch modules never read ``extract_query_signals``.
"""

from __future__ import annotations

import pathlib

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.contracts.intent_dispatch import (
    IntentPromptMode,
    build_intent_dispatch,
)
from app.chat.contracts.pipeline_dispatch import (
    LlmHop,
    PipelineDispatchContract,
    PipelineStage,
    build_pipeline_dispatch,
    next_stage_after,
    project_dispatch_flags,
)
from app.chat.contracts.slot_handoff import slot_handoff_from_normalized_summary
from app.chat.evidence_planner import _attach_canonical_handoff_summaries
from app.query_understanding.parser import understand_query


def _minimal_plan() -> EvidencePlan:
    return EvidencePlan(
        answer_mode="live_investigation",
        rag_phase="post_mcp",
        needs_rag=False,
        needs_spl=True,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=True,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )


def test_evidence_plan_includes_llm_slots_in_handoff() -> None:
    """A 2C-advisory slot with no deterministic source must surface as slot_sources.llm."""
    query = "show me the recent activity"  # no host/user entity in the text
    qu = understand_query(query)
    query_to_intent = {
        "llm_intent_advisory": {
            "entity_slots_candidate": {"host": "web01"},
        }
    }
    enriched = _attach_canonical_handoff_summaries(
        _minimal_plan(),
        query_to_intent=query_to_intent,
        query_understanding=qu,
    )
    summary = enriched.normalized_slot_summary or {}
    assert summary.get("normalized_slots", {}).get("host") == "web01"
    assert summary.get("slot_sources", {}).get("host") == "llm"


def test_handoff_without_advisory_has_no_llm_source() -> None:
    qu = understand_query("show me the recent activity")
    enriched = _attach_canonical_handoff_summaries(
        _minimal_plan(),
        query_to_intent={},
        query_understanding=qu,
    )
    summary = enriched.normalized_slot_summary or {}
    assert "host" not in summary.get("normalized_slots", {})


def test_build_intent_dispatch_skip_when_advisory_skipped() -> None:
    decision = build_intent_dispatch(skip_advisory=True, skip_reason="deterministic_exact_match_t0")
    assert decision.call_2c_llm is False
    assert decision.prompt_mode is IntentPromptMode.skip
    assert decision.skip_reasons == ["deterministic_exact_match_t0"]


def test_build_pipeline_dispatch_stub_is_empty_and_coerces_handoff() -> None:
    state = build_pipeline_dispatch(
        evidence_plan={"normalized_slot_summary": {"normalized_slots": {"index": "pgcil_soc"}}}
    )
    assert state.decision.stage_schedule == []
    assert state.decision.llm_hops == []
    assert state.decision.slot_handoff.normalized_slots == {"index": "pgcil_soc"}


def test_project_dispatch_flags_round_trip() -> None:
    decision = PipelineDispatchContract(
        request_mode="spl_authoring",
        stage_schedule=[PipelineStage.workflow_spl, PipelineStage.spl_postprocessor],
        llm_hops=[LlmHop.spl_plan_compiler],
    )
    flags = project_dispatch_flags(decision)
    assert flags["run_workflow_spl"] is True
    assert flags["run_spl_postprocessor"] is True
    assert flags["run_rag_early"] is False
    assert flags["call_spl_llm"] is True
    assert flags["call_mcp_tool_planner"] is False
    # call_2c_llm is never projected from post-evidence dispatch.
    assert "call_2c_llm" not in flags


def test_next_stage_after_orders_and_terminates() -> None:
    schedule = [
        PipelineStage.workflow_spl,
        PipelineStage.spl_postprocessor,
        PipelineStage.spl_source_resolve,
    ]
    assert next_stage_after(schedule, None) is PipelineStage.workflow_spl
    assert next_stage_after(schedule, PipelineStage.workflow_spl) is PipelineStage.spl_postprocessor
    assert next_stage_after(schedule, PipelineStage.spl_source_resolve) is None
    assert next_stage_after([], None) is None


def test_slot_handoff_coercion_is_tolerant() -> None:
    handoff = slot_handoff_from_normalized_summary(
        {"normalized_slots": {"index": "pgcil_soc", "threshold": 5}, "slot_sources": {"index": "user_explicit"}}
    )
    assert handoff.normalized_slots == {"index": "pgcil_soc", "threshold": "5"}
    assert handoff.slot_sources == {"index": "user_explicit"}
    assert slot_handoff_from_normalized_summary(None).normalized_slots == {}


def test_pipeline_dispatch_authority_read_sweep() -> None:
    """Dispatch contracts/builder must not read ``extract_query_signals`` for routing.

    Phase 0 baseline guard — grows as later phases add dispatch consumers.
    """
    base = pathlib.Path(__file__).resolve().parents[1] / "chat" / "contracts"
    dispatch_modules = [
        base / "intent_dispatch.py",
        base / "pipeline_dispatch.py",
        base / "slot_handoff.py",
        base / "spl_candidate.py",
    ]
    for module in dispatch_modules:
        text = module.read_text(encoding="utf-8")
        assert "extract_query_signals" not in text, f"{module.name} reads query signals for dispatch"
