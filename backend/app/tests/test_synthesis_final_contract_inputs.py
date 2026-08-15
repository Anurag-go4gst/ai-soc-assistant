"""Plan 8 O0 — synthesis consumes final RQC, InvestigationOutcome, and EvidenceState."""

from __future__ import annotations

from app.actions.capability_policy import action_capability_for
from app.synthesis.lab_runner import run_governed_synthesis_lab
from app.synthesis.models import build_governed_synthesis_package
from app.tests.test_p6_guarded_synthesis_lab import _source_evidence, _structured_context


def test_synthesis_package_binds_final_contract_inputs() -> None:
    package = build_governed_synthesis_package(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        mitre_mappings=[],
        action_capability=action_capability_for("attack_discovery", "P2 High"),
        resolved_query_contract={
            "intent_family": "live_investigation",
            "answer_goal": "live_results",
            "evidence_requirements": ["user"],
            "required_capabilities": ["mcp"],
            "time_scope": "-15m",
            "clarification_required": False,
        },
        investigation_outcome={
            "disposition": "inconclusive",
            "severity_label": "P2 High",
            "recommended_actions": ["summarize"],
            "action_eligibility": {"allowed_actions": ["summarize"]},
        },
        evidence_state={"required": ["user"], "obtained": ["user"], "missing": [], "blocked": []},
        evidence_sufficiency={"status": "SUFFICIENT", "next_action": "CONTINUE", "stage": "EVIDENCE"},
        route_plan_summary={"primary_skill": "attack_discovery", "intent_family": "live_investigation"},
    )
    assert package.resolved_query_contract["intent_family"] == "live_investigation"
    assert package.investigation_outcome["disposition"] == "inconclusive"
    assert package.evidence_state["obtained"] == ["user"]
    assert package.evidence_sufficiency["status"] == "SUFFICIENT"
    assert package.route_plan_summary["primary_skill"] == "attack_discovery"
    assert package.synthesis_allowed is False


def test_lab_draft_actions_come_from_outcome_not_prose(monkeypatch) -> None:
    monkeypatch.setattr("app.synthesis.lab_runner.settings.ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr("app.synthesis.lab_runner.settings.ai_soc_llm_require_context_sufficiency", False)
    result = run_governed_synthesis_lab(
        structured_context=_structured_context(),
        source_evidence=_source_evidence(),
        context_sufficiency={"status": "full_answer", "synthesis_readiness": True},
        mitre_mappings=[],
        action_capability=action_capability_for("attack_discovery", "P2 High"),
        severity_label="P2 High",
        spl_validation=None,
        human_review=None,
        investigation_outcome={
            "disposition": "inconclusive",
            "recommended_actions": ["summarize", "explain"],
            "severity_label": "P2 High",
        },
        resolved_query_contract={"intent_family": "live_investigation", "required_capabilities": ["mcp"]},
        evidence_sufficiency={"status": "SUFFICIENT", "next_action": "CONTINUE"},
    )
    assert result.package is not None
    assert result.package.investigation_outcome["disposition"] == "inconclusive"
    assert result.draft is not None
    assert result.draft["recommended_actions"] == ["summarize", "explain"]
    assert result.draft["execution_eligible"] is False
    assert "block_ip" not in result.draft["recommended_actions"]
    assert result.package.resolved_query_contract["intent_family"] == "live_investigation"
