"""Bundle-level RunContract regression tests (plan tests A–E)."""

from __future__ import annotations

import json

import pytest

from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import GENERIC_LIVE_DATA_FAMILY_ID

_SUBSTATION_QUERY = (
    "Show me all external connections or remote access sessions currently mapping "
    "to the substation networks."
)
_OT_GUIDANCE_QUERY = "How should SOC investigate repeated port 502 scans targeting OT PLCs?"
_VPN_QUERY = "Show me privileged VPN sessions from last night"

_FORBIDDEN_PREVIEW_PHRASES = (
    "guided investigation",
    "detected",
    "observed",
    "found",
    "currently showing",
    "mapped to",
)

_FORBIDDEN_EVIDENCE_CLAIMS = (
    "detected ot/protocol signals",
    "currently showing",
    "confirmed compromise",
)


def _run_chat(query: str) -> dict:
    return build_live_chat_response(ChatRequest(message=query)).model_dump(mode="json")


def _routing(payload: dict) -> dict:
    run_contract = payload.get("run_contract") or {}
    routing = run_contract.get("routing") or {}
    return routing if isinstance(routing, dict) else {}


def _run_contract(payload: dict) -> dict:
    contract = payload.get("run_contract") or {}
    return contract if isinstance(contract, dict) else {}


@pytest.fixture(autouse=True)
def _enable_control_plane_and_draft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


def test_bundle_a_substation_live_data() -> None:
    payload = _run_chat(_SUBSTATION_QUERY)
    routing = _routing(payload)
    contract = _run_contract(payload)

    assert routing.get("canonical_skill") == "spl_generation"
    assert routing.get("live_data_request") is True
    assert contract.get("execution_needed_for_answer") is True
    assert contract.get("mcp_needed_for_live_answer") is True
    assert contract.get("collected_evidence_count") == 0
    assert contract.get("effective_hil_required") is True

    action_cap = payload.get("action_capability") or {}
    assert action_cap.get("hil_required") is True

    analyst = payload.get("analyst_response") or {}
    assert not (analyst.get("splunk_results_table") or [])

    from app.chat.run_contract_builder import build_answer_preview
    from app.chat.contracts.run_contract import RunContract

    preview = build_answer_preview(RunContract.model_validate(contract))
    preview_lower = preview.lower()
    for phrase in _FORBIDDEN_PREVIEW_PHRASES:
        assert phrase not in preview_lower, f"forbidden preview phrase: {phrase!r}"


def test_bundle_b_ot_guidance() -> None:
    payload = _run_chat(_OT_GUIDANCE_QUERY)
    routing = _routing(payload)
    contract = _run_contract(payload)

    assert routing.get("guidance_request") is True
    assert routing.get("canonical_skill") == "guided_investigation"
    assert routing.get("live_data_request") is False
    assert contract.get("execution_needed_for_answer") is False


def test_bundle_c_vpn_generic_detection_family() -> None:
    payload = _run_chat(_VPN_QUERY)
    routing = _routing(payload)
    draft = payload.get("spl_draft_preview") or {}

    assert routing.get("canonical_skill") == "spl_generation"
    assert draft.get("detection_family") == GENERIC_LIVE_DATA_FAMILY_ID
    assert "esp_it_to_ot_connection" not in json.dumps(payload).lower()


def test_bundle_d_substation_strong_template_match() -> None:
    payload = _run_chat(_SUBSTATION_QUERY)
    draft = payload.get("spl_draft_preview") or {}

    assert draft.get("template_match_strength") == "strong"
    assert draft.get("detection_family") == "esp_it_to_ot_connection"


def test_bundle_e_no_false_evidence_claims() -> None:
    payload = _run_chat(_SUBSTATION_QUERY)
    blob = json.dumps(payload).lower()

    for phrase in _FORBIDDEN_EVIDENCE_CLAIMS:
        assert phrase not in blob, f"false evidence claim: {phrase!r}"

    analyst = payload.get("analyst_response") or {}
    assert not (analyst.get("splunk_results_table") or [])
