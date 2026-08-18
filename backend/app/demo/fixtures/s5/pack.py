"""S5 — Cisco R-17 policy-driven remediation. Simulated Cisco MCP only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo import ec_actions, ec_email_drafts
from app.demo.ec_remediation_s5 import (
    S5_LAYER2_PATH,
    build_s5_action_readiness,
    build_s5_investigation_scope,
    build_s5_resource_composition,
    build_s5_status_summary,
)
from app.demo.ec_journeys import journey_for
from app.demo.fixtures import common as C

S5_SCENARIO_ID = "s5_cisco_hardening_remediation"
S5_FAMILY = "s5_cisco_remediation"
S5_DEVICE = "R-17"
S5_QUERY = "Investigate the breach on Cisco router R-17 and check whether our hardening policy requires remediation."
S5_ALL_FOLLOWUPS = (
    C.chip("show_hardening_policy", "Show hardening policy"),
    C.chip("check_current_version", "Check current version"),
    C.chip("check_maintenance_window", "Check maintenance window"),
    C.chip("create_change_ticket", "Create change ticket", action=True),
    C.chip("request_network_approval", "Ask network team for approval", action=True),
    C.chip("approve_upgrade", "Approve upgrade", action=True),
    C.chip("execute_upgrade", "Execute upgrade", action=True),
    C.chip("verify_version", "Verify version", action=True),
    C.chip("update_incident", "Update incident", action=True),
    C.chip("generate_closure_summary", "Generate closure summary"),
)
S5_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S5_ALL_FOLLOWUPS)


def _visible_chips(applied: list[str]) -> list[Any]:
    chips = list(S5_ALL_FOLLOWUPS)
    if "execute_upgrade" not in applied:
        chips = [item for item in chips if item.follow_up_id != "verify_version"]
    if "check_current_version" not in applied and "show_hardening_policy" not in applied:
        chips = [item for item in chips if item.follow_up_id not in {"approve_upgrade", "execute_upgrade"}]
    return chips


def _version(applied: list[str], actions: list[Any]) -> int:
    if any(item.kind == "cisco_upgrade" and item.state in {"EXECUTED", "VERIFIED"} for item in actions):
        return 15
    return 14


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "confirmed",
        "confirmed": [
            f"{S5_DEVICE} is the affected Cisco router in this investigation",
            "Security evidence supports a breach condition on the device",
        ],
        "supported": ["Hardening policy applicability depends on current version"],
        "unconfirmed": ["Whether version 15 is already running", "Whether the change has been verified"],
        "missing_evidence": ["hardening policy text", "change ticket", "maintenance window"],
        "remediation_status": "not_started",
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("breach", "Breach / investigation evidence", "OBTAINED", f"{S5_DEVICE} is in a breach condition"),
        C.state_item("cisco_version", "cisco.get_version", "AVAILABLE_NOT_QUERIED", "Version probe not yet run", "simulated_mcp"),
        C.state_item("policy", "Enterprise hardening policy", "AVAILABLE_NOT_QUERIED", "EC scenario policy not opened", "ec_scenario_policy"),
        C.state_item("change", "Change ticket / maintenance window", "MISSING", "Change not prepared"),
        C.state_item("upgrade", "cisco.upgrade", "MISSING", "Upgrade not executed"),
        C.state_item("verify", "Post-upgrade verification", "MISSING", "Verification not run"),
    ]


def _upgrade_action(session_id: str):
    return next((item for item in C.actions_for(session_id, S5_SCENARIO_ID) if item.kind == "cisco_upgrade"), None)


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> None:
    if "check_current_version" in applied or not applied:
        # Initial investigation includes the version probe as Step 2 evidence when the
        # first version follow-up runs; initial turn still discloses 14 from the fixture.
        pass

    if "show_hardening_policy" in applied:
        C.set_status(state, "policy", "OBTAINED", "Compromised device on version 14 must be upgraded to 15", "ec_scenario_policy")
        extra.append(C.evidence("ev-s5-policy", "kb_fixture", "Enterprise hardening policy", [{
            "rule": "A compromised device running version 14 must be upgraded to version 15",
            "applies_because": ["device affected", "current_version=14", "breach condition met"],
            "not_production_cisco_guidance": True,
            "provenance": "ec_scenario_policy",
        }], provenance="ec_scenario_policy"))
        outcome["confirmed"].append("Hardening policy applies: version 14 must be upgraded to 15")
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "policy" not in item]

    if "check_current_version" in applied:
        C.ensure_executed_action(
            kind="cisco_get_version",
            label="cisco.get_version",
            session_id=session_id,
            scenario_id=S5_SCENARIO_ID,
            extra={"device": S5_DEVICE, "current_version": _version(applied, C.actions_for(session_id, S5_SCENARIO_ID)), "provenance": "simulated_mcp"},
        )
        version = _version(applied, C.actions_for(session_id, S5_SCENARIO_ID))
        C.set_status(state, "cisco_version", "OBTAINED", f"current_version={version}", "simulated_mcp")
        extra.append(C.evidence("ev-s5-version", "cisco_mcp_fixture", "cisco.get_version", [{"device": S5_DEVICE, "current_version": version}], provenance="simulated_mcp", tool_name="cisco.get_version"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "get_version" not in item]

    if "check_maintenance_window" in applied:
        extra.append(C.evidence("ev-s5-window", "itsm_fixture", "Maintenance window", [{"window": "2026-08-17T02:00Z/04:00Z", "required": True}], provenance="experience_center_fixture"))
        C.set_status(state, "change", "OBTAINED", "Maintenance window required 02:00–04:00Z")
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "maintenance" not in item.lower()]

    if "create_change_ticket" in applied:
        C.ensure_executed_action(
            kind="ticket_create",
            label="Create change ticket for R-17 upgrade",
            session_id=session_id,
            scenario_id=S5_SCENARIO_ID,
            extra={"ticket": {"id": "CHG-R17-15", "implementation": "cisco.upgrade 14→15", "rollback": "reload prior image", "verification": "cisco.get_version == 15"}},
        )
        C.set_status(state, "change", "OBTAINED", "CHG-R17-15 prepared with rollback and verification")

    if "request_network_approval" in applied:
        email_extra = ec_email_drafts.s5_network_approval_email(device=S5_DEVICE, applied=applied)
        C.ensure_hil_action(
            kind="email_send",
            label="Ask network team for approval",
            session_id=session_id,
            scenario_id=S5_SCENARIO_ID,
            extra=email_extra,
        )

    if "approve_upgrade" in applied:
        action = _upgrade_action(session_id) or C.ensure_hil_action(
            kind="cisco_upgrade",
            label="cisco.upgrade to 15",
            session_id=session_id,
            scenario_id=S5_SCENARIO_ID,
            extra={"device": S5_DEVICE, "target_version": 15, "verify_payload": {"current_version": 15, "device": S5_DEVICE}},
        )
        if action.state == "APPROVAL_REQUIRED":
            ec_actions.approve_action(action.action_id)

    if "execute_upgrade" in applied:
        action = _upgrade_action(session_id) or C.ensure_hil_action(
            kind="cisco_upgrade",
            label="cisco.upgrade to 15",
            session_id=session_id,
            scenario_id=S5_SCENARIO_ID,
            extra={"device": S5_DEVICE, "target_version": 15, "verify_payload": {"current_version": 15, "device": S5_DEVICE}},
        )
        if action.state == "APPROVED":
            ec_actions.execute_action(action.action_id)
            C.set_status(state, "upgrade", "OBTAINED", "cisco.upgrade executed to 15", "simulated_mcp")
            outcome["remediation_status"] = "executed_unverified"
            outcome["unconfirmed"] = ["Post-upgrade version verification"]
        else:
            C.set_status(state, "upgrade", "APPROVAL_REQUIRED", "Upgrade cannot execute until approved")

    if "verify_version" in applied:
        action = _upgrade_action(session_id)
        if action is not None and action.state == "EXECUTED":
            verified = ec_actions.verify_action(action.action_id)
            extra.append(C.evidence("ev-s5-verify", "cisco_mcp_fixture", "cisco.get_version after upgrade", [{"device": S5_DEVICE, "current_version": 15}], provenance="simulated_mcp", tool_name="cisco.get_version"))
            C.set_status(state, "verify", "OBTAINED", "current_version=15")
            C.set_status(state, "cisco_version", "OBTAINED", "current_version=15", "simulated_mcp")
            outcome["remediation_status"] = "verified"
            outcome["confirmed"].append("cisco.get_version returned 15 after upgrade")
            outcome["unconfirmed"] = [item for item in outcome["unconfirmed"] if "15" not in item and "verified" not in item.lower()]
            if verified.verify_result:
                outcome["verified_version"] = verified.verify_result.get("current_version")

    if "update_incident" in applied:
        C.ensure_executed_action(
            kind="ticket_update",
            label="Update incident and change ticket",
            session_id=session_id,
            scenario_id=S5_SCENARIO_ID,
            extra={"ticket": {"id": "INC-R17-001", "remediation": outcome.get("remediation_status")}},
        )
        outcome["remediation_status"] = "verified" if "verify_version" in applied else outcome.get("remediation_status")

    if "generate_closure_summary" in applied:
        outcome["closure_summary"] = (
            f"{S5_DEVICE} upgraded 14→15 under EC scenario policy. Verification read current_version=15. "
            "This is not production Cisco guidance."
        )


def build_s5_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = [
        C.evidence("ev-s5-breach", "splunk_mcp_fixture", "Breach evidence", [{"device": S5_DEVICE, "condition": "compromise_indicators_present"}], provenance="experience_center_fixture"),
        C.evidence("ev-s5-initial-version", "cisco_mcp_fixture", "cisco.get_version", [{"device": S5_DEVICE, "current_version": 14}], provenance="simulated_mcp", tool_name="cisco.get_version"),
    ]
    C.set_status(state, "cisco_version", "OBTAINED", "current_version=14", "simulated_mcp")
    _apply(applied, session_id, outcome, state, extra)
    version = _version(applied, C.actions_for(session_id, S5_SCENARIO_ID))
    remediation = outcome.get("remediation_status", "not_started")
    policy_opened = "show_hardening_policy" in applied
    if policy_opened:
        assessment = (
            f"{S5_DEVICE} is in a breach condition and currently reports version {version}. "
            "In this scenario, a compromised device running version 14 must be upgraded to version 15. "
            "Upgrade requires approval, then verification must read version 15."
        )
        found = (
            f"Policy applies because the device is affected, current_version={version}, "
            "and the breach condition is met."
        )
    else:
        assessment = (
            f"{S5_DEVICE} is in a breach condition and currently reports version {version}. "
            "Hardening policy applicability is not yet established — open the policy source to confirm remediation requirements."
        )
        found = (
            f"{S5_DEVICE} shows compromise indicators with current_version={version}. "
            "Policy applicability has not been confirmed yet."
        )
    return C.envelope(
        scenario_id=S5_SCENARIO_ID,
        family=S5_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=_visible_chips(applied),
        title=f"Cisco {S5_DEVICE}: hardening policy requires upgrade 14→15",
        assessment=assessment,
        found=found,
        outcome=outcome,
        evidence_state=state,
        source_evidence=extra,
        actions=C.actions_for(session_id, S5_SCENARIO_ID),
        resources=["cisco.get_version", "ec_scenario_policy hardening rule", "change ticket", "cisco.upgrade"],
        controls=["HIL before cisco.upgrade", "verification mandatory", "not production Cisco guidance"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external,
        extra={
            "ec_cisco": {"device": S5_DEVICE, "current_version": version, "target_version": 15, "provenance": "simulated_mcp"},
            "ec_policy_source": "ec_scenario_policy",
            "ec_remediation_policy": {"splunk_not_device_management": True, "cisco_authority": "version_and_upgrade"},
            "ec_resource_composition": build_s5_resource_composition(),
            "ec_investigation_scope": build_s5_investigation_scope().model_dump(),
            "ec_action_readiness": [
                row.model_dump()
                for row in build_s5_action_readiness(applied, C.actions_for(session_id, S5_SCENARIO_ID), version)
            ],
            "ec_status_summary": build_s5_status_summary(version, str(remediation)),
            **(
                {
                    "ec_email": {
                        "to": "NETWORK_TEAM",
                        "logical_recipient": "NETWORK_TEAM",
                        "status": "draft_pending_send",
                        "not_transmitted": True,
                    }
                }
                if "request_network_approval" in applied
                else {}
            ),
        },
        journey=journey_for(S5_SCENARIO_ID, applied),
        recommended=[
            "Show the hardening policy source",
            "Create the change ticket with rollback and verification",
            "Obtain network-team approval",
            "Execute upgrade only after approval",
            "Verify version 15 before closure",
        ],
        important=[
            "current_version starts at 14",
            "Policy is EC scenario policy, not vendor production guidance",
            "Success without verification is incomplete",
        ],
        table=[
            {"Step": "Version", "Value": str(version)},
            {"Step": "Policy", "Value": "14 must go to 15"},
            {"Step": "Remediation", "Value": str(outcome.get("remediation_status"))},
        ],
        systems=[{
            "system": S5_DEVICE,
            "role": "Cisco router",
            "activity": "Breach condition; version-gated hardening",
            "first_seen": "2026-08-16T11:00:00Z",
            "last_seen": "2026-08-16T16:44:00Z",
            "allowed_denied": "n/a",
            "auth_correlation": "n/a",
            "risk_note": "Upgrade required if version is 14",
        }],
        layer2_path=list(S5_LAYER2_PATH),
    )


def s5_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S5_SCENARIO_ID:
        return None
    env = build_s5_turn(session_id="s5-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s5_demo_scenarios() -> dict[str, Any]:
    return {
        S5_SCENARIO_ID: C.demo_scenario(
            scenario_id=S5_SCENARIO_ID,
            label="S5 · Policy-driven Cisco remediation",
            query=S5_QUERY,
            demo_order=5,
            family=S5_FAMILY,
            summary="R-17 is on version 14. Scenario policy requires upgrade to 15 with approval and verification.",
        )
    }
