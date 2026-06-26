"""Query-aware auth failed-login draft preview customization."""

from __future__ import annotations

import pytest

from app.config import settings
from app.spl.draft_preview import build_draft_preview
from app.spl.draft_preview_customization import (
    auth_failed_login_aggregation_shape,
    reconcile_evidence_plan_for_draft_preview,
    time_window_display_label,
)


def _blocked_validation() -> dict:
    return {"spl_template_status": "missing"}


@pytest.fixture(autouse=True)
def _enable_draft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


def test_last_hour_user_ranking_query_customizes_draft() -> None:
    query = "in the last hour, which users have abnormally high failed login counts?"
    preview = build_draft_preview(query, spl_validation=_blocked_validation())
    assert preview is not None
    assert preview["detection_family"] == "auth_failed_login_threshold"
    assert preview["aggregation_shape"] == "user_ranking"
    assert preview["time_window_label"] == "the last hour"
    spl = preview["draft_spl"]
    assert "earliest=-60m latest=now" in spl
    assert "by user_norm" in spl
    assert "dc(user_norm)" not in spl
    assert "fail_count>20" not in spl
    assert "distinct_sources" in spl


def test_time_window_label_last_hour() -> None:
    assert time_window_display_label("failed logins in the last hour") == "the last hour"


def test_auth_shape_user_vs_source() -> None:
    assert auth_failed_login_aggregation_shape("which users have failed logins") == "user_ranking"
    assert auth_failed_login_aggregation_shape("top source IPs by failed logins") == "source_user_pair"


def test_draft_preview_reconcile_clears_schema_field_gaps() -> None:
    preview = build_draft_preview(
        "in the last hour, which users have abnormally high failed login counts?",
        spl_validation=_blocked_validation(),
    )
    assert preview is not None
    plan = {
        "required_evidence_keys": ["user", "src", "host", "fail_count"],
        "missing_required_evidence": ["user", "src", "host", "privileged_account_impacted"],
        "present_evidence_keys": [],
    }
    reconciled = reconcile_evidence_plan_for_draft_preview(plan, preview)
    assert reconciled is not None
    assert "user" not in reconciled["missing_required_evidence"]
    assert "privileged_account_impacted" in reconciled["missing_required_evidence"]
