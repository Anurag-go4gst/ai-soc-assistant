from __future__ import annotations

import pytest

import app.chat  # noqa: F401  warm lazy chat imports
from app.chat.pipeline import build_live_chat_response
from app.schemas.requests import ChatRequest


@pytest.fixture(autouse=True)
def _disable_optional_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_answer_guard_enabled", False)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_spl_fallback_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_spl_draft_preview_enabled", True)


def _chat(message: str) -> dict:
    return build_live_chat_response(ChatRequest(message=message, session_id="cisco-live-contract")).model_dump()


def test_cisco_paraphrase_live_path_stays_review_only() -> None:
    payload = _chat("Show firewall traffic from the industrial DMZ going to foreign countries.")

    understanding = payload["query_understanding"]
    planning = payload["planning_decision"]
    candidate = payload["candidate_spl"]
    validation = payload["spl_validation"]
    execution = payload["execution"]

    assert understanding["mapped_question_ref"] == "cisco.perim.006"
    assert understanding["mapped_pattern_type"] == "cisco_firewall_geo_egress"
    assert planning["question_ref"] == "cisco.perim.006"
    assert planning["execution_enabled"] is False
    if candidate is not None:
        assert candidate["execution_eligible"] is False
    if validation is not None:
        assert validation["approved"] is False
        assert validation["normalized_spl"] is None
    assert execution["executed_spl"] is None


def test_cisco_metadata_live_path_surfaces_environment_hygiene_envelope() -> None:
    payload = _chat("log generation formats transmitting operational updates with ingest latency indicators")

    planning = payload["planning_decision"]
    envelope = payload["environment_hygiene"]
    execution = payload["execution"]

    assert planning["use_case_id"] == "soc_environment_hygiene"
    assert planning["question_ref"] == "cisco.endpoint.046"
    assert payload["candidate_spl"] is None
    assert payload["spl_validation"] is None
    assert envelope["pattern_type"] == "environment_hygiene"
    assert envelope["needs_spl"] is False
    assert envelope["execution_enabled"] is False
    assert envelope["execution_eligible"] is False
    assert envelope["planned_tool"] == "splunk_get_metadata"
    assert "splunk_run_query" not in envelope["planned_tool_sequence"]
    assert execution["executed_spl"] is None

def test_dns_observation_window_paraphrase_live_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.chat.pipeline.run_mitre_risk_rationale",
        lambda **_: pytest.fail("draft preview path must skip MITRE/risk LLM rationale"),
    )
    monkeypatch.setattr(
        "app.chat.pipeline.run_resource_plan_shadow",
        lambda **_: pytest.fail("draft preview path must skip resource-plan LLM shadow"),
    )
    payload = _chat("List all DNS requests during the observation window.")

    understanding = payload["query_understanding"]
    analyst = payload["analyst_response"]
    preview = payload.get("spl_draft_preview")
    validation = payload.get("spl_validation")

    assert understanding["mapped_question_ref"] == "cisco.perim.010"
    assert payload["selected_skill"] == "spl_generation"
    assert payload["candidate_spl"]["generation_mode"] == "deterministic_lab_draft"
    assert payload["candidate_spl"]["selected_candidate_spl_provider"] == "deterministic_lab_draft"
    assert payload["spl_validation"]["selected_candidate_spl_provider"] == "deterministic_lab_draft"
    assert payload["candidate_spl"]["llm_fallback_status"] == "lab_draft_fallback"
    assert preview is not None
    assert preview["detection_family"] == "dns_query_window_review"
    assert analyst is not None
    assert analyst["draft_spl_code"]
    assert analyst["spl_draft_preview"]["detection_family"] == "dns_query_window_review"
    assert analyst["spl_status_detail"]["generation_status"] == "draft_preview"
    assert analyst["spl_status_detail"]["reason"] == "draft_preview_lab"
    assert analyst["hil_status"] == "required"
    assert analyst["direct_answer_summary"]
    bad_answer_fragments = (
        "spl query generation is blocked",
        "hil status is not required",
        "human intelligence (hil) status is not required",
        "no mitre techniques are applicable as none are listed in the contract",
        "spl template status is unknown",
        "spl validation failed",
    )
    rendered_text = " ".join(
        str(value)
        for value in (
            analyst.get("direct_answer_summary"),
            analyst.get("one_sentence_finding"),
            analyst.get("foundation_sec_analysis"),
            analyst.get("spl_status_detail", {}).get("reason_display"),
        )
        if value
    ).lower()
    assert not any(fragment in rendered_text for fragment in bad_answer_fragments)
    if validation is not None:
        assert validation["approved"] is False
        assert validation["normalized_spl"] is None
