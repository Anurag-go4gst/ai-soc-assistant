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
from app.tests.support.chat_visible import spl_from_payload, visible_from_payload

_WEEKEND_QUERY = (
    "Without using any specific company templates, write a standard, universal SPL block "
    "that extracts the hour of the day and day of the week from an event timestamp, "
    "filtering only for weekend events."
)

_Q046 = "Which users have excessive failed logins?"


@pytest.fixture
def spl_authoring_flags(monkeypatch: pytest.MonkeyPatch) -> None:
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
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )
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
    assert post.get("final_spl_authority") == "deterministic_postprocessor"
    assert validation.get("approved") is False


def test_universal_spl_authoring_falls_back_to_deterministic_skeleton_on_llm_timeout(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.generate_llm_spl_fallback",
        lambda **_: None,
    )
    result, trace = attempt_bounded_utility_spl_llm_draft(_WEEKEND_QUERY)
    assert result is None
    assert trace.get("llm_spl_draft_used") is False
    assert trace.get("llm_spl_draft_completed") is False
    assert trace.get("llm_spl_draft_dropped_reason") in {
        "llm_spl_fallback_unavailable",
        "llm_disabled",
        "utility_spl_draft_disabled",
    }

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


def test_llm_draft_index_invention_is_dropped(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )
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


def test_live_response_surfaces_utility_mode_and_postprocessor_trace(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {"auth_index": "pgcil_soc"},
    )
    from app.chat.pipeline import graph_node_rag_early
    from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring

    qu = understand_query(_WEEKEND_QUERY)
    rag_state = graph_node_rag_early(
        {
            "request": ChatRequest(message=_WEEKEND_QUERY),
            "effective_query": _WEEKEND_QUERY,
            "query_understanding": qu,
            "workflow_plan": {"required_sources": []},
            "execution": {"block_reason": None},
            "evidence_plan": {"answer_mode": "spl_utility_authoring"},
        }
    )
    retrieval = rag_state.get("soc_kb_retrieval") or {}
    assert retrieval.get("rag_skipped_for_spl_utility_authoring") is True

    candidate, validation = candidate_from_universal_utility_authoring(
        trace_id="utility-live",
        skill="spl_generation",
        user_query=_WEEKEND_QUERY,
        telemetry=_Telemetry(),
        profile=__import__(
            "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
        ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl"),
        spl_governance=None,
    )
    assert candidate is not None
    assert validation is not None
    assert candidate.get("candidate_spl")
    post = candidate.get("review_only_spl_postprocessor_trace") or {}
    assert post.get("dependency_preserved") is True or post.get("changes")


def test_placeholder_not_unresolved_when_no_coe_index(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.build_source_profile_binding_slots",
        lambda *_args, **_kwargs: type(
            "_Binding",
            (),
            {"slots": {}, "trace": staticmethod(lambda: {"source_profile_bindings_missing": []})},
        )(),
    )
    monkeypatch.setattr(settings, "ai_soc_utility_spl_default_index", "")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_WEEKEND_QUERY)).model_dump(mode="json")
    visible = visible_from_payload(payload)
    spl_blob = spl_from_payload(payload)
    assert "index=<your_index>" in spl_blob
    assert "`<your_index>` is a placeholder" in visible
    assert "Unresolved source bindings" not in visible
    assert "missing source profile" not in visible.lower()


def test_coe_single_approved_index_wins_over_placeholder(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {"auth_index": "pgcil_soc"},
    )
    payload = build_live_chat_response(ChatRequest(message=_WEEKEND_QUERY)).model_dump(mode="json")
    visible = visible_from_payload(payload)
    spl_blob = spl_from_payload(payload)
    candidate = payload.get("candidate_spl") or {}
    post = candidate.get("review_only_spl_postprocessor_trace") or {}
    assert "index=pgcil_soc" in spl_blob
    assert post.get("index_resolution_source") == "source_profile_resolver"
    assert "using coe-resolved index `pgcil_soc`" in visible.lower()
    assumptions = "\n".join(candidate.get("assumptions") or [])
    assert "using COE-resolved index `pgcil_soc`" in assumptions
    assert "using a <your_index> placeholder" not in assumptions


