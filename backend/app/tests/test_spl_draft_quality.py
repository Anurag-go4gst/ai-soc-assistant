from __future__ import annotations

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
    assert any(item.rule_id.endswith("Q03") for item in report.findings)


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
    report = evaluate_draft_quality(family.draft_spl, extra_text=" ".join(family.assumptions))
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
    assert "caller_host" in spl
    assert preview["quality_status"] == "passed"


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
