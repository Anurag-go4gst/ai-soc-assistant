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
    assert contract.get("execution_authorized") is False
    assert contract.get("allow_results_table") is False
    assert contract.get("collected_evidence_count") == 0
    assert contract.get("effective_hil_required") is True
    assert (payload.get("evidence_plan") or {}).get("needs_mcp") is True
    assert (payload.get("evidence_plan") or {}).get("mcp_allowed") is False

    action_cap = payload.get("action_capability") or {}
    assert action_cap.get("hil_required") is True

    analyst = payload.get("analyst_response") or {}
    assert not (analyst.get("splunk_results_table") or [])
    assert (payload.get("route_authority") or {}).get("authority_holder") == routing.get("authority_holder")
    # Dedicated review-only SPL renderer owns the answer shape: the review-only title
    # (em-dash, matching the RunContract answer preview) is the card heading and the
    # summary header carries the status block.
    assert analyst.get("finding_title") == "Review-only SPL draft — no live query was executed"
    summary = analyst.get("direct_answer_summary") or ""
    assert "Severity: Not assigned from this question alone" in summary
    assert "Execution: Not executed" in summary
    assert analyst.get("severity_label") == "Not assigned from this question alone"
    assert "```" not in (analyst.get("direct_answer_summary") or "")
    assert "search index=" not in (analyst.get("direct_answer_summary") or "").lower()
    assert not any(
        str(item).startswith(("P1", "P2", "P3"))
        for item in analyst.get("recommended_actions") or []
    )

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


def test_bundle_f_run_contract_gate4_required_fields_present() -> None:
    payload = _run_chat(_SUBSTATION_QUERY)
    contract = _run_contract(payload)
    routing = _routing(payload)

    for field in (
        "execution_status",
        "collected_evidence_count",
        "source_evidence_available",
        "allow_live_result_language",
        "allow_results_table",
        "effective_hil_required",
    ):
        assert field in contract
    for field in (
        "canonical_skill",
        "legacy_skill",
        "legacy_authoritative",
        "authority_holder",
    ):
        assert field in routing


@pytest.fixture
def _dispatch_v2_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)


def _dispatch_decision(payload: dict) -> dict:
    dispatch = payload.get("pipeline_dispatch") or {}
    if not dispatch:
        cpt = payload.get("control_plane_trace") or {}
        dispatch = cpt.get("pipeline_dispatch") if isinstance(cpt, dict) else {}
    dispatch = dispatch if isinstance(dispatch, dict) else {}
    decision = dispatch.get("decision") if isinstance(dispatch, dict) else {}
    return decision if isinstance(decision, dict) else {}


def test_bundle_dispatch_f_mitre_knowledge(_dispatch_v2_on: None) -> None:
    payload = _run_chat("Explain MITRE technique T1021 in the context of remote services")
    decision = _dispatch_decision(payload)
    stages = decision.get("stage_schedule") or []
    assert decision.get("request_mode") == "mitre_knowledge"
    assert "workflow_spl" not in stages
    assert "mitre_finalize" in stages


def test_bundle_dispatch_g_cve_review(_dispatch_v2_on: None) -> None:
    payload = _run_chat(
        "Review CVE-2024-1234 vulnerability exposure for VPN appliances without live scanning"
    )
    decision = _dispatch_decision(payload)
    stages = decision.get("stage_schedule") or []
    assert decision.get("request_mode") == "cve_review"
    assert "cve_adapter" in stages


def test_bundle_dispatch_h_sop_knowledge(_dispatch_v2_on: None) -> None:
    payload = _run_chat("What is the SOP for ransomware incident response?")
    decision = _dispatch_decision(payload)
    assert decision.get("request_mode") == "knowledge"
    assert decision.get("stage_schedule") == ["rag_early"]


def test_bundle_dispatch_i_spl_authoring_meta(_dispatch_v2_on: None) -> None:
    query = (
        "Generate SPL for outbound DNS volume spike by src_ip over last 24h "
        "for index=pgcil_soc sourcetype=dns"
    )
    payload = _run_chat(query)
    decision = _dispatch_decision(payload)
    assert decision.get("request_mode") in {"spl_authoring", "hybrid", "live_investigation"}
    assert "workflow_spl" in (decision.get("stage_schedule") or [])
    candidate = payload.get("candidate_spl") or {}
    trace = candidate.get("review_only_spl_postprocessor_trace") if isinstance(candidate, dict) else {}
    if isinstance(trace, dict) and trace:
        assert trace.get("postprocessor_evaluated") is True


def test_bundle_dispatch_j_hybrid_alert(_dispatch_v2_on: None) -> None:
    payload = _run_chat(
        "For alert ALT-2024-0891 (failed logins followed by a successful login from the same user "
        "in the last hour), what's the severity, MITRE mapping with status, and a governed SPL "
        "I can review—but not execute"
    )
    decision = _dispatch_decision(payload)
    stages = decision.get("stage_schedule") or []
    if decision.get("request_mode") == "hybrid":
        assert "workflow_spl" in stages
        assert "mitre_finalize" in stages
