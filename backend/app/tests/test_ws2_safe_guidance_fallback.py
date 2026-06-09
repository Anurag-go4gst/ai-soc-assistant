from __future__ import annotations

from app.chat.analyst_response_builder import build_minimal_guidance_envelope
from app.chat.contracts.answer_contract import AnswerContract
from app.chat.guidance_templates import build_conceptual_mitre_guidance, build_investigation_triage_guidance
from app.evals.powergrid_soc_question_eval import classify_powergrid_response


def test_minimal_guidance_envelope_from_contract() -> None:
    contract = AnswerContract(
        analyst_checklist_safe=["Validate source IP ownership", "Review MFA result"],
        investigation_steps=["Correlate VPN and IdP logs"],
        missing_evidence=["mfa_status"],
        limitations=["No live MCP execution"],
    )
    envelope = build_minimal_guidance_envelope(
        user_query="What should SOC validate?",
        message="Investigation guidance for new source IP.",
        contract=contract,
        evidence_plan={"checklist": contract.analyst_checklist_safe},
        human_review=None,
        execution={"status": "skipped"},
        mitre_rows=[],
        draft_spl_code=None,
        spl_draft_preview=None,
        selected_use_case_label="VPN access review",
    )
    assert envelope is not None
    assert envelope.recommended_actions
    assert "mfa_status" in (envelope.direct_answer_summary or envelope.one_sentence_finding or "")


def test_conceptual_mitre_template_usable_in_envelope() -> None:
    text = build_conceptual_mitre_guidance("Is DNS enough to confirm C2?")
    assert "not enough to confirm" in text.lower()


def test_triage_guidance_includes_checklist_marker() -> None:
    text = build_investigation_triage_guidance(
        "We are seeing multiple failed MFA attempts for one user. How should SOC triage this?"
    )
    assert "SOC review checklist" in text
    severity, violations = classify_powergrid_response(
        {"safety_expectations": {"requires_guidance": True}, "must_include_terms": [], "must_not_include_terms": []},
        {"answer_text": text, "execution_executed": False, "draft_spl_text": ""},
    )
    assert severity == "pass"
    assert not violations
