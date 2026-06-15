"""LLM endpoint health ping — green / red / wired_disabled + caching."""

from __future__ import annotations

import app.llm.endpoint_health as eh
from app.config import settings
from app.llm.clients.endpoint_resolver import ResolvedEndpoint


def _endpoint(label: str) -> ResolvedEndpoint:
    return ResolvedEndpoint(label=label, base_url="http://x/v1", model="m", api_key="", timeout_seconds=5)


def test_qwen_wired_disabled_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", False)
    monkeypatch.setattr(eh, "resolve_local_primary_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_foundation_sec_instruct_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_foundation_sec_reasoning_endpoint", lambda **_: None)
    payload = eh.llm_endpoint_health(force=True)
    qwen = next(e for e in payload["endpoints"] if e["role"] == "qwen_primary")
    assert qwen["status"] == eh.STATUS_WIRED_DISABLED
    assert "disabled" in qwen["detail"].lower()


def test_local_primary_green_when_reachable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", False)
    monkeypatch.setattr(eh, "resolve_local_primary_endpoint", lambda **_: _endpoint("local_primary"))
    monkeypatch.setattr(eh, "resolve_foundation_sec_instruct_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_foundation_sec_reasoning_endpoint", lambda **_: None)
    monkeypatch.setattr(
        eh, "_probe",
        lambda endpoint: eh.EndpointHealth(role="", label=endpoint.label, status=eh.STATUS_GREEN, latency_ms=7),
    )
    payload = eh.llm_endpoint_health(force=True)
    assert payload["overall"] == eh.STATUS_GREEN
    local = next(e for e in payload["endpoints"] if e["role"] == "local_primary")
    assert local["status"] == eh.STATUS_GREEN and local["latency_ms"] == 7
    assert payload["expected_latency_hint"]


def test_overall_red_when_active_endpoints_down(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", False)
    monkeypatch.setattr(eh, "resolve_local_primary_endpoint", lambda **_: _endpoint("local_primary"))
    monkeypatch.setattr(eh, "resolve_foundation_sec_instruct_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_foundation_sec_reasoning_endpoint", lambda **_: None)
    monkeypatch.setattr(
        eh, "_probe",
        lambda endpoint: eh.EndpointHealth(role="", label=endpoint.label, status=eh.STATUS_RED, detail="URLError"),
    )
    payload = eh.llm_endpoint_health(force=True)
    assert payload["overall"] == eh.STATUS_RED


def test_qwen_red_when_enabled_but_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", True)
    monkeypatch.setattr(eh, "resolve_qwen_primary_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_local_primary_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_foundation_sec_instruct_endpoint", lambda **_: None)
    monkeypatch.setattr(eh, "resolve_foundation_sec_reasoning_endpoint", lambda **_: None)
    payload = eh.llm_endpoint_health(force=True)
    qwen = next(e for e in payload["endpoints"] if e["role"] == "qwen_primary")
    assert qwen["status"] == eh.STATUS_RED
