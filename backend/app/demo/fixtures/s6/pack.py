"""S6 — investigation continuity across seven turns. EC session only."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.demo.ec_continuity_s6 import (
    S6_CONTINUITY_POLICY,
    S6_LAYER2_PATH,
    build_s6_action_readiness,
    build_s6_evidence_reuse,
    build_s6_status_summary,
)
from app.demo.ec_journeys import journey_for
from app.demo import ec_email_drafts
from app.demo.fixtures import common as C

S6_SCENARIO_ID = "s6_investigation_continuity"
S6_FAMILY = "s6_continuity"
S6_QUERY = "Investigate failed privileged VPN logins from Germany yesterday."
S6_FOLLOWUPS = (
    C.chip("scope_service_accounts", "What about service accounts?"),
    C.chip("scope_build_servers", "Only those that touched the build servers."),
    C.chip("check_last_month_incident", "Did we see this in last month's incident?"),
    C.chip("fetch_old_incident_ticket", "Fetch the old incident ticket"),
    C.chip("update_incident_ticket", "Add this new evidence to that ticket", action=True),
    C.chip("notify_incident_owner", "Email the incident owner", action=True),
    C.chip("generate_current_scope_summary", "Produce current-scope incident summary"),
)
S6_FOLLOWUP_IDS = frozenset(item.follow_up_id for item in S6_FOLLOWUPS)
S6_SYNONYMS = {
    "what about service accounts": "scope_service_accounts",
    "what about service accounts?": "scope_service_accounts",
    "only those that touched the build servers": "scope_build_servers",
    "only those that touched the build servers.": "scope_build_servers",
    "did we see this in last month's incident": "check_last_month_incident",
    "did we see this in last month's incident?": "check_last_month_incident",
    "fetch the old incident ticket": "fetch_old_incident_ticket",
    "add this new evidence to that ticket": "update_incident_ticket",
    "notify the incident owner": "notify_incident_owner",
}


def resolve_s6_follow_up(follow_up_id: str) -> str:
    key = follow_up_id.strip().lower()
    return S6_SYNONYMS.get(key, follow_up_id)


def _base_outcome() -> dict[str, Any]:
    return {
        "disposition": "suspicious",
        "scope": "privileged_admin_vpn_germany_yesterday",
        "confirmed": [
            "Failed privileged VPN logins from Germany yesterday",
            "Administrator accounts are in the initial evidence window",
        ],
        "supported": ["Geo source Germany is present on the failed privileged attempts"],
        "unconfirmed": ["Service-account involvement", "Build-server touch", "Link to last month's incident"],
        "missing_evidence": ["Service-account VPN failures", "Build-server correlation", "Historical incident ticket"],
        "applicability": [],
        "production_investigation_outcome_unused": True,
    }


def _base_state() -> list[dict[str, Any]]:
    return [
        C.state_item("admin_vpn", "Privileged admin VPN failures", "OBTAINED", "Germany, yesterday, administrator accounts"),
        C.state_item("service_accounts", "Service-account VPN failures", "OUT_OF_SCOPE", "Not in the initial privileged-admin scope"),
        C.state_item("build_servers", "Build-server touch", "MISSING", "Not yet constrained"),
        C.state_item("historical", "Last month's incident", "AVAILABLE_NOT_QUERIED", "Historical investigation not retrieved"),
        C.state_item("old_ticket", "Historical incident ticket", "MISSING", "Ticket not fetched"),
    ]


def _apply(applied: list[str], session_id: str, outcome: dict[str, Any], state: list[dict[str, Any]], extra: list[dict[str, Any]]) -> None:
    if "scope_service_accounts" in applied:
        outcome["scope"] = "service_accounts_vpn_germany"
        C.set_status(state, "admin_vpn", "OUT_OF_SCOPE", "Previous administrator-account evidence is no longer applicable after the scope changed to service accounts")
        C.set_status(state, "service_accounts", "OBTAINED", "Service-account VPN failures from Germany collected")
        extra.append(C.evidence("ev-s6-svc", "splunk_mcp_fixture", "Service-account VPN failures", [
            {"account": "svc_deploy", "src_geo": "DE", "result": "failed", "count": 14},
            {"account": "svc_backup", "src_geo": "DE", "result": "failed", "count": 3},
        ], provenance="simulated_mcp"))
        outcome["confirmed"] = ["Service-account VPN failures from Germany are in evidence"]
        outcome["applicability"] = [
            {"key": "admin_vpn", "status": "OUT_OF_SCOPE", "reason": "Scope changed from administrator accounts to service accounts"},
        ]
        outcome["unconfirmed"] = ["Whether those service accounts touched build servers"]
        outcome["missing_evidence"] = ["Build-server correlation", "Historical incident ticket"]

    if "scope_build_servers" in applied:
        outcome["scope"] = "service_accounts_build_servers"
        C.set_status(state, "service_accounts", "SUPERSEDED", "Broad service-account window superseded by build-server constraint")
        C.set_status(state, "build_servers", "OBTAINED", "Only svc_deploy touched build servers")
        extra.append(C.evidence("ev-s6-build", "cmdb_fixture", "Build-server touch", [
            {"account": "svc_deploy", "asset": "bld-01", "touched": True},
            {"account": "svc_backup", "asset": "bld-01", "touched": False},
        ], provenance="simulated_mcp"))
        outcome["confirmed"] = ["svc_deploy failed VPN logins from Germany and touched build servers"]
        outcome["applicability"] = [
            {"key": "admin_vpn", "status": "OUT_OF_SCOPE", "reason": "Administrator evidence is outside the current scope"},
            {"key": "svc_backup", "status": "OUT_OF_SCOPE", "reason": "Did not touch build servers"},
            {"key": "service_accounts_broad", "status": "SUPERSEDED", "reason": "Replaced by build-server constraint"},
        ]

    if "check_last_month_incident" in applied:
        C.set_status(state, "historical", "OBTAINED", "Prior incident INC-VPN-0712 is related but stale on current scope")
        extra.append(C.evidence("ev-s6-hist", "investigation_archive_fixture", "Last month's incident", [{
            "incident_id": "INC-VPN-0712",
            "summary": "Privileged VPN failures from DE",
            "freshness": "STALE",
            "applicability": "REUSABLE_FOR_CONTEXT",
            "matches_current_service_account_scope": False,
        }], provenance="experience_center_fixture"))
        outcome["applicability"].append({"key": "INC-VPN-0712", "status": "STALE", "reason": "Prior incident covered admin VPN, not the current service-account/build-server scope"})
        outcome["applicability"].append({"key": "INC-VPN-0712-context", "status": "REUSABLE", "reason": "Geo and VPN failure pattern remain useful context"})

    if "fetch_old_incident_ticket" in applied:
        C.ensure_executed_action(
            kind="ticket_fetch",
            label="Fetch INC-VPN-0712",
            session_id=session_id,
            scenario_id=S6_SCENARIO_ID,
            extra={"ticket": {"id": "INC-VPN-0712", "owner": "soc.lead"}},
        )
        C.set_status(state, "old_ticket", "OBTAINED", "INC-VPN-0712 retrieved")
        extra.append(C.evidence("ev-s6-ticket", "itsm_fixture", "Historical incident ticket", [{"ticket_id": "INC-VPN-0712", "owner": "soc.lead", "status": "closed"}], provenance="simulated_mcp"))
        outcome["ticket_id"] = "INC-VPN-0712"

    if "update_incident_ticket" in applied:
        C.ensure_executed_action(
            kind="ticket_update",
            label="Add new evidence to INC-VPN-0712",
            session_id=session_id,
            scenario_id=S6_SCENARIO_ID,
            extra={"ticket": {"id": "INC-VPN-0712", "comment": "svc_deploy + build servers"}},
        )
        outcome["ticket_updated"] = True

    if "notify_incident_owner" in applied:
        email_extra = ec_email_drafts.s6_incident_owner_email(applied=applied)
        C.ensure_hil_action(
            kind="email_send",
            label="Email incident owner",
            session_id=session_id,
            scenario_id=S6_SCENARIO_ID,
            extra=email_extra,
        )

    if "generate_current_scope_summary" in applied:
        outcome["closure_summary"] = (
            "Current scope is service accounts that touched build servers. "
            "Administrator VPN evidence is OUT_OF_SCOPE. Prior ticket INC-VPN-0712 is STALE for this scope "
            "and REUSABLE only as geo/VPN-failure context. No destructive remediation."
        )


def build_s6_turn(*, session_id: str, turn: int, applied_follow_up_ids: list[str], pending_action_id: str | None = None, awaiting_external: bool = False):
    applied = list(applied_follow_up_ids)
    outcome = deepcopy(_base_outcome())
    state = deepcopy(_base_state())
    extra: list[dict[str, Any]] = []
    _apply(applied, session_id, outcome, state, extra)
    source = [
        C.evidence("ev-s6-admin", "splunk_mcp_fixture", "Privileged VPN failures", [
            {"account": "adm_mueller", "src_geo": "DE", "result": "failed", "count": 27, "when": "yesterday"},
        ], provenance="simulated_mcp"),
        *extra,
    ]
    return C.envelope(
        scenario_id=S6_SCENARIO_ID,
        family=S6_FAMILY,
        session_id=session_id,
        turn=turn,
        applied=applied,
        chips=list(S6_FOLLOWUPS),
        title="Failed privileged VPN logins from Germany — scope will evolve",
        assessment=(
            "Yesterday's privileged VPN failures from Germany are in evidence for administrator accounts. "
            "Later scope changes must re-evaluate prior evidence rather than silently reuse it."
        ),
        found="Administrator VPN failures from Germany yesterday. Service accounts are currently out of scope.",
        outcome=outcome,
        evidence_state=state,
        source_evidence=source,
        actions=C.actions_for(session_id, S6_SCENARIO_ID),
        resources=["Splunk VPN auth", "CMDB build servers", "historical incident", "ITSM ticket"],
        controls=["EC session only", "stable follow_up_id", "no production session"],
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external,
        extra={
            "ec_scope": outcome.get("scope"),
            "ec_applicability": outcome.get("applicability"),
            "ec_ticket_id": outcome.get("ticket_id"),
            "ec_continuity_policy": S6_CONTINUITY_POLICY,
            "ec_evidence_reuse": [row.model_dump() for row in build_s6_evidence_reuse(outcome, applied)],
            "ec_action_readiness": [row.model_dump() for row in build_s6_action_readiness(applied)],
            "ec_status_summary": build_s6_status_summary(str(outcome.get("scope"))),
            **(
                {
                    "ec_email": {
                        "to": "INCIDENT_OWNER",
                        "logical_recipient": "INCIDENT_OWNER",
                        "status": "draft_pending_send",
                        "not_transmitted": True,
                    }
                }
                if "notify_incident_owner" in applied
                else {}
            ),
        },
        journey=journey_for(S6_SCENARIO_ID, applied),
        recommended=[
            "If the question changes to service accounts, collect that evidence separately",
            "Do not reuse administrator evidence after a scope change",
        ],
        important=["Initial scope is privileged administrator VPN from Germany yesterday"],
        table=[
            {"Scope": str(outcome.get("scope")), "Turn": str(turn)},
        ],
        layer2_path=list(S6_LAYER2_PATH),
    )


def s6_analyst_override(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    if scenario_id != S6_SCENARIO_ID:
        return None
    env = build_s6_turn(session_id="s6-override", turn=0, applied_follow_up_ids=[])
    return {**base, **(env.analyst or {})}


def build_s6_demo_scenarios() -> dict[str, Any]:
    return {
        S6_SCENARIO_ID: C.demo_scenario(
            scenario_id=S6_SCENARIO_ID,
            label="S6 · Investigation continuity",
            query=S6_QUERY,
            demo_order=6,
            family=S6_FAMILY,
            summary="Seven-turn investigation: admin VPN → service accounts → build servers → historical ticket.",
        )
    }
