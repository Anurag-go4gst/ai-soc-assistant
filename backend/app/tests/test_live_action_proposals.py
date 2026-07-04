"""Item 6.2 — live action proposal attachment on /chat responses."""

from __future__ import annotations

import pytest

from app.actions.action_lane import get_action_lane_store
from app.actions.live_action_proposals import attach_live_action_proposals
from app.config import settings


@pytest.fixture(autouse=True)
def _clear_store():
    get_action_lane_store().clear()
    yield
    get_action_lane_store().clear()


def test_flag_off_returns_no_proposals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_action_lane_live_proposals_enabled", False)
    state = {
        "canonical_facts": {
            "schema_version": "v1",
            "authority_holder": "canonical_facts_spine",
            "facts": [
                {
                    "fact_id": "f1",
                    "kind": "executed_evidence",
                    "payload": {"evidence_id": "ev_1", "row_count": 1},
                    "provenance": {"node": "source_evidence", "evidence_class": "mcp_search"},
                }
            ],
        },
        "message": "Investigation summary",
        "severity_decision": {"severity_label": "High"},
    }
    assert attach_live_action_proposals(state, trace_id="tr_1") == []


def test_flag_on_emits_pending_create_ticket_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_action_lane_live_proposals_enabled", True)
    state = {
        "canonical_facts": {
            "schema_version": "v1",
            "authority_holder": "canonical_facts_spine",
            "facts": [
                {
                    "fact_id": "f1",
                    "kind": "executed_evidence",
                    "payload": {"evidence_id": "ev_abc", "row_count": 2},
                    "provenance": {"node": "source_evidence", "evidence_class": "mcp_search"},
                }
            ],
        },
        "analyst_response": {"one_sentence_finding": "Repeated failed logins observed"},
        "severity_decision": {"severity_label": "High"},
        "message": "fallback",
    }
    proposals = attach_live_action_proposals(state, trace_id="tr_2")
    assert len(proposals) == 1
    assert proposals[0]["status"] == "pending_approval"
    assert proposals[0]["tool_id"] == "action_tool:create_ticket"
    assert proposals[0]["payload"]["source_refs"] == ["ev_abc"]
