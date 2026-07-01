"""S6a — governed SPL template coverage expansion."""

from __future__ import annotations

import pytest

from app.chat import pipeline as chat_pipeline
from app.config import settings
from app.spl.template_registry import get_spl_template
from app.safeguards.spl_validator import validate_spl


@pytest.fixture(autouse=True)
def _flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "spl_allowed_sourcetypes", "pgcil:auth,pgcil:edr,pgcil:dns,pgcil:mail")


def test_active_templates_pass_validate_spl() -> None:
    for template_id in ("dns_beaconing_candidate", "edr_powershell_suspicious_command"):
        row = get_spl_template(template_id)
        assert row is not None
        result = validate_spl(str(row.spl_text or ""))
        assert result["approved"] is True


def test_planned_phishing_template_blocked_outside_lab() -> None:
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
    assert validation["execution_enabled"] is False


def test_planned_ransomware_template_metadata_present() -> None:
    row = get_spl_template("endpoint_ransomware_impact_review")
    assert row is not None
    assert row.enabled is False
    assert row.status == "planned"


def test_invalid_template_blocked() -> None:
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="attack_discovery",
        user_query="generate SPL",
        template_id="missing_template_xyz",
        use_case_id="auth_failed_login_spike",
    )
    assert validation is not None
    assert validation["approved"] is False
    assert validation["execution_enabled"] is False
