from __future__ import annotations

from app.config import settings
from app.orchestration.mcp_execution_gate import evaluate_mcp_execution
from app.spl.saved_search_preference import (
    SavedSearchHarvest,
    apply_saved_search_preference_to_spl,
    evaluate_saved_search_preference,
    preference_from_discovery_context,
    saved_searches_from_knowledge_result,
)


ALLOWLISTED_NAME = "SOC - Failed login spike"
UNLISTED_NAME = "Lab - Failed login draft"


def test_saved_searches_from_knowledge_result_parses_objects() -> None:
    payload = {
        "objects": [
            {"name": ALLOWLISTED_NAME, "object_type": "savedsearch", "description": "failed login brute force"},
            {"name": "lookup_table_x", "object_type": "lookup"},
        ]
    }
    harvested = saved_searches_from_knowledge_result(payload)
    assert len(harvested) == 1
    assert harvested[0].name == ALLOWLISTED_NAME


def test_allowlisted_match_plans_saved_search_primary(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", ALLOWLISTED_NAME)
    preference = evaluate_saved_search_preference(
        query="investigate failed login spike on app01",
        harvested=[SavedSearchHarvest(name=ALLOWLISTED_NAME, description="failed login detection")],
    )
    assert preference.status == "primary_saved_search"
    assert preference.planned_tool == "splunk_run_saved_search"
    assert preference.allowlisted is True

    generated_candidate = {"candidate_spl": "index=wineventlog action=failure", "source": "template"}
    generated_validation = {"approved": True, "normalized_spl": "index=wineventlog action=failure"}
    candidate, validation = apply_saved_search_preference_to_spl(
        preference,
        candidate_spl=generated_candidate,
        spl_validation=generated_validation,
    )
    assert candidate is not None
    assert candidate.get("generation_mode") == "saved_search_primary"
    assert candidate.get("saved_search_name") == ALLOWLISTED_NAME
    assert candidate.get("fallback_candidate_spl") == generated_candidate
    assert validation is not None
    assert validation.get("saved_search_name") == ALLOWLISTED_NAME
    assert validation.get("normalized_spl") is None


def test_matching_not_allowlisted_keeps_spl_with_advisory(monkeypatch) -> None:
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", "")
    monkeypatch.setattr(
        "app.spl.saved_search_preference.saved_search_name_allowed",
        lambda _name: False,
    )
    preference = evaluate_saved_search_preference(
        query="investigate failed login spike on app01",
        harvested=[SavedSearchHarvest(name=UNLISTED_NAME, description="failed login draft search")],
    )
    assert preference.status == "spl_generation"
    assert preference.allowlisted is False
    assert preference.matched_name == UNLISTED_NAME
    assert preference.analyst_message is not None
    assert "not allowlisted" in preference.analyst_message

    candidate, validation = apply_saved_search_preference_to_spl(
        preference,
        candidate_spl={"candidate_spl": "index=wineventlog"},
        spl_validation={"approved": True, "normalized_spl": "index=wineventlog"},
    )
    assert candidate == {"candidate_spl": "index=wineventlog"}
    assert validation == {"approved": True, "normalized_spl": "index=wineventlog"}


def test_no_harvest_is_byte_identical_preference() -> None:
    preference = evaluate_saved_search_preference(query="investigate failed login spike", harvested=[])
    assert preference.status == "no_harvest"
    assert preference_from_discovery_context(
        query="investigate failed login spike",
        discovery_context={"indexes": ["wineventlog"]},
    ) is None


def test_gate_saved_search_primary_requires_hil(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GLOBAL_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVER_MOCK_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(settings, "splunk_allow_run_saved_search", True)
    monkeypatch.setattr(settings, "splunk_allowed_saved_searches", ALLOWLISTED_NAME)
    monkeypatch.setattr("app.orchestration.mcp_execution_gate.settings.splunk_allowed_saved_searches", ALLOWLISTED_NAME)
    monkeypatch.setattr("app.orchestration.mcp_tool_selector.settings.splunk_allow_run_saved_search", True)
    monkeypatch.setattr(
        "app.orchestration.mcp_execution_gate.get_telemetry_connector",
        lambda: _FakeTelemetry(),
    )

    execution, review = evaluate_mcp_execution(
        trace_id="trace-saved-pref",
        selected_skill="spl_generation",
        workflow_plan={},
        spl_validation={"saved_search_name": ALLOWLISTED_NAME, "approved": True},
        execution_intent="saved_search_execution",
        requested_mcp_tool="splunk_run_saved_search",
    )
    assert execution["status"] == "requires_human_review"
    assert review["review_type"] == "saved_search_execution_confirmation"
    assert execution.get("execution_intent") == "saved_search_execution"


class _FakeTelemetry:
    def record_mcp_execution(self, *_args, **_kwargs) -> None:
        return None

    def record_mcp_tool_selection(self, *_args, **_kwargs) -> None:
        return None
