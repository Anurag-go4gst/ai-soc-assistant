"""PR #58 — budgeted LLM SPL drafting for universal utility authoring (mocked, no live LLM)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.chat.pipeline import (
    _candidate_spl_stage,
    build_live_chat_response,
    graph_node_query_to_intent,
    graph_node_rag_early,
)
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest
from app.spl.llm_fallback import generate_llm_spl_fallback, spl_advisory_prompts
from app.spl.utility_spl_authoring import (
    attempt_bounded_utility_spl_llm_draft,
    candidate_from_universal_utility_authoring,
)

_WEEKEND_QUERY = (
    "Without using any specific company templates, write a standard, universal SPL block "
    "that extracts the hour of the day and day of the week from an event timestamp, "
    "filtering only for weekend events."
)

_Q046 = "Which users have excessive failed logins?"


@pytest.fixture
def spl_authoring_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)


def _skeleton_spl(*, index_value: str = "<your_index>") -> str:
    from app.spl.draft_preview import build_draft_preview

    draft = build_draft_preview(_WEEKEND_QUERY, live_data_request=True)
    assert draft is not None
    spl = str(draft["draft_spl"])
    if index_value != "<your_index>":
        spl = spl.replace("index=<your_index>", f"index={index_value}")
    return spl


def _weekend_llm_payload(*, spl: str | None = None, invented_index: str | None = None) -> str:
    candidate = spl or _skeleton_spl(index_value=invented_index or "wineventlog")
    return json.dumps(
        {
            "status": "candidate_generated",
            "confidence_score": 0.72,
            "confidence_label": "medium",
            "detection_family": "universal_timestamp_spl",
            "candidate_spl": candidate,
            "assumptions": ["Universal utility draft for review only"],
            "required_fields": ["_time", "index"],
            "missing_details": [],
            "clarifying_questions": [],
            "validation_notes": [],
            "soc_std_rules_applied": [],
            "risk_notes": [],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )


class _Telemetry:
    def record_step(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    def record_spl_validation(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None


def test_spl_advisory_prompts_include_weekend_few_shot_for_utility_authoring() -> None:
    system, _user = spl_advisory_prompts(_WEEKEND_QUERY, utility_authoring=True)
    assert "Universal utility SPL authoring" in system
    assert "universal_timestamp_spl" in system
    assert "day_of_week_num" in system


def test_utility_authoring_bypasses_global_spl_fallback_flag(spl_authoring_flags: None) -> None:
    payload = _weekend_llm_payload(spl=_skeleton_spl())
    result = generate_llm_spl_fallback(
        user_query=_WEEKEND_QUERY,
        utility_authoring=True,
        llm_raw_output_provider=lambda: payload,
    )
    assert result is not None
    assert result.candidate_spl
    assert result.clarification_required is False


def test_universal_spl_authoring_skips_intent_advisor(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline.generate_llm_intent_advisory",
        lambda *_, **__: pytest.fail("intent advisor must be skipped for universal utility SPL"),
    )
    qu = understand_query(_WEEKEND_QUERY)
    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=_WEEKEND_QUERY),
            "effective_query": _WEEKEND_QUERY,
            "query_understanding": qu,
            "routed": {"skill": "spl_generation"},
        }
    )
    advisory = state.get("llm_intent_advisory") or {}
    trace = advisory.get("scheduling_trace") or {}
    assert advisory.get("llm_called") is False
    assert trace.get("deterministic_route_proceeded_without_waiting_for_intent") is True
    assert trace.get("intent_advisory_not_required_for_universal_utility_route") is True
    assert trace.get("intent_advisor_skip_reason") == "intent_advisory_not_required_for_universal_utility_route"
    assert trace.get("budget_reallocated_to_spl_drafting") is True


def test_universal_spl_authoring_uses_mock_llm_spl_draft_when_available(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline._routes_chat",
        lambda: type("_Routes", (), {"get_telemetry_connector": staticmethod(lambda: _Telemetry())})(),
    )
    payload = _weekend_llm_payload()
    candidate, validation = candidate_from_universal_utility_authoring(
        trace_id="t-utility-llm",
        skill="spl_generation",
        user_query=_WEEKEND_QUERY,
        telemetry=_Telemetry(),
        profile=__import__(
            "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
        ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl"),
        spl_governance=None,
        llm_raw_output_provider=lambda: payload,
    )
    assert candidate is not None and validation is not None
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert trace.get("llm_spl_draft_requested") is True
    assert trace.get("llm_spl_draft_completed") is True
    assert trace.get("llm_spl_draft_used") is True
    assert trace.get("final_raw_spl_source") == "llm_draft"
    assert "index=<your_index>" in candidate["candidate_spl"]
    post = candidate.get("review_only_spl_postprocessor_trace") or {}
    assert post.get("postprocessor_applied") is True
    assert post.get("final_spl_authority") == "llm_draft_normalized"
    assert validation.get("approved") is False


def test_universal_spl_authoring_falls_back_to_deterministic_skeleton_on_llm_timeout(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.invoke_sidecar_role",
        lambda **_: ("", True, "timed_out"),
    )
    result, trace = attempt_bounded_utility_spl_llm_draft(_WEEKEND_QUERY)
    assert result is None
    assert trace.get("llm_spl_draft_timed_out") is True

    monkeypatch.setattr(
        "app.chat.pipeline._routes_chat",
        lambda: type("_Routes", (), {"get_telemetry_connector": staticmethod(lambda: _Telemetry())})(),
    )
    candidate, _validation = candidate_from_universal_utility_authoring(
        trace_id="t-timeout",
        skill="spl_generation",
        user_query=_WEEKEND_QUERY,
        telemetry=_Telemetry(),
        profile=__import__(
            "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
        ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl"),
        spl_governance=None,
    )
    assert candidate is not None
    draft_trace = candidate.get("utility_spl_draft_trace") or {}
    assert draft_trace.get("final_raw_spl_source") == "deterministic_skeleton"
    assert draft_trace.get("deterministic_skeleton_used") is True
    assert "index=<your_index>" in candidate["candidate_spl"]


def test_llm_draft_index_invention_is_dropped(spl_authoring_flags: None) -> None:
    payload = _weekend_llm_payload(invented_index="wineventlog")
    candidate, _validation = candidate_from_universal_utility_authoring(
        trace_id="t-index-drop",
        skill="spl_generation",
        user_query=_WEEKEND_QUERY,
        telemetry=_Telemetry(),
        profile=__import__(
            "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
        ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl"),
        spl_governance=None,
        llm_raw_output_provider=lambda: payload,
    )
    assert candidate is not None
    assert "index=wineventlog" not in candidate["candidate_spl"]
    assert "index=<your_index>" in candidate["candidate_spl"]
    post = candidate.get("review_only_spl_postprocessor_trace") or {}
    assert post.get("raw_llm_index_dropped") is True


def test_user_explicit_index_wins_over_llm_draft(spl_authoring_flags: None) -> None:
    query = _WEEKEND_QUERY + " Use index=my_custom_index."
    payload = _weekend_llm_payload(invented_index="wineventlog")
    candidate, _validation = candidate_from_universal_utility_authoring(
        trace_id="t-user-index",
        skill="spl_generation",
        user_query=query,
        telemetry=_Telemetry(),
        profile=__import__(
            "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
        ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl"),
        spl_governance=None,
        llm_raw_output_provider=lambda: payload,
    )
    assert candidate is not None
    assert "index=my_custom_index" in candidate["candidate_spl"]
    post = candidate.get("review_only_spl_postprocessor_trace") or {}
    assert post.get("index_resolution_source") == "user_explicit"


def test_coe_or_source_profile_index_wins_over_llm_draft(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {"index": "soc_main"},
    )
    payload = _weekend_llm_payload(invented_index="wineventlog")
    candidate, _validation = candidate_from_universal_utility_authoring(
        trace_id="t-profile-index",
        skill="spl_generation",
        user_query=_WEEKEND_QUERY,
        telemetry=_Telemetry(),
        profile=__import__(
            "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
        ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl"),
        spl_governance=None,
        llm_raw_output_provider=lambda: payload,
    )
    assert candidate is not None
    assert "index=soc_main" in candidate["candidate_spl"]
    post = candidate.get("review_only_spl_postprocessor_trace") or {}
    assert post.get("index_resolution_source") == "source_profile_resolver"


def test_rag_skipped_for_universal_spl_utility(spl_authoring_flags: None) -> None:
    qu = understand_query(_WEEKEND_QUERY)
    state = graph_node_rag_early(
        {
            "request": ChatRequest(message=_WEEKEND_QUERY),
            "effective_query": _WEEKEND_QUERY,
            "query_understanding": qu,
            "workflow_plan": {"required_sources": []},
            "execution": {"block_reason": None},
        }
    )
    retrieval = state.get("soc_kb_retrieval") or {}
    assert retrieval.get("rag_skipped_for_spl_utility_authoring") is True
    assert retrieval.get("retrieval_status") == "skipped"
    assert not retrieval.get("retrieved_entries")


def test_candidate_spl_stage_routes_universal_utility_through_budgeted_path(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline._routes_chat",
        lambda: type("_Routes", (), {"get_telemetry_connector": staticmethod(lambda: _Telemetry())})(),
    )
    signals = extract_query_signals(_WEEKEND_QUERY)
    candidate, validation = _candidate_spl_stage(
        trace_id="t-stage",
        skill="spl_generation",
        user_query=_WEEKEND_QUERY,
        query_signals=signals,
    )
    assert candidate is not None and validation is not None
    assert candidate.get("generation_mode") in {"utility_llm_spl_draft", "deterministic_lab_draft"}
    assert candidate.get("detection_family") == "universal_timestamp_spl"


def test_q046_unchanged_reference_in_explicit_spl_authoring(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_Q046)).model_dump(mode="json")
    hr = payload.get("human_review") or {}
    assert hr.get("review_type") == "spl_revision"
    assert hr.get("reason") == "template_review_required"
    candidate = payload.get("candidate_spl") or {}
    assert candidate.get("template_id") or "auth_failed" in str(candidate.get("candidate_spl", "")).lower()