def test_unrelated_unknown_index_key_does_not_force_placeholder(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {
            "auth_index": "pgcil_soc",
            "network_index": "pgcil_soc",
            "zzz_dummy_test_index": "abc",
        },
    )
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_WEEKEND_QUERY)).model_dump(mode="json")
    spl_blob = spl_from_payload(payload)
    post = (payload.get("candidate_spl") or {}).get("review_only_spl_postprocessor_trace") or {}
    assert "index=pgcil_soc" in spl_blob
    assert "index=<your_index>" not in spl_blob
    assert post.get("index_resolution_source") == "source_profile_resolver"


def test_non_universal_lab_draft_ignores_global_single_index_heuristic(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {
            "network_index": "pgcil_soc",
            "auth_index": "pgcil_soc",
            "aws_index": "pgcil_soc",
            "scada_perf_index": "scada_perf",
            "cisco_asa_index": "cisco_asa",
        },
    )
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = build_live_chat_response(
        ChatRequest(message="Which source IPs generated the most outbound connections?")
    ).model_dump(mode="json")
    assert payload.get("response_mode") == "human_review_required"
    human_review = payload.get("human_review") or {}
    assert human_review.get("review_type") == "spl_revision"


def test_unsafe_execute_delete_is_not_utility_authoring(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    query = _WEEKEND_QUERY + " Then execute it and pipe to delete."
    payload = build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")
    assert payload.get("answer_mode") != "spl_utility_authoring"
    assert "delete" not in str((payload.get("candidate_spl") or {}).get("candidate_spl") or "").lower()
    execution = payload.get("execution") or {}
    assert execution.get("status") != "executed"


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

def test_run_contract_utility_spl_no_live_execution_needed(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_WEEKEND_QUERY)).model_dump(mode="json")
    contract = payload.get("run_contract") or {}
    assert contract.get("mcp_needed_for_live_answer") is False
    assert contract.get("execution_needed_for_answer") is False
    assert contract.get("execution_authorized") is False
    assert contract.get("mcp_allowed") is False
    assert contract.get("spl_candidate_present") is True


def test_build_source_evidence_skips_rag_for_utility_skip() -> None:
    from app.chat.pipeline import _utility_spl_rag_skipped_payload
    from app.evidence.source_evidence import build_source_evidence

    evidence = build_source_evidence(
        trace_id="t-rag-skip",
        query=_WEEKEND_QUERY,
        selected_skill="spl_generation",
        spl_validation={"approved": False},
        execution={"status": "skipped"},
        soc_kb_retrieval=_utility_spl_rag_skipped_payload(),
    )
    assert not any(item.get("source_type") == "rag" for item in evidence)


def test_resolve_trace_answer_mode_from_payload() -> None:
    from app.chat.pipeline import _resolve_trace_answer_mode

    payload = {
        "candidate_spl": {"detection_family": "universal_timestamp_spl"},
        "spl_validation": {"review_required_reason": "universal_spl_authoring_review_only"},
    }
    assert _resolve_trace_answer_mode(payload) == "spl_utility_authoring"


def test_debug_summary_review_only_postprocessor_applied(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.chat.debug_summary import build_debug_summary

    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_WEEKEND_QUERY)).model_dump(mode="json")
    summary = build_debug_summary(payload=payload)
    spl = summary.get("spl") or {}
    assert spl.get("review_only_postprocessor_applied") is True
    assert spl.get("postprocessor_applied") is True
    assert spl.get("final_spl_authority") == "deterministic_postprocessor"
    assert spl.get("normalized_spl") is False
    assert spl.get("review_only_spl_postprocessor_trace")


def test_coe_index_resolution_trace_fields(
    spl_authoring_flags: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", False)
    payload = build_live_chat_response(ChatRequest(message=_WEEKEND_QUERY)).model_dump(mode="json")
    post = (payload.get("candidate_spl") or {}).get("review_only_spl_postprocessor_trace") or {}
    assert post.get("index_resolution_source") == "source_profile_resolver"
    assert post.get("placeholder_used") is False
    assert post.get("resolved_index") == "pgcil_soc"
