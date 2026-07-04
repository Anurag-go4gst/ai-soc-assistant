from __future__ import annotations

from app.chat.intent_classifier import classify_intent
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import _resolve_path_type
from app.chat.evidence_planner import plan_evidence
from app.chat.pipeline_dispatch_builder import build_pipeline_dispatch
from app.chat.query_signals import extract_query_signals
from app.chat.contracts.pipeline_dispatch import PipelineStage
from app.chat.pipeline import _candidate_spl_stage
from app.config import settings
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding


def test_explicit_run_spl_routes_spl_review_not_unsafe_blocked() -> None:
    query = "Run the SPL and give me results."
    signals = extract_query_signals(query)
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings={},
        query_understanding=understand_query(query),
    ).model_dump()
    qu = understand_query(query)
    path = _resolve_path_type(intent, {"needs_spl": True}, {}, None, qu)
    assert path == "spl_review"
    assert intent["intent_family"] == "spl_generation_and_run"


def test_containment_still_routes_unsafe_blocked() -> None:
    query = "Block this IP on the firewall immediately."
    signals = extract_query_signals(query)
    intent = classify_intent(
        query=query,
        signals=signals,
        candidate_mappings={},
        query_understanding=understand_query(query),
    ).model_dump()
    qu = understand_query(query)
    path = _resolve_path_type(intent, {}, {}, None, qu)
    assert path == "unsafe_blocked"


def test_out_of_registry_discovery_command_does_not_route_guided() -> None:
    query = "List Splunk indexes and sourcetypes that can prove whether AGC logs exist."
    qu = understand_query(query)
    base, provenance = select_route_from_understanding(qu, query)

    assert extract_query_signals(query)["discovery_ask"] is True
    assert base["skill"] != "guided_investigation"
    assert provenance["authority_source"] != "guided_investigation_rescue"


def test_command_run_query_dispatches_spl_and_run_not_clarification() -> None:
    query = "Run the SPL and give me results."
    qu = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=qu)
    evidence_plan = plan_evidence(
        q2i.intent_classification.model_dump(),
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
    )
    dispatch = build_pipeline_dispatch(
        evidence_plan=evidence_plan.model_dump(),
        query_to_intent=q2i.model_dump(),
        intent_classification=q2i.intent_classification.model_dump(),
        query_understanding=qu,
    )

    assert dispatch.decision.request_mode == "spl_and_run"
    assert PipelineStage.pre_spl_mcp_discovery in dispatch.decision.stage_schedule
    assert PipelineStage.workflow_spl in dispatch.decision.stage_schedule
    assert PipelineStage.spl_postprocessor in dispatch.decision.stage_schedule
    assert PipelineStage.spl_source_resolve in dispatch.decision.stage_schedule
    assert PipelineStage.mcp_execution in dispatch.decision.stage_schedule


def test_pasted_spl_ingests_user_query_as_candidate(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)
    query = (
        "Here is SPL: search index=pgcil_soc sourcetype=pgcil:ot_agc earliest=-2h "
        "| stats count by command_src setpoint | head 100. Validate and optimize it, "
        "then ask me before running."
    )
    signals = extract_query_signals(query)
    candidate, validation = _candidate_spl_stage(
        trace_id="trace-user-spl",
        skill="spl_generation",
        user_query=query,
        query_signals=signals,
        spl_allowed=True,
    )

    assert candidate is not None
    assert validation is not None
    assert candidate["generation_mode"] == "user_provided_spl"
    assert "command_src" in candidate["candidate_spl"]
    assert "Validate and optimize" not in candidate["candidate_spl"]
    assert candidate["execution_eligible"] is False
    assert (candidate.get("review_only_spl_postprocessor_trace") or {}).get("postprocessor_evaluated") is True
