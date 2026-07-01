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
    assert "SOC review checklist" in summary
    assert "Validate VPN geo anomalies" in summary
    assert "Correlate source IPs" in summary
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
