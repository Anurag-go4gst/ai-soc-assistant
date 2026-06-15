from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

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
    DETECTION_FAMILIES,
    DRAFT_PREVIEW_FORBIDDEN_PHRASES,
    DRAFT_STATUS,
    DRAFT_WARNING,
    build_draft_preview,
    family_presentation,
    match_detection_family,
)
from app.spl.draft_preview_lint import (
    lint_draft_spl,
    lint_prohibited_claims,
    lint_quoted_string_newlines,
    lint_strftime_for_time_fields,
    lint_windows_path_escaping,
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
SMB_TOP_HOSTS_QUERY = "Which hosts are generating the most SMB traffic?"
VPN_NEW_COUNTRY_QUERY = (
    "Draft a Splunk search to find VPN logins from countries not seen before for the same user."
)
AUTH_SUCCESS_AFTER_FAIL_QUERY = (
    "Look for successful VPN logins after repeated failures for the same user."
)
DNS_BEACONING_QUERY = "Find DNS queries that may indicate beaconing or C2 activity."
POWERSHELL_QUERY = (
    "Search endpoint logs for suspicious PowerShell with encoded commands or download cradles."
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


def _preview(monkeypatch: pytest.MonkeyPatch, query: str, family_id: str | None = None) -> dict:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(query, spl_validation=_blocked_validation("spl_template_missing"))
    assert preview is not None
    if family_id:
        assert preview["detection_family"] == family_id
    return preview


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
    preview = _preview(monkeypatch, query, family)
    assert preview["draft_status"] == DRAFT_STATUS
    assert preview["draft_source"] == "deterministic_pattern"
    assert preview["review_required"] is True
    assert preview["execution_enabled"] is False
    assert preview["governed"] is False
    assert preview["catalog_approved"] is False
    assert preview["warning"] == DRAFT_WARNING
    assert "<" in preview["draft_spl"]
    assert preview["draft_lint_status"] == "passed"
    assert preview["quality_status"] == "passed"
    assert preview["quality_standard"] == "SOC-STD-SPL-001"
    assert preview["hard_fail_count"] == 0
    assert preview["validator_status"] in {"approved", "blocked"}


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
def test_draft_preview_never_calls_llm_fallback(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    family: str,
) -> None:
    """Lab draft preview is deterministic-only; LLM SPL fallback is a separate path."""
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_spl_fallback_enabled", True)
    with patch("app.spl.llm_fallback.generate_llm_spl_fallback") as llm_fallback:
        preview = build_draft_preview(query, spl_validation=_blocked_validation("spl_template_missing"))
        assert preview is not None
        assert preview["detection_family"] == family
        assert preview["draft_source"] == "deterministic_pattern"
        llm_fallback.assert_not_called()


def test_draft_preview_runs_quality_lint_before_return(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    from app.spl.draft_quality import evaluate_draft_quality as real_evaluate_draft_quality

    with patch(
        "app.spl.draft_preview.evaluate_draft_quality",
        wraps=real_evaluate_draft_quality,
    ) as quality_lint:
        preview = build_draft_preview(
            LOCKOUT_QUERY,
            spl_validation=_blocked_validation("spl_template_missing"),
        )
        assert preview is not None
        quality_lint.assert_called_once()
        assert preview["quality_standard"] == "SOC-STD-SPL-001"
        assert "quality_status" in preview
        assert "draft_lint_status" in preview


def test_all_registered_drafts_pass_lint() -> None:
    from app.spl.draft_quality import evaluate_draft_quality

    for family in DETECTION_FAMILIES:
        report = evaluate_draft_quality(
            family.draft_spl,
            extra_text=" ".join(family.assumptions),
            detection_family=family.family_id,
        )
        assert report.hard_fail_count == 0, f"{family.family_id}: {report.findings}"
        violations = lint_draft_spl(family.draft_spl, extra_text=" ".join(family.assumptions))
        assert violations == [], f"{family.family_id}: {violations}"


def test_family_selection_separates_success_after_failure_from_vpn_new_country() -> None:
    """Generic: shared tokens (login/same user) must not collapse the two auth families."""
    success_after_failure = "Look for successful logins after repeated failures for the same user."
    new_country = "Draft a Splunk search for VPN logins from a country not seen before for the same user."
    assert match_detection_family(success_after_failure) == "auth_success_after_failure"
    assert match_detection_family(new_country) == "vpn_new_country_login"
    # And the inverse: neither prompt steals the other's draft family.
    assert match_detection_family(success_after_failure) != "vpn_new_country_login"
    assert match_detection_family(new_country) != "auth_success_after_failure"


def test_vpn_new_country_draft_uses_eventstats_first_seen_not_streamstats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = _preview(
        monkeypatch,
        "VPN login from a new country never seen for this user",
        "vpn_new_country_login",
    )
    spl = preview["draft_spl"]
    assert "eventstats min(_time) as first_country_seen" in spl
    assert "streamstats current=f" not in spl
    assert "sort 0 - _time" in spl  # native-time sort before strftime presentation
    assert preview["hard_fail_count"] == 0


def test_success_after_failure_draft_correlates_failure_then_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = _preview(
        monkeypatch,
        "Show successful login after repeated failed attempts for the same account",
        "auth_success_after_failure",
    )
    spl = preview["draft_spl"]
    assert "failure_count" in spl and "success_count" in spl
    assert "last_success_epoch>first_failure_epoch" in spl  # success must follow failure
    assert "by user_norm" in spl  # correlate per user
    assert preview["hard_fail_count"] == 0
    assert preview["governed"] is False
    assert preview["execution_enabled"] is False


def test_mixed_spl_and_block_ip_routes_unsafe_and_suppresses_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsafe enforcement intent overrides SPL/search intent — no draft surfaced."""
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    response = build_live_chat_response(
        ChatRequest(message="Give me an SPL to block this IP immediately on the firewall.")
    )
    payload = response.model_dump()
    assert (payload.get("planning_decision") or {}).get("path_type") == "unsafe_blocked"
    assert response.spl_draft_preview is None
    assert (payload.get("analyst_response") or {}).get("hil_status") == "required"


@pytest.mark.parametrize(
    "query",
    [
        "Clear MFA factors for this user.",
        "Expire all sessions for the compromised user.",
        "Quarantine endpoint now.",
    ],
)
def test_additional_enforcement_verbs_route_unsafe_block(
    query: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generic: enforcement verbs beyond block-ip also route unsafe (one shared signal)."""
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    response = build_live_chat_response(ChatRequest(message=query))
    payload = response.model_dump()
    assert (payload.get("planning_decision") or {}).get("path_type") == "unsafe_blocked"
    assert response.spl_draft_preview is None
    assert (payload.get("analyst_response") or {}).get("hil_status") == "required"


def test_lint_rejects_newline_inside_quoted_string() -> None:
    bad = 'search index=foo sourcetype=bar earliest=-1h latest=now "line1\nline2" | stats count'
    violations = lint_quoted_string_newlines(bad)
    assert violations and violations[0].endswith("Q01")


def test_lint_rejects_unescaped_windows_path_backslash() -> None:
    bad = 'search index=foo | where ParentImage="*\\w3wp.exe"'
    assert lint_windows_path_escaping(bad)


def test_lint_requires_strftime_when_earliest_latest_used() -> None:
    bad = "| stats count earliest(_time) as first_seen latest(_time) as last_seen by user"
    violations = lint_strftime_for_time_fields(bad)
    assert violations and any(item.endswith("U02") for item in violations)
    good = "| stats min(_time) as t | eval first_seen=strftime(t, \"%F %T\")"
    assert lint_strftime_for_time_fields(good) == []


def test_lint_rejects_prohibited_claims() -> None:
    assert lint_prohibited_claims("results were found in Splunk")
    assert lint_prohibited_claims("this SPL is catalog-approved")
    assert lint_prohibited_claims("approved for execution")


def test_privileged_group_spl_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, PRIVILEGED_GROUP_QUERY, "windows_privileged_group_changes")
    spl = preview["draft_spl"]
    assert "group_norm=lower(coalesce" in spl
    assert "actor_norm=lower(coalesce" in spl
    assert 'NOT like(actor_norm, "%$")' in spl
    assert "earliest(_time)" in spl
    assert "strftime" in spl


def test_4740_lockout_spl_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, LOCKOUT_QUERY, "windows_account_lockout")
    spl = preview["draft_spl"]
    assert "Caller_Computer_Name" in spl
    assert "caller_host_norm" in spl
    assert "values(caller_host_norm)" in spl
    assert re.search(r"\bComputerName\b", spl.replace("CallerComputerName", "")) is None
    assert "earliest(_time)" in spl


def test_sysmon_web_shell_spl_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, SYSMON_QUERY, "sysmon_web_shell_spawn")
    spl = preview["draft_spl"]
    assert "pwsh.exe" in spl
    assert "tomcat.exe" in spl
    assert "parent_image_norm" in spl
    assert "child_image_norm" in spl
    assert "sort 0 - _time" in spl
    assert 'spawn_time=strftime(_time, "%Y-%m-%d %H:%M:%S")' in spl
    assert "*\\w3wp.exe" not in spl


