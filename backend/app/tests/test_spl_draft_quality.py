from __future__ import annotations

import re

import pytest

from app.spl.draft_preview import DETECTION_FAMILIES, DRAFT_STATUS, build_draft_preview
from app.spl.draft_quality import STANDARD_ID, evaluate_draft_quality
from app.config import settings


def test_standard_id_constant() -> None:
    assert STANDARD_ID == "SOC-STD-SPL-001"


def test_broken_quoted_string_is_hard_fail() -> None:
    bad = 'search index=foo sourcetype=bar earliest=-1h latest=now "line1\nline2" | stats count'
    report = evaluate_draft_quality(bad)
    assert report.hard_fail_count >= 1
    assert any(item.rule_id.endswith("Q01") for item in report.findings)


def test_unescaped_windows_path_is_hard_fail() -> None:
    bad = 'search index=foo | where ParentImage="*\\w3wp.exe"'
    report = evaluate_draft_quality(bad)
    assert report.hard_fail_count >= 1
    assert any(item.rule_id.endswith("Q02") for item in report.findings)


def test_early_strftime_before_stats_is_hard_fail() -> None:
    bad = """
search index=foo sourcetype=bar
| eval event_time=_time
| eval readable=strftime(event_time, "%F %T")
| stats count by user
"""
    report = evaluate_draft_quality(bad)
    assert report.hard_fail_count >= 1
    assert any(item.rule_id.endswith("U02") for item in report.findings)


def test_strftime_on_time_before_streamstats_is_hard_fail() -> None:
    bad = """
search index=foo sourcetype=bar
| eval t=strftime(_time, "%F")
| streamstats count as fail_count by src_ip_norm
"""
    report = evaluate_draft_quality(bad)
    assert any(
        item.rule_id.endswith("U02") and item.severity == "hard_fail" for item in report.findings
    )


def test_earliest_latest_without_strftime_after_stats_is_hard_fail() -> None:
    bad = """
search index=foo sourcetype=bar EventCode=4740
| stats count earliest(_time) as first_seen latest(_time) as last_seen by user
| table user count first_seen last_seen
"""
    report = evaluate_draft_quality(bad)
    assert any(item.rule_id.endswith("U02") for item in report.findings)


def test_shift_left_eventcode_must_be_in_base_search() -> None:
    bad = """
search index=win sourcetype=wineventlog earliest=-24h latest=now
| search EventCode=4740
| stats count by user
"""
    report = evaluate_draft_quality(bad, detection_family="windows_account_lockout")
    assert any(item.rule_id.endswith("U01") for item in report.findings)


def test_delayed_static_filter_emits_shift_left_warning() -> None:
    bad = """
search index=fw sourcetype=pan earliest=-24h latest=now
| search action=allowed
| stats count by src_ip
"""
    report = evaluate_draft_quality(bad)
    assert any(
        item.rule_id.endswith("U01") and item.severity == "warning" for item in report.findings
    )


def test_esp_noisy_wildcard_in_base_search_is_hard_fail() -> None:
    bad = """
search index=fw sourcetype=pan action=allowed (*it* OR *corporate*)
| eval session_state_norm=lower(coalesce(session_state, ""))
| stats count by src_ip_norm
"""
    report = evaluate_draft_quality(bad, detection_family="esp_it_to_ot_connection")
    assert any(item.rule_id.endswith("Q13") and item.severity == "hard_fail" for item in report.findings)


def test_esp_blank_session_state_pass_is_hard_fail() -> None:
    bad = """
search index=fw sourcetype=pan (action=allowed OR action=accept)
| eval session_state_norm=lower(coalesce(session_state, ""))
| where session_state_norm="" OR like(session_state_norm, "%establish%")
| stats count by src_ip_norm
"""
    report = evaluate_draft_quality(bad, detection_family="esp_it_to_ot_connection")
    assert any(item.rule_id.endswith("Q13") for item in report.findings)


def test_esp_fuzzy_zone_like_is_warning() -> None:
    bad = """
search index=fw sourcetype=pan action=allowed earliest=-24h latest=now
| eval src_zone_norm=lower(coalesce(src_zone, ""))
| eval dest_zone_norm=lower(coalesce(dest_zone, ""))
| where like(src_zone_norm, "%it%") AND like(dest_zone_norm, "%ot%")
| stats count by src_ip_norm
"""
    report = evaluate_draft_quality(bad, detection_family="esp_it_to_ot_connection")
    assert any(item.rule_id.endswith("Q12") for item in report.findings)


def test_stats_inclusion_critical_field_is_hard_fail() -> None:
    bad = """
search index=fw sourcetype=pan action=allowed earliest=-24h latest=now
| eval src_zone_norm=lower(coalesce(src_zone, ""))
| eval app_norm=lower(coalesce(app, ""))
| stats count by src_ip_norm
| table src_ip_norm src_zones applications
"""
    report = evaluate_draft_quality(bad, detection_family="esp_it_to_ot_connection")
    assert any(
        item.rule_id.endswith("U03") and item.severity == "hard_fail" for item in report.findings
    )


