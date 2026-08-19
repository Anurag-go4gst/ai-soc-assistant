"""EC action simulation never touches production /api/actions."""

from __future__ import annotations

import inspect

from app.demo import ec_actions


def setup_function() -> None:
    ec_actions.clear_all_for_tests()


def test_ec_actions_module_does_not_import_routes_actions() -> None:
    source = inspect.getsource(ec_actions)
    assert "routes_actions" not in source
    assert "from app.actions" not in source
    assert "evaluate_mcp_execution" not in source


def test_approve_execute_verify_has_no_production_side_effect() -> None:
    prepared = ec_actions.prepare_action(
        kind="ticket_create",
        label="Open P1 incident ticket",
        session_id="ec-act",
        scenario_id="firewall_deny_coordinated_attack",
    )
    approved = ec_actions.approve_action(prepared.action_id)
    assert approved.state == "APPROVED"
    assert approved.production_side_effect is False
    executed = ec_actions.execute_action(prepared.action_id)
    assert executed.state == "EXECUTED"
    assert executed.production_side_effect is False
    assert executed.receipt is not None
    assert executed.receipt["production_side_effect"] is False
    verified = ec_actions.verify_action(prepared.action_id)
    assert verified.state == "VERIFIED"
    assert verified.production_side_effect is False


def test_ticket_receipt_uses_incident_id_and_demo_friendly_summary() -> None:
    prepared = ec_actions.prepare_action(
        kind="ticket_create",
        label="Create incident ticket",
        session_id="ec-ticket",
        scenario_id="s1_governed_splunk_investigation",
        extra={"ticket": {"id": "INC-2026-89412", "severity": "P2 High"}},
    )
    executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
    assert executed.receipt is not None
    assert executed.receipt["summary"] == "Incident ticket INC-2026-89412 created and linked to this investigation."
    assert executed.receipt["ticket"]["ticket_id"] == "INC-2026-89412"
