"""Coordinated Firewall Incident — leadership demo scenarios (Experience Center only)."""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import (
    PRIMARY_ATTACKER_IP,
    INCIDENT_ID,
    build_discovery_hops,
    build_mcp_console_lines,
)


def _ec_resolve_slots(spl: str) -> str:
    """Replace <slot> placeholders with COE Environment KB values at module load time."""
    from app.spl.source_profile_store import load_persisted_source_profile

    for slot, value in load_persisted_source_profile().items():
        spl = spl.replace(f"<{slot}>", value)
    return spl


# Per-source hourly deny baseline. Hour-aligned window (@h) so partial hours don't skew it;
# ``hours_observed`` makes each baseline's sample size visible and sparse sources (<24 active
# hours) are dropped rather than given meaningless bounds. Averages are per *active* hour — the
# analyst checklist says so, because hours with zero denies are not in the stats.
_FIREWALL_BASELINE_SPL = _ec_resolve_slots(
    "search index=<firewall_index> sourcetype=<firewall_sourcetype> earliest=-7d@h latest=@h action=deny "
    "| bucket _time span=1h "
    "| stats count as deny_count dc(dest_port) as distinct_ports by _time, src "
    "| stats count as hours_observed, avg(deny_count) as avg_deny, stdev(deny_count) as stdev_deny, "
    "avg(distinct_ports) as avg_ports, stdev(distinct_ports) as stdev_ports by src "
    "| where hours_observed>=24 "
    "| eval deny_upper_bound=round(avg_deny + (2*stdev_deny), 2) "
    "| eval port_upper_bound=round(avg_ports + (2*stdev_ports), 2) "
    "| sort - avg_deny "
    "| table src, hours_observed, avg_deny, deny_upper_bound, avg_ports, port_upper_bound "
    "| head 100"
)

# <scada_index> is intentionally unmapped in the env KB (key is ot_asset_index, not
# scada_index) — keeps the Q5 HIL-gate demo honest.
_SCADA_PERF_SPL = (
    "search index=<scada_index> sourcetype=ot:scada earliest=-30d latest=now "
    "rtu_id=* transmission_error_count=* "
    "| bin _time span=1h "
    "| stats avg(transmission_error_count) as hourly_metric by _time rtu_id "
    "| head 100"
)


def visual_lanes_for_scenario(
    scenario: Any,
    pipeline_dispatch: dict[str, Any],
    analyst_response: dict[str, Any],
) -> dict[str, Any] | None:
    sid = scenario.scenario_id
    lanes: dict[str, Any] = {}

    if sid == "firewall_baseline_template_spl":
        lanes["coe_logic"] = {
            "title": "Governed SPL template · Environment KB slots resolved",
            "slot_transitions": [
                {"from": "<firewall_index>", "to": "pgcil_soc"},
                {"from": "<firewall_sourcetype>", "to": "pgcil:firewall"},
            ],
            "body": (
                "V.AI SOC selected the firewall baseline template. "
                "Environment KB resolved firewall_index → pgcil_soc and firewall_sourcetype → pgcil:firewall. "
                "Candidate SPL is review-only — analyst approval required before execution."
            ),
        }
        return lanes

    if sid == "splunk_env_asa_ti_readiness":
        hops = build_discovery_hops(discovery_only=True, include_search=False)
        lanes["mcp_console"] = {
            "lines": build_mcp_console_lines(hops),
            "tools_called": [str(h.get("tool")) for h in hops],
        }
        return lanes

    if sid == "network_blast_radius_attacker_ip":
        hops = build_discovery_hops(discovery_only=False, include_search=True)
        lanes["coe_logic"] = {
            "title": "Source profile slot resolution",
            "slot_transitions": [
                {"from": "<firewall_index>", "to": "pgcil_soc"},
                {"from": "cisco_asa (catalog alias)", "to": "pgcil_soc"},
            ],
            "body": "COE Environment KB resolved firewall and ASA indexes before SPL validation.",
        }
        lanes["mcp_console"] = {
            "lines": build_mcp_console_lines(hops),
            "tools_called": [str(h.get("tool")) for h in hops],
        }
        return lanes

    if sid == "scada_critical_telemetry_health":
        lanes["hil_banner"] = {
            "severity": "warning",
            "message": (
                "Analyst review required: placeholder <scada_index> is unmapped in the current "
                "Environment Knowledge Base."
            ),
        }
        hops = build_discovery_hops(discovery_only=False, include_search=True)
        lanes["mcp_console"] = {
            "lines": build_mcp_console_lines(hops[:4]),
            "tools_called": [str(h.get("tool")) for h in hops[:4]],
        }
        return lanes

    if sid == "ir_containment_advisory_firewall_incident":
        lanes["llm_insight"] = {
            "markdown": analyst_response.get("narrative_summary")
            or analyst_response.get("one_sentence_finding")
            or "",
            "timeline": [
                {"time": "T+0h", "event": f"Firewall deny spike detected · incident {INCIDENT_ID}"},
                {"time": "T+1h", "event": f"Blast-radius review anchored on attacker {PRIMARY_ATTACKER_IP}"},
                {"time": "T+2h", "event": "Perimeter and identity response options drafted for approval"},
            ],
        }
        return lanes

    if sid == "executive_incident_mitre_summary":
        lanes["llm_insight"] = {
            "markdown": (
                "## Executive incident summary\n\n"
                f"Coordinated perimeter activity (**{INCIDENT_ID}**) shows external source "
                f"(**{PRIMARY_ATTACKER_IP}**) driving ~5,200 denies with allow/success on jump host "
                "**10.20.1.10 (svc_jump_ops)**. Env KB resolves ASA searches to **pgcil_soc**.\n\n"
                "### MITRE ATT&CK alignment\n"
                "- **T1595** Active Scanning — supported by deny volume across hosts and ports\n"
                "- **T1078** Valid Accounts — requires validation after identity review\n"
                "- **T1048** Exfiltration Over Alternative Protocol — candidate pending data-movement proof"
            ),
        }
        return lanes

    if sid == "firewall_deny_coordinated_attack":
        hops = build_discovery_hops(discovery_only=False, include_search=True)
        lanes["coe_logic"] = {
            "title": "Firewall deny spike · governed template",
            "body": "Scenario fixture selected attack_discovery with governed firewall_deny_spike template on pgcil_soc/pgcil:firewall.",
        }
        lanes["mcp_console"] = {
            "lines": build_mcp_console_lines(hops),
            "tools_called": [str(h.get("tool")) for h in hops],
        }
        lanes["llm_insight"] = {
            "markdown": analyst_response.get("one_sentence_finding") or "",
        }
        return lanes

    return None


