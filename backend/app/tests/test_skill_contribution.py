"""P1 steps 4–5: skill-contribution contract + investigation visible-section floor."""

from __future__ import annotations

from app.chat.skill_contribution import (
    apply_investigation_floor,
    build_skill_contribution,
)
from app.schemas.responses import AnalystResponseEnvelope


def _env(**kw) -> AnalystResponseEnvelope:
    return AnalystResponseEnvelope(**kw)


def test_contribution_records_populated_sections_and_provenance():
    env = _env(
        investigation_steps=["Confirm scope", "Pull events"],
        spl_code="index=foo | stats count",
    )
    contrib = build_skill_contribution(
        selected_skill="guided_investigation",
        envelope=env,
        routing_provenance={"authority_source": "guided_investigation_rescue", "selected_by": "x"},
        source_evidence=[{"source_id": "SOC-KB-1"}, {"title": "playbook-2"}],
    )
    assert "investigation_steps" in contrib.contributed_sections
    assert "spl_artifact" in contrib.contributed_sections
    assert contrib.contributed_evidence_keys == ["SOC-KB-1", "playbook-2"]
    assert contrib.provenance["authority_source"] == "guided_investigation_rescue"
    assert contrib.visible_domain_section is True
    assert contrib.survived_into_card is True
    assert contrib.floor_applied is False


def test_floor_fires_when_investigation_skill_has_no_section():
    env = _env()  # no sections at all
    contrib = build_skill_contribution(selected_skill="guided_investigation", envelope=env)
    assert contrib.visible_domain_section is False
    assert contrib.skip_reason is None  # no legitimate skip → floor should fire

    updated = apply_investigation_floor(envelope=env, contribution=contrib)
    assert updated.investigation_steps  # generic floor injected
    assert updated.render_sections.get("investigation_steps") is True
    assert contrib.floor_applied is True
    assert contrib.gap_recorded is True
    assert contrib.visible_domain_section is True


def test_floor_stands_down_on_clarification_skip():
    env = _env(execution_status_label="clarification_required")
    contrib = build_skill_contribution(
        selected_skill="guided_investigation",
        envelope=env,
        human_review={"reason": "intent_clarification"},
    )
    assert contrib.skip_reason == "clarification_required"
    updated = apply_investigation_floor(envelope=env, contribution=contrib)
    assert not updated.investigation_steps  # no floor — empty card is correct
    assert contrib.floor_applied is False


def test_floor_does_not_touch_knowledge_recall():
    env = _env()
    contrib = build_skill_contribution(selected_skill="knowledge_recall", envelope=env)
    updated = apply_investigation_floor(envelope=env, contribution=contrib)
    assert not updated.investigation_steps
    assert contrib.floor_applied is False


def test_boundary_class_unsafe_is_legitimate_skip():
    env = _env()
    contrib = build_skill_contribution(
        selected_skill="spl_generation",  # an investigation skill
        envelope=env,
        boundary_class="unsafe_execution",
    )
    assert contrib.skip_reason == "unsafe_execution_refused"
    updated = apply_investigation_floor(envelope=env, contribution=contrib)
    assert not updated.investigation_steps
    assert contrib.floor_applied is False


def test_none_envelope_is_safe():
    contrib = build_skill_contribution(selected_skill="guided_investigation", envelope=None)
    assert contrib.skip_reason == "no_envelope"
    assert contrib.floor_applied is False


def test_render_hidden_section_does_not_count_as_visible():
    env = _env(
        investigation_steps=["step"],
        render_sections={"investigation_steps": False},
    )
    contrib = build_skill_contribution(selected_skill="guided_investigation", envelope=env)
    assert contrib.visible_domain_section is False
    # floor should then fire to restore a visible section
    updated = apply_investigation_floor(envelope=env, contribution=contrib)
    assert updated.render_sections.get("investigation_steps") is True
    assert contrib.floor_applied is True


def test_derive_boundary_class_marks_destructive_and_unsafe_rows() -> None:
    from app.chat.skill_contribution import derive_boundary_class

    assert derive_boundary_class(
        "Run a Splunk search now for every event containing a password and return all raw records."
    ) == "unsafe_execution"
    assert derive_boundary_class(
        "Delete all firewall rules that might block our incident response tooling."
    ) == "unsafe_execution"
    assert derive_boundary_class("Summarize the company vacation policy.") == "out_of_scope_boundary"
    assert derive_boundary_class(
        "Summarize the company leave policy and approve my vacation request."
    ) == "out_of_scope_boundary"
