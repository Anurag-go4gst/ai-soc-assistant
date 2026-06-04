from __future__ import annotations

from app.chat.contracts.answer_contract import build_answer_contract


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
