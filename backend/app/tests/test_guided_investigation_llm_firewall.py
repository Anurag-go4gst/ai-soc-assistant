"""Guided investigation LLM budget + firewall coordinated query regressions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.answer_guard.rules import guard_priority_enum
from app.chat.pipeline import build_live_chat_response
from app.chat.signal_class_guidance import build_signal_class_guidance, classify_signal_class
from app.config import settings
from app.graph.chat_workflow import run_chat_via_langgraph
from app.llm.guided_llm_budget import should_skip_intent_advisor_for_guided
from app.schemas.requests import ChatRequest
from app.schemas.responses import AnalystResponseEnvelope
from app.synthesis.governed_answer_composer import GovernedComposerResult

_FIREWALL_COORDINATED_QUERY = (
    "We have more than 5,000 firewall blocks in the last hour and a successful breach "
    "on an internal server account — summarize top offenders and assess whether this "
    "looks coordinated."
)
_ALERT_SUMMARY = "summarize alert ALT-123"
_KNOWLEDGE = "explain firewall deny SOP"
_BLOCK_IP = "Block IP 10.0.0.5 immediately"
_OT_QUERY = (
    "Investigate unauthorized Modbus TCP register writes on substation RTU-12 overnight"
)


@pytest.fixture(autouse=True)
def _base_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_hybrid_investigation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_answer_guard_lab_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)


def test_skip_intent_advisor_when_guided_route_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    skip, _reason = should_skip_intent_advisor_for_guided(
        routed_skill="guided_investigation",
        query_signals={"security_log_aggregation_investigation": True},
    )
    assert skip is False
    monkeypatch.setattr(settings, "ai_soc_guided_llm_enabled", True)
    skip, reason = should_skip_intent_advisor_for_guided(
        routed_skill="guided_investigation",
        query_signals={"security_log_aggregation_investigation": True},
    )
    assert skip is True
    assert reason == "guided_route_locked_skip_intent_advisor"


def test_firewall_query_uses_firewall_aggregation_not_ot() -> None:
    assert classify_signal_class(_FIREWALL_COORDINATED_QUERY) == "firewall_aggregation"
    body = build_signal_class_guidance(_FIREWALL_COORDINATED_QUERY)
    assert "firewall aggregation" in body.lower()
    assert "IT-to-OT" not in body


def test_guard_priority_enum_allows_not_assigned_severity_shape() -> None:
    findings = guard_priority_enum(
        {
            "severity_label": None,
            "severity_status": "not_assigned",
            "severity_explanation": "Not assigned from this question alone",
        }
    )
    assert all(item.status == "pass" for item in findings)


def test_firewall_guided_llm_success_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_llm_enabled", True)
    composed = (
        "Firewall deny spike review (last hour): prioritize top blocked source IPs, "
        "destination IPs, ports/actions, and overlap with the breached internal server "
        "account. Treat coordinated activity as a hypothesis until corroborated across "
        "firewall, DNS/proxy, and endpoint metadata."
    )
    envelope = AnalystResponseEnvelope(
        direct_answer_summary=composed,
        one_sentence_finding=composed[:200],
        investigation_steps=[
            "Rank top blocked source IPs and destination IPs for the last hour.",
            "Compare deny spike timing to the breached internal server account activity.",
        ],
    )

    def _mock_compose(**_kwargs):  # noqa: ANN003
        return GovernedComposerResult(
            envelope=envelope,
            llm_composer_enabled=True,
            llm_composer_used=True,
            llm_guard_status="passed",
            llm_fallback_used=False,
        )

    with patch("app.chat.pipeline.compose_governed_answer", side_effect=_mock_compose):
        payload = build_live_chat_response(ChatRequest(message=_FIREWALL_COORDINATED_QUERY)).model_dump(
            mode="json"
        )

    assert payload["selected_skill"] == "guided_investigation"
    trace = payload.get("control_plane_trace") or {}
    composer = trace.get("llm_composer") or {}
    assert composer.get("guided_llm_required") is True
    assert composer.get("guided_llm_used") is True
    assert composer.get("deterministic_guided_fallback") is False
    text = str(payload.get("message") or "") + str(
        (payload.get("analyst_response") or {}).get("direct_answer_summary") or ""
    )
    assert "firewall" in text.lower()
    assert "top" in text.lower() or "blocked" in text.lower()
    assert "IT-to-OT" not in text
    guard = trace.get("answer_guard") or {}
    assert guard.get("guard_status") != "blocked"
    rc = payload.get("run_contract") or {}
    assert rc.get("mcp_allowed") is False
    assert rc.get("execution_authorized") is False


def test_firewall_guided_llm_timeout_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_llm_enabled", True)

    def _mock_compose(**_kwargs):  # noqa: ANN003
        return GovernedComposerResult(
            envelope=_kwargs["fallback_envelope"],
            llm_composer_enabled=True,
            llm_composer_used=False,
            llm_guard_status="skipped",
            llm_fallback_used=True,
            llm_blocked_reason="url_error:timeout",
        )

    with patch("app.chat.pipeline.compose_governed_answer", side_effect=_mock_compose):
        payload = build_live_chat_response(ChatRequest(message=_FIREWALL_COORDINATED_QUERY)).model_dump(
            mode="json"
        )

    trace = payload.get("control_plane_trace") or {}
    composer = trace.get("llm_composer") or {}
    assert composer.get("guided_llm_required") is True
    assert composer.get("guided_llm_degraded_fallback") is True
    assert composer.get("guided_llm_timeout") is True
    text = str(payload.get("message") or "") + str(
        (payload.get("analyst_response") or {}).get("direct_answer_summary") or ""
    )
    assert "Guided investigation requires the local LLM planner" in text
    assert "No live telemetry was queried" in text
    rc = payload.get("run_contract") or {}
    assert rc.get("mcp_allowed") is False
    assert rc.get("execution_authorized") is False


def test_routing_regressions_unchanged() -> None:
    alert = build_live_chat_response(ChatRequest(message=_ALERT_SUMMARY))
    assert alert.selected_skill == "alert_summary"

    knowledge = build_live_chat_response(ChatRequest(message=_KNOWLEDGE))
    assert knowledge.selected_skill == "knowledge_recall"

    block = build_live_chat_response(ChatRequest(message=_BLOCK_IP))
    assert block.human_review is not None
    assert block.human_review.reason == "unsafe_action_blocked"

    ot_body = build_signal_class_guidance(_OT_QUERY)
    assert "modbus" in ot_body.lower() or "protocol" in ot_body.lower()

    fw = build_signal_class_guidance(_FIREWALL_COORDINATED_QUERY)
    assert "IT-to-OT" not in fw


def test_langgraph_firewall_skips_intent_advisor_when_guided_llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_guided_llm_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")

    with patch("app.chat.pipeline.compose_governed_answer") as mock_compose:
        mock_compose.return_value = GovernedComposerResult(
            envelope=AnalystResponseEnvelope(direct_answer_summary="mock guided"),
            llm_composer_enabled=True,
            llm_composer_used=True,
            llm_guard_status="passed",
            llm_fallback_used=False,
        )
        response = run_chat_via_langgraph(ChatRequest(message=_FIREWALL_COORDINATED_QUERY))

    trace = response.control_plane_trace or {}
    scheduling = (trace.get("query_to_intent") or {}).get("llm_intent_advisory") or {}
    if isinstance(scheduling, dict):
        sched_trace = scheduling.get("scheduling_trace") or {}
        assert sched_trace.get("intent_advisor_skip_policy") in {
            "guided_route_locked_skip_intent_advisor",
            "guided_hunt_deterministic_routing",
        }
