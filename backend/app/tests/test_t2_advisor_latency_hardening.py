"""T2 / out-of-registry advisor latency hardening regressions."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.chat.pipeline import (
    _FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS,
    _compute_turn_deadline_for_state,
    build_live_chat_response,
    graph_node_query_to_intent,
)
from app.config import settings
from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph
from app.llm.sidecar_governance import run_sidecar_llm_with_timeout
from app.llm.t2_advisory_latency_policy import t2_intent_advisor_bound_seconds
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding
from app.schemas.requests import ChatRequest

_Q046 = "Which users have excessive failed logins?"
_SCADA = "SCADA analog threshold breach on substation sensors"
_CISCO_IOC = "Look up IOC 1.2.3.4 in Cisco ASA logs"
_GENERIC_SPL = "Write me a SPL query for failed logins"
_GUIDED = "Hunt for CI/CD supply-chain compromise indicators across our environment"
_BLOCK_IP = "Block IP 10.0.0.5 immediately"


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_t2_intent_advisor_bound_seconds", 25.0)
    monkeypatch.setattr(settings, "ai_soc_llm_t2_turn_deadline_seconds", 45.0)


def _payload(question: str) -> dict:
    return build_live_chat_response(ChatRequest(message=question)).model_dump(mode="json")


def _intent_node(question: str) -> LLMIntentAdvisory:
    qu = understand_query(question)
    route, _ = select_route_from_understanding(qu, question)
    state = graph_node_query_to_intent(
        {
            "request": ChatRequest(message=question),
            "effective_query": question,
            "query_understanding": qu,
            "routed": {"skill": route["skill"]},
        }
    )
    return state["llm_intent_advisory"]


def _slow_provider() -> str:
    time.sleep(60)
    return "{}"


@pytest.mark.parametrize(
    "question",
    [_SCADA, _CISCO_IOC, _GENERIC_SPL],
)
def test_t2_intent_advisor_hop_is_bounded(question: str, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, float | None] = {}

    def _fake_advisor(*_args, timeout_seconds=None, **_kwargs):
        captured["timeout_seconds"] = timeout_seconds
        return LLMIntentAdvisory(llm_called=True, dropped_reasons=["test_advisory_called"])

    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", _fake_advisor)
    advisory = _intent_node(question)
    assert advisory.llm_called is True
    assert captured["timeout_seconds"] is not None
    assert captured["timeout_seconds"] <= t2_intent_advisor_bound_seconds()
    trace = advisory.scheduling_trace or {}
    assert trace.get("intent_advisor_bound_reason") == "t2_review_only_advisory_bounded"
    assert trace.get("llm_advisory_budget_ms") == int(t2_intent_advisor_bound_seconds() * 1000)


def test_t2_slow_advisor_times_out_under_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_t2_intent_advisor_bound_seconds", 0.15)

    def _provider():
        return run_sidecar_llm_with_timeout(_slow_provider, timeout_seconds=0.15)

    monkeypatch.setattr(
        "app.chat.llm_intent_advisor.invoke_sidecar_role",
        lambda **_: (None, True, "test-local"),
    )
    started = time.monotonic()
    advisory = _intent_node(_SCADA)
    elapsed = time.monotonic() - started
    assert elapsed < 5.0
    assert "llm_timed_out" in advisory.dropped_reasons
    trace = advisory.scheduling_trace or {}
    assert trace.get("llm_advisory_timed_out") is True
    assert trace.get("advisory_classification_source") == "deterministic_fallback_after_timeout"


def test_t2_review_only_response_under_slow_advisor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_t2_intent_advisor_bound_seconds", 0.15)
    monkeypatch.setattr(
        "app.chat.llm_intent_advisor.invoke_sidecar_role",
        lambda **_: (None, True, "test-local"),
    )
    started = time.monotonic()
    payload = _payload(_SCADA)
    elapsed = time.monotonic() - started
    assert elapsed < 30.0
    spl = (payload.get("candidate_spl") or {}).get("candidate_spl") or ""
    assert len(spl) > 40
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False


def test_guided_investigation_stays_fast_under_slow_spl_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")

    def _hang(**_kwargs):  # noqa: ANN003
        time.sleep(60)
        return None

    with patch("app.spl.llm_plan_compiler.generate_llm_spl_via_plan", side_effect=_hang):
        started = time.monotonic()
        response = run_chat_via_resource_planner_graph(ChatRequest(message=_GUIDED))
        elapsed = time.monotonic() - started

    assert elapsed < 30.0
    assert response.selected_skill == "guided_investigation"
    assert (response.run_contract or {}).get("execution_authorized") is False


def test_q046_frozen_t0_keeps_sharp_bound_not_t2_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, float | None] = {}

    def _fake_advisor(*_args, timeout_seconds=None, **_kwargs):
        captured["timeout_seconds"] = timeout_seconds
        return LLMIntentAdvisory(llm_called=True)

    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", _fake_advisor)
    advisory = _intent_node(_Q046)
    assert captured["timeout_seconds"] is not None
    assert captured["timeout_seconds"] <= _FROZEN_T0_INTENT_ADVISOR_BOUND_SECONDS
    trace = advisory.scheduling_trace or {}
    assert trace.get("intent_advisor_bound_reason") == "exact_template_bound_intent_advisor_bounded"


def test_q046_contract_unchanged() -> None:
    hil = (_payload(_Q046).get("human_review") or {})
    assert hil.get("review_type") == "spl_revision"
    assert hil.get("reason") == "template_review_required"


def test_unsafe_block_ip_still_blocked_under_slow_advisor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_t2_intent_advisor_bound_seconds", 0.15)
    monkeypatch.setattr(
        "app.chat.llm_intent_advisor.invoke_sidecar_role",
        lambda **_: (None, True, "test-local"),
    )
    payload = _payload(_BLOCK_IP)
    hr = payload.get("human_review") or {}
    assert hr.get("reason") == "unsafe_action_blocked"
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False


def test_fast_advisory_still_used_when_within_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    advisory_payload = {
        "intent_family_candidate": "spl_generation_only",
        "use_case_id_candidate": "soc_generate_spl",
        "confidence_metadata": {"confidence": 0.9},
    }

    def _fast_advisor(*_args, **_kwargs):
        return LLMIntentAdvisory.model_validate({**advisory_payload, "llm_called": True})

    monkeypatch.setattr("app.chat.pipeline.generate_llm_intent_advisory", _fast_advisor)
    advisory = _intent_node(_GENERIC_SPL)
    assert advisory.intent_family_candidate == "spl_generation_only"
    trace = advisory.scheduling_trace or {}
    assert trace.get("llm_advisory_status") in {"completed", "skipped"}


def test_t2_turn_deadline_capped_for_out_of_registry() -> None:
    qu = understand_query(_SCADA)
    route, _ = select_route_from_understanding(qu, _SCADA)
    deadline = _compute_turn_deadline_for_state(
        qu,
        {"skill": route["skill"], "routing_provenance": {"deterministic_match_path": qu.deterministic_match_path}},
    )
    assert deadline <= float(settings.ai_soc_llm_t2_turn_deadline_seconds)


def test_advisory_trace_surfaces_latency_fields_on_live_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.chat.llm_intent_advisor.invoke_sidecar_role",
        lambda **_: (None, True, "test-local"),
    )
    monkeypatch.setattr(settings, "ai_soc_llm_t2_intent_advisor_bound_seconds", 0.15)
    payload = _payload(_CISCO_IOC)
    advisory = (payload.get("control_plane_trace") or {}).get("llm_advisory_trace") or {}
    assert advisory.get("llm_advisory_timed_out") is True
    assert advisory.get("intent_advisor_bound_reason") == "t2_review_only_advisory_bounded"
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False