def test_scada_dnp3_modbus_spl_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, SCADA_QUERY, "scada_dnp3_modbus_write")
    spl = preview["draft_spl"]
    assert "(*dnp3* OR *modbus*)" in spl
    assert "protocol_norm=lower(coalesce" in spl
    assert "cidrmatch(" in spl
    assert "strftime" in spl


def test_esp_it_to_ot_spl_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, ESP_QUERY, "esp_it_to_ot_connection")
    spl = preview["draft_spl"]
    base_search = spl.split("|")[0]
    assert "action=allowed" in base_search
    assert "action=accept" in base_search
    assert "action=permit" in base_search
    assert "action=success" in base_search
    assert "*it*" not in base_search
    assert "*corporate*" not in base_search
    assert "*ot*" not in base_search
    assert "*control*" not in base_search
    assert 'session_state_norm=""' not in spl
    assert 'session_state_norm IN ("established"' in spl
    assert "session_state_norm" in spl
    assert "connection_state" in spl
    assert "protocol_norm" in spl
    assert "dest_port_norm" in spl
    assert "action_norm" in spl
    assert "values(protocol_norm)" in spl
    assert "values(dest_port_norm)" in spl
    assert "values(action_norm)" in spl
    assert "values(session_state_norm)" in spl
    assert "%establish%" not in spl
    assert "%connected%" not in spl
    assert "%built%" not in spl
    assert "src_zone_norm" in spl
    assert 'src_zone_norm IN ("<corporate_it_zone>"' in spl
    assert 'dest_zone_norm IN ("<ot_control_center_zone>"' in spl
    assert 'like(src_zone_norm, "%it%")' not in spl
    assert 'like(dest_zone_norm, "%ot%")' not in spl
    assert "values(app_norm)" in spl
    assert "cidrmatch(" in spl
    assert "corporate_it_cidr" in preview["required_source_profile_fields"]
    assert "corporate_it_cidr" not in preview["required_log_fields"]
    assert "session_state" in preview["required_log_fields"]
    assert preview.get("investigation_checklist")
    assert preview.get("scope_notice")
    assert preview["governed"] is False
    assert preview["catalog_approved"] is False
    assert preview["execution_enabled"] is False


