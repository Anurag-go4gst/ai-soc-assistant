"""Phase 3 — MITRE/risk rationale prose from fixed decision dumps only."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.chat.contracts.answer_contract import AnswerContract, build_answer_contract
from app.config import settings
from app.llm.mitre_risk_rationale import (
    MitreRiskRationaleResult,
    build_deterministic_mitre_rationale,
    build_deterministic_severity_rationale,
    run_mitre_risk_rationale,
    validate_rationale_prose,
)
from app.risk.severity_policy import SeverityDecision
from app.schemas.responses import AnalystResponseEnvelope


def _enable_rationale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)


def _contract(**overrides) -> AnswerContract:
    payload = {
        "intent_classification": {
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["severity_assessment", "mitre_mapping"],
        },
        "evidence_plan": {
            "answer_mode": "hybrid",
            "spl_allowed": True,
            "mcp_allowed": False,
            "missing_required_evidence": ["mfa_status"],
            "limitations": ["Do not claim account compromise from failed logins alone."],
        },
        "mitre_decision": {"answer_visible": True},
        "severity_decision": SeverityDecision(
            use_case_id="auth_failed_login_spike",
            severity_label="P3 Medium",
            matched_rules=["default_policy"],
            why_not_higher=["P1 requires: confirmed_success"],
            missing_evidence=["confirmed_success"],
            source_refs=[],
            recommended_priority="standard_triage",
            allowed_action_tier=1,
        ),
        "spl_validation": {"approved": False, "review_required": True},
        "execution": {"status": "skipped"},
        "human_review": {"required": False},
        "mitre_mappings": [{"technique_id": "T1110.001"}],
        "mitre_branch_result": {
            "candidate_mitre": ["T1110.001"],
            "evidence_supported_mitre": [],
            "not_claimed_mitre": ["T1078"],
        },
    }
    payload.update(overrides)
    return build_answer_contract(**payload)


def test_deterministic_rationale_from_decision_dump() -> None:
    severity = SeverityDecision(
        use_case_id="auth_failed_login_spike",
        severity_label="P3 Medium",
        matched_rules=["default_policy"],
        why_not_higher=["P1 requires: confirmed_success"],
        missing_evidence=["confirmed_success"],
        source_refs=[],
        recommended_priority="standard_triage",
        allowed_action_tier=1,
    )
    contract = _contract()
    det_severity = build_deterministic_severity_rationale(severity)
    det_mitre = build_deterministic_mitre_rationale(
        contract=contract,
        mitre_branch_result={"candidate_mitre": ["T1110.001"]},
    )
    assert det_severity and "P1 requires" in det_severity
    assert det_mitre and "T1110.001" in det_mitre


def test_guard_rejects_severity_upgrade() -> None:
    contract = _contract()
    ok, reason = validate_rationale_prose(
        "This is a P1 Critical incident requiring immediate action.",
        severity_label="P3 Medium",
        contract=contract,
    )
    assert not ok and reason


def test_llm_rationale_generated_without_changing_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_rationale(monkeypatch)
    contract = _contract()
    severity = SeverityDecision(
        use_case_id="auth_failed_login_spike",
        severity_label="P3 Medium",
        matched_rules=["default_policy"],
        why_not_higher=["P1 requires: confirmed_success"],
        missing_evidence=["confirmed_success"],
        source_refs=[],
        recommended_priority="standard_triage",
        allowed_action_tier=1,
    )
    mitre_payload = {
        "reasoning_summary": "Failed-login spike remains candidate brute force pending validation.",
        "mitre_reasoning": ["T1110.001 remains candidate only; not evidence-supported."],
        "why_not_higher_or_final": ["Higher severity thresholds were not met."],
    }
    risk_payload = {
        "selected_severity": "P3 Medium",
        "why_selected": ["Default policy for failed-login spike."],
        "why_not_higher": ["P1 requires confirmed success evidence."],
        "missing_evidence_for_higher": ["confirmed_success"],
        "escalate_if": [],
        "recommended_validation_steps": ["Review success-after-failure ordering."],
    }

    def _fake_invoke(*, role: str, user_prompt: str, system_prompt: str, max_tokens: int):
        payload = mitre_payload if role == "mitre_reasoner" else risk_payload
        return json.dumps(payload), False, "local_primary"

    with patch("app.llm.mitre_risk_rationale.invoke_sidecar_role", side_effect=_fake_invoke):
        result = run_mitre_risk_rationale(
            contract=contract,
            query="Show failed logins in the last hour",
            severity_decision=severity,
            mitre_decision={"answer_visible": True},
            mitre_branch_result={"candidate_mitre": ["T1110.001"]},
        )

    assert result.llm_called is True
    assert result.guard_status == "passed"
    assert result.severity_rationale_prose and "P1 requires" in result.severity_rationale_prose
    assert result.mitre_rationale_prose and "candidate" in result.mitre_rationale_prose.lower()

    envelope = AnalystResponseEnvelope(
        severity_label="P3 Medium",
        mitre_mappings=[{"technique_id": "T1110.001", "Status": "Candidate"}],
    )
    updated = envelope.model_copy(
        update={
            "severity_rationale": result.severity_rationale_prose,
            "foundation_sec_analysis": result.mitre_rationale_prose,
        }
    )
    assert updated.severity_label == "P3 Medium"
    assert updated.mitre_mappings[0]["Status"] == "Candidate"


def test_guard_reject_falls_back_to_deterministic_rationale(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_rationale(monkeypatch)
    contract = _contract()
    severity = SeverityDecision(
        use_case_id="auth_failed_login_spike",
        severity_label="P3 Medium",
        matched_rules=["default_policy"],
        why_not_higher=["P1 requires: confirmed_success"],
        missing_evidence=["confirmed_success"],
        source_refs=[],
        recommended_priority="standard_triage",
        allowed_action_tier=1,
    )
    bad_payload = {
        "reasoning_summary": "Evidence-supported T1110.001 confirms account compromise and executed SPL.",
        "mitre_reasoning": ["T1110.001 is evidence-supported."],
    }

    def _fake_invoke(*, role: str, user_prompt: str, system_prompt: str, max_tokens: int):
        if role == "mitre_reasoner":
            return json.dumps(bad_payload), False, "local_primary"
        return json.dumps({"selected_severity": "P3 Medium", "why_not_higher": ["ok"]}), False, "local_primary"

    with patch("app.llm.mitre_risk_rationale.invoke_sidecar_role", side_effect=_fake_invoke):
        result = run_mitre_risk_rationale(
            contract=contract,
            query="failed logins",
            severity_decision=severity,
            mitre_decision={"answer_visible": True},
            mitre_branch_result={"candidate_mitre": ["T1110.001"]},
        )

    assert result.guard_status == "blocked"
    assert result.fallback_used is True
    assert result.mitre_rationale_prose == build_deterministic_mitre_rationale(
        contract=contract,
        mitre_branch_result={"candidate_mitre": ["T1110.001"]},
    )


def test_disabled_returns_deterministic_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", False)
    contract = _contract()
    result = run_mitre_risk_rationale(
        contract=contract,
        query="q",
        severity_decision=SeverityDecision(
            severity_label="P3 Medium",
            matched_rules=["default_policy"],
            why_not_higher=["P1 requires: confirmed_success"],
            missing_evidence=[],
            source_refs=[],
            recommended_priority="standard_triage",
            allowed_action_tier=1,
        ),
        mitre_decision={},
        mitre_branch_result={"candidate_mitre": ["T1110.001"]},
    )
    assert isinstance(result, MitreRiskRationaleResult)
    assert result.llm_called is False
    assert result.severity_rationale_prose


def _severity() -> SeverityDecision:
    return SeverityDecision(
        use_case_id="auth_failed_login_spike",
        severity_label="P3 Medium",
        matched_rules=["default_policy"],
        why_not_higher=["P1 requires: confirmed_success"],
        missing_evidence=["confirmed_success"],
        source_refs=[],
        recommended_priority="standard_triage",
        allowed_action_tier=1,
    )


def test_two_internal_calls_record_two_budget_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: rationale makes mitre + risk calls; each must consume one slot.
    _enable_rationale(monkeypatch)
    from app.llm.turn_llm_budget import TurnLlmBudget

    payload = json.dumps(
        {
            "reasoning_summary": "Remains candidate.",
            "why_selected": ["Default policy."],
        }
    )

    def _fake_invoke(*, role: str, user_prompt: str, system_prompt: str, max_tokens: int):
        return payload, False, "local_primary"

    budget = TurnLlmBudget()
    with patch("app.llm.mitre_risk_rationale.invoke_sidecar_role", side_effect=_fake_invoke):
        run_mitre_risk_rationale(
            contract=_contract(),
            query="q",
            severity_decision=_severity(),
            mitre_decision={"answer_visible": True},
            mitre_branch_result={"candidate_mitre": ["T1110.001"]},
            budget=budget,
        )
    assert budget.sidecar_calls == 2


def test_budget_exhausted_blocks_second_internal_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_rationale(monkeypatch)
    from app.llm.turn_llm_budget import TurnLlmBudget

    calls: list[str] = []

    def _fake_invoke(*, role: str, user_prompt: str, system_prompt: str, max_tokens: int):
        calls.append(role)
        return json.dumps({"reasoning_summary": "x", "why_selected": ["y"]}), False, "local_primary"

    # Budget already at 1; cap is 2, so exactly one internal call may run.
    budget = TurnLlmBudget()
    budget.record_sidecar(role="intent_shadow_classifier", provider_label="local_primary", outcome="completed")
    with patch("app.llm.mitre_risk_rationale.invoke_sidecar_role", side_effect=_fake_invoke):
        run_mitre_risk_rationale(
            contract=_contract(),
            query="q",
            severity_decision=_severity(),
            mitre_decision={"answer_visible": True},
            mitre_branch_result={"candidate_mitre": ["T1110.001"]},
            budget=budget,
        )
    # One call ran (mitre), then budget hit cap of 2 → risk call blocked.
    assert budget.sidecar_calls == 2
    assert len(calls) == 1
