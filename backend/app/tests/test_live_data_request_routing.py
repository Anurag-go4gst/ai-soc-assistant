"""Pattern-based routing invariants for live data retrieval vs guided rescue."""

from __future__ import annotations

import pytest

from app.chat.intent_classifier import build_query_to_intent
from app.chat.query_signals import extract_query_signals, is_live_data_request, is_guidance_request
from app.query_understanding.parser import understand_query
from app.routing.select_route_from_understanding import select_route_from_understanding

_LIVE_DATA_QUERIES = (
    "Show me all failed logins in the last 24 hours",
    "List endpoints connecting to rare external IPs",
    "Find users with impossible travel",
    "Search DNS logs for beaconing domains",
    "Give me current VPN sessions for privileged users",
    "Map all external connections from OT networks",
    "Check logs for PowerShell encoded commands",
    "Show me all external connections or remote access sessions currently mapping to the substation networks.",
)

_OUT_OF_REGISTRY_LIVE_DATA = (
    "List endpoints connecting to rare external IPs",
    "Give me current VPN sessions for privileged users",
    "Map all external connections from OT networks",
    "Check logs for PowerShell encoded commands",
    "Show me all external connections or remote access sessions currently mapping to the substation networks.",
)

_GUIDANCE_QUERIES = (
    "How should SOC investigate repeated port 502 scans targeting OT PLCs?",
    "What should SOC check if corporate IT traffic is allowed into an OT VLAN?",
    "Show me the sop for incident response",
)


@pytest.mark.parametrize("query", _LIVE_DATA_QUERIES)
def test_live_data_queries_signal_as_live_data_not_guidance(query: str) -> None:
    signals = extract_query_signals(query)
    assert is_live_data_request(signals), f"expected live_data_request for: {query!r}"
    assert not is_guidance_request(signals)


@pytest.mark.parametrize("query", _OUT_OF_REGISTRY_LIVE_DATA)
def test_out_of_registry_live_data_never_routes_guided(query: str) -> None:
    understanding = understand_query(query)
    assert understanding.deterministic_match_path == "out_of_registry"

    route, _ = select_route_from_understanding(understanding, query)
    assert route["skill"] != "guided_investigation"
    assert route["skill"] in {"spl_generation", "attack_discovery", "knowledge_recall"}

    qi = build_query_to_intent(query=query, query_understanding=understanding, routed_skill=route["skill"])
    assert qi.intent_classification.intent_family != "guided_investigation"
    assert qi.intent_classification.intent_family in {
        "spl_generation_only",
        "live_investigation",
        "clarification_required",
        "knowledge_only",
    }


@pytest.mark.parametrize("query", _GUIDANCE_QUERIES)
def test_guidance_queries_are_not_live_data_retrieval(query: str) -> None:
    signals = extract_query_signals(query)
    assert is_guidance_request(signals)
    assert not is_live_data_request(signals)


def test_live_data_intent_beats_soc_investigation_shaped_for_substation_query() -> None:
    query = _OUT_OF_REGISTRY_LIVE_DATA[-1]
    understanding = understand_query(query)
    assert understanding.soc_investigation_shaped is True

    route, _ = select_route_from_understanding(understanding, query)
    assert route["skill"] == "spl_generation"
    reasons = route.get("reasons", [])
    assert any(
        token in " ".join(reasons)
        for token in ("unmapped_live_data", "detection_family", "spl_artifact")
    )

    qi = build_query_to_intent(query=query, query_understanding=understanding, routed_skill=route["skill"])
    assert qi.intent_classification.intent_family == "spl_generation_only"


def test_no_collected_evidence_scrubs_live_result_phrasing() -> None:
    from app.chat.contracts.answer_contract import AnswerContract
    from app.chat.final_answer_readability import apply_final_answer_readability
    from app.schemas.responses import AnalystResponseEnvelope

    contract = AnswerContract(
        answer_goal=["spl_artifact"],
        intent_family="spl_generation_only",
        answer_mode="live_investigation",
        spl_status="review_required",
        execution_status="review_only_not_executed",
        hil_status="required",
        render_sections={"live_results": False, "severity_assessment": False},
        section_order=["spl_artifact"],
    )
    envelope = AnalystResponseEnvelope(
        direct_answer_summary="We detected mapped connections currently showing in telemetry.",
        severity_label="P3 Medium",
        splunk_results_table=[{"src": "10.0.0.1"}],
    )
    out = apply_final_answer_readability(envelope, contract)
    assert out.severity_label is None
    assert out.splunk_results_table == []
    assert "detected" not in (out.direct_answer_summary or "").lower()

