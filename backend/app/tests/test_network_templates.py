"""WS-B: governed template promotion for vpn_failure_spike + firewall_deny_spike.

Both required new sourcetypes (pgcil:vpn, pgcil:firewall) added to the allowlist;
previously blocked_until_scd_fields_exist. Asserts approve + blocked paths.
"""
from __future__ import annotations

import pytest

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import SplValidationPolicy, load_spl_policy
from app.spl.template_registry import get_spl_template


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


@pytest.mark.parametrize(
    "template_id,sourcetype,fields",
    [
        ("vpn_failure_spike", "pgcil:vpn", ("failed_vpn_logins", "user", "first_seen")),
        ("firewall_deny_spike", "pgcil:firewall", ("deny_count", "src", "dest")),
    ],
)
def test_template_active_and_validates(template_id, sourcetype, fields):
    t = get_spl_template(template_id)
    assert t is not None
    assert t.status == "active"
    assert t.is_production_executable() is True
    result = validate_spl(t.spl_text, policy=_policy_for(t))
    assert result.get("approved") is True, result.get("reject_reasons")
    assert result.get("normalized_spl")
    assert sourcetype in t.spl_text
    for field in fields:
        assert field in t.spl_text


@pytest.mark.parametrize("template_id", ["vpn_failure_spike", "firewall_deny_spike"])
def test_blocked_path_disallowed_command(template_id):
    t = get_spl_template(template_id)
    result = validate_spl(t.spl_text + " | delete", policy=_policy_for(t))
    assert result.get("approved") is False
    assert result.get("reject_reasons")


@pytest.mark.parametrize(
    "template_id,wrong",
    [("vpn_failure_spike", "pgcil:auth"), ("firewall_deny_spike", "pgcil:dns")],
)
def test_blocked_path_wrong_sourcetype(template_id, wrong):
    t = get_spl_template(template_id)
    src = t.validation_rules["allowed_sourcetypes"][0]
    result = validate_spl(t.spl_text.replace(src, wrong), policy=_policy_for(t))
    assert result.get("approved") is False
    assert any("sourcetype" in r for r in (result.get("reject_reasons") or []))
