from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.chat import pipeline as chat_pipeline
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.evals.spl_draft_preview_eval import (
    load_questions,
    run_spl_draft_preview_eval,
    write_spl_draft_preview_outputs,
)
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import (
    DRAFT_STATUS,
    DRAFT_WARNING,
    build_draft_preview,
    match_detection_family,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
QUESTIONS_PATH = REPO_ROOT / "docs" / "evals" / "known_spl_draft_questions.json"

PRIVILEGED_GROUP_QUERY = (
    "find any user who has added someone to a privileged group like Domain Admins "
    "more than 3 times in the past week, and show me who was added"
)
LOCKOUT_QUERY = (
    "Show me a list of all Windows Event ID 4740 account lockout events from the last 24 hours, "
    "including the target user, the computer where the lockout happened, and the total count per user."
)
SYSMON_QUERY = (
    "Search Sysmon logs for any instance where cmd.exe or powershell.exe was spawned directly "
    "by a web server process like w3wp.exe or apache.exe."
)
SCADA_QUERY = (
    "Search our SCADA firewall logs for any DNP3 or Modbus write/modify commands sent to our "
    "substation PLCs from an IP address that is not our engineering workstation."
)
ESP_QUERY = (
    "Look at our electronic security perimeter firewall logs and find any successful connections "
    "originating from the corporate IT network directly to the OT control center network."
)
HMI_QUERY = (
    "Find any IP address that has failed to log into our substation OS or HMI portals more than "
    "10 times within a 5-minute window."
)


@pytest.fixture(autouse=True)
def _governance_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_template_governance_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", False)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(settings, "mcp_server_mock_execution_enabled", False)


def _blocked_validation(reason: str) -> dict:
    return {
        "approved": False,
        "normalized_spl": None,
        "reject_reasons": [reason],
        "review_required_reason": reason,
        "spl_template_status": "unavailable",
    }


def test_flag_off_preserves_blocked_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", False)
    preview = build_draft_preview(PRIVILEGED_GROUP_QUERY, spl_validation=_blocked_validation("spl_template_missing"))
    assert preview is None

    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="spl_generation",
        user_query=PRIVILEGED_GROUP_QUERY,
        template_id=None,
        use_case_id="soc_incident_triage",
    )
    assert candidate is not None
    assert validation is not None
    assert candidate["candidate_spl"] == ""
    assert validation["approved"] is False


@pytest.mark.parametrize(
    ("query", "family"),
    [
        (PRIVILEGED_GROUP_QUERY, "windows_privileged_group_changes"),
        (LOCKOUT_QUERY, "windows_account_lockout"),
        (SYSMON_QUERY, "sysmon_web_shell_spawn"),
        (SCADA_QUERY, "scada_dnp3_modbus_write"),
        (ESP_QUERY, "esp_it_to_ot_connection"),
        (HMI_QUERY, "substation_hmi_brute_force"),
    ],
)
def test_flag_on_builds_draft_preview_for_families(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    family: str,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    assert match_detection_family(query) == family
    preview = build_draft_preview(query, spl_validation=_blocked_validation("spl_template_missing"))
    assert preview is not None
    assert preview["draft_status"] == DRAFT_STATUS
    assert preview["draft_source"] == "deterministic_pattern"
    assert preview["detection_family"] == family
    assert preview["review_required"] is True
    assert preview["execution_enabled"] is False
    assert preview["governed"] is False
    assert preview["catalog_approved"] is False
    assert preview["warning"] == DRAFT_WARNING
    assert "<" in preview["draft_spl"]
    assert preview["validator_status"] in {"approved", "blocked"}


def test_draft_is_never_marked_governed_or_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(LOCKOUT_QUERY, spl_validation=_blocked_validation("spl_template_missing"))
    assert preview is not None
    assert preview["governed"] is False
    assert preview["execution_enabled"] is False
    assert preview["execution_eligible"] is False
    assert "not catalog-approved" in preview["not_catalog_approved_notice"].lower()


def test_live_response_includes_draft_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    response = build_live_chat_response(ChatRequest(message=SYSMON_QUERY))
    assert response.spl_draft_preview is not None
    assert response.spl_draft_preview.draft_status == DRAFT_STATUS
    if response.spl_validation is not None:
        assert response.spl_validation.approved is False
    assert response.execution is None or response.execution.status != "executed"
    assert DRAFT_WARNING in (response.message or "")


def test_live_response_omits_draft_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", False)
    response = build_live_chat_response(ChatRequest(message=SYSMON_QUERY))
    assert response.spl_draft_preview is None


def test_known_questions_file_has_six_examples() -> None:
    questions = load_questions(QUESTIONS_PATH)
    assert len(questions) == 6
    ids = {str(item["id"]) for item in questions}
    assert ids == {
        "privileged_group_additions",
        "windows_4740_lockouts",
        "sysmon_web_shell_spawn",
        "scada_dnp3_modbus_write",
        "esp_it_to_ot_connection",
        "substation_hmi_brute_force",
    }


def test_draft_eval_report_is_generated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    result = run_spl_draft_preview_eval(questions_path=QUESTIONS_PATH)
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "summary.md"
    write_spl_draft_preview_outputs(result, json_path=json_path, md_path=md_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_rows"] == 12
    assert json_path.exists()
    assert md_path.exists()
    assert result.passed_rows == result.total_rows