def test_guidance_vs_live_data_routing_boundary_for_external_ot() -> None:
    guidance = "How should SOC investigate external OT connections?"
    live = "Show me external OT connections"

    guidance_signals = extract_query_signals(guidance)
    live_signals = extract_query_signals(live)
    assert is_guidance_request(guidance_signals)
    assert not is_live_data_request(guidance_signals)
    assert is_live_data_request(live_signals)
    assert not is_guidance_request(live_signals)

    guidance_understanding = understand_query(guidance)
    live_understanding = understand_query(live)

    guidance_route, _ = select_route_from_understanding(guidance_understanding, guidance)
    live_route, _ = select_route_from_understanding(live_understanding, live)

    assert guidance_route["skill"] == "guided_investigation"
    assert live_route["skill"] == "spl_generation"


def test_vpn_live_data_uses_generic_skeleton_not_it_ot_template(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.spl.draft_preview import (
        GENERIC_LIVE_DATA_FAMILY_ID,
        build_draft_preview,
        match_detection_family,
    )

    query = "Show me privileged VPN sessions from last night"
    assert match_detection_family(query) is None
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(query, live_data_request=True)
    assert preview is not None
    assert preview["detection_family"] == GENERIC_LIVE_DATA_FAMILY_ID
    assert preview["detection_family"] != "esp_it_to_ot_connection"
    assert preview.get("template_match_strength") == "none"
    assert "<index>" in preview["draft_spl"]


def _collected_count_from_response(response) -> int:
    analyst = response.analyst_response
    if analyst is None:
        return 0
    table = getattr(analyst, "splunk_results_table", None) or []
    return len(table)


def _answer_text(response) -> str:
    analyst = response.analyst_response
    if analyst is None:
        return ""
    parts = [
        getattr(analyst, "direct_answer_summary", None) or "",
        getattr(analyst, "analyst_summary", None) or "",
        getattr(analyst, "message", None) or "",
    ]
    return " ".join(parts).lower()


def test_live_data_invariants_without_collected_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat.pipeline import build_live_chat_response
    from app.config import settings
    from app.schemas.requests import ChatRequest

    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)

    query = "Show me privileged VPN sessions from last night"
    response = build_live_chat_response(ChatRequest(message=query))
    collected = _collected_count_from_response(response)
    assert collected == 0

    answer = _answer_text(response)
    assert "detected" not in answer
    assert "mapped to" not in answer

    contract = response.answer_contract or {}
    execution_status = str(contract.get("execution_status") or "")
    assert execution_status != "executed"
    analyst = response.analyst_response
    assert analyst is not None
    assert not (getattr(analyst, "splunk_results_table", None) or [])

    severity_label = getattr(analyst, "severity_label", None)
    use_case_id = response.selected_use_case.use_case_id if response.selected_use_case else None
    if use_case_id is None and collected == 0:
        assert severity_label not in {"P3 Medium", "P2 High", "P1 Critical"}

    planning = response.planning_decision or {}
    assert planning.get("effective_hil_required") is planning.get("hil_required")
    assert planning.get("effective_hil_required") is True
    governance = response.governance_trace
    assert governance is not None
    assert governance.effective_hil_required is True


def test_substation_live_data_keeps_strong_family_match(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.spl.draft_preview import build_draft_preview, match_detection_family

    query = _OUT_OF_REGISTRY_LIVE_DATA[-1]
    assert match_detection_family(query) == "esp_it_to_ot_connection"
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(query, live_data_request=True)
    assert preview is not None
    assert preview["detection_family"] == "esp_it_to_ot_connection"
    assert preview.get("template_match_strength") == "strong"

