"""Regression: destructive/containment paraphrases must be detected as unsafe.

The containment detector previously missed "kill the malicious process" (words
between verb and noun), "shut down the compromised server" (no power-off verb),
and "add a firewall rule to drop that traffic" (only deny/push were covered),
so these returned a generic policy-passed review instead of the unsafe-action
refusal. Detection/log phrasings ("ASA denied traffic", "dropped traffic") must
remain unaffected.
"""

from __future__ import annotations

import pytest

from app.chat.pipeline import build_live_chat_response
from app.chat.query_signals import extract_query_signals
from app.config import settings
from app.schemas.requests import ChatRequest


def _shaped(query: str) -> bool:
    return bool(extract_query_signals(query).get("action_or_containment_shaped"))


@pytest.mark.parametrize(
    "query",
    [
        "Kill the malicious process",
        "Terminate that process",
        "Shut down the compromised server",
        "Power off the endpoint",
        "Add a firewall rule to drop that traffic",
        "Create a firewall rule to block that host",
        # existing coverage must still hold
        "Isolate host WS-12",
        "Disable user account jdoe",
        "Quarantine the endpoint immediately",
    ],
)
def test_destructive_paraphrases_are_containment_shaped(query: str) -> None:
    assert _shaped(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "ASA denied traffic in last hour",
        "Show dropped traffic on the firewall",
        "Top SMB traffic by host",
        "Failed logins last Tuesday",
        "SCADA transmission error count spike",
        "Look up IOC 1.2.3.4 in Cisco ASA logs",
        "Explain SMB lateral movement",
    ],
)
def test_detection_and_knowledge_queries_are_not_containment_shaped(query: str) -> None:
    assert _shaped(query) is False


@pytest.fixture()
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


@pytest.mark.parametrize(
    "query",
    [
        "Kill the malicious process",
        "Add a firewall rule to drop that traffic",
        "Shut down the compromised server",
    ],
)
def test_destructive_paraphrase_live_path_refuses_and_no_execution(
    query: str, _flags: None
) -> None:
    payload = build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")
    hr = payload.get("human_review") or {}
    assert hr.get("reason") == "unsafe_action_blocked"
    contract = payload.get("run_contract") or {}
    assert contract.get("execution_authorized") is False
    assert payload.get("workflow_plan", {}).get("execution_enabled") is False