def _assert_draft_preview_narrative(response) -> None:
    assert response.spl_draft_preview is not None
    analyst = response.analyst_response
    assert analyst is not None
    blob = " ".join(
        filter(
            None,
            [
                response.message,
                analyst.direct_answer_summary,
                analyst.foundation_sec_analysis,
                analyst.review_notice,
            ],
        )
    ).lower()
    for phrase in DRAFT_PREVIEW_FORBIDDEN_PHRASES:
        assert phrase not in blob, f"forbidden phrase in narrative: {phrase!r}"
    assert "lab-only draft spl preview" in blob
    assert "hil/soc review is required" in blob
    assert blob.count("lab-only draft spl preview") == 1
    assert analyst.hil_status == "required"
    assert analyst.spl_status == "review_required"
    assert response.message
    assert "hil/soc review is required" in response.message.lower()


def test_esp_draft_preview_review_wording(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    response = build_live_chat_response(ChatRequest(message=ESP_QUERY))
    _assert_draft_preview_narrative(response)


def test_esp_draft_preview_review_wording_with_live_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Composer must not overwrite draft-preview HIL/SOC review messaging."""
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "control_plane_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    bad_prose = (
        "The Security Pipeline (SPL) does not require review at this time, "
        "and no Human Intelligence (HIL) analysis is necessary."
    )
    with patch(
        "app.synthesis.governed_answer_composer.build_synthesis_client_from_settings",
        return_value=object(),
    ), patch(
        "app.synthesis.governed_answer_composer.LocalChatClient.generate",
        return_value=type("R", (), {"text": bad_prose})(),
    ):
        response = build_live_chat_response(ChatRequest(message=ESP_QUERY))
    _assert_draft_preview_narrative(response)


def test_substation_hmi_brute_force_spl_quality(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, HMI_QUERY, "substation_hmi_brute_force")
    spl = preview["draft_spl"]
    assert "like(app_norm" in spl
    assert "streamstats time_window=5m" in spl
    assert "sort 0 + _time" in spl
    assert "user_norm" in spl


def test_draft_is_never_marked_governed_or_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, LOCKOUT_QUERY)
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


def test_smb_top_talkers_uses_fielded_base_search_not_unfielded_wildcards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = _preview(monkeypatch, SMB_TOP_HOSTS_QUERY, "network_smb_top_talkers")
    spl = preview["draft_spl"]
    assert "*smb*" not in spl
    assert "*cifs*" not in spl
    assert "dest_port=445" in spl
    assert preview["family_title"] == "SMB top talkers — network analytics"
    assert preview["review_type"] == "analytics_review"


def test_bytes_total_uses_null_safe_coalesce(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, SMB_TOP_HOSTS_QUERY, "network_smb_top_talkers")
    assert "coalesce(bytes_out,0)+coalesce(bytes_in,0)" in preview["draft_spl"]
    assert "bytes_out + bytes_in" not in preview["draft_spl"]


def test_esp_it_to_ot_draft_uses_exact_zone_cidr_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = _preview(monkeypatch, ESP_QUERY, "esp_it_to_ot_connection")
    spl = preview["draft_spl"]
    assert "<corporate_it_zone>" in spl
    assert "<ot_control_center_zone>" in spl
    assert 'cidrmatch("<corporate_it_cidr>"' in spl
    assert "*ot*" not in spl.lower()


def test_vpn_new_country_draft_is_lab_only_with_source_profile_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preview = _preview(monkeypatch, VPN_NEW_COUNTRY_QUERY, "vpn_new_country_login")
    assert preview["review_type"] == "investigation_review"
    assert "vpn_index" in preview["required_source_profile_fields"]
    assert preview["draft_status"] == DRAFT_STATUS
    assert "not executed" in " ".join(preview["assumptions"]).lower()


@pytest.mark.parametrize(
    ("query", "family_id"),
    [
        (AUTH_SUCCESS_AFTER_FAIL_QUERY, "auth_success_after_failure"),
        (DNS_BEACONING_QUERY, "dns_beaconing_hunt"),
        (POWERSHELL_QUERY, "endpoint_powershell_suspicious"),
    ],
)
def test_investigation_draft_families_remain_review_only_not_executed(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    family_id: str,
) -> None:
    preview = _preview(monkeypatch, query, family_id)
    assert preview["draft_status"] == DRAFT_STATUS
    presentation = family_presentation(family_id)
    assert presentation["review_type"] == "investigation_review"
    assert "not executed" in presentation["review_type_display"].lower()


def test_draft_preview_never_marks_execution_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    preview = _preview(monkeypatch, SMB_TOP_HOSTS_QUERY)
    assert preview.get("execution_eligible") is not True
    assert preview["draft_status"] == DRAFT_STATUS
    for phrase in DRAFT_PREVIEW_FORBIDDEN_PHRASES:
        assert phrase.lower() not in preview["draft_spl"].lower()


def test_candidate_spl_still_requires_validator_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    candidate, validation = chat_pipeline._candidate_spl_stage(
        trace_id="t",
        skill="spl_generation",
        user_query=SMB_TOP_HOSTS_QUERY,
        template_id=None,
        use_case_id="network_smb_top_talkers",
    )
    assert candidate is not None
    assert validation is not None
    assert validation["approved"] is False or candidate.get("candidate_spl") == ""


def test_catalogue_use_case_family_fallback(monkeypatch):
    """Phase D: catalogue rows with no keyword/pattern match resolve to their
    mapped existing family via use_case_id, instead of returning no SPL."""
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "ai_soc_spl_draft_preview_enabled", True)
    # 'Investigate lateral movement candidate' does not hit a keyword rule alone.
    assert match_detection_family("Investigate lateral movement candidate") is None
    preview = build_draft_preview(
        "Investigate lateral movement candidate",
        use_case_id="edr_lateral_movement_candidate",
    )
    assert preview is not None
    assert preview["detection_family"] == "lateral_movement_internal"
    assert preview["execution_enabled"] is False


def test_catalogue_use_case_family_fallback_unmapped_returns_none(monkeypatch):
    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "ai_soc_spl_draft_preview_enabled", True)
    # An analyst-workflow use case (no detection family) gets no deterministic
    # draft via the use_case fallback.
    preview = build_draft_preview(
        "Show the SOP for this alert",
        use_case_id="soc_show_sop",
    )
    assert preview is None
