"""R1 governed RAG answer: every claim is traceable to the captured governed retrieval.

Plan: plans/2026-09-24_1635_ec-cio-coherence-and-lifecycle.md (item A4.2).
"""

from __future__ import annotations

from app.demo.ec_turn import run_experience_center_turn
from app.demo.fixtures.r1.pack import R1_SCENARIO_ID
from app.demo.fixtures.r1.rag_content import (
    ANSWER_SENTENCES,
    CITATION_LABELS,
    build_rag_trace,
    captured_entry_ids,
    load_capture,
)


def test_every_answer_sentence_cites_a_captured_passage() -> None:
    captured = captured_entry_ids()
    for text, cites in ANSWER_SENTENCES:
        assert cites, text
        assert set(cites) <= captured, (text, set(cites) - captured)


def test_capture_comes_from_governed_retrieval_of_approved_passages_only() -> None:
    capture = load_capture()
    assert capture["retrieval_status"] == "retrieved"
    assert capture["direct_to_llm"] is False
    assert {entry["approval_status"] for entry in capture["retrieved_entries"]} == {"coe_reviewed"}
    excluded = capture["excluded_counts"]
    for reason in ("draft", "rejected", "superseded", "expired"):
        assert excluded[reason] >= 1, reason


def test_rag_trace_shows_used_passages_exclusions_and_gaps() -> None:
    trace = build_rag_trace()
    assert trace["excluded_total"] >= 4
    assert all(passage["used"] for passage in trace["passages"])
    labels = {passage["label"] for passage in trace["passages"]}
    assert {"AUTH-003", "AUTH-001", "ESC-AUTH-001"} <= labels
    assert trace["answer"]["gaps"], "gaps must be reported, not filled in"
    for sentence in trace["answer"]["sentences"]:
        assert set(sentence["citations"]) <= set(CITATION_LABELS.values())


def test_rag_trace_only_after_the_plan_is_approved() -> None:
    plan = run_experience_center_turn(R1_SCENARIO_ID, session_id=None).model_dump()
    assert plan["ec_agent_lifecycle"] == "PLAN_READY"
    assert plan["ec_agent_workflow"]["investigation_conclusion"] is None
    session_id = plan["ec_session_state"]["session_id"]
    after = run_experience_center_turn(
        R1_SCENARIO_ID,
        session_id=session_id,
        follow_up_id="run_investigation",
        agent_payload={"selected_step_ids": [s["id"] for s in plan["ec_agent_workflow"]["investigation_plan"]["steps"]]},
    ).model_dump()
    assert after["ec_agent_lifecycle"] == "INVESTIGATION_COMPLETE"
    assert after["ec_agent_workflow"]["investigation_conclusion"]["sources"]
    assert after["ec_provenance"]["live_rag_called"] is False
