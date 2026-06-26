"""Envelope population from shaped guidance prose."""

from __future__ import annotations

from app.chat.guidance_envelope import parse_guidance_sections, populate_envelope_from_guidance
from app.schemas.responses import AnalystResponseEnvelope

_GUIDANCE = (
    "Guided investigation — signal class: protocol command (review-only)\n\n"
    "Hypotheses\n"
    "- Approved engineering or vendor maintenance command.\n"
    "- Unauthorized write or function-code abuse on OT field gear.\n\n"
    "Evidence to collect\n"
    "- OT protocol logs: function code, source master, response timing.\n"
    "- Change tickets and maintenance approvals for the affected RTU.\n\n"
    "Next steps\n"
    "- Validate scope and time window.\n"
    "- Check existing detections and local playbooks.\n"
)


def test_parse_groups_bullets_by_header() -> None:
    sections = parse_guidance_sections(_GUIDANCE)
    assert len(sections["hypotheses"]) == 2
    assert len(sections["checklist"]) == 2  # evidence bucket
    assert len(sections["steps"]) == 2


def test_populate_fills_empty_arrays() -> None:
    env = AnalystResponseEnvelope()
    out = populate_envelope_from_guidance(env, _GUIDANCE, limitations=["no live query was run"])
    assert out.initial_assessment and "vendor maintenance" in out.initial_assessment[0]
    assert out.analyst_checklist and any("OT protocol logs" in c for c in out.analyst_checklist)
    assert out.investigation_steps == ["Validate scope and time window.", "Check existing detections and local playbooks."]
    assert out.recommended_actions  # steps preferred
    assert out.limitations == ["no live query was run"]


def test_populate_does_not_overwrite_existing() -> None:
    env = AnalystResponseEnvelope(recommended_actions=["existing action"], analyst_checklist=["existing item"])
    out = populate_envelope_from_guidance(env, _GUIDANCE)
    assert out.recommended_actions == ["existing action"]
    assert out.analyst_checklist == ["existing item"]
