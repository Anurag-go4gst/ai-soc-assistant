"""S2 — AI application security / prompt injection. EC fixture only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo import ec_actions, ec_email_drafts
from app.demo.ec_journeys import journey_for
from app.demo.ec_siem import (
    S2_DETECTION_NAME,
    S2_GAP_CANDIDATE_SPL,
    S2_LAYER2_PATH,
    S2_SAVED_SEARCH_NAME,
    build_s2_attack_chain,
    build_s2_detection_opportunity,
    build_s2_evidence_findings,
    build_s2_siem_coverage,
    build_s2_tool_traces,
    s2_gap_spl_validation,
)
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
    C.chip("notify_app_security", "Email AppSec / AI platform team", action=True),
    C.chip("verify_credential_state", "Verify credential state", action=True),
    C.chip("update_incident", "Update incident ticket", action=True),
    C.chip("generate_closure_summary", "Generate closure summary"),
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
        C.state_item("siem_detection", "Existing Splunk detection", "OBTAINED", f"{S2_DETECTION_NAME} replayed (partial coverage)", "simulated_mcp"),
        C.state_item("ai_gateway", "AI gateway / guardrail events", "OBTAINED", "Injection indicators on 3 requests", "simulated_mcp"),
        C.state_item("tool_audit", "Tool-call audit", "OBTAINED", "export_customer_records blocked by authorization", "simulated_mcp"),
        C.state_item("app_logs", "AI application logs", "OBTAINED", "Suspicious prompt patterns in assistant API", "experience_center_fixture"),
        C.state_item("dlp", "DLP window", "AVAILABLE_NOT_QUERIED", "DLP resource available"),
        C.state_item("identity", "Identity / session", "MISSING", "No confirmed session hijack; identity not yet reviewed"),
        C.state_item("data_source", "Restricted-data access logs", "MISSING", "Downstream audit not yet run"),
        C.state_item("ai_policy", "Enterprise AI security policy", "AVAILABLE_NOT_QUERIED", "EC scenario policy not yet opened", "ec_scenario_policy"),
        C.state_item("appsec_email", "AppSec / AI platform email", "MISSING", "Outbound team notification not prepared"),
        C.state_item("credential_verify", "Credential disable verification", "MISSING", "No verification until credential action executes"),
        C.state_item("incident_update", "Incident ticket update", "MISSING", "Ticket not updated after investigation actions"),
        C.state_item("closure", "Closure summary", "MISSING", "Closure summary not generated"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[Any], bool, dict[str, Any]]:
    actions = list(ec_actions.list_actions_for_session(session_id, S2_SCENARIO_ID))
    kinds = {item.kind for item in actions}
    awaiting = False
    extras: dict[str, Any] = {}

    if "check_dlp" in applied:
        C.set_status(state, "dlp", "OBTAINED", "No customer-record exfiltration in the DLP window")
        extra.append(C.evidence("ev-s2-dlp", "dlp_fixture", "Simulated DLP", [{"channel": "ai_assistant", "exfil_confirmed": False, "alerts": 0}], provenance="simulated_mcp", tool_name="splunk_run_saved_search"))
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "DLP" not in item]
        if "No DLP exfiltration confirmed in the reviewed window" not in outcome["confirmed"]:
            outcome["confirmed"].append("No DLP exfiltration confirmed in the reviewed window")

    if "check_tool_call_history" in applied:
        extra.append(C.evidence("ev-s2-tools", "tool_audit_fixture", "Broader tool-call history", [
            {"tool": "export_customer_records", "result": "blocked", "policy": "tool_authorization"},
            {"tool": "search_kb", "result": "allowed", "count": 12},
        ], provenance="simulated_mcp", tool_name="splunk_run_saved_search"))
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
        outcome["missing_evidence"] = [item for item in outcome["missing_evidence"] if "policy" not in item.lower()]

    if "create_ai_incident_ticket" in applied and "ticket_create" not in kinds:
        prepared = ec_actions.prepare_action(kind="ticket_create", label="Create AI security incident", session_id=session_id, scenario_id=S2_SCENARIO_ID, extra={"ticket": {"title": "Prompt injection blocked", "impact": "attempted_blocked"}})
        executed = ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id)
        actions.append(executed)
        kinds.add("ticket_create")

    if "disable_integration_credential" in applied and "iam_disable" not in kinds:
        actions.append(ec_actions.prepare_action(
            kind="iam_disable",
            label="Disable integration credential",
            session_id=session_id,
            scenario_id=S2_SCENARIO_ID,
            extra={
                "target": "ai-assistant-export-connector",
                "verify_payload": {"credential_state": "disabled", "target": "ai-assistant-export-connector", "simulated": True},
            },
        ))
        kinds.add("iam_disable")

    if "notify_app_security" in applied and "email_send" not in kinds:
        email_extra = ec_email_drafts.s2_appsec_email(applied=applied)
        actions.append(ec_actions.prepare_action(
            kind="email_send",
            label="Email AppSec / AI platform team",
            session_id=session_id,
            scenario_id=S2_SCENARIO_ID,
            extra=email_extra,
        ))
        C.set_status(state, "appsec_email", "OBTAINED", "Draft prepared for logical recipient APPSEC_TEAM; not transmitted until Send email")
        extras["ec_email"] = {
            "to": email_extra["email"]["to"],
            "logical_recipient": "APPSEC_TEAM",
            "subject": email_extra["email"]["subject"],
            "status": "draft_pending_send",
            "not_transmitted": True,
        }

    if "verify_credential_state" in applied:
        disable = next((item for item in actions if item.kind == "iam_disable"), None)
        if disable is not None and disable.state == "EXECUTED":
            verified = ec_actions.verify_action(disable.action_id)
            C.set_status(state, "credential_verify", "OBTAINED", "Simulated credential state is disabled")
            if verified.verify_result and "Simulated credential disable verified" not in outcome["confirmed"]:
                outcome["confirmed"].append("Simulated credential disable verified")
        else:
            C.set_status(state, "credential_verify", "MISSING", "Verification is unavailable until the credential action is executed after HIL approval")

    if "update_incident" in applied and "ticket_update" not in kinds:
        prepared = ec_actions.prepare_action(
            kind="ticket_update",
            label="Update AI security incident",
            session_id=session_id,
            scenario_id=S2_SCENARIO_ID,
            extra={"ticket": {"impact": "attempted_blocked", "breach_confirmed": False}},
        )
        actions.append(ec_actions.execute_action(ec_actions.approve_action(prepared.action_id).action_id))
        C.set_status(state, "incident_update", "OBTAINED", "Simulated incident ticket updated")

    if "generate_closure_summary" in applied:
        outcome["closure_summary"] = (
            "Prompt injection was attempted and the unauthorized tool call was blocked. "
            "Breach is not confirmed. Credential disable remains HIL-gated."
        )
        C.set_status(state, "closure", "OBTAINED", "Closure summary generated")

    return outcome, state, extra, list(ec_actions.list_actions_for_session(session_id, S2_SCENARIO_ID)), awaiting, extras


def build_s2_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    outcome, state, extra, actions, awaiting, extras = _apply(applied, session_id, outcome, state, extra)
    disable = next((item for item in actions if item.kind == "iam_disable"), None)
    chips = list(S2_FOLLOWUPS)
    if disable is None or disable.state not in {"EXECUTED", "VERIFIED"}:
        chips = [item for item in chips if item.follow_up_id != "verify_credential_state"]

    gap_validation = s2_gap_spl_validation()
    normalized_spl = gap_validation.get("normalized_spl")

    source = [
        C.evidence(
            "ev-s2-detection",
            "splunk_saved_search",
            S2_DETECTION_NAME,
            [
                {"request_id": "ai-8841", "pattern": "ignore previous instructions", "action": "blocked_prompt"},
                {"request_id": "ai-8842", "pattern": "export all customer records", "action": "tool_denied"},
            ],
            provenance="simulated_mcp",
            tool_name="splunk_run_saved_search",
            summary=f"saved_search={S2_SAVED_SEARCH_NAME}",
        ),
        C.evidence("ev-s2-gateway", "ai_gateway_fixture", "AI gateway events", [
            {"request_id": "ai-8841", "pattern": "ignore previous instructions", "action": "blocked_prompt"},
        ], provenance="simulated_mcp", tool_name="splunk_run_saved_search"),
        C.evidence("ev-s2-tool", "tool_audit_fixture", "Tool-call audit", [
            {"tool": "export_customer_records", "authorized": False, "executed": False, "reason": "tool_authorization_denied"},
        ], provenance="simulated_mcp", tool_name="splunk_run_query"),
        *extra,
    ]

    dlp_obtained = "check_dlp" in applied
    siem_coverage = build_s2_siem_coverage(dlp_obtained=dlp_obtained)

    return C.envelope(
        scenario_id=S2_SCENARIO_ID,
        family=S2_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=chips,
        title="Prompt injection confirmed · execution blocked · restricted-data access not confirmed",
        assessment=(
            "Attack attempted, breach not confirmed. The assistant received instruction-override prompts and an "
            "unauthorized export_customer_records tool call. Authorization blocked execution. Restricted-data access, "
            "credential compromise, and session hijack are not confirmed."
        ),
        found=(
            "Existing Splunk detection provided partial coverage for prompt injection. A governed gap search confirmed "
            "the sensitive tool was requested and denied; no successful execution receipt was observed."
        ),
        outcome=outcome,
        evidence_state=state,
        source_evidence=source,
        actions=actions,
        resources=[
            "siem_coverage_discovery",
            "splunk_get_knowledge_objects",
            "splunk_run_saved_search",
            "splunk_run_query (gap only)",
            "tool_authorization",
            "dlp (follow-up)",
            "iam (follow-up)",
        ],
        controls=["reuse before generate", "tool authorization required", "restricted-data export denied", "HIL for credential disable"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting or awaiting_external,
        understanding=(
            "Three evidence questions: (1) prompt-injection attempts, (2) unauthorized tool execution, "
            "(3) restricted-data access — decomposed before any new SPL."
        ),
        layer2_path=S2_LAYER2_PATH,
        extra={
            "ec_impact_legend": [
                "Attack: Confirmed",
                "Control: Blocked",
                "Impact: Not confirmed",
                "Confidence: High",
            ],
            "ec_status_summary": "P2 High · Attack: Confirmed · Control: Blocked · Impact: Not confirmed",
            "ec_gap_spl_notice": "Additional governed SIEM search was required to resolve the evidence gap.",
            "ec_gap_spl_layer2_only": True,
            "candidate_spl": {
                "candidate_spl": S2_GAP_CANDIDATE_SPL,
                "execution_eligible": False,
                "generation_mode": "ec_bounded_gap_search",
                "note": "Gap-driven only — existing detection reused first",
            },
            "spl_validation": {
                **gap_validation,
                "approved": bool(gap_validation.get("approved")),
                "execution_eligible": False,
                "selected_candidate_spl_provider": "ec_bounded_gap_search",
            },
            "execution": {
                "status": "simulated_receipts_packaged",
                "production_mcp_executed": False,
                "executed_spl": normalized_spl if gap_validation.get("approved") else None,
                "block_reason": "live_mcp_not_called",
                "exact_call_authorization": "APPROVED" if gap_validation.get("approved") else "BLOCKED",
                "candidate_spl_not_executed": True,
            },
            "ec_siem_coverage": siem_coverage.model_dump(),
            "ec_siem_tool_traces": [item.model_dump() for item in build_s2_tool_traces(gap_validation=gap_validation)],
            "ec_attack_chain": [item.model_dump() for item in build_s2_attack_chain()],
            "ec_evidence_findings": [item.model_dump() for item in build_s2_evidence_findings()],
            "ec_detection_opportunity": build_s2_detection_opportunity().model_dump(),
            **extras,
        },
        journey=journey_for(S2_SCENARIO_ID, applied),
        recommended=[
            "Review DLP for the same window",
            "Inspect broader tool-call history",
            "Check identity/session context",
            "Audit restricted-data stores",
            "Open an AI security incident",
        ],
        important=[
            "Existing Splunk detection reused for prompt injection (partial coverage)",
            "Governed gap search only for tool execution — blocked, not executed",
            "No successful unauthorized tool execution in current evidence",
        ],
        table=[
            {"Investigation point": "Prompt manipulation", "Finding": "Confirmed", "Evidence basis": "Existing detection + gateway"},
            {"Investigation point": "Sensitive tool requested", "Finding": "Confirmed", "Evidence basis": "Tool-call audit"},
            {"Investigation point": "Authorization", "Finding": "Blocked", "Evidence basis": "Authorization decision"},
            {"Investigation point": "Successful execution", "Finding": "Not observed", "Evidence basis": "No execution receipt"},
            {"Investigation point": "Restricted data accessed", "Finding": "Not confirmed", "Evidence basis": "Data audit incomplete"},
        ],
        severity="P2 High",
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
