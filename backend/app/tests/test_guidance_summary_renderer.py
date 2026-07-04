from __future__ import annotations

from app.chat.guidance_summary_renderer import apply_guidance_summary_render
from app.schemas.responses import AnalystResponseEnvelope


def test_guidance_summary_render_replaces_thin_guided_stub() -> None:
    envelope = AnalystResponseEnvelope(
        direct_answer_summary="Guided investigation prepared for analyst review; no live query was performed.",
        investigation_steps=["Confirm affected assets", "Review authentication logs"],
        recommended_actions=["Confirm affected assets"],
    )
    rendered, message = apply_guidance_summary_render(
        envelope,
        "",
        path_type="guided_investigation",
        evidence_plan={
            "checklist": ["Validate VPN geo anomalies", "Review MFA posture"],
            "investigation_workflow": ["Correlate source IPs across auth logs"],
        },
        answer_contract=None,
        user_query="How should SOC investigate repeated VPN failures?",
    )
    assert rendered is not None
    summary = str(rendered.direct_answer_summary or "")
    # Lead prose stays in the summary; checklist items live in owned sections.
    assert "SOC review checklist" not in summary
    assert "Guided investigation prepared" in summary
    steps = list(rendered.investigation_steps or [])
    assert "Validate VPN geo anomalies" in steps
    assert any("Correlate source IPs" in str(item) for item in steps)
    assert message == ""


def test_guidance_summary_render_skips_spl_only_profile() -> None:
    envelope = AnalystResponseEnvelope(
        response_profile="spl_only",
        direct_answer_summary="Severity: Not assigned from this question alone",
    )
    rendered, message = apply_guidance_summary_render(
        envelope,
        "composed spl body",
        path_type="hybrid_investigation",
        evidence_plan={"checklist": ["Should not appear"]},
        answer_contract=None,
        user_query="show me spl",
    )
    assert rendered is not None
    assert rendered.direct_answer_summary == envelope.direct_answer_summary
    assert message == "composed spl body"


def test_guidance_summary_render_preserves_llm_composer_prose() -> None:
    composed = (
        "We are observing a significant spike in firewall denies totaling 5000 over the last hour. "
        "Prioritize top blocked source and destination IPs and assess overlap with the breached "
        "internal server account before treating the pattern as coordinated."
    )
    envelope = AnalystResponseEnvelope(
        direct_answer_summary=composed,
        one_sentence_finding=composed[:200],
    )
    rendered, message = apply_guidance_summary_render(
        envelope,
        "",
        path_type="guided_investigation",
        evidence_plan={
            "checklist": ["Validate VPN geo anomalies", "Review MFA posture"],
            "investigation_workflow": ["Correlate source IPs across auth logs"],
        },
        answer_contract=None,
        user_query=(
            "We have more than 5,000 firewall blocks in the last hour and a successful breach "
            "on an internal server account — summarize top offenders and assess whether this "
            "looks coordinated."
        ),
        llm_composer_used=True,
    )
    assert rendered is not None
    assert rendered.direct_answer_summary == composed
    assert "Guided investigation prepared for analyst review" not in str(rendered.direct_answer_summary)
    assert message == composed
