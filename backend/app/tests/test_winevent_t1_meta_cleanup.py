"""Batch E — Winevent off-shift framing + T1 SPL-native meta cleanliness."""

from __future__ import annotations

import pytest

from app.chat.network_boundary_display import (
    is_firewall_boundary_query,
    is_windows_identity_logon_query,
)
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import build_draft_preview
from app.tests.support.chat_visible import spl_from_payload, visible_from_payload

_WINEVENT_OFF_SHIFT = (
    "Run a Splunk search on the wineventlog index for Event ID 4624 (Successful Logon) "
    "originating from substation subnets outside normal shift hours."
)
_GENERIC_SPL_META = "Generate SPL for failed logins"

_FORBIDDEN_LIVE = (
    "currently showing",
    "we found in splunk",
    "observed in splunk",
    "execution: executed",
    "mock mcp execution complete",
    "live-backed",
)

_GATE_FIELDS = (
    "collected_evidence_count",
    "allow_severity_assessment",
    "allow_results_table",
    "allow_mitre_mapping",
    "allow_live_result_language",
    "execution_authorized",
)


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def _chat_payload(query: str) -> dict:
    return build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")


def _assert_gate_review_only(payload: dict) -> None:
    gate = (payload.get("structured_context") or {}).get("final_evidence_gate") or {}
    contract = payload.get("run_contract") or {}
    assert gate and contract
    for field in _GATE_FIELDS:
        if field in gate and field in contract:
            assert gate[field] == contract[field], field
    assert contract.get("execution_authorized") is False
    assert contract.get("allow_live_result_language") is False
    msg = str(payload.get("message") or "").lower()
    for phrase in _FORBIDDEN_LIVE:
        assert phrase not in msg, phrase


def test_winevent_off_shift_is_not_firewall_boundary_query() -> None:
    assert is_windows_identity_logon_query(_WINEVENT_OFF_SHIFT)
    assert is_firewall_boundary_query(_WINEVENT_OFF_SHIFT) is False


def test_winevent_answer_framing_avoids_it_to_ot_boundary() -> None:
    payload = _chat_payload(_WINEVENT_OFF_SHIFT)
    visible = visible_from_payload(payload).lower()
    assert "it-to-ot" not in visible
    assert "firewall boundary" not in visible
    assert "windows logon" in visible or "off-shift" in visible or "off shift" in visible
    spl = spl_from_payload(payload)
    assert "index=wineventlog" in spl
    assert "login_hour" in spl
    assert "login_hour < 6" in spl and "login_hour >= 22" in spl


def test_winevent_trace_includes_fixed_off_shift_constraint() -> None:
    preview = build_draft_preview(_WINEVENT_OFF_SHIFT, live_data_request=True)
    assert preview is not None
    ucb = preview.get("user_constraint_bindings") or {}
    trace = ucb.get("debug_trace", {}).get("shift_hour_binding_trace") or {}
    assert trace.get("status") == "fixed_off_shift_hour_constraint_applied"

    payload = _chat_payload(_WINEVENT_OFF_SHIFT)
    ep = (payload.get("control_plane_trace") or {}).get("evidence_plan") or {}
    slot_summary = ep.get("normalized_slot_summary") or {}
    ep_trace = slot_summary.get("shift_hour_binding_trace") or {}
    assert ep_trace.get("status") == "fixed_off_shift_hour_constraint_applied"


def test_winevent_run_contract_gate_alignment() -> None:
    payload = _chat_payload(_WINEVENT_OFF_SHIFT)
    _assert_gate_review_only(payload)
    cs = payload.get("candidate_spl") or {}
    assert cs.get("execution_eligible") is False
    contract = payload.get("run_contract") or {}
    assert contract.get("mcp_allowed") is False


def test_generic_spl_meta_routes_soc_generate_spl() -> None:
    payload = _chat_payload(_GENERIC_SPL_META)
    use_case = (payload.get("selected_use_case") or {}).get("use_case_id")
    assert use_case == "soc_generate_spl"
    assert payload.get("selected_skill") == "spl_generation"
    trace = payload.get("control_plane_trace") or {}
    ra = trace.get("route_adjudication") or {}
    assert ra.get("row_authority_decision") == "catalog_t1_spl_native"


def test_generic_spl_meta_answer_is_review_only_with_clean_metadata() -> None:
    payload = _chat_payload(_GENERIC_SPL_META)
    _assert_gate_review_only(payload)
    visible = visible_from_payload(payload).lower()
    assert "t1 spl-generation review" in visible or "lab draft" in visible
    assert "not executed" in visible or "not performed" in visible
    assert "exact_105" not in visible and "t0 exact" not in visible
    cs = payload.get("candidate_spl") or {}
    assert cs.get("execution_eligible") is False
    contract = payload.get("run_contract") or {}
    routing = contract.get("routing") or {}
    assert routing.get("authority_holder") == "canonical_run_contract"
    assert routing.get("canonical_skill") == "spl_generation"
