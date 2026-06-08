from __future__ import annotations

import pytest

from app.chat import pipeline as chat_pipeline
from app.config import settings
from app.spl.llm_fallback import LlmSplFallbackResult
from app.use_cases.content_enrichment import enrichment_spl_governance_for_runtime


class _Telemetry:
    def record_step(self, *args, **kwargs) -> None: ...
    def record_spl_validation(self, *args, **kwargs) -> None: ...


class _Profile:
    def model_dump(self) -> dict:
        return {}


@pytest.fixture(autouse=True)
def _phase6_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail,pgcil:edr,pgcil:dns")


def test_allowed_active_template_passes_validation_and_remains_review_only() -> None:
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="attack_discovery",
        user_query="generate SPL for failed login spike by source",
        template_id="auth_failed_login_spike",
        use_case_id="auth_failed_login_spike",
    )

    assert candidate is not None
    assert validation is not None
    assert validation["approved"] is True
    assert validation["normalized_spl"]
    assert validation["spl_template_status"] == "active"
    assert validation["allowed_by_enrichment"] is True
    assert validation["validator_status"] == "approved"
    assert validation["execution_enabled"] is False
    assert validation["review_required"] is True
    assert validation["review_required_reason"] == "candidate_spl_review_only"


def test_disallowed_template_is_blocked() -> None:
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="attack_discovery",
        user_query="generate SPL for failed login spike",
        template_id="auth_success_after_failure",
        use_case_id="auth_failed_login_spike",
    )

    assert candidate is not None
    assert validation is not None
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert validation["review_required_reason"] == "spl_template_not_allowed_by_enrichment"
    assert "spl_template_not_allowed_by_enrichment" in validation["reject_reasons"]


def test_planned_template_does_not_emit_governed_spl() -> None:
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="attack_discovery",
        user_query="investigate suspicious email headers",
        template_id=None,
        use_case_id="email_phishing_header_review",
    )

    assert candidate is not None
    assert validation is not None
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert validation["spl_template_status"] == "planned"
    assert validation["review_required_reason"] == "spl_template_planned_no_free_spl_fallback"


def test_unavailable_or_missing_template_does_not_emit_governed_spl() -> None:
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="attack_discovery",
        user_query="triage a generic SOC incident",
        template_id="missing_template",
        use_case_id="soc_incident_triage",
    )

    assert candidate is not None
    assert validation is not None
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert validation["spl_template_status"] == "unavailable"
    assert validation["review_required_reason"] == "spl_template_unavailable_no_free_spl_fallback"


def test_sop_only_does_not_claim_active_spl_investigation_support() -> None:
    candidate, validation = chat_pipeline._candidate_clarification(
        trace_id="t",
        skill="attack_discovery",
        user_query="show SOP only",
        telemetry=_Telemetry(),
        profile=_Profile(),
        reason="spl_template_sop_only_no_active_investigation_support",
        spl_governance={
            "spl_template_status": "sop_only",
            "allowed_spl_templates": [],
            "evidence_requirements": [],
            "governed_limitation": "spl_template_sop_only_no_active_investigation_support",
        },
    )

    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["spl_template_status"] == "sop_only"
    assert validation["template_production_executable"] is False
    assert validation["review_required_reason"] == "spl_template_sop_only_no_active_investigation_support"


def test_spl_validator_failure_blocks_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failed_validate(_spl: str) -> dict:
        return {
            "approved": False,
            "normalized_spl": None,
            "reject_reasons": ["blocked_command:delete"],
            "warnings": [],
            "enforced_limits": {},
            "policy_version": "test",
        }

    monkeypatch.setattr(chat_pipeline, "validate_spl", _failed_validate)

    candidate, validation = chat_pipeline._candidate_from_default_template(
        trace_id="t",
        skill="attack_discovery",
        user_query="generate SPL for failed login spike",
        template_id="auth_failed_login_spike",
        spl_governance=enrichment_spl_governance_for_runtime("auth_failed_login_spike"),
    )

    assert candidate["candidate_spl"]
    assert validation["approved"] is False
    assert validation["normalized_spl"] is None
    assert validation["validator_status"] == "blocked"
    assert validation["review_required_reason"] == "spl_validation_failed"
    assert "blocked_command:delete" in validation["reject_reasons"]


def test_llm_spl_fallback_is_not_used_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def _fallback(*, user_query: str) -> LlmSplFallbackResult:
        nonlocal called
        called = True
        return LlmSplFallbackResult(candidate_spl="search index=pgcil_soc sourcetype=pgcil:auth earliest=-1h latest=now | stats count | head 100", approved=True, validation={})

    monkeypatch.setattr(chat_pipeline, "generate_llm_spl_fallback", _fallback)

    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="spl_generation",
        user_query="write unsupported SPL",
        template_id=None,
        use_case_id="auth_failed_login_spike",
    )

    assert called is False
    assert candidate is not None
    assert validation is not None
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False
    assert validation["review_required_reason"] == "spl_template_missing"


def test_planner_selecting_spl_branch_does_not_imply_execution() -> None:
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="spl_generation",
        user_query="generate SPL for DNS beaconing candidates",
        template_id="dns_beaconing_candidate",
        use_case_id="dns_beaconing_candidate",
    )

    assert candidate is not None
    assert validation is not None
    assert validation["approved"] is True
    assert candidate["execution_enabled"] is False
    assert validation["execution_enabled"] is False
    assert validation["execution_eligible"] is False
    assert validation["review_required"] is True


def test_enrichment_only_pilot_cannot_provide_runtime_spl_governance() -> None:
    assert enrichment_spl_governance_for_runtime("email_phishing_header_review") is None

    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="attack_discovery",
        user_query="investigate suspicious email headers",
        template_id=None,
        use_case_id="email_phishing_header_review",
    )

    assert candidate is not None
    assert validation is not None
    assert validation["candidate_provider_reason"] == "spl_template_planned_no_free_spl_fallback"
    assert validation["approved"] is False
