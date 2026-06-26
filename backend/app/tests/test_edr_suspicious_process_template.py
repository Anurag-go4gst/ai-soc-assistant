"""WS-B: governed template promotion for edr_suspicious_process (plan §4 B1/B3).

Promotes a previously `planned` (lab-draft-only) family to an active governed
template. Asserts the approve path (its own SPL validates under its rules) and the
blocked path (tampered SPL is rejected by the deterministic validator).
"""
from __future__ import annotations

import pytest

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import load_spl_policy, policy_with_template_profile
from app.spl.template_registry import get_spl_template

TEMPLATE_ID = "edr_suspicious_process"


def _policy_for(template):
    return policy_with_template_profile(load_spl_policy(), template.validation_rules)


@pytest.fixture
def template():
    t = get_spl_template(TEMPLATE_ID)
    assert t is not None, "edr_suspicious_process template missing from registry"
    return t


def test_template_is_active_and_production_executable(template):
    assert template.status == "active"
    assert template.is_production_executable() is True
    assert template.spl_text and template.spl_text.strip()
    assert template.use_case_id == "edr_suspicious_process"


def test_approve_path_template_spl_validates(template):
    result = validate_spl(template.spl_text, policy=_policy_for(template))
    assert result.get("approved") is True, result.get("reject_reasons")
    assert result.get("normalized_spl")
    # Stays within the EDR data boundary.
    assert "pgcil:edr" in template.spl_text
    assert "index=pgcil_soc" in template.spl_text


def test_returned_fields_present_in_spl(template):
    # Output contract fields the renderer relies on must actually be produced.
    for field in ("event_count", "process_name", "first_seen", "last_seen"):
        assert field in template.spl_text


def test_blocked_path_disallowed_command_rejected(template):
    # Append a command outside the template allowlist -> must be rejected.
    tampered = template.spl_text + " | delete"
    result = validate_spl(tampered, policy=_policy_for(template))
    assert result.get("approved") is False
    assert result.get("reject_reasons")


def test_blocked_path_wrong_sourcetype_rejected(template):
    tampered = template.spl_text.replace("pgcil:edr", "pgcil:firewall")
    result = validate_spl(tampered, policy=_policy_for(template))
    assert result.get("approved") is False
    assert any("sourcetype" in r for r in (result.get("reject_reasons") or []))
