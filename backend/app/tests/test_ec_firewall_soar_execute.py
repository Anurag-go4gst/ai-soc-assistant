"""Firewall execute path uses EC SOAR adapter."""

from __future__ import annotations

from app.demo import ec_actions, ec_soar


def setup_function() -> None:
    ec_actions.clear_all_for_tests()
    ec_soar.clear_all_for_tests()


def test_firewall_execute_uses_soar_adapter() -> None:
    fake = ec_soar.FakeSoarTransport()
    ec_soar.set_transport_for_tests(fake)
    prepared = ec_actions.prepare_action(
        kind="firewall_block",
        label="Prepare firewall block",
        session_id="s1-fw",
        scenario_id="s1_governed_splunk_investigation",
        extra={
            "indicator": "198.51.100.42",
            "soar": {"playbook": "ip_block", "indicator": "198.51.100.42", "action": "block"},
        },
    )
    approved = ec_actions.approve_action(prepared.action_id)
    executed = ec_actions.execute_action(approved.action_id)
    assert executed.state == "EXECUTED"
    assert executed.production_side_effect is False
    assert len(fake.submitted) == 1
    assert "SOAR" in str(executed.receipt.get("summary") or "")
