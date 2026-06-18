"""WS-B: governed template promotion for vpn_failure_spike + firewall_deny_spike.

Both required new sourcetypes (pgcil:vpn, pgcil:firewall) added to the allowlist;
previously blocked_until_scd_fields_exist. Asserts approve + blocked paths.
"""
from __future__ import annotations

import pytest

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import load_spl_policy, policy_with_template_profile
from app.spl.template_registry import get_spl_template


def _policy_for(template):
    return policy_with_template_profile(load_spl_policy(), template.validation_rules)


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
