from __future__ import annotations

import pytest

from app.api.routes_chat import chat
from app.chat.contracts.answer_contract import build_answer_contract
from app.schemas.requests import ChatRequest


@pytest.fixture
def _control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.control_plane_enabled", True)
    monkeypatch.setattr("app.config.settings.spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail")


def test_policy_rag_only_hides_mitre_and_spl_sections() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "policy_knowledge",
            "answer_goal": ["policy_citation", "analyst_action_guidance"],
        },
        evidence_plan={"answer_mode": "rag_only", "mcp_allowed": False, "spl_allowed": False},
        mitre_decision={"answer_visible": False, "not_claimed": []},
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    assert contract.render_sections["mitre_mapping"] is False
    assert contract.render_sections["spl_artifact"] is False
    assert contract.render_sections["policy_citation"] is True


def test_hybrid_alert_review_shows_mitre_spl_not_policy() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["severity_assessment", "mitre_mapping", "spl_artifact"],
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "mcp_allowed": False,
            "spl_allowed": True,
            "needs_mitre": True,
        },
        mitre_decision={"answer_visible": True, "not_claimed": ["T1003"]},
        severity_decision=type("Severity", (), {"severity_label": "P2 High", "missing_evidence": []})(),
        spl_validation={"approved": True, "normalized_spl": "index=x | stats count"},
        execution={"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}],
    )
    assert contract.execution_status_display == "Review only — not executed"
    assert contract.render_sections["mitre_mapping"] is True
    assert contract.render_sections["not_claimed"] is True
    assert contract.render_sections["spl_artifact"] is True
    assert contract.render_sections["policy_citation"] is False


def test_lab_draft_contract_status_is_draft_preview() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "spl_generation_only",
            "answer_goal": ["spl_artifact"],
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "mcp_allowed": False,
            "spl_allowed": True,
        },
        mitre_decision={"answer_visible": False, "not_claimed": []},
        severity_decision=None,
        spl_validation={
            "approved": False,
            "normalized_spl": None,
            "review_required": True,
            "review_required_reason": "spl_validation_failed",
            "selected_candidate_spl_provider": "deterministic_lab_draft",
            "llm_fallback_status": "lab_draft_fallback",
        },
        execution={"status": "skipped"},
        human_review={"required": True},
        candidate_spl={"generation_mode": "deterministic_lab_draft"},
    )
    assert contract.spl_status_detail is not None
    assert contract.spl_status_detail["generation_status"] == "draft_preview"
    assert contract.spl_status_detail["reason"] == "draft_preview_lab"
    assert contract.spl_status_detail["reason_display"] == "Review-only draft preview"


def test_execution_label_mock_vs_live() -> None:
    mock = build_answer_contract(
        intent_classification={"answer_goal": ["spl_artifact"]},
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": True},
        mitre_decision={},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=x"},
        execution={
            "status": "executed",
            "splunk_result_envelope": {"origin": "fixture"},
        },
        human_review={"required": False},
    )
    live = build_answer_contract(
        intent_classification={"answer_goal": ["spl_artifact"]},
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": True},
        mitre_decision={},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=x"},
        execution={"status": "executed", "splunk_result_envelope": {"origin": "live"}},
        human_review={"required": False},
    )
    assert mock.execution_status_display == "Executed — mock evidence"
    assert live.execution_status_display == "Executed — live evidence"


def test_blocked_findings_source_from_mitre_decision_union() -> None:
    """not_claimed_technique_ids = MitreDecision.not_claimed ∪ rejected_techniques.

    The contract makes no new MITRE decision; it projects the decider.
    """
    contract = build_answer_contract(
        intent_classification={"answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        mitre_decision={
            "answer_visible": True,
            "not_claimed": ["T1078"],
            "rejected_techniques": ["T1003", "T1562.001"],
        },
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}],
    )
    assert set(contract.not_claimed_technique_ids) == {"T1078", "T1003", "T1562.001"}
    assert contract.mitre_technique_ids == ["T1110.001"]


def test_limitations_section_disabled_when_no_content() -> None:
    """AQ-001: do not enable limitations render section without backing text."""
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "spl_generation_only",
            "answer_goal": ["spl_artifact"],
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "mcp_allowed": False,
            "spl_allowed": True,
            "limitations": [],
        },
        mitre_decision={"answer_visible": False, "not_claimed": []},
        severity_decision=None,
        spl_validation={"approved": False, "review_required": True},
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    assert contract.limitations == []
    assert contract.render_sections["limitations"] is False
    assert "limitations" not in contract.section_order


def test_limitations_section_enabled_when_plan_has_content() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "spl_generation_only",
            "answer_goal": ["spl_artifact"],
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "limitations": ["Candidate SPL only; Splunk search was not executed."],
        },
        mitre_decision={"answer_visible": False, "not_claimed": []},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=x | stats count"},
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    assert contract.render_sections["limitations"] is True
    assert contract.limitations == ["Candidate SPL only; Splunk search was not executed."]


def test_limitations_section_enabled_for_auth_hybrid_alert_review() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["severity_assessment", "mitre_mapping", "spl_artifact"],
        },
        evidence_plan={
            "answer_mode": "live_investigation",
            "use_case_id": "auth_failed_login_spike",
            "mcp_allowed": False,
            "spl_allowed": True,
        },
        mitre_decision={"answer_visible": True, "not_claimed": []},
        severity_decision=type("Severity", (), {"severity_label": "P3 Medium", "missing_evidence": []})(),
        spl_validation={"approved": True, "normalized_spl": "index=x | stats count"},
        execution={"status": "skipped"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}],
        use_case_id="auth_failed_login_spike",
    )
    assert contract.render_sections["limitations"] is True


def test_human_review_forces_blocked_label() -> None:
    contract = build_answer_contract(
        intent_classification={"answer_goal": ["spl_artifact"]},
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": True},
        mitre_decision={},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=x"},
        execution={"status": "requires_human_review"},
        human_review={"required": True},
    )
    assert contract.human_review_required is True
    assert contract.execution_status_label == "blocked_approval_required"


def test_answer_contract_wired_into_live_chat(_control_plane: None) -> None:
    """Commit 2 wiring: the live /chat response carries the projected contract."""
    response = chat(ChatRequest(message="Generate SPL for the top failed-login users in the last 24 hours"))
    assert response.answer_contract is not None
    assert response.control_plane_trace is not None
    assert response.control_plane_trace.get("answer_contract") is not None
    # answer_goal is projected straight from IntentClassification, not re-derived.
    intent_goal = response.query_to_intent["intent_classification"]["answer_goal"]
    assert response.answer_contract["answer_goal"] == [str(g) for g in intent_goal]
