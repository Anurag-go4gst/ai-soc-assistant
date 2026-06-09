from __future__ import annotations

from app.chat.mitre_branch import run_mitre_evidence_branch
from app.chat.pipeline import _mitre_outputs_for_finalize
from app.config import settings


def _planning(*branches: str) -> dict:
    return {"branches": list(branches), "path_type": "hybrid_investigation"}


def test_mitre_branch_disabled_preserves_compatibility_path(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", False)

    mappings, decision, branch = run_mitre_evidence_branch(
        query="Map failed logins to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        planning_decision=_planning("mitre"),
        alert_context_present=True,
    )

    assert mappings == []
    assert decision is None
    assert branch.ran is False
    assert branch.status == "skipped"


def test_mitre_branch_uses_resolver_as_authority_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    mappings, decision, branch = run_mitre_evidence_branch(
        query="Map failed login attempts across 12 users to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        planning_decision=_planning("mitre"),
        query_signals={"failed_login": True, "spray_breadth": True},
        alert_context_present=True,
    )

    assert branch.ran is True
    assert branch.status == "completed"
    assert branch.branch_authority == "planner_mitre_branch"
    # Query-signal-only context (no executed MCP / source-grounded evidence):
    # the WS1 evidence-tier gate caps MITRE to candidate, never evidence_supported.
    assert "T1110.001" in branch.candidate_mitre
    assert branch.evidence_supported_mitre == []
    assert decision is not None
    assert decision["mitre_status"] == "candidate"
    assert {item.technique_id for item in mappings} >= {"T1110.001"}


def test_mitre_branch_does_not_evidence_support_without_preconditions(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    _mappings, decision, branch = run_mitre_evidence_branch(
        query="Map failed-login alert to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        planning_decision=_planning("mitre"),
        query_signals={},
        alert_context_present=True,
    )

    assert branch.evidence_supported_mitre == []
    assert decision is not None
    assert "evidence_supported" not in set((decision.get("evidence_statuses") or {}).values())


def test_metadata_only_use_case_candidates_do_not_become_runtime_evidence(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    mappings, decision, branch = run_mitre_evidence_branch(
        query="Suspicious email headers with SPF fail and malicious URL",
        question_ref=None,
        use_case_id="email_phishing_header_review",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        planning_decision=_planning("mitre"),
        query_signals={"email_auth_failure": True, "malicious_url_or_domain": True},
        alert_context_present=True,
    )

    assert mappings == []
    assert decision is None
    assert branch.ran is True
    assert branch.evidence_supported_mitre == []
    assert branch.candidate_mitre
    assert branch.reason == "metadata_only_use_case_mitre_candidates_not_runtime_evidence"


def test_mitre_branch_missing_context_requires_context_not_claim(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    mappings, decision, branch = run_mitre_evidence_branch(
        query="Map this to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=[],
        intent_classification={
            "intent_family": "mitre_mapping",
            "answer_goal": ["mitre_mapping"],
            "requires_clarification": True,
        },
        evidence_plan={"answer_mode": "clarification", "needs_mitre": True},
        planning_decision=_planning("mitre"),
        alert_context_present=False,
    )

    assert mappings == []
    assert decision is not None
    assert decision["answer_visible"] is False
    assert branch.status == "requires_context"
    assert branch.evidence_supported_mitre == []


def test_finalize_uses_branch_output_when_branch_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    mappings, decision = _mitre_outputs_for_finalize(
        query="Map failed login attempts across 12 users to MITRE",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=["src-1"],
        intent_classification={"intent_family": "mitre_mapping", "answer_goal": ["mitre_mapping"]},
        evidence_plan={"answer_mode": "live_investigation", "needs_mitre": True},
        planning_decision=_planning("mitre"),
        query_signals={"failed_login": True, "spray_breadth": True},
        session_alert_context=True,
    )

    assert decision is not None
    # Signal-only finalize path (no executed MCP evidence): tier gate caps to candidate.
    assert decision["mitre_status"] == "candidate"
    assert {item.technique_id for item in mappings} >= {"T1110.001"}


def test_cp_off_legacy_path_remains_compatible(monkeypatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_planner_mitre_branch_enabled", True)

    mappings, decision = _mitre_outputs_for_finalize(
        query="policy question",
        question_ref="q0.q046",
        use_case_id="auth_failed_login_spike",
        source_refs=["legacy"],
        intent_classification={"intent_family": "policy_knowledge", "answer_goal": []},
        evidence_plan={"answer_mode": "rag_only"},
    )

    assert decision is None
    assert mappings
    assert {item.technique_id for item in mappings} == {"T1110.001"}
