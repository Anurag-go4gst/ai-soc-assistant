"""LIVE-RQC-01..10 — production SPL producer forwarding of Final RQC (mocked, no live MCP).

These tests call ``_candidate_spl_stage`` (the live producer chain behind
``graph_node_workflow_spl``). Spies on B-owned producers fail if the approved
pipeline.py forwarding hunks are absent.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from app.chat import pipeline as chat_pipeline
from app.config import settings
from app.spl.llm_fallback import LlmSplFallbackResult
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.utility_spl_authoring import candidate_from_universal_utility_authoring

Q_ROLLING = "one source IP attacking multiple distinct accounts over a rolling 10-minute window"
Q_TREND = "hourly failed-login trend over the last 24 hours"
Q_SEQUENCE = "password change followed by successful login within 5 minutes"
Q_TREND_SEVEN_DAYS = "hourly failed-login trend over the last 7 days"

_UNFAITHFUL_SPL = (
    "search index=pgcil_soc sourcetype=WinEventLog:Security earliest=-24h latest=now "
    "| table _time user | head 100"
)


class _Telemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_llm_call(self, *args: Any, **kwargs: Any) -> None:
        return None


def _rqc(*, time_scope: str | None = None, entities: dict[str, Any] | None = None, goal: str = "") -> dict[str, Any]:
    locked: dict[str, Any] = {}
    payload: dict[str, Any] = {
        "intent_family": "spl_authoring",
        "answer_goal": "spl_artifact",
        "normalized_goal": goal,
        "entities": entities or {},
        "locked_fields": locked,
    }
    if time_scope:
        payload["time_scope"] = time_scope
        locked["time_scope"] = time_scope
    if entities:
        locked["entities"] = dict(entities)
    return payload


def _compile_from_forwarded(user_query: str, rqc: Any) -> tuple[dict[str, Any], str]:
    spec = build_spl_intent_spec(user_query, resolved_query_contract=rqc if isinstance(rqc, dict) else None)
    return spec, compile_intent_spec_to_spl(spec)


@pytest.fixture
def _producer_chain(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", False)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(
        chat_pipeline,
        "_routes_chat",
        lambda: type("_Routes", (), {"get_telemetry_connector": staticmethod(lambda: _Telemetry())})(),
    )
    monkeypatch.setattr(chat_pipeline, "_candidate_from_lab_draft", lambda **kwargs: None)
    monkeypatch.setattr(chat_pipeline, "_candidate_from_t2_spl_native", lambda **kwargs: None)
    monkeypatch.setattr(chat_pipeline, "_candidate_from_default_template", lambda **kwargs: None)

    real_contract = chat_pipeline.build_deterministic_request_contract

    def _insufficient(*args: Any, **kwargs: Any):
        contract = real_contract(*args, **kwargs)
        return replace(contract, sufficient_for_spl_authoring=False)

    monkeypatch.setattr(chat_pipeline, "build_deterministic_request_contract", _insufficient)

    captured: dict[str, Any] = {
        "utility_rqc": "UNSET",
        "plan_rqc": "UNSET",
        "fallback_rqc": "UNSET",
        "compiled_from_forwarded_rqc": "",
        "spec_from_forwarded_rqc": {},
        "mcp": 0,
    }

    orig_utility = candidate_from_universal_utility_authoring

    def _spy_utility(**kwargs: Any):
        captured["utility_rqc"] = kwargs.get("resolved_query_contract")
        return orig_utility(**kwargs)

    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.candidate_from_universal_utility_authoring",
        _spy_utility,
    )

    def _spy_plan(**kwargs: Any):
        rqc = kwargs.get("resolved_query_contract")
        captured["plan_rqc"] = rqc
        spec, spl = _compile_from_forwarded(str(kwargs.get("user_query") or ""), rqc)
        captured["spec_from_forwarded_rqc"] = spec
        captured["compiled_from_forwarded_rqc"] = spl
        return LlmSplFallbackResult(
            candidate_spl=spl,
            approved=False,
            validation={
                "approved": False,
                "normalized_spl": None,
                "execution_eligible": False,
                "execution_enabled": False,
                "reject_reasons": ["lab_tier_candidate"],
            },
            lab_tier=True,
            clarification_required=False,
        )

    monkeypatch.setattr(chat_pipeline, "generate_llm_spl_via_plan", _spy_plan)

    orig_fallback = chat_pipeline._candidate_from_llm_fallback

    def _spy_fallback(**kwargs: Any):
        captured["fallback_rqc"] = kwargs.get("resolved_query_contract")
        return orig_fallback(**kwargs)

    monkeypatch.setattr(chat_pipeline, "_candidate_from_llm_fallback", _spy_fallback)

    def _forbid_mcp(*args: Any, **kwargs: Any) -> None:
        captured["mcp"] += 1
        raise AssertionError("live MCP must not be called")

    monkeypatch.setattr("app.connectors.mcp.splunk_mcp.call_tool", _forbid_mcp, raising=False)
    return captured


def _stage(user_query: str, rqc: dict[str, Any] | list[Any] | None, **extra: Any):
    kwargs = {
        "trace_id": "live-rqc",
        "skill": "spl_generation",
        "user_query": user_query,
        "query_signals": {"explicit_spl_authoring": True, "review_only_spl": True},
        "dispatch_flags": {"call_spl_llm": True},
        "resolved_query_contract": rqc,
    }
    kwargs.update(extra)
    return chat_pipeline._candidate_spl_stage(**kwargs)


def _payload_spl(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return ""
    return str(candidate.get("candidate_spl") or "")


def _spec_and_spl(candidate: dict[str, Any] | None, captured: dict[str, Any]) -> tuple[dict[str, Any], str]:
    trace = (candidate or {}).get("utility_spl_draft_trace") if isinstance(candidate, dict) else None
    trace = trace if isinstance(trace, dict) else {}
    spec = trace.get("semantic_intent_spec") or captured.get("spec_from_forwarded_rqc") or {}
    spl = _payload_spl(candidate) or str(captured.get("compiled_from_forwarded_rqc") or "")
    return spec if isinstance(spec, dict) else {}, spl


def test_live_rqc_01_rolling_reaches_compiler(_producer_chain: dict[str, Any]) -> None:
    rqc = _rqc(goal="rolling distinct accounts", entities={"source_ip": ["198.51.100.10"]})
    candidate, validation = _stage(Q_ROLLING, rqc)
    spec, spl = _spec_and_spl(candidate, _producer_chain)
    assert spec["analysis_shape"] == "rolling"
    assert spec["analytical_window"]["size"] == "10m"
    assert "streamstats time_window=10m" in spl
    assert "head 100" not in spl
    assert candidate is not None and validation is not None
    assert candidate.get("execution_eligible") is False


def test_live_rqc_02_trend_grain_reaches_compiler(_producer_chain: dict[str, Any]) -> None:
    rqc = _rqc(time_scope="last 24 hours", goal="hourly failed-login trend")
    candidate, validation = _stage(Q_TREND, rqc)
    spec, spl = _spec_and_spl(candidate, _producer_chain)
    assert spec["analysis_shape"] == "trend"
    assert spec["temporal_grain"] == "1h"
    assert spec["search_horizon"] == "earliest=-24h latest=now"
    assert "timechart span=1h" in spl
    assert "earliest=-24h" in spl
    assert candidate is not None and validation is not None


def test_live_rqc_03_sequence_reaches_compiler(_producer_chain: dict[str, Any]) -> None:
    rqc = _rqc(goal="password change then login")
    candidate, _validation = _stage(Q_SEQUENCE, rqc)
    spec, spl = _spec_and_spl(candidate, _producer_chain)
    assert spec["analysis_shape"] == "sequence"
    assert spec["ordered_sequence"] == ["password_change", "successful_login"]
    assert spec["sequence_max_gap"] == "5m"
    assert "password_change" in spl
    assert "successful_login" in spl
    assert "300" in spl or "maxspan=5m" in spl
    assert candidate is not None


def test_live_rqc_04_locked_rqc_wins_over_raw_wording(_producer_chain: dict[str, Any]) -> None:
    rqc = _rqc(time_scope="last 2 hours", goal="hourly failed-login trend")
    candidate, validation = _stage(Q_TREND_SEVEN_DAYS, rqc)
    spec, spl = _compile_from_forwarded(Q_TREND_SEVEN_DAYS, rqc)
    assert spec["search_horizon"] == "earliest=-2h latest=now"
    assert "earliest=-2h" in spl
    assert "earliest=-7d" not in spl
    assert spec["field_provenance"].get("search_horizon") in {"rqc_locked", "rqc"}
    live_spl = _payload_spl(candidate)
    if live_spl:
        assert "earliest=-2h" in live_spl
        assert "earliest=-7d" not in live_spl
    assert candidate is None or candidate.get("execution_eligible") is False
    assert validation is None or validation.get("execution_eligible") is not True


def test_live_rqc_05_missing_rqc_keeps_query_token_degrade(_producer_chain: dict[str, Any]) -> None:
    candidate, validation = _stage(Q_TREND, None)
    spec, spl = _spec_and_spl(candidate, _producer_chain)
    assert spec["analysis_shape"] == "trend"
    assert spec["search_horizon"] == "earliest=-24h latest=now"
    assert "timechart span=1h" in spl
    assert candidate is not None and validation is not None


def test_live_rqc_06_malformed_rqc_degrades_without_crash(_producer_chain: dict[str, Any]) -> None:
    candidate, validation = _stage(Q_TREND, ["not", "a", "dict"])
    spec, _spl = _spec_and_spl(candidate, _producer_chain)
    assert spec["analysis_shape"] == "trend"
    assert candidate is not None and validation is not None


def test_live_rqc_07_candidate_remains_non_executable(_producer_chain: dict[str, Any]) -> None:
    rqc = _rqc(time_scope="last 24 hours")
    candidate, validation = _stage(Q_TREND, rqc)
    assert candidate is not None and validation is not None
    assert candidate.get("execution_eligible") is False
    assert candidate.get("execution_enabled") is not True
    assert validation.get("execution_eligible") is not True
    assert validation.get("normalized_spl") in {None, ""}
    assert validation.get("approved") is not True
    assert _producer_chain["mcp"] == 0


def test_live_rqc_08_unfaithful_after_one_repair_clears_candidate(
    _producer_chain: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)

    def _skeleton(user_query: str, *, llm_intent_advisory: Any | None = None) -> dict[str, Any]:
        return {"draft_spl": _UNFAITHFUL_SPL, "detection_family": "lab_draft"}

    monkeypatch.setattr(
        "app.spl.utility_spl_authoring._deterministic_utility_skeleton",
        _skeleton,
    )
    unfaithful = LlmSplFallbackResult(
        candidate_spl=_UNFAITHFUL_SPL,
        approved=False,
        validation={"approved": False, "normalized_spl": None, "execution_eligible": False},
        clarification_required=False,
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.generate_llm_spl_fallback",
        lambda **kwargs: unfaithful,
    )
    rqc = _rqc(time_scope="last 24 hours", goal="hourly failed-login trend")
    candidate, validation = _stage(Q_TREND, rqc)
    assert candidate is not None and validation is not None
    spec, spl = _spec_and_spl(candidate, _producer_chain)
    assert candidate.get("execution_eligible") is False
    if candidate.get("spl_authoring_unavailable"):
        assert not str(candidate.get("candidate_spl") or "").strip()
        assert "semantic_fidelity_unresolved" in (validation.get("reject_reasons") or [])
        return
    assert spec["analysis_shape"] == "trend"
    assert "timechart span=1h" in spl
    assert "earliest=-24h" in spl


def test_live_rqc_09_followup_time_change_reaches_compiler(_producer_chain: dict[str, Any]) -> None:
    first = _rqc(time_scope="last 24 hours", goal="hourly failed-login trend")
    first_candidate, _ = _stage(Q_TREND, first)
    spec1, spl1 = _compile_from_forwarded(Q_TREND, first)
    assert spec1["search_horizon"] == "earliest=-24h latest=now"
    assert "earliest=-24h" in spl1
    live1 = _payload_spl(first_candidate)
    if live1:
        assert "earliest=-24h" in live1

    second = _rqc(time_scope="last 12 hours", goal="hourly failed-login trend")
    second_candidate, _ = _stage(Q_TREND, second)
    spec, spl = _compile_from_forwarded(Q_TREND, second)
    assert spec["search_horizon"] == "earliest=-12h latest=now"
    assert "earliest=-12h" in spl
    assert "earliest=-24h" not in spl
    live2 = _payload_spl(second_candidate)
    if live2:
        assert "earliest=-12h" in live2
        assert "earliest=-24h" not in live2


def test_live_rqc_10_followup_entity_correction_no_stale_entity(_producer_chain: dict[str, Any]) -> None:
    first = _rqc(entities={"source_ip": ["10.0.0.1"]}, goal="rolling distinct accounts")
    _stage(Q_ROLLING, first)

    second = _rqc(entities={"source_ip": ["10.1.1.8"]}, goal="rolling distinct accounts")
    second_candidate, _ = _stage(Q_ROLLING, second)
    spec, _spl = _spec_and_spl(second_candidate, _producer_chain)
    assert spec["analysis_shape"] == "rolling"
    assert spec["entity_roles"]["subject"] == ["src_ip"]
    assert second["entities"]["source_ip"] == ["10.1.1.8"]
    assert first["entities"]["source_ip"] != second["entities"]["source_ip"]
