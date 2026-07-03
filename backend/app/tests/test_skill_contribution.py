"""P1 steps 4–5: skill-contribution contract + investigation visible-section floor."""

from __future__ import annotations

from app.chat.skill_contribution import (
    apply_evidence_summary_floor,
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


def test_guided_floor_includes_branching_hypotheses():
    env = _env()
    contrib = build_skill_contribution(selected_skill="guided_investigation", envelope=env)
    updated = apply_investigation_floor(envelope=env, contribution=contrib)
    joined = " ".join(updated.investigation_steps or [])
    assert "Hypothesis:" in joined
    assert updated.recommended_actions
    assert any("vendor" in item.lower() or "maintenance" in item.lower() for item in updated.recommended_actions)


def test_evidence_summary_floor_cites_rows_with_lineage_when_evidence_exists():
    env = _env(severity_confidence="High")
    contrib = build_skill_contribution(selected_skill="attack_discovery", envelope=env)
    grounding_block = {
        "evidence_citations": [
            {"evidence_id": "ev_1", "source_type": "mcp_search", "row_count": 5, "row_summary": []}
        ],
        "limitations": [],
    }
    updated = apply_evidence_summary_floor(envelope=env, contribution=contrib, grounding_block=grounding_block)
    assert updated.render_sections.get("evidence_summary") is True
    assert "ev_1" in updated.evidence_summary
    assert "mcp_search" in updated.evidence_summary
    # Confidence is not downgraded when evidence backs the answer.
    assert updated.severity_confidence == "High"
    assert contrib.floor_applied is True
    assert "evidence_summary" in contrib.contributed_sections


def test_evidence_summary_floor_states_gap_honestly_and_caps_confidence_when_no_evidence():
    env = _env(severity_confidence="High")
    contrib = build_skill_contribution(selected_skill="attack_discovery", envelope=env)
    grounding_block = {
        "evidence_citations": [],
        "limitations": ["No executed evidence rows available for this turn; grounding is advisory taxonomy only, not evidence-backed."],
    }
    updated = apply_evidence_summary_floor(envelope=env, contribution=contrib, grounding_block=grounding_block)
    assert updated.render_sections.get("evidence_summary") is True
    assert "No executed evidence" in updated.evidence_summary
    # Cannot claim High confidence with no evidence behind it — downgraded.
    assert updated.severity_confidence == "Medium"


def test_evidence_summary_floor_noop_when_no_grounding_block():
    env = _env()
    contrib = build_skill_contribution(selected_skill="attack_discovery", envelope=env)
    updated = apply_evidence_summary_floor(envelope=env, contribution=contrib, grounding_block=None)
    assert updated is env
    assert contrib.floor_applied is False


def test_evidence_summary_floor_wired_end_to_end_on_live_chat(monkeypatch) -> None:
    """Item 5.5: proves the floor actually fires on a live, out-of-registry turn
    — not dead-ended, reaches the analyst_response the response is built from.
    Forces match_path via monkeypatch (item 3.4 found natural-language queries
    that reliably land on out_of_registry hard to construct); the query itself
    is in-catalogue and would otherwise correctly skip the floor (scoping,
    see test_evidence_summary_floor_scoped_off_in_catalogue_traffic below)."""
    from app.api.routes_chat import chat
    from app.chat import pipeline as pl
    from app.schemas.requests import ChatRequest

    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr(pl, "_candidate_match_path", lambda state: "out_of_registry")
    response = chat(ChatRequest(message="Find failed-login users in the last 24 hours"))
    assert response.control_plane_trace is not None
    grounding = response.control_plane_trace.get("grounding_block")
    assert grounding is not None
    # assemble_grounding_from_facts always emits either a citation or a
    # limitation (item 5.4), so evidence_summary is always populated once
    # a grounding block and an analyst_response both exist for the turn.
    analyst = response.analyst_response
    if analyst is not None:
        assert analyst.evidence_summary
        assert analyst.render_sections.get("evidence_summary") is True


def test_evidence_summary_floor_scoped_off_in_catalogue_traffic() -> None:
    """The contract guard (item 0.3) pins in-catalogue answer sections; an
    earlier unscoped version of this floor broke it by adding evidence_summary
    to every turn. Confirms a real 105-catalogue question (exact_105_question
    match_path) is untouched — "Find failed-login users..." was tried first but
    turned out to resolve to near_105_question/out_of_registry under bare
    default settings, not a strict catalogue match, so it doesn't isolate the
    scoping guard the way this question does."""
    from app.api.routes_chat import chat
    from app.schemas.requests import ChatRequest

    response = chat(ChatRequest(message="Which source IPs generated the most outbound connections?"))
    analyst = response.analyst_response
    if analyst is not None:
        assert analyst.render_sections.get("evidence_summary") is not True
