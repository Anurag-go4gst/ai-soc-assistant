from __future__ import annotations

import pytest

from app.chat.answer_shape_router import (
    IN_CATALOG_MATCH_PATHS,
    build_shaped_guidance,
    classify_answer_shape,
    shape_suppresses_spl,
    should_bypass_shape_router,
)
from app.chat.guidance_templates import build_guided_investigation_guidance
from app.chat.signal_class_guidance import classify_signal_class, extract_ot_terms
from app.chat.t2_answer_surfacing import (
    apply_t2_answer_surfacing,
    build_merged_t2_message,
    enhance_answer_contract_for_t2_surfacing,
    human_review_kind_to_analyst_copy,
)
from app.chat.contracts.answer_contract import AnswerContract, build_answer_contract
from app.config import settings
from app.schemas.responses import AnalystResponseEnvelope


@pytest.fixture(autouse=True)
def _reset_t2_flags(monkeypatch):
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", False)


def test_happy_path_bypass_match_paths() -> None:
    for path in IN_CATALOG_MATCH_PATHS:
        assert should_bypass_shape_router(path) is True
    assert should_bypass_shape_router("out_of_registry") is False


def test_shape_router_regulatory_beats_hunt(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    query = "What is our CERT-In 6-hour reporting obligation for this OT incident?"
    result = classify_answer_shape(query)
    assert result.primary_shape == "regulatory_knowledge"
    guidance = build_shaped_guidance(query, match_path="out_of_registry")
    assert "no SPL" in guidance.lower() or "knowledge-only" in guidance.lower()
    assert shape_suppresses_spl(result.primary_shape) is True


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("A new advisory targets utilities; based on what we log today, are we exposed?", "ti_advisory_mapping"),
        ("Which OT log sources have stopped sending events to Splunk?", "source_health"),
        ("What does normal Modbus polling volume look like over a typical week?", "baselining"),
    ],
)
def test_canonical_shape_phrases_are_classified(query: str, expected: str) -> None:
    assert classify_answer_shape(query).primary_shape == expected


