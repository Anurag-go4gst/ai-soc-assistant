from __future__ import annotations

from app.config import settings
from app.orchestration.catalogue_execution_eligibility import catalogue_auto_execute_eligible


def test_catalogue_auto_execute_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED", "false")
    monkeypatch.setattr(settings, "ai_soc_catalogue_auto_execute_enabled", False)
    ok, reason = catalogue_auto_execute_eligible(
        match_path="exact_105_question",
        question_ref="q0.q046",
        use_case_id="auth_failed_login_spike",
        spl_validation={"approved": True, "normalized_spl": "search index=x | stats count"},
    )
    assert ok is False
    assert reason == "catalogue_auto_execute_disabled"


def test_catalogue_auto_execute_eligible_when_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED", "true")
    monkeypatch.setattr(settings, "ai_soc_catalogue_auto_execute_enabled", True)
    ok, reason = catalogue_auto_execute_eligible(
        match_path="exact_105_question",
        question_ref="q0.q046",
        use_case_id="auth_failed_login_spike",
        spl_validation={"approved": True, "normalized_spl": "search index=pgcil_soc | stats count"},
        selected_mcp_tool="splunk_run_query",
    )
    assert ok is True
    assert reason == "catalogue_known_template_binding"