@pytest.mark.parametrize(
    ("family_id", "needle"),
    [
        ("windows_account_lockout", "EventCode=4740"),
        ("sysmon_web_shell_spawn", "EventCode=1"),
        ("windows_privileged_group_changes", "EventCode=4728"),
        ("esp_it_to_ot_connection", "action=allowed"),
        ("substation_hmi_brute_force", "failure"),
        ("scada_dnp3_modbus_write", "*dnp3*"),
    ],
)
def test_draft_families_shift_left_static_filters(family_id: str, needle: str) -> None:
    family = next(item for item in DETECTION_FAMILIES if item.family_id == family_id)
    base_search = family.draft_spl.split("|")[0]
    assert needle.lower() in base_search.lower()


def test_cidr_in_without_cidrmatch_is_warning() -> None:
    bad = 'search index=fw | where src_ip IN ("10.0.0.0/8")'
    report = evaluate_draft_quality(bad)
    assert any(item.rule_id.endswith("Q07") and item.severity == "warning" for item in report.findings)


def test_cidrmatch_passes_cidr_rule() -> None:
    good = 'search index=fw | where cidrmatch("10.0.0.0/8", src_ip)'
    report = evaluate_draft_quality(good)
    assert not any(item.rule_id.endswith("Q07") for item in report.findings)


@pytest.mark.parametrize("family_id", [family.family_id for family in DETECTION_FAMILIES])
def test_all_draft_families_pass_quality_lint(family_id: str) -> None:
    family = next(item for item in DETECTION_FAMILIES if item.family_id == family_id)
    report = evaluate_draft_quality(
        family.draft_spl,
        extra_text=" ".join(family.assumptions),
        detection_family=family_id,
    )
    assert report.hard_fail_count == 0, f"{family_id}: {[item.message for item in report.findings if item.severity == 'hard_fail']}"


def test_4740_draft_uses_caller_computer_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(
        "Show Windows Event ID 4740 lockouts",
        spl_validation={"approved": False, "normalized_spl": None, "reject_reasons": ["spl_template_missing"]},
        family_id="windows_account_lockout",
    )
    assert preview is not None
    spl = preview["draft_spl"]
    assert "Caller_Computer_Name" in spl
    assert "caller_host_norm" in spl
    assert re.search(r"\bComputerName\b", spl.replace("CallerComputerName", "")) is None
    assert preview["quality_status"] == "passed"


def test_4740_computer_name_only_is_hard_fail() -> None:
    bad = """
search index=win sourcetype=wineventlog EventCode=4740
| eval caller_host_norm=lower(coalesce(ComputerName, ""))
| stats count by target_user_norm
"""
    report = evaluate_draft_quality(bad, detection_family="windows_account_lockout")
    assert any(item.rule_id.endswith("Q10") for item in report.findings)


def test_hmi_requires_streamstats_sort_order() -> None:
    bad = """
search index=sub sourcetype=hmi (failure OR fail)
| streamstats time_window=5m count as fail_count by src_ip_norm
"""
    report = evaluate_draft_quality(bad, detection_family="substation_hmi_brute_force")
    assert any(item.rule_id.endswith("Q11") for item in report.findings)
    good = """
search index=sub sourcetype=hmi (failure OR fail)
| sort 0 + _time
| streamstats time_window=5m count as fail_count by src_ip_norm
"""
    report_good = evaluate_draft_quality(good, detection_family="substation_hmi_brute_force")
    assert report_good.hard_fail_count == 0


def test_sysmon_draft_has_escaped_paths_and_pwsh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(
        "Sysmon w3wp.exe spawning cmd.exe",
        spl_validation={"approved": False, "normalized_spl": None, "reject_reasons": ["spl_template_missing"]},
        family_id="sysmon_web_shell_spawn",
    )
    assert preview is not None
    spl = preview["draft_spl"]
    assert "pwsh.exe" in spl
    assert "%\\\\w3wp.exe" in spl or '%\\w3wp.exe' in spl
    assert preview["quality_status"] == "passed"


def test_draft_preview_remains_not_governed_not_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(
        "privileged group Domain Admins 4728",
        spl_validation={"approved": False, "normalized_spl": None, "reject_reasons": ["spl_template_missing"]},
        family_id="windows_privileged_group_changes",
    )
    assert preview is not None
    assert preview["draft_status"] == DRAFT_STATUS
    assert preview["governed"] is False
    assert preview["catalog_approved"] is False
    assert preview["execution_enabled"] is False
    assert preview["quality_standard"] == STANDARD_ID
