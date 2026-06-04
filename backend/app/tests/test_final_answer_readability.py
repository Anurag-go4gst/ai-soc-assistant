from __future__ import annotations

from app.chat.contracts.answer_contract import build_answer_contract
from app.chat.final_answer_readability import apply_final_answer_readability
from app.schemas.responses import AnalystResponseEnvelope


def _hybrid_envelope() -> AnalystResponseEnvelope:
    return AnalystResponseEnvelope(
        severity_label="P2 High — Review required",
        severity_confidence="Medium",
        severity_rationale="Repeated failures with possible success.",
        severity_safety_note="This is not confirmed account compromise.",
        finding_title="Alert ALT-2024-0891 review",
        one_sentence_finding="Alert ALT-2024-0891 requires review.",
        mitre_mappings=[
            {"Technique": "T1110.001", "Status": "Candidate", "Evidence": "failed logins"},
            {"Technique": "T1078", "Status": "Candidate", "Evidence": "valid accounts"},
        ],
        not_claimed=[
            {"Technique": "T1003", "Status": "Not Claimed", "Evidence": "no credential dump evidence"},
            {"Technique": "T1562.001", "Status": "Not Claimed", "Evidence": "no defense evasion evidence"},
        ],
        spl_code='index=pgcil_soc sourcetype=pgcil:auth | stats count by user | where count>5',
        review_notice="Candidate SPL — review only, not executed.",
        response_profile="hybrid_alert_review",
        retrieved_playbook={"title": "Should not show"},
        recommended_actions=["Review failed-login volume and source distribution."],
    )


def test_no_duplicate_section_labels_and_standard_execution_status() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["severity_assessment", "mitre_mapping", "spl_artifact"],
        },
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": False, "spl_allowed": True},
        mitre_decision={"answer_visible": True, "not_claimed": ["T1003", "T1562.001"]},
        severity_decision=type("Severity", (), {"severity_label": "P2 High", "missing_evidence": []})(),
        spl_validation={"approved": True, "normalized_spl": "index=x | stats count"},
        execution={"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}, {"technique_id": "T1078"}],
    )
    result = apply_final_answer_readability(_hybrid_envelope(), contract)
    assert result.execution_status_label == "Review only — not executed"
    assert result.review_notice == "Review only — not executed"
    assert "review required" not in (result.severity_label or "").lower()
    assert result.direct_answer_summary
    assert "Severity:" in result.direct_answer_summary
    assert "SPL:" in result.direct_answer_summary
    assert result.retrieved_playbook is None
    assert result.recommended_actions == []


def test_spl_multiline_rendering() -> None:
    contract = build_answer_contract(
        intent_classification={"answer_goal": ["spl_artifact"]},
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": False},
        mitre_decision={},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=x | stats count by user | head 20"},
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    envelope = AnalystResponseEnvelope(spl_code="index=x | stats count by user | head 20")
    result = apply_final_answer_readability(envelope, contract)
    assert result.spl_code is not None
    assert "\n" in result.spl_code
    assert result.spl_code.startswith("index=x")


def test_not_claimed_separate_from_positive_mappings() -> None:
    contract = build_answer_contract(
        intent_classification={"answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": True},
        mitre_decision={"answer_visible": True, "not_claimed": ["T1003"]},
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}],
    )
    result = apply_final_answer_readability(_hybrid_envelope(), contract)
    mapped = {row["Technique"] for row in result.mitre_mappings}
    blocked = {row["Technique"] for row in result.not_claimed}
    assert "T1110.001" in mapped
    assert "T1003" in blocked
    assert mapped.isdisjoint(blocked)


def test_policy_answer_hides_unnecessary_mitre() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "policy_knowledge",
            "answer_goal": ["policy_citation"],
        },
        evidence_plan={"answer_mode": "rag_only", "mcp_allowed": False, "spl_allowed": False},
        mitre_decision={"answer_visible": False, "not_claimed": []},
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    envelope = AnalystResponseEnvelope(
        mitre_mappings=[{"Technique": "T1110.001", "Status": "Candidate", "Evidence": "x"}],
        not_claimed=[{"Technique": "T1003", "Status": "Not Claimed", "Evidence": "y"}],
        spl_code="index=x",
        retrieved_playbook={"title": "Failed login escalation SOP"},
    )
    result = apply_final_answer_readability(envelope, contract)
    assert result.mitre_mappings == []
    assert result.not_claimed == []
    assert result.spl_code is None


def test_spl_only_hides_unrelated_sop_blocks() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "spl_generation_only",
            "answer_goal": ["spl_artifact"],
        },
        evidence_plan={"answer_mode": "live_investigation", "mcp_allowed": False, "spl_allowed": True},
        mitre_decision={"answer_visible": False},
        severity_decision=None,
        spl_validation={"approved": True, "normalized_spl": "index=x | head 10"},
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    envelope = AnalystResponseEnvelope(
        spl_code="index=x | head 10",
        retrieved_playbook={"title": "Unrelated SOP"},
        sop_guidance={"triage_steps": ["Check MFA"]},
        mitre_mappings=[{"Technique": "T1110.001", "Status": "Candidate", "Evidence": "x"}],
    )
    result = apply_final_answer_readability(envelope, contract)
    assert result.retrieved_playbook is None
    assert result.sop_guidance is None
    assert result.mitre_mappings == []
    assert result.spl_code is not None


def test_hybrid_includes_spl_status_and_playbook_when_requested() -> None:
    contract = build_answer_contract(
        intent_classification={
            "intent_family": "hybrid_investigation_plus_policy",
            "answer_goal": ["spl_artifact", "mitre_mapping", "policy_citation", "analyst_action_guidance"],
        },
        evidence_plan={"answer_mode": "hybrid", "mcp_allowed": False, "spl_allowed": True},
        mitre_decision={"answer_visible": True, "not_claimed": ["T1003"]},
        severity_decision=type("Severity", (), {"severity_label": "P2 High", "missing_evidence": []})(),
        spl_validation={"approved": True, "normalized_spl": "index=x | stats count"},
        execution={"status": "skipped", "block_reason": "mcp_not_allowed_by_evidence_plan"},
        human_review={"required": False},
        mitre_mappings=[{"technique_id": "T1110.001"}],
    )
    envelope = AnalystResponseEnvelope(
        spl_code="index=x | stats count",
        mitre_mappings=[{"Technique": "T1110.001", "Status": "Candidate", "Evidence": "x"}],
        retrieved_playbook={"title": "Auth investigation playbook"},
        recommended_actions=["Check for successful login after repeated failures."],
    )
    result = apply_final_answer_readability(envelope, contract)
    assert result.execution_status_label == "Review only — not executed"
    assert result.mitre_mappings
    assert result.retrieved_playbook is not None
    assert result.recommended_actions
    assert result.recommended_actions[0].startswith("P2 —")


def test_investigation_actions_use_priority_prefix() -> None:
    contract = build_answer_contract(
        intent_classification={"answer_goal": ["analyst_action_guidance"]},
        evidence_plan={"answer_mode": "hybrid", "mcp_allowed": True},
        mitre_decision={},
        severity_decision=None,
        spl_validation=None,
        execution={"status": "skipped"},
        human_review={"required": False},
    )
    envelope = AnalystResponseEnvelope(
        recommended_actions=[
            "Review failed-login volume and source distribution.",
            "Check for successful login after repeated failures.",
        ]
    )
    result = apply_final_answer_readability(envelope, contract)
    assert all(" — " in action for action in result.recommended_actions)
    assert result.recommended_actions[0].startswith("P2 —")
