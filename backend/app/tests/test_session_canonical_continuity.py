"""Plan 8 O1 — session pins carry redacted RQC/outcome for Phase 1 follow-up."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.chat.contracts.resolved_query import ResolvedQueryContract
from app.chat.resolved_query_builder import apply_session_continuity, attach_understanding_authority
from app.chat.session_context import pins_from_pipeline_state, resolve_session_context
from app.chat.session_store import SessionPins, clear_all_session_pins_for_tests, save_session_pins
from app.config import settings
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse


@pytest.fixture(autouse=True)
def _enable_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    clear_all_session_pins_for_tests()


def test_pins_store_redacted_rqc_and_outcome_refs() -> None:
    response = PlaceholderResponse(
        trace_id="t-o1",
        message="ok",
        note="ok",
        user_query="Check failed VPN admin logins from Germany yesterday.",
        selected_skill="attack_discovery",
    )
    pins = pins_from_pipeline_state(
        session_id="sess-o1",
        trace_id="t-o1",
        response=response,
        state={
            "resolved_query_contract": {
                "intent_family": "live_investigation",
                "answer_goal": "live_results",
                "entities": {"user": "admin", "event_type": ["vpn"]},
                "time_scope": "-24h",
                "clarification_required": False,
                "required_capabilities": ["mcp"],
            },
            "investigation_outcome": {
                "disposition": "inconclusive",
                "evidence_refs": ["ev1"],
                "missing_evidence": ["host"],
                "provenance": {"trace_id": "t-o1"},
            },
            "evidence_state": {"obtained": ["mcp"]},
            "evidence_plan": {"resource_plan": {"provenance": {"resource_plan_id": "rp:1"}}},
        },
    )
    assert pins.last_rqc_redacted["entities"]["user"] == "admin"
    assert pins.last_rqc_redacted["time_scope"] == "-24h"
    assert pins.last_investigation_outcome_ref["disposition"] == "inconclusive"
    assert "mcp" in pins.last_evidence_refs
    assert pins.last_plan_identity["resource_plan_id"] == "rp:1"
    assert pins.last_evidence_scope["time_scope"] == "-24h"


def test_generic_what_about_uses_prior_rqc_not_phrase_catalogue() -> None:
    save_session_pins(
        SessionPins(
            session_id="sess-delta",
            last_trace_id="t-prior",
            last_entities={"user": "admin"},
            last_rqc_redacted={"intent_family": "live_investigation", "entities": {"user": "admin"}},
            last_investigation_outcome_ref={"disposition": "inconclusive"},
            last_plan_identity={"trace_id": "t-prior"},
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    resolution = resolve_session_context(
        ChatRequest(message="What about service accounts?", session_id="sess-delta")
    )
    assert resolution.follow_up_kind == "scope_delta"
    assert resolution.status.used_previous_context is True
    assert "last_rqc_redacted" in resolution.status.used_fields
    assert resolution.effective_query == "What about service accounts?"
    assert resolution.apply_use_case_id is None


def test_scope_delta_retains_prior_rqc_and_replaces_account_class() -> None:
    original = attach_understanding_authority(
        ResolvedQueryContract(
            normalized_goal="What about service accounts?",
            intent_family="clarification_required",
            answer_goal="clarification",
            ambiguity_state="clarification_required",
            clarification_required=True,
            clarification_reason="underspecified follow-up",
            qualification_tier="T4",
            qualification_source="out_of_registry",
            confidence=0.2,
            entities={},
        )
    )
    merged = apply_session_continuity(
        original,
        prior_rqc={
            "intent_family": "live_investigation",
            "answer_goal": "live_results",
            "time_scope": "-24h",
            "entities": {"user": ["admin"], "event_type": ["vpn"], "geo": "Germany"},
        },
        delta_remainder="service accounts",
        follow_up_kind="scope_delta",
    )
    assert merged.intent_family == "live_investigation"
    assert merged.clarification_required is False
    assert merged.time_scope == "-24h"
    assert merged.entities["event_type"] == ["vpn"]
    assert merged.entities["geo"] == "Germany"
    assert merged.entities["account_type"] == "service_account"
    assert merged.entities.get("user") in (None, [], {})
    assert merged.provenance["session_continuity"] == "scope_delta"
    assert "spl" in merged.required_capabilities or "mcp" in merged.required_capabilities
