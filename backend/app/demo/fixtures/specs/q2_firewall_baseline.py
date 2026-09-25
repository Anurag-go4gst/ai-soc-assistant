"""Q2 — firewall baseline for traffic to admin systems."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, ScenarioSpec

SAVED_SEARCH = "FW – Admin subnet inbound baseline (30d)"
BASELINE_SPL = (
    'search index=netfw sourcetype=cisco:ftd dest_ip="10.20.1.*" action=allowed earliest=-30d latest=now '
    "| stats count as connections dc(dest_port) as ports by src_ip, dest_ip | sort - connections | head 50"
)

Q2 = ScenarioSpec(
    scenario_id="firewall_baseline_template_spl",
    family="firewall_baseline_template_spl",
    label="Q2 · Firewall baseline",
    question=(
        "Generate our standard firewall baseline search so we know what normal traffic to our admin systems "
        "looks like."
    ),
    category="Coordinated Firewall Incident",
    keep_legacy_entry=True,
    demo_order=20,
    plan_title="Firewall baseline for admin systems — plan ready",
    plan_intro=(
        "I'll look for our existing baseline search, run it for the last 30 days, and check what our detection "
        "standard expects. Nothing runs until you approve."
    ),
    checks=(
        Check(
            id="existing_search",
            title="Do we already have a baseline search?",
            plan="Look for a saved baseline search in Splunk.",
            tool="splunk_mcp",
            operation="splunk_get_knowledge_objects · saved searches",
            result=f"Yes — '{SAVED_SEARCH}', owned by Detection Engineering.",
            evidence=("Last changed {D-64}; not scheduled — run on demand",),
        ),
        Check(
            id="run_baseline",
            title="What does normal look like?",
            plan="Run the saved search for {W30}.",
            tool="splunk_mcp",
            operation="splunk_run_saved_search",
            spl=BASELINE_SPL,
            result=(
                "14 sources make 96% of allowed connections to the admin subnet — all internal systems or approved "
                "partner gateways. 3 outside sources appear only once."
            ),
            evidence=(
                "Top sources: automation server 10.20.4.55, backup servers 10.20.6.11–12, monitoring 10.20.7.3",
                f"One of the 3 one-off sources is {E.EXTERNAL_IP}, already in incident {E.INCIDENT_S1}",
            ),
        ),
        Check(
            id="detection_standard",
            title="What does our detection standard need?",
            plan=f"Retrieve {E.STD_DETECTION}.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.STD_DETECTION}",
            result=(
                f"{E.STD_DETECTION}: a baseline covers 30 days, lists the approved sources, and is reviewed by "
                "Detection Engineering before it's used for alerting."
            ),
        ),
    ),
    conclusion_headline="Baseline ready: normal traffic to the admin subnet comes from 14 known sources.",
    points=(
        "The 14 sources can become the approved list for the 'new external source to admin systems' alert.",
        "The 3 one-off outside sources should be reviewed before the list is approved.",
    ),
    threat="Benign",
    asset_tier=0,
    evidence_state="benign",
    assessed=False,
    subject="Admin subnet 10.20.1.0/24",
    decision=f"Proposed: send the baseline and the approved-source list to Detection Engineering for review, as {E.STD_DETECTION} requires.",
    actions=(
        Action(
            id="send_to_detection",
            title="Send the baseline to Detection Engineering",
            proposal="ITSM request with the validated search and the 14-source list attached.",
            tool="itsm",
            verb="request",
            ticket_id=E.TASK_Q2_DETECTION,
            spl=BASELINE_SPL,
            executed=f"Request {E.TASK_Q2_DETECTION} raised with Detection Engineering",
            status_after="REQUESTED",
        ),
    ),
    final_state="DETECTION CHANGE REQUESTED",
    final_headline="Baseline and approved-source list sent to Detection Engineering for review.",
    pending=("Detection Engineering to review the approved-source list",),
    next_triggers="Once approved, the list tunes the 'new external source to admin systems' alert.",
)
