"""S2 — AI application security / prompt injection. EC fixture only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo import ec_actions
from app.demo.fixtures import common as C

S2_SCENARIO_ID = "s2_ai_prompt_injection"
S2_FAMILY = "s2_ai_security"
S2_QUERY = (
    "Investigate whether our customer-facing AI assistant is being targeted with prompt-injection "
    "attempts and whether any attempts resulted in unauthorized tool execution or restricted-data access."
)
S2_FOLLOWUPS = (
    C.chip("check_dlp", "Check DLP window"),
    C.chip("check_tool_call_history", "Check broader tool-call history"),
    C.chip("check_identity", "Check identity / session context"),
    C.chip("check_data_source", "Check restricted-data access logs"),
    C.chip("show_ai_security_policy", "Show AI security policy"),
    C.chip("create_ai_incident_ticket", "Create AI incident ticket", action=True),
    C.chip("disable_integration_credential", "Disable integration credential", action=True),
    C.chip("notify_app_security", "Notify application security", action=True),
)
S2_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S2_FOLLOWUPS)


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "suspicious",
        "confirmed": [
            "Prompt-injection attempt occurred against the customer-facing assistant",
            "Unauthorized tool call export_customer_records was attempted",
            "Tool authorization blocked execution",
        ],
        "supported": ["Attempted jailbreak/instruction-override pattern in gateway events"],
        "unconfirmed": [
            "Successful unauthorized tool execution",
            "Restricted customer-data access",
            "Credential compromise",
            "Session hijack",
        ],
        "missing_evidence": ["DLP window", "Broader tool-call history", "Identity context", "Downstream data-source audit"],
        "impact": "attempted_blocked",
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("ai_gateway", "AI gateway / guardrail events", "OBTAINED", "Injection indicators on 3 requests", "simulated_mcp"),
        C.state_item("tool_audit", "Tool-call audit", "OBTAINED", "export_customer_records blocked by authorization", "simulated_mcp"),
        C.state_item("app_logs", "AI application logs", "OBTAINED", "Suspicious prompt patterns in assistant API", "experience_center_fixture"),
        C.state_item("dlp", "DLP window", "AVAILABLE_NOT_QUERIED", "DLP resource available"),
        C.state_item("identity", "Identity / session", "MISSING", "No confirmed session hijack; identity not yet reviewed"),
        C.state_item("data_source", "Restricted-data access logs", "MISSING", "Downstream audit not yet run"),
        C.state_item("ai_policy", "Enterprise AI security policy", "AVAILABLE_NOT_QUERIED", "EC scenario policy not yet opened", "ec_scenario_policy"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[Any], bool]:
    actions = list(ec_actions.list_actions_for_session(session_id, S2_SCENARIO_ID))
    kinds = {item.kind for item in actions}
    awaiting = False

    if "check_dlp" in applied:
        C.set_status(state, "dlp", "OBTAINED", "No customer-record exfiltration in the DLP window")
        extra.append(C.evidence("ev-s2-dlp", "dlp_fixture", "Simulated DLP", [{"channel": "ai_assistant", "exfil_confirmed": False, "alerts": 0}], provenance="simulated_mcp"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "DLP" not in item]
        if "No DLP exfiltration confirmed in the reviewed window" not in outcome["confirmed"]:
            outcome["confirmed"].append("No DLP exfiltration confirmed in the reviewed window")

    if "check_tool_call_history" in applied:
        extra.append(C.evidence("ev-s2-tools", "tool_audit_fixture", "Broader tool-call history", [
            {"tool": "export_customer_records", "result": "blocked", "policy": "tool_authorization"},
            {"tool": "search_kb", "result": "allowed", "count": 12},
        ], provenance="simulated_mcp"))
        if "No other unauthorized tools executed in the reviewed history" not in outcome["confirmed"]:
            outcome["confirmed"].append("No other unauthorized tools executed in the reviewed history")

    if "check_identity" in applied:
        C.set_status(state, "identity", "OBTAINED", "Interactive user session intact; no hijack indicators")
        extra.append(C.evidence("ev-s2-iam", "iam_fixture", "Identity context", [{"user": "ext-assistant-gw", "session_hijack": False}], provenance="simulated_mcp"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "Identity" not in item]

    if "check_data_source" in applied:
        C.set_status(state, "data_source", "OBTAINED", "No restricted-table reads attributed to the blocked tool")
        extra.append(C.evidence("ev-s2-data", "datastore_fixture", "Restricted-data access logs", [{"store": "customer_records", "unauthorized_read": False}], provenance="simulated_mcp"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "data-source" not in item]

    if "show_ai_security_policy" in applied:
        C.set_status(state, "ai_policy", "OBTAINED", "EC AI security policy: tool authorization required; restricted-data export denied", "ec_scenario_policy")
        extra.append(C.evidence("ev-s2-policy", "kb_fixture", "Enterprise AI security policy", [{
            "allowed_tools": ["search_kb", "summarize_case"],
            "denied_tools": ["export_customer_records"],
            "restricted_data_export": "deny",
            "tool_authorization_required": True,
            "not_production_policy": True,
        }], provenance="ec_scenario_policy"))

    if "create_ai_incident_ticket" in applied and "ticket_create" not in kinds:
        prepared = ec_actions.prepare_action(kind="ticket_create", label="Create AI security incident", session_id=session_id, scenario_id=S2_SCENARIO_ID, extra={"ticket": {"title": "Prompt injection blocked", "impact": "attempted_blocked"}})
        executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
        actions.append(executed)
        kinds.add("ticket_create")

    if "disable_integration_credential" in applied and "iam_disable" not in kinds:
        actions.append(ec_actions.prepare_action(kind="iam_disable", label="Disable integration credential", session_id=session_id, scenario_id=S2_SCENARIO_ID, extra={"target": "ai-assistant-export-connector"}))
        kinds.add("iam_disable")

    if "notify_app_security" in applied and "notify" not in kinds:
        prepared = ec_actions.prepare_action(kind="notify", label="Notify application security", session_id=session_id, scenario_id=S2_SCENARIO_ID, extra={"team": "app-security"})
        executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
        actions.append(executed)

    return outcome, state, extra, list(ec_actions.list_actions_for_session(session_id, S2_SCENARIO_ID)), awaiting


def build_s2_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    outcome, state, extra, actions, awaiting = _apply(applied, session_id, outcome, state, extra)
    source = [
        C.evidence("ev-s2-gateway", "ai_gateway_fixture", "AI gateway events", [
            {"request_id": "ai-8841", "pattern": "ignore previous instructions", "action": "blocked_prompt"},
            {"request_id": "ai-8842", "pattern": "export all customer records", "action": "tool_denied"},
        ], provenance="simulated_mcp", tool_name="ai_gateway.audit"),
        C.evidence("ev-s2-tool", "tool_audit_fixture", "Tool-call audit", [
            {"tool": "export_customer_records", "authorized": False, "executed": False, "reason": "tool_authorization_denied"},
        ], provenance="simulated_mcp"),
        *extra,
    ]
    return C.envelope(
        scenario_id=S2_SCENARIO_ID,
        family=S2_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=list(S2_FOLLOWUPS),
        title="Prompt injection attempted — unauthorized tool execution blocked",
        assessment=(
            "Attack attempted, breach not confirmed. The assistant received instruction-override prompts and an "
            "unauthorized export_customer_records tool call. Authorization blocked execution. Restricted-data access, "
            "credential compromise, and session hijack are not confirmed."
        ),
        found="Gateway events show injection indicators; the only sensitive tool attempt was denied before execution.",
        outcome=outcome,
        evidence_state=state,
        source_evidence=source,
        actions=actions,
        resources=["ai_gateway.audit", "tool_authorization", "dlp (unqueried)", "iam (missing)"],
        controls=["tool authorization required", "restricted-data export denied", "HIL for credential disable", "not production policy"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting or awaiting_external,
        extra={"ec_impact_legend": ["Attempted", "Blocked", "Confirmed impact", "Not confirmed", "Evidence still required"]},
        recommended=[
            "Review DLP for the same window",
            "Inspect broader tool-call history",
            "Check identity/session context",
            "Audit restricted-data stores",
            "Open an AI security incident",
        ],
        important=[
            "Prompt-injection attempt confirmed",
            "export_customer_records attempted and blocked",
            "No successful unauthorized tool execution in current evidence",
        ],
        table=[
            {"Signal": "Prompt injection", "Status": "Attempted / confirmed"},
            {"Signal": "export_customer_records", "Status": "Blocked"},
            {"Signal": "Restricted-data access", "Status": "Not confirmed"},
            {"Signal": "Session hijack", "Status": "Not confirmed"},
        ],
    )


def s2_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S2_SCENARIO_ID:
        return None
    env = build_s2_turn(session_id="s2-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s2_demo_scenarios() -> dict[str, Any]:
    return {
        S2_SCENARIO_ID: C.demo_scenario(
            scenario_id=S2_SCENARIO_ID,
            label="S2 · AI application security",
            query=S2_QUERY,
            demo_order=2,
            family=S2_FAMILY,
            summary="Prompt injection attempted; unauthorized tool execution blocked. Breach not confirmed.",
        )
    }