def build_firewall_incident_scenarios() -> dict[str, Any]:
    """Build leadership firewall scenarios; call after scenarios.py helpers exist."""
    from app.demo import scenarios as S

    DemoScenario = S.DemoScenario
    _evidence = S._evidence
    _context = S._context
    _fact = S._fact
    _rag_row = S._rag_row
    _scoped_template_spl = S._scoped_template_spl
    _ec_resolve_env_kb_slots = S._ec_resolve_env_kb_slots

    # Pre-bake Environment KB slots so the display SPL shows real index/sourcetype names.
    deny_spl = _ec_resolve_env_kb_slots(_scoped_template_spl("firewall_deny_spike"))
    # cisco_asa_ioc_lookup uses literal 'index=cisco_asa' (Splunk alias, not a <slot>).
    asa_spl = _scoped_template_spl("cisco_asa_ioc_lookup")

    q1_rows = [
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": "10.20.1.10",
            "deny_count": 1842,
            "allow_count": 3,
            "actions": "deny,allow",
            "account": "svc_jump_ops",
            "distinct_ports": 12,
            "dest_ports": "443,8443",
            "apps": "ssl,web-browsing",
        },
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": "10.20.4.55",
            "deny_count": 1260,
            "allow_count": 0,
            "actions": "deny",
            "distinct_ports": 8,
            "dest_ports": "22,443",
            "apps": "ssh,ssl",
        },
        {
            "src": PRIMARY_ATTACKER_IP,
            "dest": "10.20.8.90",
            "deny_count": 980,
            "allow_count": 0,
            "actions": "deny",
            "distinct_ports": 6,
            "dest_ports": "3389,443",
            "apps": "rdp,ssl",
        },
        {
            "src": "10.10.2.44",
            "dest": "198.18.0.50",
            "deny_count": 412,
            "allow_count": 0,
            "actions": "deny",
            "distinct_ports": 3,
            "dest_ports": "53",
            "apps": "dns",
        },
        {
            "src": "10.10.9.18",
            "dest": "198.18.0.51",
            "deny_count": 318,
            "allow_count": 0,
            "actions": "deny",
            "distinct_ports": 2,
            "dest_ports": "443",
            "apps": "ssl",
        },
    ]
    q4_rows = [
        {
            "src_ip": "10.20.1.10",
            "dest_ip": PRIMARY_ATTACKER_IP,
            "actions": "allow,success",
            "event_count": 14,
            "matched_ioc": PRIMARY_ATTACKER_IP,
            "account": "svc_jump_ops",
        },
        {
            "src_ip": "10.20.1.10",
            "dest_ip": PRIMARY_ATTACKER_IP,
            "actions": "deny,reset",
            "event_count": 398,
            "matched_ioc": PRIMARY_ATTACKER_IP,
        },
        {
            "src_ip": "10.20.4.55",
            "dest_ip": PRIMARY_ATTACKER_IP,
            "actions": "deny",
            "event_count": 286,
            "matched_ioc": PRIMARY_ATTACKER_IP,
        },
        {
            "src_ip": "10.20.8.90",
            "dest_ip": PRIMARY_ATTACKER_IP,
            "actions": "deny,reset",
            "event_count": 194,
            "matched_ioc": PRIMARY_ATTACKER_IP,
        },
    ]

    return {
        "firewall_deny_coordinated_attack": DemoScenario(
            scenario_id="firewall_deny_coordinated_attack",
            label="Q1 · Firewall deny spike assessment",
            category="Coordinated Firewall Incident",
            query=(
                "I see we have over 5,000 firewall blocks in the last hour and a successful breach "
                "on an internal server account. Summarize the top offenders and tell me if any of "
                "this looks like a coordinated attack."
            ),
            display_query=(
                "We have more than 5,000 firewall blocks in the last hour and a successful breach "
                "on an internal server account — summarize top offenders and assess whether this "
                "looks coordinated."
            ),
            demo_order=10,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="connected_coe_demo",
            expected_skill="attack_discovery",
            expected_sources=["mcp:splunk", "rag:sop"],
            expected_sufficiency_mode="partial_answer",
            mcp_execution_mode="mock_success",
            saia_available=True,
            rag_available=True,
            selected_use_case_id="net_firewall_deny_spike",
            candidate_spl=deny_spl,
            analyst_summary=(
                f"Governed firewall deny aggregation shows ~5,200 denies/hour with {PRIMARY_ATTACKER_IP} "
                "as the dominant external offender; three allow events on jump host 10.20.1.10 for "
                "svc_jump_ops indicate a likely account breach — escalate as P1 Critical."
            ),
            trace_explanation=[
                "Scenario fixture selected attack_discovery for firewall deny spike review.",
                "Governed firewall_deny_spike template validated; Splunk MCP search returned top offender pairs.",
                "Coordinated-attack assessment stays evidence-grounded — no auto-block or enforcement.",
            ],
            source_evidence=[
                _evidence(
                    "ev-fw-deny-q1",
                    "splunk_mcp_fixture",
                    "Splunk firewall deny results",
                    len(q1_rows),
                    ["src", "dest", "deny_count", "allow_count", "actions", "account", "distinct_ports", "dest_ports", "apps"],
                    q1_rows,
                    tool_name="splunk_run_query",
                    query_or_request_summary="Firewall deny spike aggregation on pgcil_soc/pgcil:firewall.",
                    executed_spl=deny_spl,
                    provider_used="splunk_mcp_fixture",
                ),
            ],
            structured_context=_context(
                "firewall_deny_coordinated_attack",
                "attack_discovery",
                [
                    _fact(
                        "fact-fw-deny-total",
                        (
                            f"~5,200 firewall denies in the last hour; primary external offender "
                            f"{PRIMARY_ATTACKER_IP}; three allow events on 10.20.1.10 for svc_jump_ops."
                        ),
                        ["ev-fw-deny-q1"],
                    ),
                ],
                metrics={
                    "deny_count_total": 5200,
                    "allow_count_breach": 3,
                    "primary_attacker_ip": PRIMARY_ATTACKER_IP,
                    "breach_host": "10.20.1.10",
                    "breach_account": "svc_jump_ops",
                },
                mitre=[
                    {"technique_id": "T1595", "name": "Active Scanning", "support": "supported", "source_refs": ["ev-fw-deny-q1"]},
                    {"technique_id": "T1078", "name": "Valid Accounts", "support": "requires_validation", "source_refs": ["ev-fw-deny-q1"]},
                ],
                refs=["ev-fw-deny-q1"],
            ),
        ),
        "firewall_baseline_template_spl": DemoScenario(
            scenario_id="firewall_baseline_template_spl",
            label="Q2 · Firewall baseline SPL template",
            category="Coordinated Firewall Incident",
            query="Generate the standard firewall baseline template",
            display_query="Generate the standard firewall baseline SPL template for our environment.",
            demo_order=20,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="connected_coe_demo",
            expected_skill="spl_generation",
            expected_sources=["spl_policy"],
            expected_sufficiency_mode="spl_review_only",
            mcp_execution_mode="not_required",
            saia_available=True,
            rag_available=False,
            candidate_spl=_FIREWALL_BASELINE_SPL,
            analyst_summary="Governed firewall baseline SPL with Environment KB slots resolved (pgcil_soc / pgcil:firewall) — candidate artifact ready for analyst review before execution.",
            trace_explanation=[
                "Scenario fixture selected spl_generation for governed template authoring.",
                "Environment KB resolved firewall_index → pgcil_soc and firewall_sourcetype → pgcil:firewall at load time.",
            ],
        ),
        "splunk_env_asa_ti_readiness": DemoScenario(
            scenario_id="splunk_env_asa_ti_readiness",
            label="Q3 · Splunk ASA + Wave-3 TI readiness",
            category="Coordinated Firewall Incident",
            query=(
                "Before we look into those malicious IPs, check our live Splunk environment to confirm "
                "our Wave-3 threat intelligence lookups are active and which index hosts ASA traffic "
                "(Environment Knowledge maps cisco_asa to pgcil_soc)."
            ),
            display_query=(
                "Before investigating malicious IPs, confirm Wave-3 threat-intel lookups are active and "
                "which index hosts ASA traffic (Env KB maps cisco_asa → pgcil_soc)."
            ),
            demo_order=30,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="connected_coe_demo",
            expected_skill="attack_discovery",
            expected_sources=["mcp:splunk"],
            expected_sufficiency_mode="partial_answer",
            mcp_execution_mode="disabled",
            saia_available=True,
            rag_available=False,
            analyst_summary=(
                "Splunk MCP discovery confirms pgcil_soc (Environment KB alias for cisco_asa) plus "
                "Wave-3 lookup power_sector_iocs.csv — readiness check only, no search executed."
            ),
            trace_explanation=[
                "Pre-SPL MCP discovery chronology: indexes and knowledge objects only.",
                "No splunk_run_query on this turn — analyst-directed readiness gate.",
            ],
            source_evidence=[
                _evidence(
                    "ev-mcp-discovery-q3",
                    "splunk_mcp_fixture",
                    "Splunk discovery readiness",
                    0,
                    ["indexes", "lookups"],
                    [{"indexes": ["pgcil_soc"], "index_aliases": {"cisco_asa": "pgcil_soc"}, "lookups": ["power_sector_iocs.csv"]}],
                    tool_name="splunk_get_knowledge_objects",
                    query_or_request_summary="Discovery: indexes + Wave-3 TI lookup readiness.",
                    provider_used="splunk_mcp_fixture",
                ),
            ],
        ),
        "network_blast_radius_attacker_ip": DemoScenario(
            scenario_id="network_blast_radius_attacker_ip",
            label="Q4 · Blast radius for attacker IP",
            category="Coordinated Firewall Incident",
            query=(
                "Run a query via MCP against our network traffic logs for the last 24 hours to track "
                "the blast radius of that specific attacker IP"
            ),
            display_query=(
                f"Track the blast radius of attacker {PRIMARY_ATTACKER_IP} across network traffic for the last 24 hours."
            ),
            demo_order=40,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="connected_coe_demo",
            expected_skill="attack_discovery",
            expected_sources=["mcp:splunk"],
            expected_sufficiency_mode="partial_answer",
            mcp_execution_mode="mock_success",
            saia_available=True,
            rag_available=False,
            selected_use_case_id="cisco_asa_ioc_lookup",
            candidate_spl=asa_spl,
            analyst_summary=(
                f"IOC search on pgcil_soc (Env KB resolved from cisco_asa) shows allow/success for svc_jump_ops "
                f"on 10.20.1.10 plus sustained deny activity involving {PRIMARY_ATTACKER_IP} on three hosts."
            ),
            trace_explanation=[
                "Slot resolution applied before SPL validation.",
                "Full MCP playbook chronology ending in splunk_run_query with governed ASA IOC template.",
            ],
            source_evidence=[
                _evidence(
                    "ev-asa-blast-q4",
                    "splunk_mcp_fixture",
                    "ASA IOC blast-radius results",
                    len(q4_rows),
                    ["src_ip", "dest_ip", "actions", "event_count", "matched_ioc", "account"],
                    q4_rows,
                    tool_name="splunk_run_query",
                    query_or_request_summary=f"ASA IOC lookup blast radius for {PRIMARY_ATTACKER_IP}.",
                    executed_spl=asa_spl,
                    provider_used="splunk_mcp_fixture",
                ),
            ],
            structured_context=_context(
                "network_blast_radius_attacker_ip",
                "attack_discovery",
                [
                    _fact(
                        "fact-blast-radius",
                        (
                            f"Blast-radius search on pgcil_soc shows allow/success for svc_jump_ops on "
                            f"10.20.1.10 plus deny activity with {PRIMARY_ATTACKER_IP} on three hosts."
                        ),
                        ["ev-asa-blast-q4"],
                    ),
                ],
                metrics={
                    "affected_internal_hosts": 3,
                    "breach_account": "svc_jump_ops",
                    "primary_attacker_ip": PRIMARY_ATTACKER_IP,
                    "resolved_index": "pgcil_soc",
                },
                mitre=[{"technique_id": "T1078", "name": "Valid Accounts", "support": "requires_validation", "source_refs": ["ev-asa-blast-q4"]}],
                refs=["ev-asa-blast-q4"],
            ),
        ),
        "scada_critical_telemetry_health": DemoScenario(
            scenario_id="scada_critical_telemetry_health",
            label="Q5 · SCADA telemetry health check",
            category="Coordinated Firewall Incident",
            query="Check if we have any active telemetry logs for our critical SCADA infrastructure performance",
            display_query="Check whether active telemetry exists for critical SCADA infrastructure performance.",
            demo_order=50,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="connected_coe_demo",
            expected_skill="guided_investigation",
            expected_sources=["mcp:splunk", "rag:sop"],
            expected_sufficiency_mode="analyst_review_required",
            mcp_execution_mode="disabled",
            saia_available=True,
            rag_available=True,
            candidate_spl=_SCADA_PERF_SPL,
            analyst_summary=(
                "SCADA performance telemetry search requires analyst review — <scada_index> is unmapped "
                "in the Environment Knowledge Base; governed OT template stays review-only."
            ),
            trace_explanation=[
                "Guided OT source-health path with placeholder slot unresolved.",
                "HIL banner surfaces before any SCADA SPL would be approved for execution.",
            ],
        ),
        "ir_containment_advisory_firewall_incident": DemoScenario(
            scenario_id="ir_containment_advisory_firewall_incident",
            label="Q6 · Perimeter response advisory",
            category="Coordinated Firewall Incident",
            query=(
                "Based on the blast radius of that network attacker, what immediate containment steps "
                "should we take to protect the environment?"
            ),
            display_query=(
                f"Based on the blast radius of {PRIMARY_ATTACKER_IP}, what immediate response steps "
                "should we take to protect the environment?"
            ),
            demo_order=60,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="knowledge_only_coe_demo",
            expected_skill="knowledge_recall",
            expected_sources=["rag:sop"],
            expected_sufficiency_mode="knowledge_only_answer",
            mcp_execution_mode="not_required",
            saia_available=True,
            rag_available=True,
            analyst_summary=(
                "Decision-support advisory only: perimeter deny, segment affected hosts, and identity "
                "session review — all require change-window approval; no automated enforcement."
            ),
            trace_explanation=[
                "Scenario fixture selected knowledge_recall / ir_containment_advisory answer shape.",
                "No SPL or MCP execution — response coordination guidance only.",
            ],
            source_evidence=[
                _evidence(
                    "ev-rag-ir-advisory",
                    "rag",
                    "SOC KB fixture",
                    1,
                    ["entry_id", "document_type", "source_excerpt"],
                    [
                        _rag_row(
                            "ir-advisory-fw-001",
                            "Perimeter incident response advisory",
                            "For coordinated perimeter attacks: (1) Perimeter deny on approved block list after SOC lead sign-off; "
                            "(2) Segment affected hosts during the next change window; (3) Revoke suspicious sessions via identity team.",
                            ["SOC-IR-ADV-FW#001"],
                        )
                    ],
                    tool_name="retrieve_soc_kb",
                    query_or_request_summary="IR perimeter response advisory for coordinated firewall incident.",
                    provider_used="governed_rag_fixture",
                ),
            ],
        ),
        "executive_incident_mitre_summary": DemoScenario(
            scenario_id="executive_incident_mitre_summary",
            label="Q7 · Executive MITRE incident summary",
            category="Coordinated Firewall Incident",
            query=(
                "Compile an executive incident summary of this event, tracking it directly against "
                "the MITRE ATT&CK framework"
            ),
            display_query="Compile an executive incident summary mapped to MITRE ATT&CK for this firewall incident.",
            demo_order=70,
            picker_tier="leadership",
            incident_family="firewall_incident",
            environment_mode="connected_coe_demo",
            expected_skill="attack_discovery",
            expected_sources=["mcp:splunk", "rag:sop"],
            expected_sufficiency_mode="partial_answer",
            mcp_execution_mode="disabled",
            saia_available=True,
            rag_available=True,
            selected_use_case_id="net_firewall_deny_spike",
            analyst_summary=(
                f"Executive rollup for {INCIDENT_ID}: coordinated perimeter activity anchored on "
                f"{PRIMARY_ATTACKER_IP} with MITRE T1595 supported and T1078/T1048 flagged for validation."
            ),
            trace_explanation=[
                "Executive summary synthesizes Q1–Q4 evidence with MITRE ATT&CK alignment.",
                "CVE and OT legs remain honest degrades where data is not onboarded.",
            ],
        ),
    }


