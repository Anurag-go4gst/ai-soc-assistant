"""S1 investigation step findings — derived from EC fixture evidence only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.ec_siem_s1 import S1_DETECTION_NAME, S1_SAVED_SEARCH_NAME
from app.demo.fixtures.s1.sop_rag import SOP_DOC_ID, SOP_TITLE
from app.demo.fixtures.s1.llm_advisory import (
    advisory_payload,
    advisory_trace_label,
    fourteen_day_auth_spl,
    novelty_window_spl,
    permitted_session_spl,
    requested_30d_spl,
)

_JUMP = "10.20.1.10"
_HOST_B = "10.20.4.55"
_HOST_C = "10.20.8.90"
_ACCOUNT = "svc_jump_ops"


def _connector_io(*, request: str, response: str, spl: str | None = None, connector: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "connector": connector,
        "request": request,
        "response": response,
        "execution": "AUTHORIZED → EXECUTED",
    }
    if spl:
        payload["normalized_spl"] = spl
    return payload


def finding_for_investigation_step(
    step_id: str,
    *,
    status: str,
    applied: list[str] | None = None,
    agent_state: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    selected: bool = True,
) -> dict[str, Any] | None:
    del agent_state, outcome
    applied = list(applied or [])
    token = status.upper()
    if not selected or token == "SKIPPED":
        return {
            "headline_finding": "Skipped — not included in the approved investigation plan.",
            "headlines_by_status": {
                "QUEUED": "Queued",
                "RUNNING": "Running…",
                "COMPLETE": "Skipped",
            },
            "attention_state": "INFORMATIONAL",
            "evidence_sources": [],
            "caveat": "Skipped steps do not produce attributable findings.",
        }
    if token == "RUNNING":
        return {
            "headline_finding": "Running…",
            "headlines_by_status": {
                "QUEUED": "Queued",
                "RUNNING": "Running…",
                "COMPLETE": "Complete",
            },
            "attention_state": "NORMAL",
            "evidence_sources": [],
        }
    if token not in {"COMPLETE"}:
        return {
            "headline_finding": "Queued — waiting for investigation run",
            "headlines_by_status": {
                "QUEUED": "Queued — waiting for investigation run",
                "RUNNING": "Running…",
                "COMPLETE": "Complete",
            },
            "attention_state": "NORMAL",
            "evidence_sources": [],
        }

    if step_id == "evaluate_notable":
        return {
            "headline_finding": (
                "Existing IOC detection: No alert — IP not present in the IOC list used by this detection"
            ),
            "headlines_by_status": {
                "QUEUED": f"Queued — assess coverage of {S1_SAVED_SEARCH_NAME}",
                "RUNNING": f"Assessing saved search {S1_SAVED_SEARCH_NAME}…",
                "COMPLETE": "Existing IOC detection: No alert — IP not in IOC list",
            },
            "key_evidence": [
                f"saved_search={S1_SAVED_SEARCH_NAME}",
                f"detection={S1_DETECTION_NAME}",
                "alert_generated=false",
                "reason=indicator_not_in_ioc_lookup_or_content",
            ],
            "confidence": "high",
            "attention_state": "INFORMATIONAL",
            "caveat": (
                "No alert is not proof the IP is benign — it is proof this IOC-based Splunk content "
                "does not cover the indicator."
            ),
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s1-existing-search",
                    "provenance": "governed_saved_search",
                    "tool": "splunk_run_saved_search",
                },
            ],
            "details": _connector_io(
                connector="Splunk MCP",
                spl=f'| savedsearch "{S1_SAVED_SEARCH_NAME}"',
                request=f"action=run_saved_search\nname={S1_SAVED_SEARCH_NAME}\nindicator={PRIMARY_ATTACKER_IP}",
                response="alert_generated=false\nreason=indicator_not_in_ioc_lookup_or_content",
            ),
        }

    if step_id == "requested_30d":
        return {
            "headline_finding": (
                f"Last 30 days: 3 allowed / 922 denied on jump host {_JUMP}; "
                f"deny-only on {_HOST_B} and {_HOST_C}"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — last-30-days firewall search",
                "RUNNING": "Running governed last-30-days search…",
                "COMPLETE": f"3 allowed sessions on {_JUMP} — denied volume must not bury them",
            },
            "key_evidence": [
                f"src={PRIMARY_ATTACKER_IP}",
                f"{_JUMP}: 3 allowed / 922 denied · dest_ports 443,8443",
                f"{_HOST_B}: 0 allowed / 650 denied · dest_ports 22,443",
                f"{_HOST_C}: 0 allowed / 500 denied · dest_ports 3389,443",
            ],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "caveat": "Firewall-observed only — DNS/proxy/VPN/endpoint were not queried.",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s1-fw-search-2",
                    "provenance": "governed_search",
                    "tool": "splunk_run_query",
                },
            ],
            "details": _connector_io(
                connector="Splunk MCP",
                spl=requested_30d_spl(),
                request=f"action=splunk_run_query\nindicator={PRIMARY_ATTACKER_IP}\nwindow=last_30d",
                response=f"{_JUMP}=3_allow/922_deny\n{_HOST_B}=deny_only\n{_HOST_C}=deny_only\ndest_ports=443,8443",
            ),
        }

    if step_id == "novelty_window":
        return {
            "headline_finding": "Prior 30-day window is empty — this IP is newly observed",
            "headlines_by_status": {
                "QUEUED": "Queued — prior 30-day novelty window",
                "RUNNING": "Running novelty-window search…",
                "COMPLETE": "Prior window empty — newly observed",
            },
            "key_evidence": ["earliest=-60d latest=-30d", "result_count=0"],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s1-fw-search-1",
                    "provenance": "governed_search",
                    "tool": "splunk_run_query",
                },
            ],
            "details": _connector_io(
                connector="Splunk MCP",
                spl=novelty_window_spl(),
                request=f"action=splunk_run_query\nindicator={PRIMARY_ATTACKER_IP}\nwindow=prior_30d",
                response="result_count=0\nnewly_observed=true",
            ),
        }

    if step_id == "mcp_identity":
        return {
            "headline_finding": (
                f"Identity: registered MCP endpoint ({PRIMARY_ATTACKER_IP}) — "
                "established from inventory/SOC-KB evidence"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — inventory identity lookup",
                "RUNNING": "Reading SOC-KB inventory identity…",
                "COMPLETE": "Identity: registered MCP endpoint",
            },
            "key_evidence": [
                f"indicator={PRIMARY_ATTACKER_IP}",
                "identity=registered MCP endpoint",
                "source=SOC-KB inventory fixture",
            ],
            "confidence": "high",
            "attention_state": "RISK",
            "caveat": "A registered/new MCP endpoint is a new concern, not a confirmed malicious IOC.",
            "evidence_sources": [
                {
                    "source": "SOC-KB",
                    "evidence_id": "ev-s1-mcp-identity",
                    "provenance": "experience_center_fixture",
                    "tool": None,
                },
            ],
            "details": _connector_io(
                connector="SOC-KB",
                request=f"action=inventory_lookup\nindicator={PRIMARY_ATTACKER_IP}",
                response="identity=registered_mcp_endpoint\nsource=soc_kb_inventory",
            ),
        }

    if step_id == "threat_intel":
        done = "check_threat_intel" in applied
        return {
            "headline_finding": (
                f"Not present in local IOC / threat-intelligence evidence ({PRIMARY_ATTACKER_IP})"
                if done
                else "Threat intelligence not yet queried"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — check local threat intelligence",
                "RUNNING": "Looking up the newly observed IP in local TI…",
                "COMPLETE": "Not present in local IOC / threat-intelligence evidence",
            },
            "key_evidence": ["live_feed=false", "internet_reputation=not_used", "result=unlisted"],
            "confidence": "medium",
            "attention_state": "NO_MATCH",
            "caveat": "Unlisted is not benign. No VirusTotal/IPVoid/internet services on this air-gapped path.",
            "evidence_sources": [
                {
                    "source": "SOC-KB",
                    "evidence_id": "ev-s1-ti",
                    "provenance": "experience_center_fixture",
                    "tool": None,
                },
            ],
            "details": _connector_io(
                connector="SOC-KB",
                request=f"action=local_ti_lookup\nindicator={PRIMARY_ATTACKER_IP}\nlive_feed=false",
                response="result=unlisted\ninternet_reputation=not_used",
            ),
        }

    if step_id == "retrieve_sop":
        return {
            "headline_finding": (
                "SOP retrieved: targeted monitoring is the default; blocking requires a defined "
                "threshold plus Network/SOC HIL approval"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — retrieve enterprise SOP from SOC-KB",
                "RUNNING": "Retrieving SOC-KB SOP…",
                "COMPLETE": "SOP retrieved — monitor by default; block is conditional",
            },
            "key_evidence": [
                f"doc_id={SOP_DOC_ID}",
                f"title={SOP_TITLE}",
                "monitoring_duration=14 days",
                "block_requires=threshold + Network/SOC HIL",
            ],
            "confidence": "high",
            "attention_state": "INFORMATIONAL",
            "caveat": "Enterprise SOC SOP fixture — not vendor guidance.",
            "evidence_sources": [
                {
                    "source": "SOC-KB RAG",
                    "evidence_id": "ev-s1-sop-rag",
                    "provenance": "experience_center_fixture",
                    "tool": "retrieve_soc_kb",
                },
            ],
            "details": _connector_io(
                connector="SOC-KB RAG",
                request=f"action=retrieve_soc_kb\ndoc_id={SOP_DOC_ID}",
                response=f"title={SOP_TITLE}\nmonitoring_duration=14 days\nblock=conditional",
            ),
        }

    if step_id == "permitted_sessions":
        return {
            "headline_finding": (
                f"Three permitted sessions on jump host {_JUMP} (443/8443); "
                f"authentication is not attributable to {PRIMARY_ATTACKER_IP}"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — permitted-session drill",
                "RUNNING": "Investigating allowed sessions and authentication…",
                "COMPLETE": "3 permitted sessions remain unexplained; auth source IP not proven",
            },
            "key_evidence": [
                f"dest={_JUMP} role=jump_host criticality=high",
                "dest_ports=443,8443 (HTTPS / alternate TLS)",
                "allow_count=3 · first_seen=2026-07-18T02:08:00Z · last_seen=2026-08-16T16:44:00Z",
                "auth: 3 successful logons for svc_jump_ops exist; src IP of those logons is not proven",
                "expected_for_MCP=uncertain",
            ],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "caveat": (
                "Firewall identity association is not successful authentication. "
                "Permitted sessions remain unexplained, not confirmed malicious."
            ),
            "details": {
                "sessions": [
                    {
                        "dest": _JUMP,
                        "dest_port": 443,
                        "service": "HTTPS",
                        "action": "allow",
                        "count": 2,
                        "first_seen": "2026-07-18T02:08:00Z",
                        "last_seen": "2026-08-16T16:40:00Z",
                    },
                    {
                        "dest": _JUMP,
                        "dest_port": 8443,
                        "service": "TLS-alt",
                        "action": "allow",
                        "count": 1,
                        "first_seen": "2026-08-16T16:44:00Z",
                        "last_seen": "2026-08-16T16:44:00Z",
                    },
                ],
                "reasoning": {
                    "label": "Agent assessment",
                    "trace_label": advisory_trace_label(),
                    "summary": advisory_payload()["interpretation"],
                    "not_evidence": True,
                    "chain": list(advisory_payload()["chain"]),
                    "provenance": "llm_advisory_fixture",
                },
                **_connector_io(
                    connector="Splunk MCP",
                    spl=permitted_session_spl(),
                    request=(
                        f"action=splunk_run_query\nsrc={PRIMARY_ATTACKER_IP}\ndest={_JUMP}\n"
                        f"dest_ports=443,8443\nauth_user={_ACCOUNT}"
                    ),
                    response="allow_count=3\nauth_success=3\nauth_src=not_proven",
                ),
                "related_spl": {"svc_jump_ops_auth": fourteen_day_auth_spl().replace("earliest=-14d", "earliest=-30d")},
            },
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s1-permitted-sessions",
                    "provenance": "governed_search",
                    "tool": "splunk_run_query",
                },
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s1-auth-success",
                    "provenance": "governed_search",
                    "tool": "splunk_run_query",
                },
            ],
        }

    if step_id == "successful_auth":
        return {
            "headline_finding": "Successful logons for svc_jump_ops exist; source IP of those logons is not proven",
            "headlines_by_status": {
                "QUEUED": "Queued — check successful authentications",
                "RUNNING": "Running auth correlation…",
                "COMPLETE": "Logons exist; source IP not proven",
            },
            "attention_state": "INFORMATIONAL",
            "details": _connector_io(
                connector="Splunk MCP",
                spl=fourteen_day_auth_spl().replace("earliest=-14d", "earliest=-30d"),
                request=f"action=splunk_run_query\nhost={_JUMP}\nuser={_ACCOUNT}\nwindow=last_30d",
                response="success_count=3\nauth_src=not_proven",
            ),
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s1-auth-success",
                    "provenance": "governed_search",
                    "tool": "splunk_run_query",
                },
            ],
        }

    if step_id == "privileged_accounts":
        return {
            "headline_finding": "svc_jump_ops is a privileged jump-host service account — compromise not confirmed",
            "headlines_by_status": {
                "QUEUED": "Queued — privileged-account review",
                "RUNNING": "Reading account class…",
                "COMPLETE": "Privileged service account — compromise unconfirmed",
            },
            "attention_state": "INFORMATIONAL",
            "evidence_sources": [],
        }

    if step_id == "endpoint_activity":
        return {
            "headline_finding": "No malicious endpoint activity confirmed on the jump host",
            "headlines_by_status": {
                "QUEUED": "Queued — endpoint activity",
                "RUNNING": "Reviewing endpoint telemetry…",
                "COMPLETE": "No malicious process activity confirmed",
            },
            "attention_state": "NO_MATCH",
            "evidence_sources": [
                {
                    "source": "EDR (simulated)",
                    "evidence_id": "ev-s1-edr",
                    "provenance": "simulated_mcp",
                    "tool": None,
                },
            ],
        }

    if step_id == "previous_incidents":
        return {
            "headline_finding": "Historical ticket overlap on indicator and jump host — campaign linkage unconfirmed",
            "headlines_by_status": {
                "QUEUED": "Queued — previous incidents",
                "RUNNING": "Searching historical tickets…",
                "COMPLETE": "Overlap exists; same campaign not confirmed",
            },
            "attention_state": "INFORMATIONAL",
            "details": _connector_io(
                connector="ITSM",
                request=f"action=search_incidents\nindicator={PRIMARY_ATTACKER_IP}\nhost={_JUMP}",
                response="overlap=true\ncampaign_linkage=unconfirmed",
            ),
            "evidence_sources": [
                {
                    "source": "ITSM",
                    "evidence_id": "ev-s1-prior-ticket",
                    "provenance": "experience_center_fixture",
                    "tool": None,
                },
            ],
        }

    return None
