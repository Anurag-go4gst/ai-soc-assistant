"""OT-protocol lab draft family pack — review-only SPL for out-of-registry OT hunts.

Pins the Google-25 testing-ground upgrade: each OT/identity hunt now resolves to a
concrete review-only draft family (tier-1 SPL, never executable).
"""
from __future__ import annotations

import pytest

from app.spl.draft_preview import (
    _family_by_id,
    build_draft_preview,
    match_detection_family,
)
from app.spl.ot_protocol_families import ot_protocol_detection_families
from app.safeguards.spl_validator import validate_spl


# (query, expected detection family)
CASES = [
    ("Detect any logins to SCADA devices using known default or vendor credentials.", "ot_scada_default_credentials"),
    ("Flag any Modbus TCP traffic communicating on non-standard ports other than 502.", "ot_modbus_nonstandard_port"),
    ("Identify any smart meter or AMI endpoints running outdated firmware versions.", "ot_ami_firmware_anomaly"),
    ("Show the frequency of RTU connection drops to the control center.", "ot_rtu_connection_drops"),
    ("Identify any unusual DNP3 function codes sent to distribution RTUs.", "ot_dnp3_function_code"),
    ("Detect any PLCs that were switched from run mode into stop or program mode.", "ot_plc_mode_change"),
    ("Identify gaps or interruptions in PMU phasor data streams.", "ot_pmu_stream_gap"),
    ("Show any firewall policy or rule changes on the OT DMZ firewalls.", "ot_dmz_firewall_policy_change"),
    ("List any new Active Directory accounts created (event code 4720) in the last 7 days.", "windows_account_creation_4720"),
    ("Flag any vendor VPN account logged in concurrently from two different locations.", "auth_impossible_travel"),
]


@pytest.mark.parametrize("query,family", CASES)
def test_ot_query_matches_expected_family(query: str, family: str) -> None:
    assert match_detection_family(query) == family


def test_dnp3_write_modify_not_hijacked_by_function_code_family() -> None:
    # The existing scada_dnp3_modbus_write family must keep ownership of write/modify
    # command hunts; the new ot_dnp3_function_code only claims function-code phrasing.
    query = (
        "Search our SCADA firewall logs for any DNP3 or Modbus write/modify commands "
        "sent to our substation PLCs from an IP that is not our engineering workstation."
    )
    assert match_detection_family(query) == "scada_dnp3_modbus_write"


@pytest.mark.parametrize("family", ot_protocol_detection_families())
def test_family_spl_is_tier1_and_lint_clean(family) -> None:
    # Lab drafts stay review-only: no hard lint failures; validator only blocks on the
    # placeholder index/sourcetype (resolved at runtime), never on a disallowed command.
    from app.spl.draft_preview import evaluate_draft_quality

    quality = evaluate_draft_quality(family.draft_spl, detection_family=family.family_id)
    assert quality.hard_fail_count == 0
    reject = validate_spl(family.draft_spl).get("reject_reasons") or []
    assert set(reject) <= {"disallowed_index", "disallowed_sourcetype"}


@pytest.mark.parametrize("query,family", CASES)
def test_build_draft_preview_review_only(query: str, family: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(query)
    assert preview is not None
    assert preview["detection_family"] == family
    assert preview["execution_enabled"] is False
    assert preview["execution_eligible"] is False
    assert preview["governed"] is False
