"""WS-B: governed template promotion for privileged_account_failure (plan §4 B1/B3)."""
from __future__ import annotations

import pytest

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import SplValidationPolicy, load_spl_policy
from app.spl.template_registry import get_spl_template

TEMPLATE_ID = "privileged_account_failure"


def _policy_for(template) -> SplValidationPolicy:
    base = load_spl_policy()
    rules = template.validation_rules or {}

    def field(key: str, fallback):
        raw = rules.get(key)
        if isinstance(raw, list) and raw:
            return tuple(str(x).strip().lower() for x in raw if str(x).strip())
        return fallback

    return SplValidationPolicy(
        enabled=base.enabled,
        allowed_indexes=field("allowed_indexes", base.allowed_indexes),
        allowed_sourcetypes=field("allowed_sourcetypes", base.allowed_sourcetypes),
        default_earliest=base.default_earliest,
        default_latest=base.default_latest,
        max_result_limit=base.max_result_limit,
        allowed_commands=field("allowed_commands", base.allowed_commands),
        blocked_commands=base.blocked_commands,
        allow_wildcard_indexes=base.allow_wildcard_indexes,
        allow_macros=base.allow_macros,
        allow_subsearches=base.allow_subsearches,
        allow_external_calls=base.allow_external_calls,
        policy_version=base.policy_version,
    )


@pytest.fixture
def template():
    t = get_spl_template(TEMPLATE_ID)
    assert t is not None, "privileged_account_failure template missing from registry"
    return t


def test_template_is_active_and_production_executable(template):
    assert template.status == "active"
    assert template.is_production_executable() is True
    assert template.spl_text and template.spl_text.strip()
    assert template.use_case_id == "auth_privileged_login_anomaly"
    assert "EventCode" not in template.spl_text


def test_approve_path_template_spl_validates(template):
    result = validate_spl(template.spl_text, policy=_policy_for(template))
    assert result.get("approved") is True, result.get("reject_reasons")
    assert result.get("normalized_spl")
    assert "pgcil:auth" in template.spl_text
    assert "index=pgcil_soc" in template.spl_text


def test_returned_fields_present_in_spl(template):
    for field in ("event_count", "fail_count", "success_count", "first_seen", "last_seen"):
        assert field in template.spl_text


def test_blocked_path_disallowed_command_rejected(template):
    tampered = template.spl_text + " | delete"
    result = validate_spl(tampered, policy=_policy_for(template))
    assert result.get("approved") is False
    assert result.get("reject_reasons")


def test_blocked_path_wrong_sourcetype_rejected(template):
    tampered = template.spl_text.replace("pgcil:auth", "pgcil:edr")
    result = validate_spl(tampered, policy=_policy_for(template))
    assert result.get("approved") is False
    assert any("sourcetype" in r for r in (result.get("reject_reasons") or []))