def test_signal_classes_differ_for_ot_protocols(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_shape_enabled", True)
    dnp3 = build_guided_investigation_guidance(
        "DNP3 unsolicited responses from an RTU overnight — anything to hunt?"
    )
    ntp = build_guided_investigation_guidance(
        "Substation NTP / IRIG-B time-sync tamper — where should I start hunting?"
    )
    assert classify_signal_class(
        "DNP3 unsolicited responses from an RTU overnight — anything to hunt?"
    ) == "protocol_command"
    assert classify_signal_class(
        "Substation NTP / IRIG-B time-sync tamper — where should I start hunting?"
    ) == "timing_integrity"
    assert dnp3 != ntp
    assert "protocol command" in dnp3.lower() or "dnp3" in dnp3.lower()
    assert "ntp" in ntp.lower() or "irig" in ntp.lower() or "timing" in ntp.lower()


def test_ot_term_extractor_maps_protocol_tokens() -> None:
    terms = extract_ot_terms("GOOSE burst on IEC-61850 bus with MMS subscription spike")
    assert "goose" in terms
    assert "mms" in terms


def test_legacy_guided_guidance_when_shape_flag_off() -> None:
    query = "Substation NTP / IRIG-B time-sync tamper — where should I start hunting?"
    legacy = build_guided_investigation_guidance(query)
    assert "timing integrity" in legacy.lower() or "ntp" in legacy.lower()


def test_t2_surfacing_exposes_draft_spl(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    contract = AnswerContract(
        intent_family="guided_investigation",
        answer_mode="guided_investigation",
        render_sections={"investigation_guidance": True},
        spl_present=False,
        spl_status="not_required",
    )
    preview = {"draft_spl": "index=ot sourcetype=dnp3 | stats count", "investigation_checklist": ["Check RTU"]}
    enhanced = enhance_answer_contract_for_t2_surfacing(
        contract,
        candidate_spl=None,
        spl_draft_preview=preview,
        spl_validation=None,
        user_query="DNP3 unsolicited hunt",
        match_path="out_of_registry",
    )
    assert enhanced.render_sections.get("spl_artifact") is True
    assert enhanced.spl_present is True

    merged = build_merged_t2_message(
        guidance_text="Guided investigation text",
        human_review={"required": True, "review_type": "spl_source_profile_clarification"},
        spl_draft_preview=preview,
        candidate_spl=None,
        spl_validation=None,
        limitations=["No live query"],
        user_query="DNP3 unsolicited hunt",
        match_path="out_of_registry",
    )
    assert "index=ot" in merged
    assert "Confirm index/sourcetype" in merged


def test_t2_merge_appends_only_code_when_guidance_owns_preview_block(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    preview = {
        "draft_spl": "index=ot sourcetype=dnp3 | stats count",
        "investigation_checklist": ["Confirm RTU owner"],
    }
    guidance = (
        "Lab-only draft SPL preview. Not governed, not approved, not executed.\n\n"
        "SOC review checklist\n"
        "- Confirm RTU owner"
    )
    merged = build_merged_t2_message(
        guidance_text=guidance,
        human_review={"required": False},
        spl_draft_preview=preview,
        candidate_spl=None,
        spl_validation=None,
        limitations=[],
        user_query="Build a review-only hunt for DNP3 cold restart events",
        match_path="out_of_registry",
    )
    assert merged.lower().count("lab-only draft spl preview") == 1
    assert merged.lower().count("soc review checklist") == 1
    assert merged.count("```") == 2
    assert merged.count("index=ot sourcetype=dnp3 | stats count") == 1


def test_regulatory_shape_suppresses_spl_surfacing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    contract = AnswerContract(render_sections={"spl_artifact": True}, spl_present=True)
    preview = {"draft_spl": "index=ot | stats count"}
    enhanced = enhance_answer_contract_for_t2_surfacing(
        contract,
        candidate_spl=None,
        spl_draft_preview=preview,
        spl_validation=None,
        user_query="CERT-In 6-hour reporting obligation for OT incident",
        match_path="out_of_registry",
    )
    assert enhanced.render_sections.get("spl_artifact") is False
    assert enhanced.spl_status == "not_required"


def test_in_catalog_build_answer_contract_unchanged_with_surfacing_flag(monkeypatch) -> None:
    kwargs = dict(
        intent_classification={"intent_family": "hybrid_alert_review", "answer_goal": ["spl_artifact"]},
        evidence_plan={"answer_mode": "hybrid", "spl_allowed": True, "mcp_allowed": False},
        mitre_decision={},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=auth | stats count"},
        execution={"status": "not_executed"},
        human_review={"required": False},
        user_query="Show failed logins",
        match_path="exact_105_question",
        spl_draft_preview={"draft_spl": "index=lab | stats count"},
    )
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", False)
    off = build_answer_contract(**kwargs)
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    on = build_answer_contract(**kwargs)
    assert on.model_dump() == off.model_dump()


def test_human_review_kind_copy() -> None:
    assert "index/sourcetype" in human_review_kind_to_analyst_copy(
        "spl_source_profile_clarification"
    ).lower()


def test_t2_review_only_spl_card_has_single_section_owner(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_t2_answer_surfacing_enabled", True)
    contract = AnswerContract(
        intent_family="guided_investigation",
        answer_mode="guided_investigation",
        render_sections={"investigation_guidance": True},
        section_order=["investigation_guidance"],
        spl_present=False,
        spl_status="not_required",
        limitations=["No live query was executed."],
    )
    envelope = AnalystResponseEnvelope(
        response_profile="guided_investigation",
        direct_answer_summary="Guided investigation prepared.",
        draft_spl_code="index=ot sourcetype=modbus | stats count",
        spl_draft_preview={
            "draft_spl": "index=ot sourcetype=modbus | stats count",
            "detection_family": "modbus_write_hunt",
            "investigation_checklist": ["Confirm relay owner."],
        },
    )

    message, updated_contract, updated_response = apply_t2_answer_surfacing(
        message=(
            "Guided investigation (review-only)\n\n"
            "Hypotheses\n- Approved maintenance.\n\n"
            "Evidence to collect\n- Firewall and OT protocol logs."
        ),
        answer_contract=contract,
        analyst_response=envelope,
        human_review={"required": True, "review_type": "spl_source_profile_clarification"},
        candidate_spl=None,
        spl_draft_preview={
            "draft_spl": "index=ot sourcetype=modbus | stats count",
            "detection_family": "modbus_write_hunt",
            "investigation_checklist": ["Confirm relay owner."],
        },
        spl_validation=None,
        user_query="Modbus TCP writes to relay protection registers from non-engineering hosts",
        match_path="out_of_registry",
    )

    assert "Draft SPL" in message
    assert updated_contract is not None
    assert updated_contract.render_sections.get("spl_artifact") is True
    assert updated_response is not None
    assert updated_response.render_sections.get("draft_spl_preview") is True
    assert updated_response.render_sections.get("spl_artifact") is True
    assert "draft_spl_preview" in updated_response.section_order
    assert "spl_artifact" in updated_response.section_order
    summary = updated_response.direct_answer_summary or ""
    assert "Draft SPL" not in summary
    assert "```" not in summary
    assert "Limitations:" not in summary
    assert "Review package:" not in summary
