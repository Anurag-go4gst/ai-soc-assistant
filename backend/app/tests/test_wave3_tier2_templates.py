"""Wave 3 Cisco Tier-2 governed templates validate with template_profile."""
from __future__ import annotations

import re

import pytest

from app.safeguards.spl_validator import validate_spl
from app.spl.policy import load_spl_policy, policy_with_template_profile
from app.spl.template_registry import get_spl_template, load_spl_templates

WAVE3_TEMPLATE_IDS = (
    "cisco_cleartext_to_rtu",
    "cisco_stealthwatch_scan_with_asset",
    "cisco_duo_mfa_fatigue",
    "ot_firmware_drift",
    "ot_master_spoof",
    "ot_tftp_hmi",
    "physical_access_impossible",
    "cii_scan_detection",
    "loto_breaker_correlation",
    "cert_in_hash_match",
)

_SLOT_RESOLUTIONS = {
    "<cisco_firewall_index>": "pgcil_soc",
    "<cisco_firewall_sourcetype>": "cisco:firepower",
    "<stealthwatch_index>": "pgcil_soc",
    "<stealthwatch_sourcetype>": "cisco:stealthwatch",
    "<cisco_duo_index>": "pgcil_soc",
    "<cisco_duo_sourcetype>": "cisco:duo",
    "<network_index>": "pgcil_soc",
    "<network_traffic_sourcetype>": "pgcil:network",
    "<auth_index>": "pgcil_soc",
    "<auth_sourcetype>": "pgcil:auth",
    "<endpoint_index>": "pgcil_soc",
    "<endpoint_process_sourcetype>": "pgcil:edr",
}


def _policy_for(template):
    return policy_with_template_profile(load_spl_policy(), template.validation_rules)


def _resolve_placeholders(spl: str) -> str:
    resolved = spl
    for slot, value in _SLOT_RESOLUTIONS.items():
        resolved = resolved.replace(slot, value)
    return resolved


@pytest.mark.parametrize("template_id", WAVE3_TEMPLATE_IDS)
def test_wave3_template_active_review_only(template_id: str) -> None:
    template = get_spl_template(template_id)
    assert template is not None
    assert template.status == "active"
    assert template.use_case_id == template_id
    assert template.is_production_executable() is False


@pytest.mark.parametrize("template_id", WAVE3_TEMPLATE_IDS)
def test_wave3_template_validates_with_template_profile(template_id: str) -> None:
    template = get_spl_template(template_id)
    assert template is not None
    assert template.spl_text
    resolved = _resolve_placeholders(template.spl_text)
    result = validate_spl(resolved, policy=_policy_for(template))
    assert result.get("approved") is True, result.get("reject_reasons")


def test_registry_loads_all_wave3_templates() -> None:
    loaded = {item.template_id for item in load_spl_templates()}
    missing = [template_id for template_id in WAVE3_TEMPLATE_IDS if template_id not in loaded]
    assert not missing


def test_cleartext_template_requires_subsearch_capability_only() -> None:
    template = get_spl_template("cisco_cleartext_to_rtu")
    assert template is not None
    rules = template.validation_rules
    assert rules.get("allow_subsearches") is True
    assert "allowed_lookups" not in rules
    assert rules.get("allow_join") is not True
    assert rules.get("allow_transaction") is not True
    resolved = _resolve_placeholders(template.spl_text or "")
    assert re.search(r"\[ search ", resolved)


def test_loto_template_has_join_max_and_final_head() -> None:
    template = get_spl_template("loto_breaker_correlation")
    assert template is not None
    rules = template.validation_rules
    assert rules.get("allow_join") is True
    resolved = _resolve_placeholders(template.spl_text or "").lower()
    assert re.search(r"\|\s*join\b[^|]*\bmax=\d+\b", resolved)
    assert re.search(r"\|\s*head\s+\d+\s*$", resolved.strip())
