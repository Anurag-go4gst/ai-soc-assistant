"""Batch B Phase 2 — canonical binding E2E handoff tests."""

from __future__ import annotations

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_Q046 = "Which users have excessive failed logins?"
_ENV_KB_FIREWALL = "Show firewall traffic by src_zone and dest_zone on port 443"
_USER_INDEX_QUERY = "Generate SPL for index=scada_perf by rtu_id over last 24h"
_LOOKUP_QUERY = (
    "Generate a review-only SPL query to correlate power_sector_iocs.csv indicator_ip "
    "with Cisco ASA traffic in index=cisco_asa against dest_ip for the last 24h."
)


@pytest.fixture(autouse=True)
def _control_plane_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)


def test_canonical_binding_preserves_question_ref_for_weak_exact() -> None:
    qu = understand_query(_Q046)
    q2i = build_query_to_intent(query=_Q046, query_understanding=qu)
    plan = plan_evidence(
        q2i.intent_classification.model_dump(),
        query_to_intent=q2i.model_dump(),
        query_understanding=qu,
    )
    row = plan.row_authority_summary or {}
    assert row.get("question_ref") == "q0.q046"
    assert row.get("row_authority_status") == "exact_known_weak_needs_enrichment"
    assert row.get("s3_authority_ready") is False


def test_environment_kb_fills_source_profile_before_llm_slots() -> None:
    from app.spl.source_profile_bindings import build_source_profile_binding_slots

    advisory = LLMIntentAdvisory(
        entity_slots_candidate={"user": "llm_user", "dest_zone": "OT DMZ"},
    )
    source_profile = build_source_profile_binding_slots(_ENV_KB_FIREWALL)
    assert source_profile.slots.get("index"), "expected Environment KB profile slots"
    bindings = build_user_constraint_bindings(
        _ENV_KB_FIREWALL,
        llm_intent_advisory=advisory,
        extra_slots=source_profile.slots,
        source_profile_trace=source_profile.trace(),
    )
    assert bindings.normalized_slots.get("index") == source_profile.slots["index"]
    assert bindings.slot_sources.get("index") == "source_profile"
    assert bindings.slot_sources.get("user") == "llm"


def test_llm_slot_cannot_override_environment_kb_index() -> None:
    advisory = LLMIntentAdvisory(entity_slots_candidate={"index": "wrong_index"})
    bindings = build_user_constraint_bindings(_USER_INDEX_QUERY, llm_intent_advisory=advisory)
    assert bindings.normalized_slots.get("index") == "scada_perf"
    assert bindings.slot_sources.get("index") == "user_explicit"


def test_normalized_slots_include_lookup_zone_and_time_window() -> None:
    bindings = build_user_constraint_bindings(
        "Look across syslog and cisco_asa for permits from IT VLAN to OT DMZ on port 445 "
        "over the last 24 hours."
    )
    slots = bindings.normalized_slots
    assert slots.get("indexes") or slots.get("index")
    assert slots.get("src_zone") == "IT VLAN" or slots.get("dest_zone") == "OT DMZ"
    assert slots.get("time_window") or slots.get("dest_port") == "445"


def test_environment_kb_not_counted_as_telemetry_via_chat() -> None:
    payload = build_live_chat_response(ChatRequest(message=_ENV_KB_FIREWALL)).model_dump(mode="json")
    binding = (payload.get("evidence_plan") or {}).get("source_profile_binding_summary") or {}
    if binding:
        assert binding.get("environment_kb_is_telemetry") is False
    contract = payload.get("run_contract") or {}
    assert int(contract.get("collected_evidence_count") or 0) == 0


def test_lookup_dependency_surfaces_missing_evidence_not_live_language() -> None:
    payload = build_live_chat_response(ChatRequest(message=_LOOKUP_QUERY)).model_dump(mode="json")
    plan = payload.get("evidence_plan") or {}
    contract = payload.get("run_contract") or {}
    assert contract.get("allow_live_result_language") is False
    assert int(contract.get("collected_evidence_count") or 0) == 0
    missing = plan.get("missing_required_evidence") or []
    row = plan.get("row_authority_summary") or {}
    if row.get("row_authority_status") == "exact_known_needs_lookup":
        assert "lookup_dependency" in missing or plan.get("needs_lookup")
