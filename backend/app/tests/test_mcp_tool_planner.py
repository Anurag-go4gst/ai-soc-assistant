from __future__ import annotations

import json

import pytest

from app.connectors.mcp.mcp_tool_planner import (
    build_planner_prompts,
    plan_tool_chronology,
)
from app.llm.clients.local_chat_client import ChatResult, LocalChatError


class _FakeClient:
    """Stand-in for FailoverChatClient — returns a canned completion or raises."""

    def __init__(self, *, text: str | None = None, error: str | None = None) -> None:
        self._text = text
        self._error = error
        self.last_kwargs: dict | None = None

    def generate(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error is not None:
            raise LocalChatError(self._error)
        return ChatResult(text=self._text or "", model="fake", latency_ms=1, usage={}, answered_label="local_primary")


def test_prompt_lists_real_tools_and_blocks_saia() -> None:
    system, user = build_planner_prompts(
        "critical alerts", target_index="pgcil_soc", spl_approved=True, rbac_role="analyst"
    )
    assert "splunk_get_indexes" in system
    assert "splunk_run_query" in system
    # SAIA + user_list appear only in the BLOCKED line, never as selectable tools.
    assert "BLOCKED" in system
    assert "saia_generate_spl" in system
    assert "splunk_get_user_list" in system
    assert '"query": "critical alerts"' in user
    assert '"spl_approved": true' in user


def test_llm_proposal_is_reviewed_and_passes_response_format() -> None:
    good = json.dumps(
        {
            "tools": [
                "splunk_get_info",
                "splunk_get_indexes",
                "splunk_get_metadata",
                "splunk_get_index_info",
                "splunk_run_query",
            ],
            "reason": {},
            "excluded": {},
            "unservable": ["unpatched CVEs (no vulnerability tool)"],
        }
    )
    client = _FakeClient(text=good)
    out = plan_tool_chronology(
        "critical alerts with CVE",
        target_index="pgcil_soc",
        spl_approved=True,
        rbac_role="analyst",
        client=client,
    )
    assert out["approved_tools"][-1] == "splunk_run_query"
    assert out["planner"]["llm_called"] is True
    assert out["planner"]["llm_unservable"] == ["unpatched CVEs (no vulnerability tool)"]
    # response_format json_object must be passed to the model.
    assert client.last_kwargs["response_format"] == {"type": "json_object"}


def test_llm_proposed_blocked_tool_is_dropped_by_review() -> None:
    sneaky = json.dumps({"tools": ["splunk_get_indexes", "saia_generate_spl"], "unservable": []})
    out = plan_tool_chronology("x", spl_approved=False, client=_FakeClient(text=sneaky))
    assert "saia_generate_spl" not in out["approved_tools"]
    assert any(d["reason"] == "saia_conditional_blocked" for d in out["dropped"])


def test_unparseable_llm_output_falls_back_to_deterministic() -> None:
    out = plan_tool_chronology(
        "x", target_index="pgcil_soc", spl_approved=True, client=_FakeClient(text="sorry, here is a plan...")
    )
    assert out["planner"]["llm_error"] == "llm_output_unparseable"
    # deterministic default still produced a usable plan.
    assert out["approved_tools"][0] == "splunk_get_info"


def test_llm_transport_error_falls_back_to_deterministic() -> None:
    out = plan_tool_chronology(
        "x", target_index="pgcil_soc", spl_approved=True, client=_FakeClient(error="url_error:gaierror")
    )
    assert out["planner"]["llm_called"] is False
    assert out["planner"]["llm_error"] == "url_error:gaierror"
    assert out["approved_tools"][0] == "splunk_get_info"


def test_no_endpoint_uses_deterministic_default(monkeypatch) -> None:
    # client=None and no configured endpoint → build_planner_client returns None.
    monkeypatch.setattr(
        "app.connectors.mcp.mcp_tool_planner.build_planner_client", lambda: None
    )
    out = plan_tool_chronology("x", target_index="pgcil_soc", spl_approved=True)
    assert out["planner"]["llm_error"] == "no_planner_endpoint_configured"
    assert out["approved_tools"][-1] == "splunk_run_query"


def test_qwen_failover_flag_default_off(monkeypatch) -> None:
    from app.connectors.mcp.mcp_tool_planner import build_planner_client
    from app.config import settings

    # Default off: even if QWEN_* set, planner chain must not include qwen.
    monkeypatch.setattr(settings, "ai_soc_llm_planner_qwen_failover_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_local_base_url", "http://x:8081/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_local_model", "instruct")
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_primary_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_base_url", "http://q:8082/v1")
    monkeypatch.setattr(settings, "ai_soc_llm_qwen_model", "qwen")
    client = build_planner_client()
    labels = [label for label, _ in client.chain]
    assert "qwen_primary" not in labels

    # Flag on: qwen appended as failover (after instruct primary, not first).
    monkeypatch.setattr(settings, "ai_soc_llm_planner_qwen_failover_enabled", True)
    client2 = build_planner_client()
    labels2 = [label for label, _ in client2.chain]
    assert "qwen_primary" in labels2
    assert labels2[0] != "qwen_primary"