def analyst_response_overrides(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    """Per-scenario analyst card overrides for firewall incident track."""
    if scenario_id == "firewall_deny_coordinated_attack":
        from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

        return {
            **base,
            "severity_label": "P1 Critical",
            "finding_title": "Watch fired: coordinated scanning, 3 sessions reached the jump host",
            "one_sentence_finding": (
                f"This is the new IP from the 14-day watch: {PRIMARY_ATTACKER_IP} accounts for ~4,100 of the "
                "denies, scanning 3 internal hosts across 26 ports, and 3 sessions to jump host 10.20.1.10 "
                "were allowed — treat as P1 until the svc_jump_ops identity check rules out account use."
            ),
            "initial_assessment": [
                f"Watch fired: {PRIMARY_ATTACKER_IP} (first seen and put under a 14-day watch in INC-2026-89412) returned at volume.",
                f"{PRIMARY_ATTACKER_IP} drove ~4,100 denies across 10.20.1.10, 10.20.4.55 and 10.20.8.90 — a scanning pattern (T1595).",
                "3 sessions to jump host 10.20.1.10 (443/8443) were allowed; whether svc_jump_ops logons came from this IP is the next check.",
                "The other two hosts saw denies only — perimeter controls held there.",
            ],
            "splunk_status_line": "Splunk search · pgcil_soc/pgcil:firewall · 5 rows",
            "splunk_results_table": [
                {
                    "Source": PRIMARY_ATTACKER_IP,
                    "Destination": "10.20.1.10",
                    "Events": 1845,
                    "Actions": "deny, allow (svc_jump_ops)",
                },
                {
                    "Source": PRIMARY_ATTACKER_IP,
                    "Destination": "10.20.4.55",
                    "Events": 1260,
                    "Actions": "deny",
                },
                {
                    "Source": PRIMARY_ATTACKER_IP,
                    "Destination": "10.20.8.90",
                    "Events": 980,
                    "Actions": "deny",
                },
            ],
            "mitre_mappings": [
                {
                    "Technique": "T1595",
                    "Name": "Active Scanning",
                    "Status": "Supported",
                    "Evidence": "~4,100 denies across 3 hosts and 26 ports from one external source",
                },
                {
                    "Technique": "T1078",
                    "Name": "Valid Accounts",
                    "Status": "Requires validation",
                    "Evidence": "Allow events for svc_jump_ops after deny burst on 10.20.1.10",
                },
            ],
            "recommended_actions": [
                "P1 — check identity first: correlate the 3 allowed sessions with svc_jump_ops logons (decides whether this is account use).",
                "P1 (needs SOC lead + infrastructure owner approval): isolate jump host 10.20.1.10 and disable svc_jump_ops if the identity check attributes logons to this IP — it is the only path that got through.",
                "P1: escalate INC-2026-89412 to P1 and assign an incident commander.",
                "P2: Extend blast-radius search on pgcil_soc for lateral movement from 10.20.1.10.",
            ],
            "interactive_actions": [
                {
                    "id": "open_p1_incident_ticket",
                    "ui_action": "render_interactive_ticket",
                    "label": "Click to Execute: Open P1 Incident Ticket",
                    "success_label": "P1 Ticket created",
                    "status": "SUCCESS",
                    "provenance": "simulated_phase10_action",
                    "production_side_effect": False,
                    "ticket_details": {
                        "ticket_id": "INC-2026-89412",
                        "priority": "P1 - CRITICAL",
                        "assignment_group": "SOC-Incident-Response",
                        "incident_commander": "On-Duty SOC Lead",
                        "summary": (
                            "Coordinated firewall attack from 198.51.100.42 resulting in breach "
                            "of account svc_jump_ops on 10.20.1.10"
                        ),
                        "auto_attached_evidence": [
                            "ev-fw-deny-q1",
                            "Splunk_Search_firewall_5_rows",
                        ],
                    },
                }
            ],
        }
    if scenario_id == "firewall_baseline_template_spl":
        return {
            **base,
            "response_profile": "spl_only",
            "finding_title": "Firewall baseline SPL template",
            "one_sentence_finding": (
                "Governed firewall baseline template with Environment KB slots resolved "
                "(pgcil_soc / pgcil:firewall) and normalized fields action, src, dest, and dest_port."
            ),
            "direct_answer_summary": (
                "This query builds a per-source, 7-day statistical profile of firewall deny-rate and "
                "port-scan behavior. Output is one row per src IP with upper-bound thresholds for deny "
                "volume and destination-port spread; save the result as the firewall baseline and let "
                "downstream detections compare current activity against these bounds instead of "
                "recomputing the baseline on every alert."
            ),
            "spl_code": _FIREWALL_BASELINE_SPL,
            "spl_status": "ready_for_review",
            "spl_status_detail": {
                "status": "grounded",
                "message": (
                    "Environment KB resolved firewall_index and firewall_sourcetype before rendering "
                    "the review artifact."
                ),
                "template_status": "active",
                "generation_status": "generated / grounded to environment knowledge",
                "environment_fields_used": [
                    "index=pgcil_soc",
                    "sourcetype=pgcil:firewall",
                    "normalized fields: action, src, dest, dest_port",
                ],
                "query_complexity": "O(n) single pass over events, hourly bucketed; no subsearches and no regex on _raw.",
            },
            "key_fields": [
                "src - source IP for the baseline row",
                "avg_deny - average hourly deny count over the 7-day baseline window",
                "deny_upper_bound - avg_deny + 2 standard deviations, rounded for detection thresholds",
                "avg_ports - average hourly distinct destination-port spread",
                "port_upper_bound - avg_ports + 2 standard deviations for port-scan thresholding",
            ],
            "analyst_checklist": [
                "Review the 7-day window against maintenance calendars before saving this as a baseline.",
                "Averages are per active hour: hours with no denies are not counted, and hours_observed shows the sample size (sources under 24 active hours are excluded).",
                "Optionally append `| outputlookup firewall_baseline.csv` after analyst approval to persist the table.",
                "Use the saved lookup in downstream detections; do not auto-update it without a documented change ticket.",
            ],
            "review_notice": "Candidate baseline artifact only. Review source mapping, baseline window, and threshold policy before operational use.",
        }
    if scenario_id == "splunk_env_asa_ti_readiness":
        return {
            **base,
            "finding_title": "Splunk environment readiness",
            "one_sentence_finding": (
                "Splunk MCP discovery confirms pgcil_soc (Environment KB alias for cisco_asa) and Wave-3 "
                "lookup power_sector_iocs.csv — TI enrichment is active and the index is ready for governed IOC searches."
            ),
            "recommended_actions": [
                "P1: Confirm Wave-3 TI lookup power_sector_iocs.csv is current and the threat-intel feed was updated within the last 24 hours before pivoting to IOC search.",
                "P2: Proceed to IOC blast-radius search on pgcil_soc once SOC lead approves the investigation scope.",
                "P2: Verify cisco_asa alias is registered in the Environment KB for all relevant sourcetypes (cisco:asa, cisco:firepower) before running governed SPL.",
                "P3: Document the confirmed index alias mapping in the incident record so follow-on analysts use the same resolved index.",
            ],
        }
    if scenario_id == "network_blast_radius_attacker_ip":
        from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

        return {
            **base,
            "severity_label": "P1 Critical",
            "finding_title": f"Blast radius · {PRIMARY_ATTACKER_IP}",
            "one_sentence_finding": (
                f"IOC search on pgcil_soc (Env KB resolved from cisco_asa) shows allow/success for svc_jump_ops "
                f"on 10.20.1.10 plus deny activity involving {PRIMARY_ATTACKER_IP} on peer hosts."
            ),
            "splunk_status_line": f"Splunk search · pgcil_soc · matched IOC {PRIMARY_ATTACKER_IP}",
            "splunk_results_table": [
                {
                    "Internal host": "10.20.1.10",
                    "Events": 14,
                    "Actions": "allow,success (svc_jump_ops)",
                },
                {
                    "Internal host": "10.20.1.10",
                    "Events": 398,
                    "Actions": "deny,reset",
                },
                {
                    "Internal host": "10.20.4.55",
                    "Events": 286,
                    "Actions": "deny",
                },
                {
                    "Internal host": "10.20.8.90",
                    "Events": 194,
                    "Actions": "deny,reset",
                },
            ],
            "recommended_actions": [
                f"P1: Extend blast-radius pivot to 10.20.4.55 and 10.20.8.90 — confirm whether deny-only hosts attempted lateral movement from 10.20.1.10.",
                f"P1: Review EDR/process telemetry on 10.20.1.10 for all activity by svc_jump_ops during and after the allow window.",
                f"P1: Revoke active sessions for svc_jump_ops and disable the account pending identity team review.",
                f"P2: Correlate VPN and identity logs for {PRIMARY_ATTACKER_IP} and svc_jump_ops in the same time window.",
            ],
        }
    if scenario_id == "scada_critical_telemetry_health":
        return {
            **base,
            "status_badge": "OT/ICS · analyst review required",
            "finding_title": "SCADA telemetry health",
            "one_sentence_finding": (
                "SCADA performance telemetry cannot auto-run — <scada_index> is unmapped in the Environment "
                "Knowledge Base; analyst must confirm OT index mapping before SPL approval."
            ),
            "direct_answer_summary": (
                "This is a source-health check, not a detection verdict. The draft shows the intended "
                "hourly SCADA telemetry aggregation, but V.AI SOC holds it because the OT performance "
                "index is not mapped yet. The correct next move is to bind the SCADA index in the "
                "Environment Knowledge Base, then re-run the health check before treating missing "
                "telemetry as operational evidence."
            ),
            "review_notice": "Analyst review required for unmapped SCADA index placeholder.",
            "spl_code": _SCADA_PERF_SPL,
            "spl_status_detail": {
                "status": "blocked",
                "message": "OT index placeholder unresolved — SPL held for analyst mapping before validation.",
                "template_status": "planned",
                "generation_status": "blocked",
                "environment_fields_used": [
                    "sourcetype=ot:scada",
                    "unresolved index slot: <scada_index>",
                    "normalized fields: rtu_id, transmission_error_count",
                ],
                "query_complexity": "O(n) hourly aggregation after source binding; no subsearches and no regex on _raw.",
            },
            "key_fields": [
                "_time - hourly telemetry bucket after the SCADA index is mapped",
                "rtu_id - RTU or telemetry source identifier",
                "hourly_metric - average transmission_error_count for that RTU and hour",
            ],
            "analyst_checklist": [
                "Confirm the authoritative SCADA/OT performance index with OT engineering.",
                "Update the Environment Knowledge Base before approving this SPL.",
                "Validate recent telemetry coverage before treating missing results as a collection outage.",
            ],
            "recommended_actions": [
                "P2: Confirm the correct Splunk index name for SCADA/OT telemetry with the OT engineering team and update the Environment Knowledge Base.",
                "P2: Once the index is mapped, re-run this query to verify telemetry coverage before treating silence as absence of activity.",
                "P3: Review the SCADA data-source onboarding runbook and confirm the OT sourcetype profile is registered.",
                "P3: Validate whether current telemetry gaps affect incident detection SLAs before closing this check.",
            ],
        }
    if scenario_id == "ir_containment_advisory_firewall_incident":
        from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

        return {
            **base,
            "response_profile": "knowledge_recall",
            "spl_status": "not_required",
            "retrieved_playbook": {
                "title": "Perimeter incident response advisory",
                "id": "SOC-IR-ADV-FW",
                "version": "v2026.06",
            },
            "finding_title": "Perimeter response advisory",
            "one_sentence_finding": (
                "Decision-support only: perimeter deny on approved block list, segment blast-radius hosts "
                "in the next change window, and revoke suspicious sessions — all require explicit approval before action."
            ),
            "initial_assessment": [
                "Response posture: decision-support advisory. No automated enforcement; each action requires explicit approval.",
                f"Attacker {PRIMARY_ATTACKER_IP}: recommend perimeter deny after SOC lead sign-off.",
                "Blast-radius hosts 10.20.1.10, 10.20.4.55, 10.20.8.90: segment during next change window.",
                "svc_jump_ops on 10.20.1.10: force re-auth and revoke active sessions via identity team.",
            ],
            "narrative_summary": (
                "### Recommended response steps\n\n"
                f"1. **Perimeter deny (SOC lead approval)** — Add {PRIMARY_ATTACKER_IP} to the approved block list "
                "after SOC lead sign-off. Confirm no legitimate business traffic originates from this IP before blocking.\n\n"
                "2. **Segment blast-radius hosts (change window)** — Isolate 10.20.1.10, 10.20.4.55, and 10.20.8.90 "
                "during the next scheduled change window. Coordinate with the operations team to minimize service impact.\n\n"
                "3. **Revoke sessions (identity team)** — Force re-authentication for svc_jump_ops and any other accounts "
                "active on 10.20.1.10 during the alert window. Notify the identity team before taking action.\n\n"
                "4. **SCADA isolation advisory** — If SCADA/OT telemetry confirms any OT-segment reach by the attacker, "
                "escalate to the OT safety team immediately before taking any containment actions in the OT environment."
            ),
            "recommended_actions": [
                f"P1: Add {PRIMARY_ATTACKER_IP} to the approved perimeter block list — SOC lead sign-off required before any block is applied.",
                "P1: Force re-authentication and revoke active sessions for svc_jump_ops — coordinate with identity team before action.",
                "P1: Segment 10.20.1.10 (confirmed breach host) from the corporate VLAN during the next change window.",
                "P2: Extend segmentation review to 10.20.4.55 and 10.20.8.90 — deny-only so far, but lateral movement risk remains open.",
                "P3: Escalate to OT safety team if any evidence of OT-segment reach emerges from the SCADA telemetry check.",
            ],
        }
    if scenario_id == "executive_incident_mitre_summary":
        from app.demo.ec_mcp_lifecycle_fixture import INCIDENT_ID, PRIMARY_ATTACKER_IP

        return {
            **base,
            "severity_label": "P1 Critical",
            "finding_title": f"Executive summary · {INCIDENT_ID}",
            "one_sentence_finding": (
                f"Coordinated perimeter incident {INCIDENT_ID}: dominant external actor {PRIMARY_ATTACKER_IP} "
                "drove ~5,200 firewall denies with three confirmed allow events on jump host 10.20.1.10 for "
                "svc_jump_ops; MITRE T1595 supported, T1078 validation-required, T1048 candidate pending "
                "data-movement proof."
            ),
            "initial_assessment": [
                f"Incident {INCIDENT_ID}: P1 Critical — coordinated perimeter attack with internal account breach.",
                f"Primary external actor {PRIMARY_ATTACKER_IP}: ~5,200 denies / 3 allow events; blast radius covers 3 internal hosts.",
                "MITRE ATT&CK alignment: T1595 Supported · T1078 Requires validation · T1048 Candidate.",
                "Next step: identity + endpoint corroboration for svc_jump_ops on 10.20.1.10 before executive brief.",
            ],
            "narrative_summary": (
                f"### Incident {INCIDENT_ID} — Executive summary\n\n"
                f"**External actor {PRIMARY_ATTACKER_IP}** launched a coordinated perimeter campaign generating "
                "~5,200 firewall denies in under one hour. Three **allow** events on jump host **10.20.1.10** "
                "for account **svc_jump_ops** indicate a likely credential-access success.\n\n"
                "**Blast radius:** Three internal hosts exposed — 10.20.1.10 (breach), 10.20.4.55, 10.20.8.90 "
                "(deny-only so far). SCADA telemetry check is on hold pending OT index mapping.\n\n"
                "**MITRE ATT&CK alignment:**\n"
                "- T1595 Active Scanning — **Supported** by deny volume across hosts and ports\n"
                "- T1078 Valid Accounts — **Requires validation** after identity review of svc_jump_ops\n"
                "- T1048 Exfiltration Over Alternative Protocol — **Candidate** pending data-movement evidence"
            ),
            "mitre_mappings": [
                {"Technique": "T1595", "Name": "Active Scanning", "Tactic": "Reconnaissance", "Status": "Supported", "Evidence": "~4,100 denies across 3 hosts and 26 ports from one external source"},
                {"Technique": "T1078", "Name": "Valid Accounts", "Tactic": "Initial Access / Persistence", "Status": "Requires validation", "Evidence": "Three allow events for svc_jump_ops after sustained deny burst on 10.20.1.10"},
                {"Technique": "T1048", "Name": "Exfiltration Over Alternative Protocol", "Tactic": "Exfiltration", "Status": "Candidate", "Evidence": "Pending — data-movement proof from egress or endpoint telemetry not yet collected"},
            ],
            "recommended_actions": [
                "P1: Brief executive stakeholders with the incident evidence package and open validation questions (T1078/T1048).",
                "P1: Confirm svc_jump_ops account status — active sessions, privilege level, and owner — before the executive brief.",
                "P2: Continue identity and endpoint corroboration for blast-radius hosts 10.20.1.10, 10.20.4.55, and 10.20.8.90.",
                "P2: Escalate to P1 incident commander if T1078 identity evidence confirms account compromise.",
                "P3: Capture the evidence package and ATT&CK mapping in the incident record for stakeholder reporting.",
            ],
        }
    return None
